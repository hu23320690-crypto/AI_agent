"""Tabulate sealed intent_eval runs side by side (reads summary.json only).

    python -B -m training.intent_sft.report evaluation/results/<run> [...] [--slots]
"""
import argparse
import json
from pathlib import Path

SLOTS = ('fields', 'unknown_fields', 'requested_field_order', 'target_month', 'comparison_month',
         'compare', 'scope', 'knowledge_requested', 'unresolved_month')


def row(path):
    summary = json.loads((Path(path) / 'summary.json').read_text(encoding='utf-8'))
    manifest = json.loads((Path(path) / 'manifest.json').read_text(encoding='utf-8'))
    repeats = summary['repeats']
    exact = [item['exact_accuracy'] for item in repeats]
    dangerous = [item['severity_counts']['dangerous'] for item in repeats]
    aggregate = summary['aggregate']
    latency = aggregate['latency_seconds']['successful']
    return {
        'run': Path(path).name, 'model': manifest['model_identity']['intent']['name'],
        'mode': summary['mode'], 'repeat': summary['repeat'],
        'exact': f"{sum(exact) / len(exact):.1%} / {min(exact):.1%}",
        'dangerous': max(dangerous), 'severity': aggregate['severity_counts'],
        'failures': aggregate['execution_failure_count'],
        'p50': latency['p50'], 'p95': latency['p95'],
        'slots': aggregate['slot_accuracy'],
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('runs', nargs='+')
    parser.add_argument('--slots', action='store_true')
    args = parser.parse_args(argv)
    rows = [row(path) for path in args.runs]
    print('| 运行 | 模型 | 模式 | 完全正确（均值/最差） | 最大危险错误 | 执行失败 | p50 (s) | p95 (s) |')
    print('| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |')
    for item in rows:
        print(f"| {item['run']} | {item['model']} | {item['mode']} | {item['exact']} | "
              f"{item['dangerous']} | {item['failures']} | {item['p50']:.3f} | {item['p95']:.3f} |")
    if args.slots:
        print()
        print('| 运行 | ' + ' | '.join(SLOTS) + ' |')
        print('| --- |' + ' ---: |' * len(SLOTS))
        for item in rows:
            print(f"| {item['run']} | " + ' | '.join(f"{item['slots'][slot]:.1%}" for slot in SLOTS) + ' |')


if __name__ == '__main__':
    main()
