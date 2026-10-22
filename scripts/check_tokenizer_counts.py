"""Compare a pinned offline counter with the local Ollama runner's own counts.

Unlike model.token_count this sends generation requests (raw prompt, one
predicted token) and reads prompt_eval_count, so run it explicitly after a
cache export, not at startup. Samples are fixed slices of prompts, knowledge
files, service records and frozen evaluation cases.
"""
import argparse
import json
import os
from pathlib import Path
import random
import sys
from types import SimpleNamespace

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from model.token_count import PINNED_MODELS, get_text_counter, load_cache_identity


def samples():
    rows = []
    for path in sorted((ROOT/'prompts').glob('*.txt')):
        rows.append(('prompts/'+path.name, path.read_text(encoding='utf-8')))
    for path in sorted((ROOT/'data').glob('*.txt')) + [ROOT/'data/external/records.csv']:
        text = path.read_text(encoding='utf-8-sig')
        rng = random.Random(path.name)
        for index in range(8):
            size = rng.choice((120, 400, 1200, 2400))
            start = rng.randrange(0, max(1, len(text)-size))
            rows.append((f'{path.relative_to(ROOT).as_posix()}#{index}', text[start:start+size]))
    for dataset in ('evaluation/cases.jsonl', 'evaluation/generalization_v1/cases.jsonl',
                    'evaluation/holdout_v2/cases.jsonl'):
        lines = [line for line in (ROOT/dataset).read_text(encoding='utf-8-sig').splitlines() if line.strip()]
        for index in random.Random(dataset).sample(range(len(lines)), 8):
            case = json.loads(lines[index])
            rows.append((f'{dataset}:{case.get("id", index)}', json.dumps(case, ensure_ascii=False, indent=2)))
    rows.append(('mixed-whitespace', 'Error E-101: 主刷缠绕 —— please   check\t\tthe brush.\r\n\n  🙂 50% off！　全角'))
    return rows


def ollama_count(client, model_name, text):
    response = client.post('/api/generate', json={
        'model': model_name, 'prompt': text, 'raw': True, 'stream': False, 'think': False,
        'options': {'num_predict': 1, 'num_ctx': 8192, 'temperature': 0}})
    response.raise_for_status()
    # Raw prompts still receive BOS when the GGUF asks for it.
    return response.json()['prompt_eval_count']


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--model', choices=sorted(PINNED_MODELS), required=True)
    parser.add_argument('--bos', type=int, default=None, help='runner tokens added to a raw prompt (default: 1 for gemma4, 0 for qwen)')
    parser.add_argument('--output', type=Path, default=None)
    args = parser.parse_args()
    bos = args.bos if args.bos is not None else (1 if args.model.startswith('gemma') else 0)
    identity = load_cache_identity(model_name=args.model)
    counter = get_text_counter(SimpleNamespace(model=args.model), expected_digest=identity and identity['model_digest'])
    if counter is None:
        raise SystemExit('tokenizer cache unavailable or not matching its manifest')
    host = os.environ.get('OLLAMA_HOST', 'http://127.0.0.1:11434')
    rows = []
    with httpx.Client(base_url=host, timeout=300, trust_env=False) as client:
        ollama_count(client, args.model, 'warm up')
        for label, text in samples():
            actual = ollama_count(client, args.model, text) - bos
            rows.append({'sample': label, 'chars': len(text), 'utf8_bytes': len(text.encode('utf-8')),
                         'ollama': actual, 'offline': counter.count(text)})
    mismatched = [row for row in rows if row['ollama'] != row['offline']]
    report = {'model': args.model, 'model_digest': counter.model_digest, 'method': counter.method,
              'samples': len(rows), 'exact_matches': len(rows)-len(mismatched),
              'ollama_total': sum(row['ollama'] for row in rows),
              'offline_total': sum(row['offline'] for row in rows),
              'utf8_bytes_total': sum(row['utf8_bytes'] for row in rows),
              'mismatched': mismatched, 'rows': rows}
    text = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding='utf-8')
    print(json.dumps({key: report[key] for key in report if key != 'rows'}, ensure_ascii=True))
    return 0 if not mismatched else 1


if __name__ == '__main__':
    raise SystemExit(main())
