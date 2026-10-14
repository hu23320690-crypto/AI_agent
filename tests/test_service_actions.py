"""Offline H1-H4/H6 tests using fresh copies of a deterministic seed."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import shutil
import sqlite3
from threading import Barrier
from uuid import uuid4

import pytest

from agent.runtime import RunContext, RunCancelled
from agent.tools.policy import ToolPolicyDenied
from service_desk.access import session_context
from service_desk.actions import confirm_action, list_actions, reject_action
from service_desk.contracts import SERVICE_TOOL_NAMES
from service_desk.db import canonical_json, init_db
from service_desk.tools import build_service_tools, execute_service_tool


@pytest.fixture(scope='module')
def template(tmp_path_factory):
    path = tmp_path_factory.mktemp('service-actions') / 'seed.db'
    init_db(path)
    return path


@pytest.fixture
def db(template, tmp_path):
    path = tmp_path / 'service.db'
    shutil.copyfile(template, path)
    return path


def context(db, user='1002', session=None):
    return session_context(user, session or 'session-' + user, db)


def snapshot(db):
    with sqlite3.connect(db) as connection:
        connection.row_factory = sqlite3.Row
        tables = [r[0] for r in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        return {table: [dict(row) for row in connection.execute(f'SELECT * FROM {table} ORDER BY rowid')]
                for table in tables}


def business(db):
    return {table: rows for table, rows in snapshot(db).items() if table not in ('pending_actions', 'audit_log')}


def mutate(db, sql, params=()):
    with sqlite3.connect(db) as connection:
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute(sql, params)


def proposal(ctx, tool='propose_order', args=None):
    args = args or {'device_id': 'D-1002-01', 'sku': 'SKU-FILTER', 'qty': 2}
    return json.loads(execute_service_tool(tool, args, ctx))


def events(db):
    return [row['event'] for row in snapshot(db)['audit_log']]


def row_for(rows, key, value):
    return next(row for row in rows if row[key] == value)


CASES = [
    pytest.param('visit', '1002', 'propose_service_visit',
                 {'device_id': 'D-1002-01', 'error_code': 'E07',
                  'description': '水箱装回后仍不出水。\n已完成外部自查。', 'slot_id': 'S-east-20260113-2'}, id='visit'),
    pytest.param('order', '1002', 'propose_order',
                 {'device_id': 'D-1002-01', 'sku': 'SKU-FILTER', 'qty': 2}, id='order'),
    pytest.param('reschedule', '1004', 'propose_change',
                 {'target_id': 'A-1004-01', 'change': 'reschedule', 'new_slot_id': 'S-west-20260114-3'}, id='reschedule'),
    pytest.param('cancel_appointment', '1004', 'propose_change',
                 {'target_id': 'A-1004-01', 'change': 'cancel_appointment'}, id='cancel-appointment'),
    pytest.param('cancel_order', '1007', 'propose_change',
                 {'target_id': 'O-1007-01', 'change': 'cancel_order'}, id='cancel-order'),
]


def expected_effect(before, kind, user, args, action_id):
    """Independent row-by-row oracle for the five registered business effects."""
    expected = deepcopy(before)
    suffix = '-SVC-' + action_id.replace('-', '')
    if kind == 'visit':
        device = row_for(expected['devices'], 'device_id', args['device_id'])
        expected['tickets'].append({
            'ticket_id': 'T' + suffix, 'user_id': user, 'device_id': args['device_id'],
            'model_code': device['model_code'], 'error_code': args.get('error_code'),
            'description': args['description'], 'notes': '', 'status': 'scheduled', 'source_action_id': action_id})
        expected['appointments'].append({
            'appointment_id': 'A' + suffix, 'ticket_id': 'T' + suffix, 'slot_id': args['slot_id'],
            'user_id': user, 'status': 'scheduled', 'source_action_id': action_id})
        row_for(expected['service_slots'], 'slot_id', args['slot_id'])['booked'] += 1
    elif kind == 'order':
        device = row_for(expected['devices'], 'device_id', args['device_id'])
        item = row_for(expected['consumables'], 'sku', args['sku'])
        expected['orders'].append({
            'order_id': 'O' + suffix, 'user_id': user, 'device_id': args['device_id'],
            'model_code': device['model_code'], 'sku': args['sku'], 'qty': args['qty'],
            'amount_cents': item['price_cents'] * args['qty'], 'status': 'processing', 'source_action_id': action_id})
        item['stock'] -= args['qty']
    elif kind == 'cancel_order':
        order = row_for(expected['orders'], 'order_id', args['target_id'])
        order['status'] = 'cancelled'
        row_for(expected['consumables'], 'sku', order['sku'])['stock'] += order['qty']
    else:
        appointment = row_for(expected['appointments'], 'appointment_id', args['target_id'])
        row_for(expected['service_slots'], 'slot_id', appointment['slot_id'])['booked'] -= 1
        ticket = row_for(expected['tickets'], 'ticket_id', appointment['ticket_id'])
        if kind == 'reschedule':
            appointment['slot_id'] = args['new_slot_id']
            row_for(expected['service_slots'], 'slot_id', args['new_slot_id'])['booked'] += 1
            assert ticket['status'] == 'scheduled'
        else:
            appointment['status'] = ticket['status'] = 'cancelled'
    return expected


def assert_slot_invariant(db):
    with sqlite3.connect(db) as connection:
        assert connection.execute(
            "SELECT s.slot_id FROM service_slots s WHERE s.booked != s.external_booked + "
            "(SELECT count(*) FROM appointments a WHERE a.slot_id=s.slot_id AND a.status='scheduled')"
        ).fetchall() == []
        assert connection.execute('PRAGMA foreign_key_check').fetchall() == []


def assert_execution(db, before, kind, user, args, pending, result):
    assert business(db) == expected_effect(before, kind, user, args, pending['action_id'])
    state = snapshot(db)
    action = row_for(state['pending_actions'], 'action_id', pending['action_id'])
    assert action['status'] == result['status'] == 'executed'
    assert action['decided_at'] is not None
    assert action['result_json'] == canonical_json(result)
    assert events(db) == ['proposed', 'confirmed', 'executed']
    assert all(row['action_id'] == pending['action_id'] and row['args_sha256'] == pending['args_sha256']
               and row['user_id'] == user for row in state['audit_log'])
    assert result['message']
    assert_slot_invariant(db)


@pytest.mark.parametrize('kind,user,tool,args', CASES)
def test_h1_model_proposes_only_and_five_write_effects(db, kind, user, tool, args):
    ctx = context(db, user)
    ctx['run_context'] = RunContext()
    before = business(db)
    pending = proposal(ctx, tool, args)
    assert pending['status'] == 'pending'
    assert business(db) == before
    assert events(db) == ['proposed']
    assert list_actions(ctx)[0]['status'] == 'pending'
    assert business(db) == before
    # Confirmation remains usable after the originating model run has ended.
    ctx['run_context'].complete()
    result = confirm_action(ctx, pending['action_id'])
    assert_execution(db, before, kind, user, args, pending, result)
    if kind == 'visit':
        assert result['ticket_id'] in result['message'] and result['appointment_id'] in result['message']
        assert result['start_at'] in result['message'] and result['end_at'] in result['message']
    if kind == 'order':
        assert result['amount_cents'] == 7800 and '78.00元' in result['message']


@pytest.mark.parametrize('name', ['confirm_action', 'reject_action', 'execute_action', '_execute', 'list_actions'])
def test_h1_confirmation_and_execution_are_not_model_tools(db, name):
    assert tuple(tool.name for tool in build_service_tools()) == SERVICE_TOOL_NAMES
    assert name not in SERVICE_TOOL_NAMES
    before = snapshot(db)
    with pytest.raises(ToolPolicyDenied) as error:
        execute_service_tool(name, {'action_id': str(uuid4())}, context(db))
    assert error.value.code == 'tool_not_allowed'
    assert snapshot(db) == before


@pytest.mark.parametrize('operation', [confirm_action, reject_action])
def test_h1_forged_id_is_denied_and_audited(db, operation):
    before = business(db)
    result = operation(context(db), str(uuid4()))
    assert result['status'] == 'denied' and 'action_id' not in result
    assert business(db) == before and snapshot(db)['pending_actions'] == []
    assert events(db) == ['denied']
    audit = snapshot(db)['audit_log'][0]
    assert audit['action_id'] is None and audit['args_sha256'] == '0' * 64


@pytest.mark.parametrize('column,value', [
    ('args_json', canonical_json({'device_id': 'D-1002-01', 'sku': 'SKU-FILTER', 'qty': 1})),
    ('args_sha256', '0' * 64),
])
def test_h2_tampered_archive_denied(db, column, value):
    ctx = context(db)
    pending = proposal(ctx)
    mutate(db, f'UPDATE pending_actions SET {column}=? WHERE action_id=?', (value, pending['action_id']))
    before = business(db)
    result = confirm_action(ctx, pending['action_id'])
    assert result['status'] == 'denied'
    assert business(db) == before and events(db) == ['proposed', 'denied']
    assert snapshot(db)['pending_actions'][0]['status'] == 'pending'


@pytest.mark.parametrize('args', [
    {'device_id': 'D-1002-01', 'sku': 'SKU-FILTER', 'qty': '2'},
    {'device_id': 'D-1002-01', 'sku': 'SKU-FILTER', 'qty': 2, 'user_id': '1002'},
    {'device_id': 'D-1002-01', 'sku': 'SKU-FILTER', 'qty': 2, 'extra': 'confirm'},
    {'device_id': 'D-1002-01', 'sku': 'SKU-FILTER\n', 'qty': 2},
    {'device_id': 'D-1001-01', 'sku': 'SKU-FILTER', 'qty': 2},
    [],
])
def test_h2_revalidate_strict_args_and_ownership_even_with_matching_hash(db, args):
    ctx = context(db)
    pending = proposal(ctx)
    text = canonical_json(args)
    digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
    mutate(db, 'UPDATE pending_actions SET args_json=?,args_sha256=? WHERE action_id=?',
           (text, digest, pending['action_id']))
    before = business(db)
    assert confirm_action(ctx, pending['action_id'])['status'] == 'denied'
    assert business(db) == before and events(db) == ['proposed', 'denied']


def test_h2_noncanonical_archive_with_matching_hash_denied(db):
    ctx = context(db)
    pending = proposal(ctx)
    text = json.dumps(pending['args'], ensure_ascii=False)
    mutate(db, 'UPDATE pending_actions SET args_json=?,args_sha256=? WHERE action_id=?',
           (text, hashlib.sha256(text.encode('utf-8')).hexdigest(), pending['action_id']))
    before = business(db)
    assert confirm_action(ctx, pending['action_id'])['status'] == 'denied'
    assert business(db) == before


@pytest.mark.parametrize('operation', [confirm_action, reject_action])
@pytest.mark.parametrize('other_user,other_session', [('1002', 'foreign-session'), ('1003', 'session-1002')])
@pytest.mark.parametrize('executed', [False, True], ids=['pending', 'executed'])
def test_h3_cross_session_or_user_matches_nonexistent_denial(db, operation, other_user, other_session, executed):
    owner = context(db)
    pending = proposal(owner)
    if executed:
        confirm_action(owner, pending['action_id'])
    before = snapshot(db)
    requester = context(db, other_user, other_session)
    actual = operation(requester, pending['action_id'])
    absent = operation(requester, str(uuid4()))
    assert actual == absent and actual['status'] == 'denied'
    after = snapshot(db)
    assert after['pending_actions'] == before['pending_actions']
    assert business(db) == {k: v for k, v in before.items() if k not in ('pending_actions', 'audit_log')}
    assert after['audit_log'][:-2] == before['audit_log']
    for audit in after['audit_log'][-2:]:
        assert audit['event'] == 'denied' and audit['action_id'] is None
        assert audit['user_id'] == other_user and audit['session_id'] == other_session
    assert {k: v for k, v in after['audit_log'][-1].items() if k not in ('id', 'ts')} == {
        k: v for k, v in after['audit_log'][-2].items() if k not in ('id', 'ts')}
    assert list_actions(requester) == []


@pytest.mark.parametrize('kind,user,tool,args', CASES)
def test_h4_repeated_confirmation_returns_first_result_without_writes(db, kind, user, tool, args):
    ctx = context(db, user)
    before = business(db)
    pending = proposal(ctx, tool, args)
    first = confirm_action(ctx, pending['action_id'])
    assert_execution(db, before, kind, user, args, pending, first)
    after_first = snapshot(db)
    assert confirm_action(ctx, pending['action_id']) == first
    assert reject_action(ctx, pending['action_id']) == first
    assert snapshot(db) == after_first


@pytest.mark.parametrize('kind,user,tool,args', CASES)
def test_h4_two_threads_confirm_once_with_identical_results(db, kind, user, tool, args):
    ctx = context(db, user)
    before = business(db)
    pending = proposal(ctx, tool, args)
    barrier = Barrier(2)

    def confirm():
        barrier.wait(timeout=5)
        return confirm_action(ctx, pending['action_id'])

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(confirm) for _ in range(2)]
        results = [future.result(timeout=10) for future in futures]
    assert results[0] == results[1]
    assert_execution(db, before, kind, user, args, pending, results[0])


def test_h4_replay_ignores_changed_preconditions_and_expiry(db):
    ctx = context(db)
    pending = proposal(ctx)
    first = confirm_action(ctx, pending['action_id'])
    mutate(db, "UPDATE consumables SET stock=0,price_cents=1 WHERE sku='SKU-FILTER'")
    mutate(db, 'UPDATE pending_actions SET expires_at=? WHERE action_id=?',
           ((datetime.now(timezone.utc) - timedelta(days=1)).isoformat(), pending['action_id']))
    before = snapshot(db)
    assert confirm_action(ctx, pending['action_id']) == first
    assert snapshot(db) == before


@pytest.mark.parametrize('kind,user,tool,args', CASES)
def test_h6_reject_then_confirm_never_executes(db, kind, user, tool, args):
    ctx = context(db, user)
    pending = proposal(ctx, tool, args)
    before = business(db)
    rejected = reject_action(ctx, pending['action_id'])
    assert rejected['status'] == 'rejected' and '未执行' in rejected['message']
    after = snapshot(db)
    assert confirm_action(ctx, pending['action_id']) == rejected
    assert reject_action(ctx, pending['action_id']) == rejected
    assert snapshot(db) == after and business(db) == before
    assert events(db) == ['proposed', 'rejected']


@pytest.mark.parametrize('kind,user,tool,args', CASES)
def test_h6_superseded_old_action_cannot_execute(db, kind, user, tool, args):
    ctx = context(db, user)
    old = proposal(ctx, tool, args)
    new = proposal(ctx, tool, args)
    before = snapshot(db)
    assert confirm_action(ctx, old['action_id'])['status'] == 'superseded'
    assert reject_action(ctx, old['action_id'])['status'] == 'superseded'
    assert snapshot(db) == before
    assert events(db) == ['proposed', 'superseded', 'proposed']
    assert confirm_action(ctx, new['action_id'])['status'] == 'executed'


def test_h6_expired_real_clock_cannot_execute(db):
    ctx = context(db)
    pending = proposal(ctx)
    mutate(db, 'UPDATE pending_actions SET expires_at=? WHERE action_id=?',
           ((datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(), pending['action_id']))
    before = business(db)
    expired = confirm_action(ctx, pending['action_id'])
    assert expired['status'] == 'expired' and '未执行' in expired['message']
    assert events(db) == ['proposed', 'expired'] and business(db) == before
    after = snapshot(db)
    assert confirm_action(ctx, pending['action_id']) == expired
    assert reject_action(ctx, pending['action_id']) == expired
    assert snapshot(db) == after


def test_h6_expiry_boundary_is_inclusive(db, monkeypatch):
    from service_desk import actions
    ctx = context(db)
    pending = proposal(ctx)
    boundary = datetime.fromisoformat(pending['expires_at'])

    class BoundaryClock:
        @staticmethod
        def now(tz):
            assert tz == timezone.utc
            return boundary

    monkeypatch.setattr(actions, 'datetime', BoundaryClock)
    monkeypatch.setattr(BoundaryClock, 'fromisoformat', datetime.fromisoformat, raising=False)
    before = business(db)
    assert confirm_action(ctx, pending['action_id'])['status'] == 'expired'
    assert business(db) == before


def test_list_actions_expires_only_owned_cards_once(db):
    own, other = context(db), context(db, session='other-session')
    first, foreign = proposal(own), proposal(other)
    expired_at = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    mutate(db, 'UPDATE pending_actions SET expires_at=?', (expired_at,))
    before = business(db)
    cards = list_actions(own)
    assert len(cards) == 1 and cards[0]['action_id'] == first['action_id'] and cards[0]['status'] == 'expired'
    after = snapshot(db)
    assert row_for(after['pending_actions'], 'action_id', foreign['action_id'])['status'] == 'pending'
    assert events(db) == ['proposed', 'proposed', 'expired'] and business(db) == before
    assert list_actions(own) == cards and snapshot(db) == after


@pytest.mark.parametrize('tool,user,args,sql,reason', [
    ('propose_service_visit', '1002', {'device_id': 'D-1002-01', 'description': '仍异常',
                                     'slot_id': 'S-east-20260113-2'},
     "UPDATE service_slots SET booked=capacity,external_booked=capacity WHERE slot_id='S-east-20260113-2'",
     'slot_unavailable'),
    ('propose_change', '1004', {'target_id': 'A-1004-01', 'change': 'reschedule',
                              'new_slot_id': 'S-west-20260114-3'},
     "UPDATE service_slots SET booked=capacity,external_booked=capacity WHERE slot_id='S-west-20260114-3'",
     'slot_unavailable'),
    ('propose_order', '1002', {'device_id': 'D-1002-01', 'sku': 'SKU-FILTER', 'qty': 2},
     "UPDATE consumables SET stock=1 WHERE sku='SKU-FILTER'", 'out_of_stock'),
    ('propose_order', '1002', {'device_id': 'D-1002-01', 'sku': 'SKU-FILTER', 'qty': 2},
     "UPDATE consumables SET max_per_order=1 WHERE sku='SKU-FILTER'", 'purchase_limit'),
    ('propose_change', '1007', {'target_id': 'O-1007-01', 'change': 'cancel_order'},
     "UPDATE orders SET status='completed' WHERE order_id='O-1007-01'", 'order_not_processing'),
    ('propose_change', '1004', {'target_id': 'A-1004-01', 'change': 'cancel_appointment'},
     "UPDATE appointments SET status='completed' WHERE appointment_id='A-1004-01'", 'appointment_not_scheduled'),
])
def test_changed_precondition_fails_without_business_writes(db, tool, user, args, sql, reason):
    ctx = context(db, user)
    pending = proposal(ctx, tool, args)
    mutate(db, sql)
    before = business(db)
    failed = confirm_action(ctx, pending['action_id'])
    assert failed['status'] == 'failed' and failed['reason_code'] == reason and '未执行' in failed['message']
    assert business(db) == before and events(db) == ['proposed', 'failed']
    after = snapshot(db)
    assert confirm_action(ctx, pending['action_id']) == failed
    assert reject_action(ctx, pending['action_id']) == failed
    assert snapshot(db) == after


def test_changed_device_owner_denied_without_business_writes(db):
    ctx = context(db)
    pending = proposal(ctx)
    mutate(db, "UPDATE devices SET user_id='1003' WHERE device_id='D-1002-01'")
    before = business(db)
    assert confirm_action(ctx, pending['action_id'])['status'] == 'denied'
    assert business(db) == before and events(db) == ['proposed', 'denied']


@pytest.mark.parametrize('trigger', [
    "CREATE TRIGGER fail_effect BEFORE INSERT ON appointments BEGIN SELECT RAISE(ABORT,'effect failure'); END",
    "CREATE TRIGGER fail_audit BEFORE INSERT ON audit_log WHEN NEW.event='executed' "
    "BEGIN SELECT RAISE(ABORT,'effect failure'); END",
])
def test_partial_effect_or_audit_failure_rolls_back_entire_confirmation(db, trigger):
    ctx = context(db)
    pending = proposal(ctx, 'propose_service_visit',
                       {'device_id': 'D-1002-01', 'description': '仍异常', 'slot_id': 'S-east-20260113-2'})
    mutate(db, trigger)
    before = snapshot(db)
    with pytest.raises(sqlite3.IntegrityError, match='effect failure'):
        confirm_action(ctx, pending['action_id'])
    assert snapshot(db) == before


@pytest.mark.parametrize('sql', ['UPDATE audit_log SET detail=?', 'DELETE FROM audit_log WHERE detail!=?'])
def test_audit_is_append_only(db, sql):
    proposal(context(db))
    before = snapshot(db)
    with pytest.raises(sqlite3.IntegrityError, match='append-only'):
        mutate(db, sql, ('changed',))
    assert snapshot(db) == before


def test_supersede_object_keys_and_session_isolation(db):
    first = proposal(context(db), args={'device_id': 'D-1002-01', 'sku': 'SKU-FILTER', 'qty': 1})
    other_sku = proposal(context(db), args={'device_id': 'D-1002-01', 'sku': 'SKU-SIDE', 'qty': 1})
    foreign_session = proposal(context(db, session='other'))
    other_device = proposal(context(db, '1003'), args={'device_id': 'D-1003-01', 'sku': 'SKU-FILTER', 'qty': 1})
    newest = proposal(context(db))
    statuses = {row['action_id']: row['status'] for row in snapshot(db)['pending_actions']}
    assert statuses == {first['action_id']: 'superseded', other_sku['action_id']: 'pending',
                        foreign_session['action_id']: 'pending', other_device['action_id']: 'pending',
                        newest['action_id']: 'pending'}


def test_visit_supersedes_changed_slot_and_change_supersedes_changed_kind(db):
    ctx = context(db)
    old = proposal(ctx, 'propose_service_visit',
                   {'device_id': 'D-1002-01', 'description': '仍异常', 'slot_id': 'S-east-20260113-2'})
    new = proposal(ctx, 'propose_service_visit',
                   {'device_id': 'D-1002-01', 'description': '仍异常', 'slot_id': 'S-east-20260114-3'})
    old_change = proposal(context(db, '1004'), 'propose_change',
                          {'target_id': 'A-1004-01', 'change': 'reschedule', 'new_slot_id': 'S-west-20260114-3'})
    new_change = proposal(context(db, '1004'), 'propose_change',
                          {'target_id': 'A-1004-01', 'change': 'cancel_appointment'})
    statuses = {row['action_id']: row['status'] for row in snapshot(db)['pending_actions']}
    assert statuses == {old['action_id']: 'superseded', new['action_id']: 'pending',
                        old_change['action_id']: 'superseded', new_change['action_id']: 'pending'}


def test_two_proposals_per_run_including_supersession_and_new_run_reset(db):
    ctx = context(db)
    run = ctx['run_context'] = RunContext()
    before = business(db)
    assert proposal(ctx)['status'] == 'pending'
    assert proposal(ctx)['status'] == 'pending'
    assert run.counts['service_proposals'] == 2
    after_two = snapshot(db)
    third = proposal(ctx)
    assert third['status'] == 'blocked' and third['reason_code'] == 'proposal_limit'
    assert snapshot(db) == after_two and business(db) == before
    ctx['run_context'] = RunContext()
    assert proposal(ctx)['status'] == 'pending'
    assert ctx['run_context'].counts['service_proposals'] == 1


def test_failed_proposals_and_reads_do_not_consume_proposal_limit(db):
    ctx = context(db)
    run = ctx['run_context'] = RunContext()
    bad = {'device_id': 'D-1002-01', 'sku': 'SKU-MOP', 'qty': 1}
    before = snapshot(db)
    assert proposal(ctx, args=bad)['status'] == 'blocked'
    assert json.loads(execute_service_tool('list_my_devices', {}, ctx))['devices']
    assert snapshot(db) == before and run.counts['service_proposals'] == 0
    assert proposal(ctx)['status'] == 'pending' and proposal(ctx)['status'] == 'pending'


def test_concurrent_proposals_share_run_limit(db):
    ctx = context(db)
    run = ctx['run_context'] = RunContext()
    before = business(db)
    barrier = Barrier(3)

    def propose():
        barrier.wait(timeout=5)
        return proposal(ctx)

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(propose) for _ in range(3)]
        results = [future.result(timeout=10) for future in futures]
    assert sorted(result['status'] for result in results) == ['blocked', 'pending', 'pending']
    assert run.counts['service_proposals'] == 2
    assert len(snapshot(db)['pending_actions']) == 2 and business(db) == before
    assert events(db) == ['proposed', 'superseded', 'proposed']


def test_supersession_and_run_counter_roll_back_on_cancellation(db, monkeypatch):
    from service_desk import proposals
    ctx = context(db)
    proposal(ctx)
    run = ctx['run_context'] = RunContext()
    original = proposals._prepare

    def cancel_after_prepare(*args):
        result = original(*args)
        run.cancel()
        return result

    monkeypatch.setattr(proposals, '_prepare', cancel_after_prepare)
    before = snapshot(db)
    with pytest.raises(RunCancelled):
        proposal(ctx)
    assert snapshot(db) == before and run.counts['service_proposals'] == 0


def test_new_scheduled_appointment_blocks_visit_at_confirmation(db):
    ctx = context(db)
    args = {'device_id': 'D-1002-01', 'description': '仍异常', 'slot_id': 'S-east-20260113-2'}
    pending = proposal(ctx, 'propose_service_visit', args)
    mutate(db, "INSERT INTO tickets VALUES ('T-test','1002','D-1002-01','SV-200',NULL,'仍异常','','scheduled',NULL)")
    mutate(db, "INSERT INTO appointments VALUES ('A-test','T-test','S-east-20260114-3','1002','scheduled',NULL)")
    mutate(db, "UPDATE service_slots SET booked=booked+1 WHERE slot_id='S-east-20260114-3'")
    before = business(db)
    result = confirm_action(ctx, pending['action_id'])
    assert result['status'] == 'failed' and result['reason_code'] == 'appointment_exists'
    assert business(db) == before and events(db) == ['proposed', 'failed']
    assert_slot_invariant(db)


def test_changed_compatibility_blocks_order_at_confirmation(db):
    ctx = context(db, '1015')
    # A new synthetic SKU has no historical order FK that would prevent
    # changing compatibility. Keep one compatible device owned by this user.
    mutate(db, "INSERT INTO consumables VALUES ('SKU-TEST','测试滤网','filter',3900,80,2)")
    mutate(db, "INSERT INTO consumable_models SELECT DISTINCT 'SKU-TEST',model_code FROM devices WHERE user_id='1015'")
    with sqlite3.connect(db) as connection:
        model = connection.execute("SELECT model_code FROM devices WHERE device_id='D-1015-01'").fetchone()[0]
    args = {'device_id': 'D-1015-01', 'sku': 'SKU-TEST', 'qty': 1}
    pending = proposal(ctx, args=args)
    mutate(db, 'DELETE FROM consumable_models WHERE sku=? AND model_code=?', ('SKU-TEST', model))
    # Still visible through this user's second device, but incompatible with the selected device.
    before = business(db)
    result = confirm_action(ctx, pending['action_id'])
    assert result['status'] == 'failed' and result['reason_code'] == 'incompatible_consumable'
    assert business(db) == before


def test_changed_business_date_blocks_nonfuture_slot_at_confirmation(db):
    ctx = context(db)
    pending = proposal(ctx, 'propose_service_visit',
                       {'device_id': 'D-1002-01', 'description': '仍异常', 'slot_id': 'S-east-20260113-2'})
    ctx['business_date'] = '2026-01-13'
    before = business(db)
    result = confirm_action(ctx, pending['action_id'])
    assert result['status'] == 'failed' and result['reason_code'] == 'slot_not_future'
    assert business(db) == before


@pytest.mark.parametrize('error_code', [None, 'E07'])
def test_visit_admission_without_code_or_after_self_check_out_of_warranty(db, error_code):
    ctx = context(db, '1001')
    args = {'device_id': 'D-1001-01', 'description': '已完成自查，外部清理后仍然异响',
            'slot_id': 'S-north-20260113-2'}
    if error_code:
        args['error_code'] = error_code
    before = business(db)
    pending = proposal(ctx, 'propose_service_visit', args)
    assert '已过保' in pending['summary'] and '费用由检查结果决定' in pending['summary']
    result = confirm_action(ctx, pending['action_id'])
    assert_execution(db, before, 'visit', '1001', args, pending, result)
    ticket = row_for(snapshot(db)['tickets'], 'ticket_id', result['ticket_id'])
    assert ticket['error_code'] == error_code


def test_reschedule_to_same_available_slot_has_zero_net_booked_change(db):
    ctx = context(db, '1004')
    before = business(db)
    old = row_for(before['appointments'], 'appointment_id', 'A-1004-01')
    args = {'target_id': 'A-1004-01', 'change': 'reschedule', 'new_slot_id': old['slot_id']}
    pending = proposal(ctx, 'propose_change', args)
    result = confirm_action(ctx, pending['action_id'])
    assert_execution(db, before, 'reschedule', '1004', args, pending, result)
    assert business(db) == before


def test_deterministic_business_ids_reproduce_on_fresh_database(db, template, tmp_path, monkeypatch):
    from service_desk import proposals
    fixed_id = uuid4()
    monkeypatch.setattr(proposals, 'uuid4', lambda: fixed_id)
    second = tmp_path / 'second.db'
    shutil.copyfile(template, second)
    results = []
    for path in (db, second):
        ctx = context(path)
        pending = proposal(ctx)
        assert pending['action_id'] == str(fixed_id)
        results.append(confirm_action(ctx, pending['action_id']))
    assert results[0] == results[1]
    assert results[0]['order_id'] == 'O-SVC-' + fixed_id.hex
    assert business(db) == business(second)


def test_audit_event_order_preserves_proposal_row_and_stored_hash(db):
    ctx = context(db)
    pending = proposal(ctx)
    first_audit = snapshot(db)['audit_log']
    confirm_action(ctx, pending['action_id'])
    audit = snapshot(db)['audit_log']
    assert audit[:1] == first_audit
    assert [row['event'] for row in audit] == ['proposed', 'confirmed', 'executed']
    assert all(row['args_sha256'] == pending['args_sha256'] for row in audit)
    assert audit[1]['ts'] == audit[2]['ts'] >= audit[0]['ts']


def test_order_object_key_distinguishes_two_devices_of_same_user(db):
    ctx = context(db, '1015')
    first = proposal(ctx, args={'device_id': 'D-1015-01', 'sku': 'SKU-FILTER', 'qty': 1})
    second = proposal(ctx, args={'device_id': 'D-1015-02', 'sku': 'SKU-FILTER', 'qty': 1})
    replacement = proposal(ctx, args={'device_id': 'D-1015-01', 'sku': 'SKU-FILTER', 'qty': 2})
    assert {row['action_id']: row['status'] for row in snapshot(db)['pending_actions']} == {
        first['action_id']: 'superseded', second['action_id']: 'pending', replacement['action_id']: 'pending'}


def test_change_object_key_distinguishes_targets_of_same_user(db):
    ctx = context(db)
    first = proposal(ctx)
    first_order = confirm_action(ctx, first['action_id'])['order_id']
    second = proposal(ctx, args={'device_id': 'D-1002-01', 'sku': 'SKU-SIDE', 'qty': 1})
    second_order = confirm_action(ctx, second['action_id'])['order_id']
    changes = [proposal(ctx, 'propose_change', {'target_id': target, 'change': 'cancel_order'})
               for target in (first_order, second_order)]
    statuses = {row['action_id']: row['status'] for row in snapshot(db)['pending_actions']}
    assert all(statuses[change['action_id']] == 'pending' for change in changes)


def test_supersession_and_counter_roll_back_on_new_proposal_audit_failure(db):
    ctx = context(db)
    proposal(ctx)
    run = ctx['run_context'] = RunContext()
    mutate(db, "CREATE TRIGGER fail_new_proposal BEFORE INSERT ON audit_log WHEN NEW.event='proposed' "
           "BEGIN SELECT RAISE(ABORT,'audit failure'); END")
    before = snapshot(db)
    with pytest.raises(sqlite3.IntegrityError, match='audit failure'):
        proposal(ctx)
    assert snapshot(db) == before and run.counts['service_proposals'] == 0


def test_minimal_server_session_mapping_uses_configured_business_clock(db):
    ctx = context(db)
    pending = proposal(ctx)
    minimal = {key: ctx[key] for key in ('session_id', 'user_id', 'service_db_path')}
    assert confirm_action(minimal, pending['action_id'])['status'] == 'executed'


@pytest.mark.parametrize('expires_at', ['bad-time', '2026-01-12T00:00:00'])
def test_malformed_expiry_denied_without_business_writes(db, expires_at):
    ctx = context(db)
    pending = proposal(ctx)
    mutate(db, 'UPDATE pending_actions SET expires_at=? WHERE action_id=?', (expires_at, pending['action_id']))
    before = business(db)
    assert confirm_action(ctx, pending['action_id'])['status'] == 'denied'
    assert business(db) == before and events(db) == ['proposed', 'denied']


def test_confirm_and_reject_race_has_one_terminal_decision(db):
    ctx = context(db)
    pending = proposal(ctx)
    before = business(db)
    barrier = Barrier(2)

    def decide(operation):
        barrier.wait(timeout=5)
        return operation(ctx, pending['action_id'])

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(decide, operation) for operation in (confirm_action, reject_action)]
        results = [future.result(timeout=10) for future in futures]
    assert results[0] == results[1]
    if results[0]['status'] == 'executed':
        assert_execution(db, before, 'order', '1002', pending['args'], pending, results[0])
    else:
        assert results[0]['status'] == 'rejected'
        assert business(db) == before and events(db) == ['proposed', 'rejected']


def test_concurrent_proposals_on_different_databases_share_commit_limit(template, tmp_path, monkeypatch):
    from service_desk import proposals
    run = RunContext()
    barrier = Barrier(3)
    original = proposals._prepare
    paths = []
    for index in range(3):
        path = tmp_path / f'concurrent-{index}.db'
        shutil.copyfile(template, path)
        paths.append(path)

    def synchronize_prepare(*args):
        result = original(*args)
        # All threads pass the initial count check before any can commit.
        barrier.wait(timeout=10)
        return result

    monkeypatch.setattr(proposals, '_prepare', synchronize_prepare)

    def propose(path):
        ctx = context(path)
        ctx['run_context'] = run
        return proposal(ctx)

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(propose, path) for path in paths]
        results = [future.result(timeout=15) for future in futures]
    assert sorted(result['status'] for result in results) == ['blocked', 'pending', 'pending']
    assert run.counts['service_proposals'] == 2
    for path, result in zip(paths, results):
        state = snapshot(path)
        if result['status'] == 'blocked':
            assert state['pending_actions'] == state['audit_log'] == []
        else:
            assert len(state['pending_actions']) == len(state['audit_log']) == 1
