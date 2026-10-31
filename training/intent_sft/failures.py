"""List failed cases of a dev run with gold, prediction and raw proposal.

Only for dev runs: the plan forbids reading per-case test results.

    python -B -m training.intent_sft.failures evaluation/results/<dev run>
"""
import argparse
import json
from pathlib import Path

KEYS = ('fields', 'unknown_fields', 'limited', 'full_report', 'target_month', 'compare',
        'comparison_month', 'knowledge_requested', 'unresolved_month')


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('run')
    args = parser.parse_args(argv)
    run = Path(args.run)
    manifest = json.loads((run / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('split') != 'dev':
        raise SystemExit('failure listing is limited to dev runs')
    cases = {}
    for line in (run / 'snapshot' / 'input_dataset.jsonl').read_text(encoding='utf-8-sig').splitlines():
        if line.strip():
            case = json.loads(line)
            cases[case['id']] = case
    for line in (run / 'results.jsonl').read_text(encoding='utf-8').splitlines():
        row = json.loads(line)
        if row['score']['pass']:
            continue
        case = cases[row['case_id']]
        gold, prediction = case['gold'], row.get('prediction') or {}
        diff = {key: (gold.get(key), prediction.get(key)) for key in KEYS
                if gold.get(key) != prediction.get(key)}
        print(f"{row['case_id']} [{case['category']}] status={row['status']} {row['score'].get('severity')}")
        print(f"  Q: {case['query']}")
        if case['history']:
            print(f"  history: {case['history']}")
        print(f"  gold vs pred: {diff}")
        proposal = row.get('raw_proposal') or {}
        print(f"  proposal fields: {[(f['mention'], f['field']) for f in proposal.get('fields', [])]}"
              f" scope={proposal.get('scope')} T={proposal.get('target_month')}"
              f" excl={proposal.get('excluded_fields')} conflicts={row['trace'].get('conflicts')}")


if __name__ == '__main__':
    main()
