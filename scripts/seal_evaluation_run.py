"""Seal or verify a complete evaluation archive without importing inference code.

This is an offline file inventory, not a tamper-proof signature or a replacement
for the live input/model identity checks performed when inference is resumed.
Run this after reports and exports are final; an existing seal is never replaced.
"""
import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

if __package__:
    from .prepare_evaluation_variant import relative_path
else:
    from prepare_evaluation_variant import relative_path


EXCLUDED_DIRECTORIES = frozenset({'logs', 'workers', '__pycache__', 'tmp'})
SEAL_NAME = 'seal.json'
TERMINAL_STATUSES = frozenset({'ok', 'error', 'timeout', 'truncated'})
INTEGRITY_NOTE = (
    'Offline SHA256 inventory detects archive changes against this seal; '
    'it is not a cryptographic signature and does not replace live inference '
    'resume identity validation.'
)


def normalized_path(name):
    """Use portable manifest paths and reject roots, drives and traversal."""
    if not isinstance(name, str) or not name or '\x00' in name:
        raise ValueError(f'Unsafe relative path: {name!r}')
    result = relative_path(name).as_posix()
    if result == '.':
        raise ValueError(f'Unsafe relative path: {name!r}')
    return result


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def result_sha256(row):
    """Match evaluation.report's frozen, sorted-key compact UTF-8 binding."""
    return _sha256(json.dumps(row, ensure_ascii=False, sort_keys=True,
                              separators=(',', ':')).encode('utf-8'))


def _linked(path):
    return path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction())


def _checked_file(run, name):
    name = normalized_path(name)
    path = run
    for part in Path(name).parts:
        path = path / part
        if _linked(path):
            raise ValueError(f'Archive link is not supported: {name}')
    if not path.is_file():
        raise ValueError(f'Missing archive file: {name}')
    return path


