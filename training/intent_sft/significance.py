"""Paired exact McNemar test and bootstrap CI between registered runs (supplementary E1).

Reads only case ids, repeats and pass flags from each run's results.jsonl and
prints aggregate statistics; no per-case content is shown. A case counts as
correct when it passed in a majority of repeats. Holm adjusts the p values over
all comparisons given in one invocation.

    python -B -m training.intent_sft.significance BASE_RUN:SFT_RUN [A_RUN:B_RUN ...]
"""
import argparse
from collections import defaultdict
import json
from math import comb
from pathlib import Path
import random

ROOT = Path(__file__).resolve().parents[2]
SEED = 20261031
RESAMPLES = 10000


def majority_pass(run):
    """{case_id: bool} plus how many cases disagreed across repeats."""
    flags = defaultdict(list)
    path = ROOT / 'evaluation/results' / run / 'results.jsonl'
    with path.open(encoding='utf-8') as handle:
        for line in handle:
            row = json.loads(line)
            flags[row['case_id']].append(bool(row['score']['pass']))
    unstable = sum(len(set(values)) > 1 for values in flags.values())
    return {case: sum(values) * 2 > len(values) for case, values in flags.items()}, unstable


def exact_mcnemar(only_a, only_b):
    n = only_a + only_b
    if not n:
        return 1.0
    tail = sum(comb(n, k) for k in range(min(only_a, only_b) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def bootstrap_ci(a, b, rng):
    cases = sorted(a)
    diffs = []
    for _ in range(RESAMPLES):
        sample = [rng.choice(cases) for _ in cases]
        diffs.append(sum(b[c] - a[c] for c in sample) / len(sample))
    diffs.sort()
    return diffs[int(.025 * RESAMPLES)], diffs[int(.975 * RESAMPLES) - 1]


def holm(pvalues):
    order = sorted(range(len(pvalues)), key=pvalues.__getitem__)
    adjusted, running = [0.0] * len(pvalues), 0.0
    for rank, index in enumerate(order):
        running = max(running, min(1.0, (len(pvalues) - rank) * pvalues[index]))
        adjusted[index] = running
    return adjusted


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('pairs', nargs='+', help='A_RUN:B_RUN, difference reported as B - A')
    args = parser.parse_args(argv)
    rng = random.Random(SEED)
    rows = []
    for pair in args.pairs:
        name_a, name_b = pair.split(':')
        (a, unstable_a), (b, unstable_b) = majority_pass(name_a), majority_pass(name_b)
        if set(a) != set(b):
            raise SystemExit(f'{pair}: runs cover different cases')
        only_a = sum(a[c] and not b[c] for c in a)
        only_b = sum(b[c] and not a[c] for c in a)
        low, high = bootstrap_ci(a, b, rng)
        rows.append({'a': name_a, 'b': name_b, 'n': len(a), 'acc_a': sum(a.values()) / len(a),
                     'acc_b': sum(b.values()) / len(b), 'only_a': only_a, 'only_b': only_b,
                     'ci': (low, high), 'p': exact_mcnemar(only_a, only_b),
                     'unstable': (unstable_a, unstable_b)})
    for row, adjusted in zip(rows, holm([row['p'] for row in rows])):
        row['holm'] = adjusted
    print('| A | B | n | A 正确 | B 正确 | 差（B−A） | 95% CI | 仅 A 对 | 仅 B 对 | p | Holm p | 重复不一致 A/B |')
    print('| --- | --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | --- |')
    for r in rows:
        print(f"| {r['a']} | {r['b']} | {r['n']} | {r['acc_a']:.0%} | {r['acc_b']:.0%} | "
              f"{r['acc_b'] - r['acc_a']:+.0%} | [{r['ci'][0]:+.0%}, {r['ci'][1]:+.0%}] | "
              f"{r['only_a']} | {r['only_b']} | {r['p']:.4f} | {r['holm']:.4f} | "
              f"{r['unstable'][0]}/{r['unstable'][1]} |")


if __name__ == '__main__':
    main()
