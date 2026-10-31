"""Token count of the training-format prompt, to compare with Ollama's prompt_eval_count.

Two steps because the request builder and the tokenizer live in different envs:

    .venv/Scripts/python -B -m training.intent_sft.check_template dump --out probe.json
    <training env python> -B -m training.intent_sft.check_template count \
        --messages probe.json --tokenizer E:/envirment/models/Qwen3-1.7B
"""
import argparse
from datetime import date
import json
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('dump', 'count'))
    parser.add_argument('--out', type=Path)
    parser.add_argument('--messages', type=Path)
    parser.add_argument('--tokenizer')
    args = parser.parse_args(argv)
    if args.action == 'dump':
        from agent.intent.llm_parser import build_messages
        system, user = build_messages(
            '2025-05只列覆盖率和滤网寿命。', history_queries=(), previous_intent=None,
            known_fields=('覆盖率', '日均清扫', '滤网寿命'), today=date(2026, 10, 13),
            fallback_month='2025-05', prompt='prompts/intent_parser_sft.txt')
        args.out.write_text(json.dumps([system.content, user.content], ensure_ascii=False),
                            encoding='utf-8')
        return
    from transformers import AutoTokenizer
    system, user = json.loads(args.messages.read_text(encoding='utf-8'))
    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer)
    # LLaMA-Factory qwen3_nothink: system, user, then the bare assistant prefix.
    text = (f'<|im_start|>system\n{system}<|im_end|>\n'
            f'<|im_start|>user\n{user}<|im_end|>\n<|im_start|>assistant\n')
    print('training-format prompt tokens:', len(tokenizer(text)['input_ids']))


if __name__ == '__main__':
    main()
