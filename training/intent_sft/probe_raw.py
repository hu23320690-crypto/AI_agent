"""Send the exact training-format prompt with Ollama raw mode (no template).

Diagnostic for template parity: compares raw-mode prompt tokens and output with
the templated /api/chat request for the same messages.

    python -B -m training.intent_sft.probe_raw intent-sft-1.7b-r2
"""
import argparse
from datetime import date
import json
import urllib.request

from agent.intent.llm_parser import build_messages


def post(host, path, body):
    request = urllib.request.Request(host + path, data=json.dumps(body).encode('utf-8'),
                                     headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('model')
    parser.add_argument('--host', default='http://127.0.0.1:11434')
    args = parser.parse_args(argv)
    system, user = build_messages('2025-05只列覆盖率和滤网寿命。', history_queries=(), previous_intent=None,
                                  known_fields=('覆盖率', '日均清扫', '滤网寿命'), today=date(2026, 10, 13),
                                  fallback_month='2025-05', prompt='prompts/intent_parser_sft.txt')
    text = (f'<|im_start|>system\n{system.content}<|im_end|>\n'
            f'<|im_start|>user\n{user.content}<|im_end|>\n<|im_start|>assistant\n')
    raw = post(args.host, '/api/generate', {'model': args.model, 'prompt': text, 'raw': True,
                                            'stream': False, 'options': {'temperature': 0}})
    print(f"raw: prompt_tokens={raw.get('prompt_eval_count')} out={raw['response'][:80]!r}")
    for think in (None, False):
        body = {'model': args.model, 'stream': False, 'options': {'temperature': 0},
                'messages': [{'role': 'system', 'content': system.content},
                             {'role': 'user', 'content': user.content}]}
        if think is not None:
            body['think'] = think
        chat = post(args.host, '/api/chat', body)
        print(f"chat think={think}: prompt_tokens={chat.get('prompt_eval_count')} "
              f"out={chat['message']['content'][:80]!r}")


if __name__ == '__main__':
    main()
