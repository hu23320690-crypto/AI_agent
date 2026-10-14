"""Trusted confirmation boundary. These functions are never model tools.

Sessions are server-owned mappings as produced by access.session_context.
Public results are dictionaries; successful results are stored as canonical JSON.
The real UTC clock governs expiry, independently of the business date.
"""
from datetime import datetime, timezone
import hashlib
import hmac
import json

from agent.tools.policy import ToolPolicyDenied
from service_desk.access import connection_for
from service_desk.audit import append_event
from service_desk.config import load_config
from service_desk.contracts import WRITE_PROPOSAL_TOOLS
from service_desk.db import canonical_json
from service_desk.failures import MESSAGES, PreconditionFailed
from service_desk.policy import authorize_service_tool
from service_desk.proposals import _prepare


STATUS_MESSAGES = {
    'rejected': '已拒绝该动作，未执行。',
    'superseded': '该动作已被新提议取代，请查看新的确认卡片。',
    'expired': '该动作已过期，未执行，请重新提出请求。',
    'failed': '当前业务条件不满足，未执行，请重新查询后提出请求。',
}
DENIED = {'status': 'denied', 'reason_code': 'action_denied',
          'message': '无法处理该动作，请查看当前会话的确认卡片。'}


def _context(session):
    context = dict(session)
    # Confirmation happens after the model run has finished or been cancelled.
    context.pop('run_context', None)
    if not isinstance(context.get('session_id'), str) or not context['session_id'].strip():
        raise ToolPolicyDenied('session_missing')
    if not isinstance(context.get('user_id'), str) or not context['user_id'].strip():
        raise ToolPolicyDenied('identity_missing')
    config = context.get('service_config') or load_config()
    context.setdefault('business_date', config['business_date'])
    return context


def _require_identity(connection, context):
    # audit_log.user_id has an FK: callers must bind a real demonstration user.
    if connection.execute('SELECT 1 FROM users WHERE user_id=?', (context['user_id'],)).fetchone() is None:
        raise ToolPolicyDenied('identity_mismatch')


def _owned_action(connection, context, action_id):
    if not isinstance(action_id, str):
        return None
    return connection.execute(
        'SELECT * FROM pending_actions WHERE action_id=? AND session_id=? AND user_id=?',
        (action_id, context['session_id'], context['user_id'])).fetchone()


def _deny(connection, context, now, action=None):
    append_event(connection, context, action, 'denied', now, '动作校验未通过，未执行。')
    connection.commit()
    return dict(DENIED)


def _terminal_result(action):
    if action['result_json'] is not None:
        return json.loads(action['result_json'])
    return {'action_id': action['action_id'], 'status': action['status'],
            'message': STATUS_MESSAGES[action['status']]}


def _finish(connection, context, action, status, now, *, reason=None):
    result = {'action_id': action['action_id'], 'status': status, 'message': STATUS_MESSAGES[status]}
    if reason is not None:
        message = MESSAGES[reason].replace('，未生成订单提议', '')
        result.update(reason_code=reason, message='未执行：' + message)
    connection.execute(
        'UPDATE pending_actions SET status=?,decided_at=?,result_json=? WHERE action_id=?',
        (status, now, canonical_json(result), action['action_id']))
    append_event(connection, context, action, status, now, result['message'])
    return result


def _expired(action, now):
    expires = datetime.fromisoformat(action['expires_at'])
    if expires.tzinfo is None:
        raise ValueError('expiry requires timezone')
    return now >= expires


def _archived_args(connection, context, action):
    digest = hashlib.sha256(action['args_json'].encode('utf-8')).hexdigest()
    if not hmac.compare_digest(digest, action['args_sha256']):
        raise ToolPolicyDenied('arguments_invalid')
    if action['tool'] not in WRITE_PROPOSAL_TOOLS:
        raise ToolPolicyDenied('tool_not_allowed')
    args = authorize_service_tool(action['tool'], json.loads(action['args_json']), context,
                                  connection=connection)
    normalized = {key: value for key, value in args.items() if value is not None}
    if canonical_json(normalized) != action['args_json']:
        raise ToolPolicyDenied('arguments_invalid')
    return args


def confirm_action(session, action_id):
    """Serialize validation, effects and audit with BEGIN IMMEDIATE.

    Only an owned, pending, unexpired action can reach the private executor.
    Replays return the persisted first result, including its original message.
    """
    context = _context(session)
    with connection_for(context, readonly=False) as connection:
        _require_identity(connection, context)
        now = datetime.now(timezone.utc)
        timestamp = now.isoformat()
        action = _owned_action(connection, context, action_id)
        if action is None:
            return _deny(connection, context, timestamp)
        if action['status'] != 'pending':
            return _terminal_result(action)
        try:
            if _expired(action, now):
                result = _finish(connection, context, action, 'expired', timestamp)
                connection.commit()
                return result
            args = _archived_args(connection, context, action)
        except (ToolPolicyDenied, ValueError, TypeError):
            return _deny(connection, context, timestamp, action)
        try:
            _, extra = _prepare(action['tool'], args, context, connection)
        except PreconditionFailed as error:
            result = _finish(connection, context, action, 'failed', timestamp, reason=error.code)
            connection.commit()
            return result
        from service_desk.executor import _execute
        result = _execute(connection, context, action, args, extra)
        connection.execute(
            "UPDATE pending_actions SET status='executed',result_json=?,decided_at=? WHERE action_id=?",
            (canonical_json(result), timestamp, action['action_id']))
        append_event(connection, context, action, 'confirmed', timestamp, '用户通过确认入口确认。')
        append_event(connection, context, action, 'executed', timestamp, result['message'])
        connection.commit()
        return result


def reject_action(session, action_id):
    """Reject only pending actions; terminal states are immutable."""
    context = _context(session)
    with connection_for(context, readonly=False) as connection:
        _require_identity(connection, context)
        action = _owned_action(connection, context, action_id)
        timestamp = datetime.now(timezone.utc).isoformat()
        if action is None:
            return _deny(connection, context, timestamp)
        if action['status'] != 'pending':
            return _terminal_result(action)
        result = _finish(connection, context, action, 'rejected', timestamp)
        connection.commit()
        return result


def list_actions(session):
    """Return this session/user's cards in creation order, lazily expiring pending cards.

    All statuses remain visible for the UI's history. No other session is swept.
    """
    context = _context(session)
    with connection_for(context, readonly=False) as connection:
        _require_identity(connection, context)
        now = datetime.now(timezone.utc)
        rows = connection.execute(
            'SELECT * FROM pending_actions WHERE session_id=? AND user_id=? ORDER BY created_at,action_id',
            (context['session_id'], context['user_id'])).fetchall()
        cards = []
        for action in rows:
            status = action['status']
            if status == 'pending':
                try:
                    expired = _expired(action, now)
                except (ValueError, TypeError):
                    expired = False
                if expired:
                    _finish(connection, context, action, 'expired', now.isoformat())
                    status = 'expired'
            cards.append({key: action[key] for key in
                          ('action_id', 'tool', 'summary', 'created_at', 'expires_at', 'args_sha256')}
                         | {'status': status})
        connection.commit()
        return cards
