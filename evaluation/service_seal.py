"""Offline service archive validation; imports no inference/model code."""
import json
from pathlib import Path

from evaluation.service_eval import digest, read_rows, result_sha256
from evaluation.service_review import verify_score_lock


def validate_service_archive(run, inventory, manifest):
    """Called by the existing seal CLI; keep its inventory/immutability checks."""
    def expected(name, value):
        if inventory.get(name) != value:
            raise ValueError('Service archive hash mismatch: ' + name)
    for field in ('code_sha256', 'source_sha256', 'evaluation_sha256'):
        if not manifest.get(field):
            raise ValueError('Missing service snapshot identity: ' + field)
        for name, value in manifest[field].items():
            expected('snapshot/' + name, value)
    expected('cases.jsonl', manifest['cases_sha256'])
    expected('snapshot/dataset.jsonl', manifest['dataset_sha256'])
    for name, value in manifest['freeze_sha256'].items():
        expected('snapshot/' + name, value)
    if manifest.get('script_sha256'):
        expected('snapshot/script.json', manifest['script_sha256'])
    # SQLite content hashing imports only the offline DB/stdlib module.
    from service_desk.db import content_sha256
    if content_sha256(run / 'seed.db') != manifest['service_config']['seed_content_sha256']:
        raise ValueError('Service archive seed changed')
    cases = read_rows(run / 'cases.jsonl')
    def unique(name):
        rows = read_rows(run / name)
        index = {row['id']: row for row in rows}
        if len(index) != len(rows) or set(index) != {case['id'] for case in cases}:
            raise ValueError('Incomplete/duplicate service records: ' + name)
        return index
    results, reviews, scores = unique('results.jsonl'), unique('reviews.jsonl'), unique('scores.jsonl')
    verify_score_lock(run / 'review_archive')
    lock_digest = digest(run / 'review_archive/score_lock.json')
    locked = {row['sample_id']: row for row in read_rows(run / 'review_archive/locked_scores.jsonl')}
    for case in cases:
        key = case['id']
        row, review = results[key], reviews[key]
        if row['status'] not in ('ok', 'error', 'timeout', 'truncated'):
            raise ValueError('Nonterminal service result: ' + key)
        raw = json.loads((run / 'raw' / (key + '.json')).read_text(encoding='utf-8'))
        bound = result_sha256(row)
        if (result_sha256(raw) != bound or review['result_sha256'] != bound or
                scores[key]['result_sha256'] != bound or review['score_lock_sha256'] != lock_digest):
            raise ValueError('Service result/review binding mismatch: ' + key)
        db = run / 'databases' / (key + '.db')
        observed_hash = content_sha256(db) if db.is_file() else None
        if observed_hash != (row.get('db_content_sha256') or scores[key].get('scored_db_content_sha256')):
            raise ValueError('Service task DB changed: ' + key)
        expected_turns = sum(turn['type'] == 'user' for turn in case['turns'])
        if sorted(t['user_turn'] for t in review['turns']) != list(range(1, expected_turns + 1)):
            raise ValueError('Incomplete service turn review: ' + key)
        for turn in review['turns']:
            locked_turn = locked.get(turn['sample_id'], {})
            if (turn['result_sha256'] != bound or turn['content_score'] != locked_turn.get('content_score') or
                    turn['grounded'] != locked_turn.get('grounded') or locked_turn.get('result_sha256') != bound):
                raise ValueError('Service review differs from locked scores: ' + key)
        semantic = all(t['content_score'] == 2 and t['grounded'] for t in review['turns'])
        if (type(review['task_pass']) is not bool or
                review['task_pass'] != (semantic and scores[key]['automatic_pass'])):
            raise ValueError('Invalid aggregate service review: ' + key)
    if len(cases) != manifest['planned_tasks']:
        raise ValueError('Service planned task count mismatch')
    return {'planned_cases': len(cases), 'raw_records': len(results), 'review_records': len(reviews)}
