"""Complete tokenizer archive assets after collection, without inference.

The old snapshot suffix whitelist omitted gzip bytes although it pinned the
tokenizer descriptor. This records a post-collection addition, never a new
pre-inference freeze. Existing assets and sidecars are validated, not rewritten.
Only a missing tokenizer asset and budget_assets.json may be created.
"""
import argparse
from collections import Counter
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

if __package__:
    from .seal_evaluation_run import (
        EXCLUDED_DIRECTORIES, TERMINAL_STATUSES, _checked_file, _hash_map, _linked, _unique_rows,
        normalized_path,
    )
else:
    from seal_evaluation_run import (
        EXCLUDED_DIRECTORIES, TERMINAL_STATUSES, _checked_file, _hash_map, _linked, _unique_rows,
        normalized_path,
    )


ROOT = Path(__file__).resolve().parents[1]
SIDECAR = 'budget_assets.json'
DESCRIPTOR = 'config/context_tokenizer.json'
ASSET_NOTE = (
    'Execution identity captured the tokenizer descriptor but its suffix whitelist omitted the gzip asset. '
    'Archive closure below was added after collection, not retrospectively asserted as a new pre-inference freeze. '
    'Actual budget traces are reported separately.'
)
HISTORICAL_NOTE = (
    'Historical version has no tokenizer descriptor or Runtime budgeting; '
    'no synthetic budget traces or asset are added.'
)


def _directory(value):
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    if _linked(path):
        raise ValueError(f'Directory must not be a link: {path}')
    path = path.resolve()
    if not path.is_dir():
        raise ValueError(f'Directory does not exist: {path}')
    return path


def _safe_target(root, name):
    path = root
    for part in Path(normalized_path(name)).parts:
        path = path / part
        if _linked(path):
            raise ValueError(f'Archive link is not supported: {name}')
    return path


def _json(data, label):
    value = json.loads(data.decode('utf-8-sig'))
    if not isinstance(value, dict):
        raise ValueError(f'Expected JSON object: {label}')
    return value


def _rows(data, label):
    rows = []
    for line in data.decode('utf-8-sig').splitlines():
        if line.strip():
            rows.append(_json(line.encode('utf-8'), label))
    return rows


def _check_sha(data, expected, label):
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected:
        raise ValueError(f'Frozen hash mismatch: {label}')
    return actual


def _capture_date(value):
    if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
        raise ValueError('Capture date must be YYYY-MM-DD')
    return value


def _observed_budget(rows):
    latest, owners = {}, {}
    requests = 0
    for row in rows:
        model_requests = row.get('model_requests', [])
        snapshots = row.get('runtime_snapshots', [])
        if not isinstance(model_requests, list) or not isinstance(snapshots, list):
            raise ValueError(f'Invalid observation lists: {row["id"]}')
        requests += len(model_requests)
        for snapshot in snapshots:
            if not isinstance(snapshot, dict):
                raise ValueError(f'Invalid Runtime snapshot: {row["id"]}')
            run_id, events = snapshot.get('run_id'), snapshot.get('events')
            if not isinstance(run_id, str) or not run_id or not isinstance(events, list):
                raise ValueError(f'Invalid Runtime run ID/events: {row["id"]}')
            if any(not isinstance(event, dict) for event in events):
                raise ValueError(f'Invalid Runtime event: {row["id"]}')
            if run_id in owners and owners[run_id] != row['id']:
                raise ValueError(f'Runtime run ID reused across cases: {run_id}')
            owners[run_id] = row['id']
            previous = latest.get(run_id)
            if previous is not None:
                shared = min(len(previous), len(events))
                if previous[:shared] != events[:shared]:
                    raise ValueError(f'Conflicting Runtime snapshots: {run_id}')
            if previous is None or len(events) > len(previous):
                latest[run_id] = events
    checks = [event for events in latest.values() for event in events
              if event.get('event') == 'context_budget_checked']
    methods = Counter()
    digests, templates = set(), set()
    for event in checks:
        method = event.get('estimation_method', 'unknown')
        if not isinstance(method, str) or not method:
            raise ValueError('Invalid observed estimation method')
        methods[method] += 1
        for field, values in (('tokenizer_model_digest', digests),
                              ('tokenizer_template_sha256', templates)):
            value = event.get(field)
            if value:
                if not isinstance(value, str):
                    raise ValueError(f'Invalid observed {field}')
                values.add(value)
    return {'runtime_snapshots_deduplicated': len(latest), 'budget_checks': len(checks),
            'estimation_methods': dict(methods), 'tokenizer_model_digests': sorted(digests),
            'tokenizer_template_sha256': sorted(templates), 'observed_model_requests': requests}


