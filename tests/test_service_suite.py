"""Offline gold verifier regressions; no Agent, model, or service implementation."""
from contextlib import closing
from copy import deepcopy
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys

import pytest
from pydantic import ValidationError

from evaluation import service_suite_check as check
from service_desk.db import content_sha256, init_db


def task(task_id):
    split = 'dev' if task_id.startswith('SV-D') else 'test' if task_id.startswith('SV-T') else 'injection'
    path = check.ROOT / ('evaluation/service_injection_v1/cases.jsonl' if split == 'injection'
                         else f'evaluation/service_v1/{split}.jsonl')
    return check.Task.model_validate(next(row for row in check.load_jsonl(path) if row['id'] == task_id))


@pytest.fixture(scope='session')
def seed(tmp_path_factory):
    path = tmp_path_factory.mktemp('suite-source') / 'seed.db'
    init_db(path)
    return path


@pytest.fixture
def connection(seed):
    before = content_sha256(seed)
    with closing(sqlite3.connect(':memory:')) as target, closing(sqlite3.connect(seed)) as source:
        source.backup(target)
        target.execute('PRAGMA foreign_keys=ON')
        yield target
    assert content_sha256(seed) == before


def test_committed_reports_are_reproducible_and_all_checks_pass():
    result = check.check_all()
    assert result['ok'] and result['failures'] == []
    for suite, report in result['reports'].items():
        assert report == json.loads((check.ROOT / 'evaluation' / suite / 'static_checks.json').read_text(encoding='utf-8'))
        assert set(report['checks']) == set(check.CHECK_NAMES)
        assert all(item['failed'] == 0 for item in report['checks'].values())
    assert result['reports']['service_injection_v1']['checks']['csv_overlay']['passed'] == 2
    assert result['reports']['service_injection_v1']['checks']['sql_overlay']['passed'] == 7


def test_cli_is_offline_and_does_not_rewrite_artifacts():
    paths = [check.ROOT / 'evaluation' / name / 'static_checks.json'
             for name in ('service_v1', 'service_injection_v1')]
    before = [p.read_bytes() for p in paths]
    reserved = [check.ROOT / 'evaluation/service_v1' / name for name in ('freeze_manifest.json', 'AUTHOR_DECISIONS.json')]
    reserved_before = [p.read_bytes() if p.exists() else None for p in reserved]
    run = subprocess.run([sys.executable, '-B', '-m', 'evaluation.service_suite_check'],
                         cwd=check.ROOT, capture_output=True, text=True, encoding='utf-8', timeout=30)
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout)['ok'] is True
    assert [p.read_bytes() for p in paths] == before
    assert [p.read_bytes() if p.exists() else None for p in reserved] == reserved_before


@pytest.mark.parametrize('mutation,needle', [
    ('unknown_field', 'extra'), ('bad_ref', 'proposal_ref'), ('future_ref', 'proposal_ref'),
    ('duplicate_event', 'proposal_ref'), ('unknown_tool', 'tools'), ('required_outside', 'outside'),
    ('clarify_writes', 'must not propose'), ('unexpected_write', 'allowed write'),
    ('leaked_tool', 'leaked'), ('no_evidence', 'points/evidence'), ('unknown_forbidden', 'forbidden'),
])
def test_corrupt_task_structure_is_rejected(mutation, needle):
    raw = task('SV-T01').model_dump(exclude_none=True)
    if mutation == 'unknown_field': raw['extra'] = True
    elif mutation == 'bad_ref': raw['turns'][1]['proposal_ref'] = 't1.p9'
    elif mutation == 'future_ref': raw['turns'].reverse()
    elif mutation == 'duplicate_event': raw['turns'].append(raw['turns'][1])
    elif mutation == 'unknown_tool': raw['turns'][0]['allowed_tools'].append('send_email')
    elif mutation == 'required_outside': raw['turns'][0]['allowed_tools'].remove('check_warranty')
    elif mutation == 'clarify_writes': raw['turns'][0]['expect'] = 'clarify'
    elif mutation == 'unexpected_write': raw['turns'][0]['allowed_tools'].append('propose_order')
    elif mutation == 'leaked_tool': raw['turns'][0]['query'] = '调用check_warranty给我结果'
    elif mutation == 'no_evidence': raw['turns'][0]['evidence'] = []
    elif mutation == 'unknown_forbidden': raw['turns'][0]['forbidden_proposals'].append('execute_now')
    with pytest.raises((ValueError, ValidationError), match=needle):
        check.verify_structure(check.Task.model_validate(raw))


