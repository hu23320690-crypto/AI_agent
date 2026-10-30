"""Prepare an isolated, hash-verified historical business version for evaluation.

The evaluator is current; the business files are exactly the historical snapshot.
Indexes, models, logs and environments are never copied or downloaded.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]


def relative_path(name):
    value = PurePosixPath(name.replace('\\', '/'))
    if value.is_absolute() or '..' in value.parts or ':' in str(value):
        raise ValueError(f'Unsafe relative path in frozen manifest: {name}')
    return Path(value)


def checked_bytes(path, expected):
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError(f'Frozen hash mismatch: {path}')
    return data


def prepare_variant(project, target, dataset):
    project, target = Path(project).resolve(), Path(target).resolve()
    if target.exists():
        raise ValueError('Target already exists; preserve it and choose a new directory.')
    dataset = relative_path(dataset)
    frozen = project / 'evaluation/results/optimized_v1'
    manifest = json.loads((frozen / 'manifest.json').read_text(encoding='utf-8'))
    payload = {}
    for name, expected in manifest['code_sha256'].items():
        rel = relative_path(name)
        payload[rel] = checked_bytes(frozen / 'snapshot' / rel, expected)
    for name, expected in manifest['source_sha256'].items():
        rel = relative_path(name)
        payload[rel] = checked_bytes(project / rel, expected)
    for module in sorted((project / 'evaluation').glob('*.py')):
        payload[module.relative_to(project)] = module.read_bytes()
    review_rules = project / 'evaluation/SEMANTIC_REVIEW_V2.md'
    if review_rules.exists():
        payload[review_rules.relative_to(project)] = review_rules.read_bytes()
    for cases_path in {Path('evaluation/cases.jsonl'), Path('evaluation/holdout_v1/cases.jsonl'), dataset}:
        source_manifest = cases_path.parent / 'dataset_manifest.json'
        metadata = json.loads((project / source_manifest).read_text(encoding='utf-8'))
        payload[cases_path] = checked_bytes(project / cases_path, metadata['dataset_sha256'])
        payload[source_manifest] = (project / source_manifest).read_bytes()
        if metadata.get('scoring_sha256'):
            scoring = cases_path.parent / 'SCORING.md'
            payload[scoring] = checked_bytes(project / scoring, metadata['scoring_sha256'])
        for source, expected in metadata['files'].items():
            checked_bytes(project / relative_path(source), expected)
    identity = {
        'label': 'historical_optimized_v1',
        'origin_manifest': 'evaluation/results/optimized_v1/manifest.json',
        'historical_code_sha256': manifest['code_sha256'],
        'source_sha256': manifest['source_sha256'],
        'definition': 'Exact historical optimized-v1 business files; current evaluation observer; '
                      'separate initially empty index/cache/logs; no Runtime or context backport.'
    }
    payload[Path('variant_identity.json')] = json.dumps(identity, ensure_ascii=False, indent=2).encode('utf-8')
    target.mkdir(parents=True)
    for rel, data in payload.items():
        destination = target / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
    return {'target': str(target), 'business_files': len(manifest['code_sha256']),
            'sources': len(manifest['source_sha256']), 'observer_files': len(list((project / 'evaluation').glob('*.py'))),
            'dataset': dataset.as_posix(), 'index_copied': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', required=True, help='New experiment directory, never an existing checkout.')
    parser.add_argument('--dataset', default='evaluation/holdout_v2/cases.jsonl')
    args = parser.parse_args()
    print(json.dumps(prepare_variant(ROOT, args.target, args.dataset), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
