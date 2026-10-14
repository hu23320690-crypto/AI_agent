"""Each proposal transaction is checked against a complete row snapshot."""
from datetime import datetime, timezone
import hashlib
import json
import shutil
import sqlite3
from uuid import uuid4

import pytest

from agent.runtime import RunContext, RunCancelled
from agent.tools.policy import ToolPolicyDenied
from service_desk.access import session_context
from service_desk.contracts import RESULT_MODELS
from service_desk.db import canonical_json, init_db
from service_desk.tools import execute_service_tool


@pytest.fixture(scope='module')
def template(tmp_path_factory):
    path = tmp_path_factory.mktemp('service-proposal') / 'seed.db'
    init_db(path)
    return path


@pytest.fixture
def db(template, tmp_path):
    path = tmp_path / 'service.db'
    shutil.copyfile(template, path)
    return path


def state(db, user='1002'):
    return session_context(user, 'session-' + user, db)


def snapshot(db):
    with sqlite3.connect(db) as connection:
        tables = [r[0] for r in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        return {table: connection.execute(f'SELECT * FROM {table} ORDER BY rowid').fetchall() for table in tables}


def call(db, name, user='1002', **args):
    return json.loads(execute_service_tool(name, args, state(db, user)))


SUCCESS = [
    ('propose_service_visit', '1002', {'device_id': 'D-1002-01', 'error_code': 'E07',
        'description': '水箱正确装回后仍不出水', 'slot_id': 'S-east-20260113-2'}),
    ('propose_service_visit', '1001', {'device_id': 'D-1001-01',
        'description': '设备持续异响，外部清理后仍未改善', 'slot_id': 'S-north-20260113-2'}),
    ('propose_order', '1002', {'device_id': 'D-1002-01', 'sku': 'SKU-FILTER', 'qty': 2}),
    ('propose_change', '1004', {'target_id': 'A-1004-01', 'change': 'reschedule',
                              'new_slot_id': 'S-west-20260114-3'}),
    ('propose_change', '1004', {'target_id': 'A-1004-01', 'change': 'cancel_appointment'}),
    ('propose_change', '1007', {'target_id': 'O-1007-01', 'change': 'cancel_order'}),
]


@pytest.mark.parametrize('name,user,args', SUCCESS)
def test_success_adds_only_pending_and_audit(db, name, user, args):
    before = snapshot(db)
    started = datetime.now(timezone.utc)
    result = call(db, name, user, **args)
    RESULT_MODELS[name].model_validate(result, strict=True)
    after = snapshot(db)
    for table in before.keys() - {'pending_actions', 'audit_log'}:
        assert after[table] == before[table], table
    assert len(after['pending_actions']) == len(before['pending_actions']) + 1
    assert len(after['audit_log']) == len(before['audit_log']) + 1
    with sqlite3.connect(db) as connection:
        connection.row_factory = sqlite3.Row
        pending = dict(connection.execute('SELECT * FROM pending_actions').fetchone())
        audit = dict(connection.execute('SELECT * FROM audit_log').fetchone())
    assert pending['args_json'] == canonical_json(args)
    assert hashlib.sha256(pending['args_json'].encode('utf-8')).hexdigest() == pending['args_sha256']
    assert result['args_sha256'] == pending['args_sha256'] == audit['args_sha256']
    assert (pending['session_id'], pending['user_id'], pending['status']) == ('session-' + user, user, 'pending')
    assert pending['result_json'] is None and pending['decided_at'] is None
    assert (audit['action_id'], audit['event'], audit['tool']) == (result['action_id'], 'proposed', name)
    created, expires = map(datetime.fromisoformat, [result['created_at'], result['expires_at']])
    assert started <= created <= datetime.now(timezone.utc)
    assert created.tzinfo is not None and (expires - created).total_seconds() == 600
    assert '数量' in result['summary'] or '×' in result['summary']
    if name == 'propose_order':
        assert result['amount_cents'] == 7800 and '78.00元' in result['summary']
    if name == 'propose_service_visit' and user == '1001':
        assert '已过保' in result['summary'] and '费用由检查结果决定' in result['summary']


def test_multiline_visit_description_stays_in_pending_arguments(db):
    description = '水箱正确装回后仍不出水。\n\t已检查外部接口。'
    before = snapshot(db)
    result = call(db, 'propose_service_visit', device_id='D-1002-01', error_code='E07',
                  description=description, slot_id='S-east-20260113-2')
    assert result['status'] == 'pending' and result['args']['description'] == description
    with sqlite3.connect(db) as connection:
        args_json = connection.execute('SELECT args_json FROM pending_actions').fetchone()[0]
    assert json.loads(args_json)['description'] == description
    assert hashlib.sha256(args_json.encode('utf-8')).hexdigest() == result['args_sha256']
    after = snapshot(db)
    for table in before.keys() - {'pending_actions', 'audit_log'}:
        assert after[table] == before[table], table


FAILURES = [
    ('propose_service_visit', '1002', {'device_id': 'D-1002-01', 'error_code': 'E99',
        'description': '设备异常', 'slot_id': 'S-east-20260113-2'}, 'error_code_not_found'),
    ('propose_service_visit', '1002', {'device_id': 'D-1002-01',
        'description': '设备异常', 'slot_id': 'S-east-20260113-1'}, 'slot_unavailable'),
    ('propose_service_visit', '1002', {'device_id': 'D-1002-01',
        'description': '设备异常', 'slot_id': 'S-east-20260109-H'}, 'slot_not_future'),
    ('propose_service_visit', '1004', {'device_id': 'D-1004-01',
        'description': '设备异常', 'slot_id': 'S-west-20260114-3'}, 'appointment_exists'),
    ('propose_order', '1002', {'device_id': 'D-1002-01', 'sku': 'SKU-MOP', 'qty': 1}, 'out_of_stock'),
    ('propose_order', '1002', {'device_id': 'D-1002-01', 'sku': 'SKU-SIDE', 'qty': 101}, 'out_of_stock'),
    ('propose_order', '1002', {'device_id': 'D-1002-01', 'sku': 'SKU-FILTER', 'qty': 3}, 'purchase_limit'),
    ('propose_order', '1015', {'device_id': 'D-1015-02', 'sku': 'SKU-RUBBER', 'qty': 1},
     'incompatible_consumable'),
    ('propose_change', '1012', {'target_id': 'A-1012-01', 'change': 'reschedule',
                              'new_slot_id': 'S-west-20260114-3'}, 'appointment_not_scheduled'),
    ('propose_change', '1013', {'target_id': 'A-1013-01', 'change': 'cancel_appointment'},
     'appointment_not_scheduled'),
    ('propose_change', '1004', {'target_id': 'A-1004-01', 'change': 'reschedule',
                              'new_slot_id': 'S-west-20260114-1'}, 'slot_unavailable'),
    ('propose_change', '1004', {'target_id': 'A-1004-01', 'change': 'reschedule',
                              'new_slot_id': 'S-west-20260109-H'}, 'slot_not_future'),
    ('propose_change', '1001', {'target_id': 'O-1001-01', 'change': 'cancel_order'}, 'order_not_processing'),
    ('propose_change', '1003', {'target_id': 'O-1003-01', 'change': 'cancel_order'}, 'order_not_processing'),
]


@pytest.mark.parametrize('name,user,args,reason', FAILURES)
def test_each_failed_precondition_writes_nothing(db, name, user, args, reason):
    before = snapshot(db)
    result = call(db, name, user, **args)
    assert result['status'] == 'blocked' and result['reason_code'] == reason
    assert snapshot(db) == before


@pytest.mark.parametrize('name,args', [
    ('propose_order', {'device_id': 'D-1002-01', 'sku': 'SKU-FILTER', 'qty': '1'}),
    ('propose_order', {'device_id': 'D-1002-01', 'sku': 'SKU-FILTER', 'qty': 0}),
    ('propose_change', {'target_id': 'A-1004-01', 'change': 'reschedule'}),
    ('propose_change', {'target_id': 'O-1007-01', 'change': 'cancel_appointment'}),
    ('propose_service_visit', {'device_id': 'D-1002-01', 'description': '  ',
                              'slot_id': 'S-east-20260113-2'}),
])
def test_invalid_proposals_write_nothing(db, name, args):
    before = snapshot(db)
    with pytest.raises(ToolPolicyDenied) as error:
        execute_service_tool(name, args, state(db))
    assert error.value.code == 'arguments_invalid'
    assert snapshot(db) == before


@pytest.mark.parametrize('name,user,args', [
    ('propose_order', '1002', {'device_id': 'D-1001-01', 'sku': 'SKU-FILTER', 'qty': 1}),
    ('propose_change', '1002', {'target_id': 'O-1007-01', 'change': 'cancel_order'}),
    ('propose_change', '1002', {'target_id': 'A-1004-01', 'change': 'cancel_appointment'}),
    ('propose_change', '1004', {'target_id': 'A-1004-01', 'change': 'reschedule',
                              'new_slot_id': 'S-north-20260114-3'}),
])
def test_proposals_check_ownership_before_state(db, name, user, args):
    before = snapshot(db)
    with pytest.raises(ToolPolicyDenied) as error:
        execute_service_tool(name, args, state(db, user))
    assert error.value.code == 'identity_mismatch'
    assert snapshot(db) == before


def test_audit_failure_rolls_back_pending(db):
    with sqlite3.connect(db) as connection:
        connection.execute("CREATE TRIGGER reject_proposed BEFORE INSERT ON audit_log "
                           "BEGIN SELECT RAISE(ABORT,'test audit failure'); END")
    before = snapshot(db)
    with pytest.raises(sqlite3.IntegrityError, match='audit failure'):
        call(db, 'propose_order', device_id='D-1002-01', sku='SKU-FILTER', qty=1)
    assert snapshot(db) == before


def test_cancelled_run_cannot_write(db):
    context = state(db)
    context['run_context'] = RunContext()
    context['run_context'].cancel()
    before = snapshot(db)
    with pytest.raises(RunCancelled):
        execute_service_tool('propose_order', {'device_id': 'D-1002-01', 'sku': 'SKU-FILTER', 'qty': 1}, context)
    assert snapshot(db) == before


def test_no_session_no_proposal(db):
    context = state(db)
    context.pop('session_id')
    before = snapshot(db)
    with pytest.raises(ToolPolicyDenied) as error:
        execute_service_tool('propose_order', {'device_id': 'D-1002-01', 'sku': 'SKU-FILTER', 'qty': 1}, context)
    assert error.value.code == 'session_missing'
    assert snapshot(db) == before


def test_two_proposals_do_not_supersede_or_reserve_inventory(db):
    results = [call(db, 'propose_order', device_id='D-1002-01', sku='SKU-FILTER', qty=2) for _ in range(2)]
    assert results[0]['action_id'] != results[1]['action_id']
    with sqlite3.connect(db) as connection:
        assert connection.execute("SELECT count(*) FROM pending_actions WHERE status='pending'").fetchone()[0] == 2
        assert connection.execute("SELECT stock FROM consumables WHERE sku='SKU-FILTER'").fetchone()[0] == 80


def test_cancel_between_checks_and_commit_rolls_back_both_inserts(db, monkeypatch):
    from service_desk import proposals
    context = state(db)
    context['run_context'] = RunContext()
    original = proposals._prepare

    def cancel_after_checks(*args):
        result = original(*args)
        context['run_context'].cancel()
        return result

    monkeypatch.setattr(proposals, '_prepare', cancel_after_checks)
    before = snapshot(db)
    with pytest.raises(RunCancelled):
        execute_service_tool('propose_order', {'device_id': 'D-1002-01', 'sku': 'SKU-FILTER', 'qty': 1}, context)
    assert snapshot(db) == before
