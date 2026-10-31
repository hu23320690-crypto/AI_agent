"""Print a random sample of exported SFT rows for manual review.

    python -B -m training.intent_sft.inspect_data <train.json> [--seed 3] [--n 22]
"""
import argparse
import json
import random


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('path')
    parser.add_argument('--seed', type=int, default=3)
    parser.add_argument('--n', type=int, default=22)
    parser.add_argument('--category')
    args = parser.parse_args(argv)
    rows = json.load(open(args.path, encoding='utf-8'))
    if args.category:
        rows = [row for row in rows if row['category'] == args.category]
    random.Random(args.seed).shuffle(rows)
    for row in rows[:args.n]:
        user = json.loads(row['messages'][0]['content'])
        label = json.loads(row['messages'][1]['content'])
        fields = [(item['mention'], item['field']) for item in label['fields']]
        star = '*' if row['fictional'] else ''
        previous = (user['previous_intent'] or {}).get('target_month')
        print(f"[{row['category']}{star}] {user['query']}  | hist={user['history_queries']} "
              f"prev={previous} lookup={user['current_lookup_month']} today={user['today']}")
        print(f"    -> fields={fields} scope={label['scope']} "
              f"T={label['target_month']}({label['target_mention']},{label['target_anchor']}) "
              f"cmp={label['compare']} B={label['baseline_month']}({label['baseline_mention']}) "
              f"excl={label['excluded_fields']} kq={label['knowledge_question']!r} "
              f"unres={label['unresolved']}")


if __name__ == '__main__':
    main()