@pytest.mark.parametrize('task_id,changes,expected', [
    ('SV-T01', {'device_id': 'D-1009-01'}, 'other_user'),
    ('SV-T01', {'slot_id': 'S-west-20260116-2'}, 'other_user'),
    ('SV-T01', {'slot_id': 'S-east-20260116-1'}, 'no_slot'),
    ('SV-T06', {'qty': 4}, 'purchase_limit'),
    ('SV-T06', {'sku': 'SKU-MOP'}, 'out_of_stock'),
    ('SV-T07', {'sku': 'SKU-RUBBER'}, 'incompatible'),
    ('SV-T13', {'target_id': 'O-1001-01'}, 'other_user'),
    ('SV-T13', {'target_id': 'O-1003-01'}, 'other_user'),
])
def test_bad_gold_business_preconditions(connection, task_id, changes, expected):
    selected = task(task_id)
    proposal = selected.turns[0].expected_proposals[0]
    args = {**check.proposal_args(proposal), **changes}
    assert check.precondition(connection, selected.user_id, proposal.tool, args, '2026-01-12') == expected


def test_completed_own_order_is_not_cancellable(connection):
    assert check.precondition(connection, '1001', 'propose_change',
                              {'target_id': 'O-1001-01', 'change': 'cancel_order'}, '2026-01-12') == 'not_cancellable'


@pytest.mark.parametrize('key,value', [('user_id', '1009'), ('qty', 1.5), ('qty', True), ('qty', 0)])
def test_gold_args_use_strict_contracts(key, value):
    proposal = task('SV-T06').turns[0].expected_proposals[0]
    proposal.args[key] = value
    with pytest.raises(ValidationError):
        check.proposal_args(proposal)


@pytest.mark.parametrize('kind', ['db', 'kb', 'csv'])
def test_changed_evidence_is_rejected(connection, kind):
    selected = task('SV-T01') if kind != 'csv' else task('SV-T08')
    item = next(e for e in selected.turns[0].evidence if e.kind == kind)
    if kind == 'db': item.fields['model_code'] = 'SV-999'
    else: item.quote += '伪造事实'
    with pytest.raises(ValueError, match='mismatch'):
        check.verify_evidence(connection, item, check.ROOT)


def test_wrong_declared_blocker_is_rejected(connection):
    selected = task('SV-T24')
    selected.blocked_requests[0].reason = 'no_slot'
    with pytest.raises(ValueError, match='blocked condition mismatch'):
        check.simulate(connection, selected, '2026-01-12')


def test_rejected_proposal_needs_a_nonvacuous_final_check(connection):
    selected = task('SV-T20')
    selected.final_db_checks = [check.FinalCheck(table='orders', where={'user_id': '1009'}, expect_count=1)]
    with pytest.raises(ValueError, match='vacuous'):
        check.simulate(connection, selected, '2026-01-12')


def test_confirmed_change_must_check_business_effect_not_only_pending(connection):
    selected = task('SV-T10')
    selected.final_db_checks = [selected.final_db_checks[0]]
    with pytest.raises(ValueError, match='meaningful business'):
        check.simulate(connection, selected, '2026-01-12')


def test_superseded_card_cannot_be_confirmed(connection):
    selected = task('SV-T21')
    selected.turns[-1].proposal_ref = 't1.p0'
    with pytest.raises(ValueError, match='superseded'):
        check.simulate(connection, selected, '2026-01-12')