def complete_assets(run, assets_from=ROOT, capture_date=None):
    """Validate all inputs, then create only missing, matching archive assets."""
    run = _directory(run)
    if capture_date is not None:
        _capture_date(capture_date)
    cases_data = _checked_file(run, 'cases.jsonl').read_bytes()
    manifest = _json(_checked_file(run, 'manifest.json').read_bytes(), 'manifest.json')
    _check_sha(cases_data, manifest.get('dataset_sha256'), 'cases.jsonl')
    cases = _unique_rows(_rows(cases_data, 'cases.jsonl'), 'planned')
    if not cases:
        raise ValueError('Planned cases must not be empty')
    rows = _rows(_checked_file(run, 'results.jsonl').read_bytes(), 'results.jsonl')
    results = _unique_rows(rows, 'result', cases)
    missing = sorted(cases.keys() - results.keys())
    if missing:
        raise ValueError(f'Incomplete result records: {", ".join(missing)}')
    if any(not isinstance(row.get('status'), str) or row['status'] not in TERMINAL_STATUSES
           for row in rows):
        raise ValueError('Only terminal result records can complete archive assets')

    output = _safe_target(run, SIDECAR)
    existing = _json(output.read_bytes(), SIDECAR) if output.exists() else None
    captured = (_capture_date(existing.get('capture_date')) if existing is not None else
                capture_date or datetime.now(timezone.utc).date().isoformat())
    sidecar = {'capture_phase': 'post_collection', 'capture_date': captured,
               **_observed_budget(rows), 'note': ASSET_NOTE}
    code_hashes = _hash_map(manifest.get('code_sha256'), 'code_sha256')
    descriptor = _safe_target(run, 'snapshot/' + DESCRIPTOR)
    target, payload = None, None
    if descriptor.exists() or DESCRIPTOR in code_hashes:
        descriptor_data = _checked_file(run, 'snapshot/' + DESCRIPTOR).read_bytes()
        descriptor_sha = _check_sha(descriptor_data, code_hashes.get(DESCRIPTOR), DESCRIPTOR)
        identity = _json(descriptor_data, DESCRIPTOR)
        relative = normalized_path(identity.get('cache_file'))
        if set(Path(relative).parts[:-1]) & EXCLUDED_DIRECTORIES:
            raise ValueError('Tokenizer cache cannot be in a directory excluded from the archive')
        target = _safe_target(run, 'snapshot/config/' + relative)
        target.resolve().relative_to(descriptor.parent.resolve())
        if target.exists():
            payload = _checked_file(run, 'snapshot/config/' + relative).read_bytes()
        else:
            source_root = _directory(assets_from)
            payload = _checked_file(source_root, 'config/' + relative).read_bytes()
        cache_sha = _check_sha(payload, identity.get('cache_sha256'), 'tokenizer cache')
        sidecar['asset'] = {'descriptor_sha256': descriptor_sha,
                            'snapshot_path': target.relative_to(run).as_posix(),
                            'sha256': cache_sha, 'matches_pre_pinned_descriptor': True}
    else:
        sidecar['asset'] = None
        sidecar['note'] = (HISTORICAL_NOTE if not sidecar['runtime_snapshots_deduplicated'] else
                           'No tokenizer descriptor or asset is present. Budget statistics come only '
                           'from observed Runtime traces; no synthetic traces are added.')
    if existing is not None and (
            json.dumps(existing, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
            != json.dumps(sidecar, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)):
        raise ValueError('Preserve previous closure sidecar; its content differs')
    add_asset, add_sidecar = target is not None and not target.exists(), existing is None
    if _safe_target(run, 'seal.json').exists() and (add_asset or add_sidecar):
        raise ValueError('Do not add files to an already sealed archive')
    if add_asset:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as handle:
            handle.write(payload)
    if add_sidecar:
        encoded = (json.dumps(sidecar, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
        with output.open('xb') as handle:
            handle.write(encoded)
    return {'run': str(run), 'capture_date': captured, 'budget_checks': sidecar['budget_checks'],
            'methods': sidecar['estimation_methods'], 'asset_added': add_asset,
            'sidecar_added': add_sidecar, 'asset_present': target is not None}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True, help='Run directory, absolute or relative to the project root.')
    parser.add_argument('--assets-from', default=str(ROOT),
                        help='Asset source project root containing config/, absolute or relative to this project root.')
    parser.add_argument('--capture-date',
                        help='First capture date in YYYY-MM-DD; defaults to the current UTC date. Existing dates are preserved.')
    args = parser.parse_args(argv)
    try:
        result = complete_assets(args.run, args.assets_from, args.capture_date)
    except (ValueError, OSError) as exc:
        print(f'Archive asset completion failed: {exc}', file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
