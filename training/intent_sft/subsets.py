"""Nested random train subsets of a generated dataset (supplementary E2).

    python -B -m training.intent_sft.subsets --data E:/envirment/intent_sft/data_r2 \
        --sizes 1000 2000 4000 --seed 20261101

writes <data>_n1000, <data>_n2000, ... next to the source. Each smaller subset is
contained in the larger ones; the val split is copied unchanged.
"""
import argparse
import hashlib
import json
from pathlib import Path
import random
import shutil


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def write_dataset(out, source, rows, indices, extra):
    """train.json from rows; val.json and dataset_info.json copied from source."""
    out.mkdir(parents=True, exist_ok=True)
    data = json.dumps(rows, ensure_ascii=False, indent=1).encode('utf-8')
    (out / 'train.json').write_bytes(data)
    for name in ('val.json', 'dataset_info.json'):
        shutil.copyfile(source / name, out / name)
    (out / 'indices.json').write_text(json.dumps(indices), encoding='utf-8')
    source_manifest = json.loads((source / 'manifest.json').read_text(encoding='utf-8'))
    manifest = {'source': source.name, 'source_sha256': source_manifest['sha256'],
                'splits': {'train': len(rows), 'val': source_manifest['splits']['val']},
                'sha256': {'train.json': sha256(data),
                           'val.json': sha256((out / 'val.json').read_bytes())}, **extra}
    (out / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                                       encoding='utf-8')
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--sizes', type=int, nargs='+', required=True)
    parser.add_argument('--seed', type=int, required=True)
    args = parser.parse_args(argv)
    rows = json.loads((args.data / 'train.json').read_text(encoding='utf-8'))
    order = random.Random(args.seed).sample(range(len(rows)), len(rows))
    for size in sorted(args.sizes):
        if not 0 < size < len(rows):
            raise SystemExit(f'size {size} must be below {len(rows)}')
        indices = sorted(order[:size])
        out = args.data.with_name(f'{args.data.name}_n{size}')
        manifest = write_dataset(out, args.data, [rows[i] for i in indices], indices,
                                 {'subset_seed': args.seed})
        print(out.name, manifest['splits'], manifest['sha256']['train.json'][:12])


if __name__ == '__main__':
    main()