def test_gold_confirmation_and_rejection_leave_expected_business_effects(connection):
    selected = task('SI-I08')
    check.apply_overlay(connection, selected, check.ROOT)
    report = check.simulate(connection, selected, '2026-01-12')
    assert report['reject'] == 1 and report['confirm'] == 0 and not report['no_op_would_pass']
    assert connection.execute("SELECT count(*) FROM orders WHERE user_id='1009'").fetchone()[0] == 1
    assert connection.execute("SELECT stock FROM consumables WHERE sku='SKU-RUBBER'").fetchone()[0] == 30


def overlay_root(tmp_path, selected):
    destination = tmp_path / selected.injection.overlay
    destination.parent.mkdir(parents=True, exist_ok=True)
    return destination


@pytest.mark.parametrize('sql,needle', [
    ("UPDATE tickets SET notes='bad'", 'undeclared rows'),
    ("UPDATE tickets SET status='cancelled' WHERE ticket_id='T-1004-01'", 'authorized'),
    ("UPDATE consumables SET name='bad' WHERE sku='SKU-FILTER'", 'authorized'),
    ("DELETE FROM tickets", 'authorized'),
    ("CREATE TABLE leaked (x TEXT)", 'authorized'),
])
def test_sql_overlay_cannot_change_undeclared_rows_fields_or_schema(connection, tmp_path, sql, needle):
    selected = task('SI-I01')
    # Ensure payload presence so the broad-row example reaches scope comparison.
    sql = sql.replace('bad', selected.injection.payload)
    overlay_root(tmp_path, selected).write_text(sql, encoding='utf-8')
    with pytest.raises((ValueError, sqlite3.DatabaseError), match=needle):
        check.apply_overlay(connection, selected, tmp_path)


@pytest.mark.parametrize('tamper', ['second_cell', 'line_endings', 'no_change', 'wrong_column'])
def test_csv_overlay_is_limited_to_one_declared_cell(connection, tmp_path, tamper):
    selected = task('SI-I10')
    destination = overlay_root(tmp_path, selected)
    original_path = tmp_path / 'data/external/records.csv'
    original_path.parent.mkdir(parents=True)
    original = (check.ROOT / 'data/external/records.csv').read_bytes()
    original_path.write_bytes(original)
    altered = (check.ROOT / selected.injection.overlay).read_bytes()
    if tamper == 'second_cell': altered = altered.replace(b'85%', b'86%', 1)
    elif tamper == 'line_endings':
        ending = b'\r\n' if b'\r\n' in altered else b'\n'
        altered = altered.replace(ending, b'\n' if ending == b'\r\n' else b'\r\n')
    elif tamper == 'no_change': altered = original
    elif tamper == 'wrong_column': selected.injection.field = '特征'
    destination.write_bytes(altered)
    with pytest.raises(ValueError, match='CSV'):
        check.apply_overlay(connection, selected, tmp_path)


def test_similarity_reports_near_duplicates_across_splits():
    left, right = task('SV-D08'), task('SV-T14')
    right.turns[0].query = left.turns[0].query
    assert check.cross_similarity([left, right]) == [{'left': left.id, 'right': right.id, 'jaccard': 1.0}]
    right.split = 'dev'
    assert check.cross_similarity([left, right]) == []


def test_cross_split_duplicate_prompt_fails_checker(tmp_path):
    for directory in ('evaluation/service_v1', 'evaluation/service_injection_v1', 'data/external', 'service_kb'):
        shutil.copytree(check.ROOT / directory, tmp_path / directory)
    path = tmp_path / 'evaluation/service_v1/test.jsonl'
    rows = check.load_jsonl(path)
    rows[13]['turns'][0]['query'] = task('SV-D08').turns[0].query
    path.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
    result = check.check_all(tmp_path)
    assert not result['ok']
    assert any(f['check'] == 'isolation' for f in result['failures'])


def test_daily_gold_numbers_and_unknown_code_against_independent_seed_queries(connection):
    selected = task('SV-T18')
    total, average, maximum, observed = connection.execute(
        "SELECT sum(area_m2),avg(area_m2),max(area_m2),count(*) FROM telemetry_daily "
        "WHERE device_id='D-1007-01' AND date BETWEEN '2025-12-01' AND '2025-12-07'").fetchone()
    assert (total, round(average, 2), maximum, observed) == (282.0, 40.29, 42.0, 7)
    assert '282㎡' in selected.turns[0].required_points[0] and '40.29㎡' in selected.turns[0].required_points[0]
    assert all(item['pass'] for item in check.final_results(connection, task('SV-T30').initial_db_checks))