def _file_digest(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _inventory(run):
    result = {}
    def walk_error(error):
        raise error
    for directory, names, files in os.walk(run, followlinks=False, onerror=walk_error):
        current = Path(directory)
        kept = []
        for name in sorted(names):
            folder = current / name
            if _linked(folder):
                raise ValueError(f'Archive link is not supported: {folder.relative_to(run)}')
            if name in EXCLUDED_DIRECTORIES:
                continue
            kept.append(name)
        names[:] = kept
        for name in sorted(files):
            path = current / name
            rel = normalized_path(path.relative_to(run).as_posix())
            if rel == SEAL_NAME:
                continue
            path = _checked_file(run, rel)
            result[rel] = _file_digest(path)
    return dict(sorted(result.items()))


def _read_bytes(run, name, inventory):
    name = normalized_path(name)
    data = _checked_file(run, name).read_bytes()
    if inventory.get(name) != _sha256(data):
        raise ValueError(f'Archive changed during validation: {name}')
    return data


def _json_file(run, name, inventory):
    value = json.loads(_read_bytes(run, name, inventory).decode('utf-8-sig'))
    if not isinstance(value, dict):
        raise ValueError(f'Expected JSON object: {name}')
    return value


def _jsonl_file(run, name, inventory):
    rows = []
    for number, line in enumerate(_read_bytes(run, name, inventory).decode('utf-8-sig').splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f'Expected JSON object in {name}:{number}')
        rows.append(row)
    return rows


def _hash_map(value, label):
    if not isinstance(value, dict) or not value:
        raise ValueError(f'Missing or empty hash mapping: {label}')
    result = {}
    for name, expected in value.items():
        rel = normalized_path(name)
        if rel in result:
            raise ValueError(f'Duplicate normalized path in {label}: {rel}')
        if not isinstance(expected, str) or not re.fullmatch('[0-9a-f]{64}', expected):
            raise ValueError(f'Invalid SHA256 in {label}: {rel}')
        result[rel] = expected
    return result


def _expected_hash(inventory, name, expected):
    if not isinstance(expected, str) or not re.fullmatch('[0-9a-f]{64}', expected):
        raise ValueError(f'Missing or invalid SHA256: {name}')
    if inventory.get(name) != expected:
        raise ValueError(f'Frozen hash mismatch: {name}')


def _snapshot_hashes(inventory, value, label):
    normalized = _hash_map(value, label)
    for name, expected in normalized.items():
        _expected_hash(inventory, 'snapshot/' + name, expected)
    return normalized


def _validate_tokenizer_cache(run, inventory, code_hashes):
    descriptor = 'snapshot/config/context_tokenizer.json'
    if descriptor not in inventory:
        return  # Historical versions without a tokenizer descriptor need no cache.
    _expected_hash(inventory, descriptor, code_hashes.get('config/context_tokenizer.json'))
    values = _json_file(run, descriptor, inventory)
    relative = normalized_path(values.get('cache_file'))
    cache_name = 'snapshot/config/' + relative
    cache_path = _checked_file(run, cache_name)
    try:
        cache_path.resolve().relative_to((run / 'snapshot/config').resolve())
    except ValueError as exc:
        raise ValueError('Tokenizer cache must remain within snapshot/config') from exc
    _expected_hash(inventory, cache_name, values.get('cache_sha256'))


def _unique_rows(rows, label, allowed=None):
    result = {}
    for row in rows:
        key = row.get('id')
        if not isinstance(key, str) or not key or key in result:
            raise ValueError(f'Missing or duplicate {label} case ID: {key!r}')
        if allowed is not None and key not in allowed:
            raise ValueError(f'Unknown {label} case ID: {key}')
        result[key] = row
    return result


def _validate_inputs(run, inventory):
    manifest = _json_file(run, 'manifest.json', inventory)
    hashes = {field: _snapshot_hashes(inventory, manifest.get(field), field)
              for field in ('code_sha256', 'evaluation_sha256', 'source_sha256')}
    _validate_tokenizer_cache(run, inventory, hashes['code_sha256'])
    _expected_hash(inventory, 'cases.jsonl', manifest.get('dataset_sha256'))
    _expected_hash(inventory, 'snapshot/dataset_manifest.json',
                   manifest.get('dataset_manifest_sha256'))
    dataset = _json_file(run, 'snapshot/dataset_manifest.json', inventory)
    if dataset.get('dataset_sha256') != manifest['dataset_sha256']:
        raise ValueError('Dataset hash differs between run and dataset manifests')
    sources = _snapshot_hashes(inventory, dataset.get('files'), 'dataset files')
    if sources != hashes['source_sha256']:
        raise ValueError('Source hashes differ between run and dataset manifests')

    variant, variant_hash = manifest.get('variant_identity'), manifest.get('variant_identity_sha256')
    if variant is not None or variant_hash is not None:
        _expected_hash(inventory, 'snapshot/variant_identity.json', variant_hash)
        frozen_variant = _json_file(run, 'snapshot/variant_identity.json', inventory)
        if variant != frozen_variant:
            raise ValueError('Variant identity differs between manifest and snapshot')
        if frozen_variant.get('label') == 'historical_optimized_v1':
            if _hash_map(frozen_variant.get('historical_code_sha256'),
                         'variant historical_code_sha256') != hashes['code_sha256']:
                raise ValueError('Historical variant code hashes differ from run manifest')
            if _hash_map(frozen_variant.get('source_sha256'),
                         'variant source_sha256') != hashes['source_sha256']:
                raise ValueError('Historical variant source hashes differ from run manifest')

    cases = _unique_rows(_jsonl_file(run, 'cases.jsonl', inventory), 'planned')
    count = dataset.get('case_count')
    if type(count) is not int or count < 1 or count != len(cases):
        raise ValueError('Planned case count differs from dataset manifest')
    results = _unique_rows(_jsonl_file(run, 'results.jsonl', inventory), 'result', cases)
    reviews = _unique_rows(_jsonl_file(run, 'reviews.jsonl', inventory), 'review', cases)
    for label, rows in (('result', results), ('review', reviews)):
        missing = sorted(cases.keys() - rows.keys())
        if missing:
            raise ValueError(f'Incomplete {label} records; missing case IDs: {", ".join(missing)}')
    for key, row in results.items():
        status = row.get('status')
        if not isinstance(status, str) or status not in TERMINAL_STATUSES:
            raise ValueError(f'Incomplete result status: {key}')
    for key, review in reviews.items():
        score = review.get('answer_score')
        if score is not None and (type(score) is not int or score not in (0, 1, 2)):
            raise ValueError(f'Invalid answer_score: {key}')
        for field in ('grounded', 'task_pass'):
            if review.get(field) is not None and type(review[field]) is not bool:
                raise ValueError(f'Invalid {field}: {key}')
        if review.get('result_sha256') != result_sha256(results[key]):
            raise ValueError(f'Semantic review/result hash mismatch: {key}')
    return {'planned_cases': count, 'raw_records': len(results), 'review_records': len(reviews)}


def _verify_inventory(seal, inventory, counts):
    if (type(seal.get('seal_version')) is not int or seal['seal_version'] != 1
            or seal.get('hash_algorithm') != 'sha256'):
        raise ValueError('Unsupported seal format')
    files = _hash_map(seal.get('files'), 'seal files')
    if SEAL_NAME in files or any(set(Path(name).parts[:-1]) & EXCLUDED_DIRECTORIES for name in files):
        raise ValueError('Seal contains an excluded path')
    added, removed = sorted(inventory.keys() - files.keys()), sorted(files.keys() - inventory.keys())
    changed = sorted(name for name in inventory.keys() & files.keys() if inventory[name] != files[name])
    if added or removed or changed:
        raise ValueError(f'Archive inventory mismatch: added={added}, removed={removed}, changed={changed}')
    if any(type(seal.get(key)) is not int or seal[key] != value for key, value in counts.items()):
        raise ValueError('Seal record counts differ from validated archive')


def seal_run(run, verify=False):
    """Create a complete archive seal, or verify one without overwriting it."""
    run = Path(run)
    if _linked(run):
        raise ValueError('Run directory must not be a link')
    run = run.resolve()
    if not run.is_dir():
        raise ValueError(f'Run directory does not exist: {run}')
    seal_path = run / SEAL_NAME
    exists = seal_path.exists()
    if verify and not exists:
        raise ValueError(f'Missing archive seal: {seal_path}')
    if _linked(seal_path):
        raise ValueError('Archive seal must not be a link')
    inventory = _inventory(run)
    counts = _validate_inputs(run, inventory)
    if exists:
        seal = json.loads(seal_path.read_text(encoding='utf-8'))
        if not isinstance(seal, dict):
            raise ValueError('Expected JSON object: seal.json')
        _verify_inventory(seal, inventory, counts)
    else:
        seal = {'seal_version': 1, 'hash_algorithm': 'sha256', **counts,
                'files': inventory, 'integrity_note': INTEGRITY_NOTE}
    if _inventory(run) != inventory:
        raise ValueError('Archive changed during validation')
    if not exists:
        with seal_path.open('x', encoding='utf-8', newline='\n') as handle:
            handle.write(json.dumps(seal, ensure_ascii=False, sort_keys=True, indent=2) + '\n')
    return {'action': 'verified' if exists else 'sealed', 'run': str(run),
            'file_count': len(inventory), **counts}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True, help='Completed evaluation run directory.')
    parser.add_argument('--verify', action='store_true', help='Require and verify an existing seal.')
    args = parser.parse_args(argv)
    try:
        result = seal_run(args.run, verify=args.verify)
    except (ValueError, OSError) as exc:
        print(f'Archive seal failed: {exc}', file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
