"""Compare raw Ollama outputs of intent models across request paths.

Diagnostic only. For one request it prints output tokens, prompt tokens and the
head of the answer for: the bare HTTP API (with and without the JSON schema)
and the production ChatOllama path built by agent.intent.llm_parser.

    python -B -m training.intent_sft.probe_decoding intent-sft-1.7b-r2 [--prompt ...]
"""
import argparse
from datetime import date
import json
import urllib.request

from agent.intent.llm_parser import build_messages, intent_model
from agent.intent.schema import INTENT_SCHEMA


def chat(model, messages, schema, host, options):
    body = {'model': model, 'stream': False, 'think': False, 'options': options,
            'messages': [{'role': role, 'content': message.content}
                         for role, message in zip(('system', 'user'), messages)]}
    if schema:
        body['format'] = INTENT_SCHEMA
    request = urllib.request.Request(host + '/api/chat', data=json.dumps(body).encode('utf-8'),
                                     headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


def show(label, content, metadata):
    print(f"{label}: out_tokens={metadata.get('eval_count')} prompt_tokens={metadata.get('prompt_eval_count')} "
          f"head={content[:70]!r}")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('models', nargs='+')
    parser.add_argument('--host', default='http://127.0.0.1:11434')
    parser.add_argument('--prompt', default='prompts/intent_parser_sft.txt')
    args = parser.parse_args(argv)
    messages = build_messages('2025-05只列覆盖率和滤网寿命。', history_queries=(), previous_intent=None,
                              known_fields=('覆盖率', '日均清扫', '滤网寿命'), today=date(2026, 10, 13),
                              fallback_month='2025-05', prompt=args.prompt)
    for name in args.models:
        for schema in (False, True):
            result = chat(name, messages, schema, args.host, {'temperature': 0})
            show(f'{name} api schema={schema}', result['message']['content'], result)
        for schema in (False, True):
            model = intent_model(name, schema)
            print(f'  production request fields: format={"schema" if model.format else None} '
                  f'reasoning={model.reasoning} num_ctx={model.num_ctx} num_predict={model.num_predict}')
            response = model.invoke(messages)
            show(f'{name} production schema={schema}', response.content, response.response_metadata)


if __name__ == '__main__':
    main()
