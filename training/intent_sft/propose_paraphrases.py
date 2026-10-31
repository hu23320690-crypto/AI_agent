"""Ask a local model for candidate field paraphrases; a human curates the result.

The model sees only catalog names and example values from the demo CSV. Its
output is never used directly: candidates are reviewed into lexicon.py.

    python -B -m training.intent_sft.propose_paraphrases --model gemma4:12b --out <json>
"""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import urllib.request

PROMPT = """你在为扫地机器人月度使用报告整理“用户说法”。
字段名：{name}
该字段的取值示例：{values}

请写出12种普通用户在提问时可能用来指代【同一个指标】的中文说法，要求：
1. 不要包含字段名“{name}”原文；
2. 不要加入房间、部位、方向、模式等额外限定（那会变成另一个指标）；
3. 只写指标名词短语或简短问法，不写月份、不写“只列”“报告”等请求词；
4. 口语和书面语都要有。
只输出一个JSON字符串数组。"""


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', default='gemma4:12b')
    parser.add_argument('--host', default='http://127.0.0.1:11434')
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args(argv)
    from utils.records import load_records
    from utils.report_render import record_fields
    values = defaultdict(set)
    for record in load_records().values():
        for name, value in record_fields(record).items():
            values[name].add(value)
    result = {}
    for name in sorted(values):
        body = json.dumps({
            'model': args.model, 'stream': False, 'think': False, 'format': 'json',
            'options': {'temperature': 0.7, 'seed': 7},
            'messages': [{'role': 'user', 'content': PROMPT.format(
                name=name, values='、'.join(sorted(values[name])[:5]))}],
        }).encode('utf-8')
        request = urllib.request.Request(args.host + '/api/chat', data=body,
                                         headers={'Content-Type': 'application/json'})
        content = '[]'
        for _ in range(3):
            try:
                with urllib.request.urlopen(request, timeout=300) as response:
                    content = json.load(response)['message']['content']
                break
            except OSError:
                continue
        try:
            parsed = json.loads(content)
            candidates = parsed if isinstance(parsed, list) else next(
                value for value in parsed.values() if isinstance(value, list))
        except (ValueError, StopIteration):
            candidates = []
        result[name] = [text for text in dict.fromkeys(str(item).strip() for item in candidates)
                        if text and name not in text]
        print(name, result[name], flush=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
