"""Create pending proposals and audit only; business tables stay read-only."""
from contextlib import nullcontext
from datetime import date, datetime, timedelta, timezone
import hashlib
from uuid import uuid4

from agent.tools.policy import ToolPolicyDenied
from service_desk.access import connection_for
from service_desk.audit import append_event
from service_desk.config import load_config
from service_desk.contracts import RESULT_MODELS
from service_desk.db import canonical_json
from service_desk.failures import PreconditionFailed, failure_json
from service_desk.policy import authorize_service_tool
from service_desk.seed import add_months


def _require(condition, code):
    if not condition:
        raise PreconditionFailed(code)


def _slot(connection, slot_id, context):
    # Ownership was checked within this same transaction before any state checks.
    row = connection.execute('SELECT * FROM service_slots WHERE slot_id=?', (slot_id,)).fetchone()
    _require(row['start_at'][:10] > context['business_date'], 'slot_not_future')
    _require(row['booked'] < row['capacity'], 'slot_unavailable')
    return row


def _money(cents):
    return f'{cents // 100}.{cents % 100:02d}元'


def _prepare(name, args, context, connection):
    if name == 'propose_order':
        device = connection.execute('SELECT * FROM devices WHERE device_id=?', (args['device_id'],)).fetchone()
        compatible = connection.execute('SELECT 1 FROM consumable_models WHERE sku=? AND model_code=?',
                                        (args['sku'], device['model_code'])).fetchone()
        _require(compatible is not None, 'incompatible_consumable')
        item = connection.execute('SELECT * FROM consumables WHERE sku=?', (args['sku'],)).fetchone()
        _require(item['stock'] >= args['qty'], 'out_of_stock')
        _require(item['max_per_order'] is None or args['qty'] <= item['max_per_order'], 'purchase_limit')
        amount = item['price_cents'] * args['qty']
        summary = (f"下单：设备{device['device_id']}，{item['name']}（{item['sku']}）×{args['qty']}；"
                   f"单价{_money(item['price_cents'])}，金额{_money(amount)}；等待卡片确认。")
        return summary, {'amount_cents': amount}
    if name == 'propose_service_visit':
        device = connection.execute('SELECT * FROM devices WHERE device_id=?', (args['device_id'],)).fetchone()
        if args['error_code'] is not None:
            error = connection.execute('SELECT 1 FROM error_codes WHERE model_code=? AND code=?',
                                       (device['model_code'], args['error_code'])).fetchone()
            _require(error is not None, 'error_code_not_found')
        slot = _slot(connection, args['slot_id'], context)
        scheduled = connection.execute(
            'SELECT 1 FROM appointments a JOIN tickets t USING(ticket_id) '
            "WHERE t.device_id=? AND a.status='scheduled'", (args['device_id'],)).fetchone()
        _require(scheduled is None, 'appointment_exists')
        component = 'battery' if args['error_code'] == 'E09' else 'whole_machine'
        policy = connection.execute('SELECT months FROM warranty_policies WHERE model_code=? AND component=?',
                                    (device['model_code'], component)).fetchone()
        purchase, today = date.fromisoformat(device['purchase_date']), date.fromisoformat(context['business_date'])
        expires = add_months(purchase, policy['months'])
        covered = policy['months'] > 0 and purchase <= today <= expires
        label = '电池' if component == 'battery' else '整机'
        summary = (f"预约上门：设备{device['device_id']}，时段{slot['slot_id']}，"
                   f"{slot['start_at']}至{slot['end_at']}；"
                   f"{label}{'在保' if covered else '已过保'}（到期日{expires.isoformat()}）；"
                   "费用由检查结果决定，在保也不承诺免费；等待卡片确认。")
        return summary, {}
    if args['change'] == 'cancel_order':
        order = connection.execute('SELECT * FROM orders WHERE order_id=?', (args['target_id'],)).fetchone()
        _require(order['status'] == 'processing', 'order_not_processing')
        return (f"取消订单：{order['order_id']}，设备{order['device_id']}，耗材{order['sku']}×{order['qty']}；"
                f"订单金额{_money(order['amount_cents'])}；等待卡片确认。"), {}
    appointment = connection.execute('SELECT * FROM appointments WHERE appointment_id=?',
                                     (args['target_id'],)).fetchone()
    _require(appointment['status'] == 'scheduled', 'appointment_not_scheduled')
    old = connection.execute('SELECT * FROM service_slots WHERE slot_id=?',
                             (appointment['slot_id'],)).fetchone()
    if args['change'] == 'reschedule':
        new = _slot(connection, args['new_slot_id'], context)
        summary = (f"改约：预约{appointment['appointment_id']}，原时段{old['slot_id']}（{old['start_at']}）；"
                   f"新时段{new['slot_id']}，{new['start_at']}至{new['end_at']}；"
                   "费用由检查结果决定；等待卡片确认。")
    else:
        summary = (f"取消预约：{appointment['appointment_id']}及关联工单{appointment['ticket_id']}，"
                   f"时段{old['slot_id']}，{old['start_at']}至{old['end_at']}；"
                   "费用由检查结果决定；等待卡片确认。")
    return summary, {}


