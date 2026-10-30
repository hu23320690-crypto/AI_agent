"""Registered intent_eval batch for one model: warm up, then each mode in turn.

    python -B -m training.intent_sft.evaluate --model intent-sft-1.7b-r2 --split dev --repeat 1
    python -B -m training.intent_sft.evaluate --model qwen3:4b --split test --repeat 3 --p3-approved

A model other than the shared chat model is selected with AGENT_INTENT_MODEL
and uses the short SFT prompt; qwen3:4b keeps the original long prompt.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
DATASET = 'evaluation/intent_v1_r1/dev.jsonl'


def warm_up(model, host='http://127.0.0.1:11434'):
    """Load the model before timing; this request is not part of any run."""
    body = json.dumps({'model': model, 'prompt': 'ping', 'stream': False, 'think': False,
                       'options': {'num_predict': 1}}).encode('utf-8')
    request = urllib.request.Request(host + '/api/generate', data=body,
                                     headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=300) as response:
        response.read()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--model', required=True)
    parser.add_argument('--split', required=True, choices=('dev', 'test'))
    parser.add_argument('--repeat', type=int, default=1)
    parser.add_argument('--modes', default='llm_only,hybrid')
    parser.add_argument('--prefix', default='intent_sft')
    parser.add_argument('--p3-approved', action='store_true')
    parser.add_argument('--no-schema', action='store_true',
                        help='decode without the JSON schema grammar (V1 still parses strictly)')
    args = parser.parse_args(argv)
    dataset = DATASET if args.split == 'dev' else 'evaluation/intent_v1_r1/test.jsonl'
    env = dict(os.environ, PYTHONUTF8='1')
    for name in ('AGENT_INTENT_MODEL', 'AGENT_INTENT_PROMPT', 'AGENT_INTENT_SCHEMA'):
        env.pop(name, None)
    if args.model != 'qwen3:4b':
        env.update(AGENT_INTENT_MODEL=args.model, AGENT_INTENT_PROMPT='prompts/intent_parser_sft.txt')
    if args.no_schema:
        env['AGENT_INTENT_SCHEMA'] = '0'
    slug = args.model.replace(':', '_').replace('.', '') + ('_noschema' if args.no_schema else '')
    status = 0
    for mode in args.modes.split(','):
        warm_up(args.model)
        run = f'evaluation/results/{args.prefix}_{args.split}_{slug}_{mode}_x{args.repeat}'
        command = [sys.executable, '-B', '-m', 'evaluation.intent_eval', '--dataset', dataset,
                   '--split', args.split, '--mode', mode, '--repeat', str(args.repeat), '--run', run]
        if args.p3_approved:
            command.append('--p3-approved')
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True,
                                encoding='utf-8')
        print(result.stdout.strip().splitlines()[-1] if result.stdout.strip() else result.stderr[-2000:])
        status = status or result.returncode
    return status


if __name__ == '__main__':
    raise SystemExit(main())
