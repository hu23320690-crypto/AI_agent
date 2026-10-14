"""Synthetic cases only. No frozen dataset or real inference is read here."""
import json
import shutil
from pathlib import Path
import pytest

from evaluation.service_eval import canonical, digest, matches
from evaluation.service_run import (assert_resume_identity, create_seed, execute_case, verify_dataset)

READS = ['list_my_devices', 'lookup_error_code', 'check_warranty', 'rag_summarize',
         'fetch_external_data', 'get_daily_usage', 'find_service_slots', 'find_consumables',
         'get_my_orders_and_tickets']
ORDER = {'tool': 'propose_order', 'args': {'device_id': 'D-1001-01', 'sku': 'SKU-FILTER', 'qty': 1}}


def synthetic_case(*, expected=True, decision='confirm', expect='answer'):
    turns = [{'type': 'user', 'query': '给我的基础设备买一个滤网。', 'expect': expect,
              'required_tools': ['list_my_devices', 'find_consumables'] + (['propose_order'] if expected else []),
              'allowed_tools': READS + (['propose_order'] if expected else []),
              'expected_proposals': [ORDER] if expected else [], 'forbidden_proposals': [],
              'required_points': ['等我确认再下单'], 'evidence': []}]
    if decision:
        turns.append({'type': decision, 'proposal_ref': 't1.p0'})
    return {'id': 'SYN-ORDER', 'user_id': '1001', 'turns': turns,
            'final_db_checks': [{'table': 'orders', 'where': {'user_id': '1001', 'status': 'processing'}, 'expect_count': 1}]}


def script(qty=1):
    return {'responses': [
        {'calls': [{'name': 'list_my_devices'}]},
        {'calls': [{'name': 'find_consumables', 'args': {'device_id': 'D-1001-01'}}]},
        {'calls': [{'name': 'propose_order', 'args': {**ORDER['args'], 'qty': qty}}]},
        {'answer': '已准备卡片，等你确认。'}]}


@pytest.fixture(scope='module')
def seed(tmp_path_factory):
    path = tmp_path_factory.mktemp('synthetic-runner') / 'seed.db'
    create_seed(path)
    return path


@pytest.fixture
def db(seed, tmp_path, monkeypatch):
    monkeypatch.setenv('AGENT_TOOLSET', 'service')
    path = tmp_path / 'case.db'
    shutil.copyfile(seed, path)
    return path


def test_correct_card_confirm_and_history(db):
    case = synthetic_case()
    row = execute_case(case, db, spec=script())
    assert row['status'] == 'ok'
    assert row['operations'][0]['result']['status'] == 'executed'
    assert row['operations'][0]['history_recorded'] is True
    assert len([r for r in row['final_db']['orders'] if r['user_id'] == '1001' and r['source_action_id']]) == 1
    turn = row['turns'][0]
    assert turn['proposals'][0]['proposal_ref'] == 't1.p0'
    assert [c['name'] for c in turn['tool_calls']] == ['list_my_devices', 'find_consumables', 'propose_order']
    assert all(c['status'] == 'success' and c['content'] for c in turn['tool_calls'])
    assert turn['runtime']['counts']['model'] == 4
    assert len(turn['model_requests']) == 4


def test_mismatch_is_rejected(db):
    row = execute_case(synthetic_case(), db, spec=script(2))
    event = row['operations'][0]
    assert (event['status'], event['operation'], event['result']['status']) == ('proposal_mismatch', 'reject', 'rejected')
    assert not [r for r in row['final_db']['orders'] if r['user_id'] == '1001' and r['source_action_id']]


def test_missing_proposal(db):
    row = execute_case(synthetic_case(), db, spec={'responses': [{'answer': '请补充型号。'}]})
    assert row['operations'][0]['status'] == 'missing_proposal'
    assert row['operations'][0]['action_id'] is None


def test_reject_card(db):
    row = execute_case(synthetic_case(decision='reject'), db, spec=script())
    assert row['operations'][0]['result']['status'] == 'rejected'


@pytest.mark.parametrize('response,status', [({'error': 'synthetic-error'}, 'error'),
                                           ({'answer': 'unfinished', 'truncated': True}, 'truncated')])
def test_failure_still_records_turn(db, response, status):
    row = execute_case(synthetic_case(decision=None), db, spec={'responses': [response]})
    assert row['status'] == status
    assert row['turns'][0]['status'] == status
    assert row['turns'][0]['runtime']['counts']['model'] >= 1


def test_nfc_description_slot_and_strict_extra_arguments():
    expected = {'tool': 'propose_service_visit', 'args': {'device_id': 'D-1001-01'},
                'description_must_include': ['é'], 'slot_id_in': ['S-a', 'S-b']}
    actual = {'tool': expected['tool'], 'args': {'device_id': 'D-1001-01', 'description': 'e\u0301', 'slot_id': 'S-b'}}
    assert matches(expected, actual)
    assert not matches(expected, {'tool': expected['tool'], 'args': {**actual['args'], 'extra': 1}})


@pytest.mark.parametrize('formal,environment', [(False, {}), (True, {}), (False, {'SERVICE_EVAL_FORMAL': '1'})])
def test_formal_gate_precedes_any_dataset_read(tmp_path, formal, environment):
    missing = tmp_path / 'evaluation/service_v1/test.jsonl'
    with pytest.raises(ValueError, match='Only dev'):
        verify_dataset(missing, root=tmp_path, formal=formal, environ=environment)


def test_formal_hash_and_default_non_dev_rejection(tmp_path):
    folder = tmp_path / 'evaluation/service_v1'
    folder.mkdir(parents=True)
    test = folder / 'test.jsonl'
    test.write_text(canonical({'id': 'SYN-FORMAL', 'turns': []}) + '\n', encoding='utf-8')
    (folder / 'freeze_manifest.json').write_text(canonical({'files': {'evaluation/service_v1/test.jsonl': digest(test)}}))
    assert verify_dataset(test, root=tmp_path, formal=True, environ={'SERVICE_EVAL_FORMAL': '1'})[0]['id'] == 'SYN-FORMAL'
    test.write_text('{}\n')
    with pytest.raises(ValueError, match='hash mismatch'):
        verify_dataset(test, root=tmp_path, formal=True, environ={'SERVICE_EVAL_FORMAL': '1'})
    with pytest.raises(ValueError, match='Only dev'):
        verify_dataset(tmp_path / 'dev.jsonl', root=tmp_path)


@pytest.mark.parametrize('field', ['code_sha256', 'service_config', 'model_identity', 'dataset_sha256', 'seed', 'timeout_seconds'])
def test_resume_identity_mismatch(field):
    previous = {field: 'before'}
    with pytest.raises(ValueError, match='Cannot resume'):
        assert_resume_identity(previous, {field: 'after'})


def test_existing_failed_records_are_not_dispatched(tmp_path, monkeypatch):
    from evaluation.service_run import run_task
    (tmp_path / 'raw').mkdir()
    row = {'id': 'SYN-ORDER', 'status': 'timeout', 'turns': []}
    (tmp_path / 'raw/SYN-ORDER.json').write_text(canonical(row), encoding='utf-8')
    monkeypatch.setattr('subprocess.run', lambda *a, **k: pytest.fail('must not redispatch'))
    assert run_task({'id': 'SYN-ORDER'}, tmp_path) == row