def _supersede(connection, name, args, context, timestamp):
    fields = {'propose_service_visit': ('device_id',), 'propose_order': ('device_id', 'sku'),
              'propose_change': ('target_id',)}[name]
    predicates = ' AND '.join(f"json_extract(args_json,'$.{field}')=?" for field in fields)
    rows = connection.execute(
        "SELECT * FROM pending_actions WHERE session_id=? AND user_id=? AND tool=? AND status='pending' AND "
        + predicates + ' ORDER BY created_at,action_id',
        (context['session_id'], context['user_id'], name, *(args[field] for field in fields))).fetchall()
    for old in rows:
        message = '该动作已被新提议取代，请查看新的确认卡片。'
        result = canonical_json({'action_id': old['action_id'], 'status': 'superseded', 'message': message})
        connection.execute(
            "UPDATE pending_actions SET status='superseded',decided_at=?,result_json=? WHERE action_id=?",
            (timestamp, result, old['action_id']))
        append_event(connection, context, old, 'superseded', timestamp, message)


def propose(name, arguments, context):
    session = context.get('session_id')
    if not isinstance(session, str) or not session.strip():
        raise ToolPolicyDenied('session_missing')
    try:
        with connection_for(context, readonly=False) as connection:
            args = authorize_service_tool(name, arguments, context, connection=connection)
            run = context.get('run_context')
            if run is not None:
                with run.lock:
                    run.check()
                    if run.counts['service_proposals'] >= 2:
                        return failure_json('proposal_limit')
            summary, extra = _prepare(name, args, context, connection)
            # Omitted optional arguments have one normalized representation.
            normalized = {key: value for key, value in args.items() if value is not None}
            args_json = canonical_json(normalized)
            digest = hashlib.sha256(args_json.encode('utf-8')).hexdigest()
            now = datetime.now(timezone.utc)
            config = context.get('service_config') or load_config()
            expires = now + timedelta(seconds=config['pending_action_ttl_seconds'])
            result = RESULT_MODELS[name].model_validate({
                'action_id': str(uuid4()), 'status': 'pending', 'tool': name, 'args': normalized,
                'args_sha256': digest, 'summary': summary, 'created_at': now.isoformat(),
                'expires_at': expires.isoformat(), **extra,
            }, strict=True)
            payload = result.model_dump(by_alias=True, exclude_none=True)
            serialized = canonical_json(payload)
            _supersede(connection, name, args, context, result.created_at)
            connection.execute(
                'INSERT INTO pending_actions '
                '(action_id,session_id,user_id,tool,args_json,args_sha256,summary,created_at,expires_at,status) '
                'VALUES (?,?,?,?,?,?,?,?,?,?)',
                (result.action_id, session, context['user_id'], name, args_json, digest,
                 summary, result.created_at, result.expires_at, 'pending'))
            append_event(connection, context, payload, 'proposed', result.created_at,
                         '已生成待确认动作；业务表未变更。')
            # Cancellation cannot race this commit. A failed graph after a
            # successful proposal may leave a pending card; S2 owns its lifecycle.
            with run.lock if run is not None else nullcontext():
                if run is not None:
                    run.check_size(serialized, run.limits.max_output_chars, '工具结果')
                    # The same RunContext can be used concurrently, even with
                    # different databases. Count only successfully committed proposals.
                    if run.counts['service_proposals'] >= 2:
                        return failure_json('proposal_limit')
                connection.commit()
                if run is not None:
                    run.counts['service_proposals'] += 1
            return serialized
    except PreconditionFailed as error:
        return failure_json(error.code)