def test_duplicate_json_keys_and_path_escape_are_rejected(tmp_path):
    source = tmp_path / 'duplicate.jsonl'
    source.write_text('{"id":"a","id":"b"}\n', encoding='utf-8')
    with pytest.raises(ValueError, match='duplicate JSON key'):
        check.load_jsonl(source)
    with pytest.raises(ValueError, match='escapes'):
        check.safe_path(tmp_path, '../outside')


def test_all_nine_reads_are_allowed_even_when_not_required():
    selected = task('SV-T07')
    assert check.verify_allowed(selected) == 1
    assert check.READ_TOOLS <= set(selected.turns[0].allowed_tools)
    assert 'rag_summarize' not in selected.turns[0].required_tools
    selected.turns[0].allowed_tools.remove('rag_summarize')
    with pytest.raises(ValueError, match='all nine reads'):
        check.verify_allowed(selected)


@pytest.mark.parametrize('task_id,mutation', [
    ('SV-D01', 'add_rag'), ('SV-T01', 'remove_rag'), ('SV-D01', 'add_kb'),
])
def test_knowledge_request_gates_required_retrieval(task_id, mutation):
    selected = task(task_id)
    if mutation == 'add_rag': selected.turns[0].required_tools.append('rag_summarize')
    elif mutation == 'remove_rag': selected.turns[0].required_tools.remove('rag_summarize')
    else: selected.turns[0].evidence.append(next(e for e in task('SV-T01').turns[0].evidence if e.kind == 'kb'))
    with pytest.raises(ValueError, match='knowledge|KB-only'):
        check.verify_knowledge(selected)


@pytest.mark.parametrize('value', [None, 'false', 0])
def test_user_knowledge_flag_is_required_and_strict(value):
    raw = task('SV-D01').model_dump(exclude_none=True)
    raw['turns'][0]['knowledge_requested'] = value
    with pytest.raises((ValueError, ValidationError), match='knowledge_requested'):
        check.verify_structure(check.Task.model_validate(raw))


@pytest.mark.parametrize('task_id,missing', [
    ('SV-T01', 'list_my_devices'), ('SV-T01', 'lookup_error_code'),
    ('SV-T01', 'check_warranty'), ('SV-T01', 'find_service_slots'),
    ('SV-T08', 'find_consumables'), ('SV-T08', 'fetch_external_data'),
    ('SV-T11', 'get_my_orders_and_tickets'), ('SV-T10', 'find_service_slots'),
])
def test_proposals_require_prior_service_workflow(task_id, missing):
    selected = task(task_id)
    selected.turns[0].required_tools.remove(missing)
    with pytest.raises(ValueError, match='SOP tools missing'):
        check.verify_workflow(selected)


def test_workflow_can_reuse_prior_facts_but_not_future_reads():
    selected = task('SV-T22')
    assert 'lookup_error_code' not in selected.turns[1].required_tools
    assert check.verify_workflow(selected) == 2
    selected.turns[0].required_tools.remove('check_warranty')
    selected.turns[1].required_tools.append('check_warranty')
    with pytest.raises(ValueError, match='SOP tools missing'):
        check.verify_workflow(selected)


@pytest.mark.parametrize('words', [[], ['漏水', '接口', '水箱'], ['接口一直漏水'], ['E09']])
def test_description_keywords_reject_count_length_and_wrong_code(words):
    proposal = task('SV-T01').turns[0].expected_proposals[0]
    proposal.description_must_include = words
    with pytest.raises(ValueError, match='description'):
        check.verify_description(proposal)


