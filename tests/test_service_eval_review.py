"""Synthetic blinded packets, immutable lock and service archive integration."""
import json
import shutil
from pathlib import Path
import pytest

from evaluation.service_eval import digest, dump, read_rows, result_sha256, write_rows
from evaluation.service_review import create_packets, lock_scores, reveal
from evaluation.service_run import create_seed, execute_case
from test_service_eval_runner import synthetic_case, script


@pytest.fixture(scope='module')
def seed(tmp_path_factory):
    path = tmp_path_factory.mktemp('synthetic-review') / 'seed.db'
    create_seed(path)
    return path


@pytest.fixture
def run(seed, tmp_path, monkeypatch):
    monkeypatch.setenv('AGENT_TOOLSET', 'service')
    run = tmp_path / 'mode-secret-react'
    run.mkdir()
    for folder in ('databases', 'raw', 'snapshot/evaluation'):
        (run / folder).mkdir(parents=True, exist_ok=True)
    db = run / 'databases/SYN-ORDER.db'
    shutil.copyfile(seed, db)
    shutil.copyfile(seed, run / 'seed.db')
    case = synthetic_case()
    row = execute_case(case, db, spec=script())
    write_rows(run / 'cases.jsonl', [case])
    write_rows(run / 'results.jsonl', [row])
    dump(run / 'raw/SYN-ORDER.json', row)
    (run / 'snapshot/evaluation/fixture.py').write_text('# synthetic fixture\n')
    (run / 'snapshot/source.txt').write_text('synthetic source\n')
    (run / 'snapshot/fixture-config.json').write_text('{}\n')
    shutil.copyfile(run / 'cases.jsonl', run / 'snapshot/dataset.jsonl')
    (run / 'snapshot/freeze_manifest.json').write_text('{}\n')
    from service_desk.config import load_config
    dump(run / 'manifest.json', {'runner': 'service', 'mode': 'react', 'timeout_seconds': 240,
        'cases_sha256': digest(run / 'cases.jsonl'), 'dataset_sha256': digest(run / 'cases.jsonl'),
        'planned_tasks': 1, 'service_config': load_config(),
        'code_sha256': {'fixture-config.json': digest(run / 'snapshot/fixture-config.json')},
        'source_sha256': {'source.txt': digest(run / 'snapshot/source.txt')},
        'evaluation_sha256': {'evaluation/fixture.py': digest(run / 'snapshot/evaluation/fixture.py')},
        'freeze_sha256': {'freeze_manifest.json': digest(run / 'snapshot/freeze_manifest.json')}})
    return run


def scores_for(output, tmp_path):
    path = tmp_path / 'scores.jsonl'
    write_rows(path, [{'sample_id': row['sample_id'], 'content_score': 2, 'grounded': True,
                      'result_sha256': row['result_sha256']} for row in read_rows(output / 'blind_cases.jsonl')])
    return path


def test_packets_hide_mode_and_bind_exact_raw_result(run, tmp_path):
    output = tmp_path / 'review'
    create_packets([run], output)
    packets = read_rows(output / 'blind_cases.jsonl')
    assert 'react' not in (output / 'blind_cases.jsonl').read_text(encoding='utf-8')
    assert 'mode-secret' not in (output / 'blind_manifest.json').read_text(encoding='utf-8')
    assert packets[0]['result_sha256'] == result_sha256(read_rows(run / 'results.jsonl')[0])
    assert packets[0]['required_points'] and packets[0]['tool_evidence']
    assert read_rows(output / 'private_key.jsonl')[0]['mode'] == 'react'
    output2 = tmp_path / 'review-again'
    create_packets([run], output2)
    assert digest(output / 'blind_cases.jsonl') == digest(output2 / 'blind_cases.jsonl')


def test_reveal_requires_lock_then_binds_scores(run, tmp_path):
    output = tmp_path / 'review'
    create_packets([run], output)
    with pytest.raises(FileNotFoundError):
        reveal(output)
    locked = lock_scores(output, scores_for(output, tmp_path))
    assert locked['scores_sha256'] == digest(output / 'locked_scores.jsonl')
    assert reveal(output)['task_pass_count'] == 1
    assert read_rows(run / 'reviews.jsonl')[0]['turns'][0]['content_score'] == 2
    with pytest.raises(ValueError, match='already locked'):
        lock_scores(output, scores_for(output, tmp_path))


def test_automatic_pass_only_packs_passes_and_guards_selection(run, tmp_path):
    from evaluation.service_score import score_run
    score_run(run)
    output = tmp_path / 'review'
    create_packets([run], output, automatic_pass_only=True)
    assert len(read_rows(output / 'blind_cases.jsonl')) == 1
    lock_scores(output, scores_for(output, tmp_path))
    assert reveal(output)['task_pass_count'] == 1
    # A task skipped as an automatic failure must still be one when revealed.
    rows = read_rows(run / 'scores.jsonl')
    write_rows(run / 'scores.jsonl', [{**row, 'automatic_pass': False} for row in rows])
    skipped = tmp_path / 'review-skipped'
    create_packets([run], skipped, automatic_pass_only=True)
    assert read_rows(skipped / 'blind_cases.jsonl') == []
    lock_scores(skipped, scores_for(skipped, tmp_path))
    with pytest.raises(ValueError, match='Automatic passes changed'):
        reveal(skipped)


def test_changed_locked_score_refuses_reveal(run, tmp_path):
    output = tmp_path / 'review'
    create_packets([run], output)
    lock_scores(output, scores_for(output, tmp_path))
    (output / 'locked_scores.jsonl').write_text('{}\n')
    with pytest.raises(ValueError, match='Locked review changed'):
        reveal(output)


def test_original_result_change_refuses_reveal(run, tmp_path):
    output = tmp_path / 'review'
    create_packets([run], output)
    lock_scores(output, scores_for(output, tmp_path))
    rows = read_rows(run / 'results.jsonl')
    rows[0]['turns'][0]['answer'] = 'changed'
    write_rows(run / 'results.jsonl', rows)
    with pytest.raises(ValueError, match='Original results changed'):
        reveal(output)


def test_service_seal_uses_existing_cli_and_detects_changes(run, tmp_path):
    from scripts.seal_evaluation_run import seal_run
    output = tmp_path / 'review'
    create_packets([run], output)
    lock_scores(output, scores_for(output, tmp_path))
    reveal(output)
    assert seal_run(run)['action'] == 'sealed'
    assert seal_run(run, verify=True)['action'] == 'verified'
    (run / 'reviews.jsonl').write_text('{}\n')
    with pytest.raises((ValueError, KeyError)):
        seal_run(run, verify=True)


def test_interrupted_claim_still_audits_actual_task_database(run):
    from evaluation.service_score import score_run
    rows = read_rows(run / 'results.jsonl')
    row = rows[0]
    row.update(status='error', error_type='InterruptedRun', operations=[])
    row.pop('db_content_sha256')
    row.pop('final_db')
    write_rows(run / 'results.jsonl', rows)
    summary = score_run(run)
    assert summary['hard_gates']['H1'] == 1
    assert summary['database_result_unsealed_tasks'] == 1
    assert summary['automatic_pass_rate']['numerator'] == 0
