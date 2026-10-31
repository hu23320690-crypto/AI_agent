"""Catalog-shift probe (supplementary E5): field names never seen in training.

Generates resolver-verified samples whose catalogs use only the HELDOUT_* names,
then runs the real resolver with the chosen intent model and scores the nine
slots. Templates, months and every other feature stay in the training
distribution, so this isolates whether the model reads field_catalog; it is not
a new-domain result.

    python -B -m training.intent_sft.probe_catalog --model intent-sft-1.7b-r2 --no-schema
    python -B -m training.intent_sft.probe_catalog --model qwen3:4b
"""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import time

from training.intent_sft.evaluate import warm_up
from training.intent_sft.generate import generate

ROOT = Path(__file__).resolve().parents[2]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--model', required=True)
    parser.add_argument('--count', type=int, default=300)
    parser.add_argument('--seed', type=int, default=20261101)
    parser.add_argument('--modes', default='llm_only,hybrid')
    parser.add_argument('--no-schema', action='store_true')
    args = parser.parse_args(argv)
    from agent.intent.resolve import resolve_turn_intent
    from agent.runtime import RunContext
    from evaluation.intent_eval import adapt_result, nearest_rank, score_case
    for name in ('AGENT_INTENT_MODEL', 'AGENT_INTENT_PROMPT', 'AGENT_INTENT_SCHEMA'):
        os.environ.pop(name, None)
    if args.model != 'qwen3:4b':
        os.environ.update(AGENT_INTENT_MODEL=args.model,
                          AGENT_INTENT_PROMPT='prompts/intent_parser_sft.txt')
    if args.no_schema:
        os.environ['AGENT_INTENT_SCHEMA'] = '0'
    samples, _, _ = generate(args.count, args.seed, fictional_rate=1.0, heldout_catalog=True,
                             with_inputs=True)
    assert all(draft.fictional for _, draft, _ in samples)
    slug = args.model.replace(':', '_').replace('.', '') + ('_noschema' if args.no_schema else '')
    for mode in args.modes.split(','):
        warm_up(args.model)
        out = ROOT / f'evaluation/results/intent_sft_probe_catalog_{slug}_{mode}'
        out.mkdir(parents=True, exist_ok=True)
        rows, slots, categories, severities, latencies = [], Counter(), Counter(), Counter(), []
        for _, draft, _ in samples:
            started = time.perf_counter()
            result = resolve_turn_intent(
                draft.query, history_queries=tuple(draft.history),
                previous_intent=draft.previous, known_fields=tuple(draft.catalog),
                fallback_month=draft.fallback, today=draft.today, mode=mode, run=RunContext())
            latencies.append(time.perf_counter() - started)
            prediction = adapt_result(result, tuple(draft.catalog))
            score = score_case(prediction, draft.gold())
            slots.update(slot for slot, correct in score['slot_correct'].items() if correct)
            categories[draft.category, score['pass']] += 1
            severities[score['severity']] += 1
            rows.append({'category': draft.category, 'catalog': draft.catalog,
                         'query': draft.query, 'history': draft.history, 'gold': draft.gold(),
                         'prediction': prediction, 'pass': score['pass'],
                         'severity': score['severity'],
                         'fallback_reason': result.trace.get('fallback_reason'),
                         'conflicts': list(result.trace.get('conflicts', ()))})
        n = len(rows)
        summary = {
            'model': args.model, 'mode': mode, 'schema_constrained': not args.no_schema,
            'count': n, 'seed': args.seed, 'exact_accuracy': sum(r['pass'] for r in rows) / n,
            'slot_accuracy': {slot: slots[slot] / n for slot in score['slot_correct']},
            'by_category': {c: categories[c, True] / (categories[c, True] + categories[c, False])
                            for c in sorted({c for c, _ in categories})},
            'severity_counts': {str(k): v for k, v in severities.items()},
            'fallback_count': sum(bool(r['fallback_reason']) for r in rows),
            'latency_seconds': {'p50': nearest_rank(latencies, .5),
                                'p95': nearest_rank(latencies, .95)},
        }
        (out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                                          encoding='utf-8')
        with (out / 'cases.jsonl').open('w', encoding='utf-8') as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False, default=str) + '\n')
        print(json.dumps({'run': out.name, 'exact_accuracy': summary['exact_accuracy']}))


if __name__ == '__main__':
    main()