@pytest.mark.parametrize('task_id,removed_table', [
    ('SV-D07', 'consumables'), ('SV-T12', 'consumables'), ('SV-T13', 'consumables'),
    ('SV-T11', 'tickets'), ('SV-T11', 'service_slots'),
])
def test_cancellation_gold_cannot_omit_inventory_ticket_or_slot(connection, task_id, removed_table):
    selected = task(task_id)
    selected.final_db_checks = [item for item in selected.final_db_checks if item.table != removed_table]
    with pytest.raises(ValueError, match='cancel .*final checks'):
        check.verify_cancel_effects(connection, selected)


def test_cancellation_gold_applies_independent_business_effects(connection):
    check.simulate(connection, task('SV-T11'), '2026-01-12')
    assert connection.execute("SELECT status FROM tickets WHERE ticket_id='T-1008-01'").fetchone()[0] == 'cancelled'
    check.simulate(connection, task('SV-T12'), '2026-01-12')
    assert connection.execute("SELECT stock FROM consumables WHERE sku='SKU-RUBBER'").fetchone()[0] == 31


def test_expired_visit_is_allowed_unless_user_requires_warranty(connection):
    selected = task('SV-T05')
    proposal = selected.turns[0].expected_proposals[0]
    args = check.proposal_args(proposal)
    assert check.precondition(connection, selected.user_id, proposal.tool, args, '2026-01-12', proposal.visit_policy) is None
    proposal.visit_policy.warranty_required = True
    assert check.precondition(connection, selected.user_id, proposal.tool, args, '2026-01-12', proposal.visit_policy) == 'warranty_expired'


def test_self_fixable_visit_needs_reported_failed_self_check(connection):
    selected = task('SV-T27')
    user_turns = [turn for turn in selected.turns if turn.type == 'user']
    assert not user_turns[0].expected_proposals and not user_turns[1].expected_proposals
    proposal = user_turns[2].expected_proposals[0]
    args = check.proposal_args(proposal)
    assert check.precondition(connection, selected.user_id, proposal.tool, args, '2026-01-12') == 'self_fixable'
    assert check.precondition(connection, selected.user_id, proposal.tool, args, '2026-01-12', proposal.visit_policy) is None
    assert check.verify_workflow(selected) == 1
    proposal.visit_policy.self_check_quote = '编造用户已经自查'
    with pytest.raises(ValueError, match='self-check quote'):
        check.verify_workflow(selected)


def test_scene_overlap_uses_entities_even_with_different_wording():
    left, right = task('SV-D12'), task('SV-T22')
    assert check.scenario_pairs([left, right]) == []
    right.user_id = left.user_id
    right.turns[0].expected_proposals[0].args['error_code'] = 'E07'
    pairs = check.scenario_pairs([left, right])
    assert len(pairs) == 1 and 'error:E07' in pairs[0]['entities']


def test_test_user_cap_is_enforced(tmp_path):
    for directory in ('evaluation/service_v1', 'evaluation/service_injection_v1', 'data/external', 'service_kb'):
        shutil.copytree(check.ROOT / directory, tmp_path / directory)
    path = tmp_path / 'evaluation/service_v1/test.jsonl'
    rows = check.load_jsonl(path)
    rows[2]['user_id'] = '1006'
    path.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
    result = check.check_all(tmp_path)
    assert not result['ok']
    assert result['reports']['service_v1']['test_users_over_limit'] == {'1006': 6}
    assert any(f['check'] == 'test_user_limit' for f in result['failures'])


@pytest.mark.parametrize('mutation', ['wrong_field', 'missing_tool', 'wrong_mode', 'claim_exposed', 'absent_status'])
def test_injection_requires_declared_exposure_path_without_claiming_execution(mutation):
    selected = task('SI-I10')
    if mutation == 'wrong_field': selected.injection.exposure_field = 'data.特征'
    elif mutation == 'missing_tool': selected.turns[0].required_tools.remove('fetch_external_data')
    elif mutation == 'wrong_mode': selected.injection.exposure_mode = 'retrieval_result'
    elif mutation == 'claim_exposed': selected.exposed = True
    else: selected.model_fields_set.remove('exposed')
    with pytest.raises(ValueError, match='exposure|exposed'):
        check.verify_exposure(selected)
