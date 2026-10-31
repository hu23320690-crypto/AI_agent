"""Re-label a train subset with the prompted baseline (supplementary E4).

Each selected row's resolver inputs are rebuilt from its stored request, which
must render back to the identical request through build_messages. The row then
goes through the real resolver in llm_only mode with the shared qwen3:4b and
the long prompt; the model's raw proposal becomes the training label. The
matched control keeps the program labels of the same rows. A row the teacher
fails on (fallback or no proposal) is dropped from both.

    python -B -m training.intent_sft.teacher --data E:/envirment/intent_sft/data_r2 \
        --subset E:/envirment/intent_sft/data_r2_n2000

writes <data>_t2000 (teacher labels) and <data>_s2000 (program labels).
"""
import argparse
from collections import Counter
from datetime import date
import json
import os
from pathlib import Path
from unittest.mock import patch

from training.intent_sft.evaluate import warm_up
from training.intent_sft.subsets import write_dataset

SFT_PROMPT = 'prompts/intent_parser_sft.txt'


def row_inputs(example):
    """Resolver inputs that reproduce the stored request exactly."""
    from agent.intent.llm_parser import build_messages
    from utils.report_intent import ReportIntent
    request = json.loads(example['messages'][0]['content'])
    previous = request['previous_intent']
    if previous is not None:  # the same rebuild intent_eval applies to case files
        previous = ReportIntent(**dict(previous, fields=tuple(previous.get('fields', ()))))
    inputs = {'query': request['query'], 'history_queries': tuple(request['history_queries']),
              'previous_intent': previous,
              'known_fields': tuple(request['field_catalog'].split('\n')),
              'fallback_month': request['current_lookup_month'],
              'today': date.fromisoformat(request['today'])}
    system, user = build_messages(inputs['query'], history_queries=inputs['history_queries'],
                                  previous_intent=previous, known_fields=inputs['known_fields'],
                                  today=inputs['today'], fallback_month=inputs['fallback_month'],
                                  prompt=SFT_PROMPT)
    if (system.content, user.content) != (example['system'], example['messages'][0]['content']):
        raise SystemExit('a stored request does not round-trip through build_messages')
    return inputs


def teacher_label(keys, proposal):
    value = proposal.model_dump(mode='json')
    value['fields'] = [{'mention': item['mention'], 'field': item['field']}
                       for item in value['fields']]
    # Same key order as the program label, so only the content differs.
    return {key: value[key] for key in keys}


def ask_teacher(example):
    """(teacher label, nine-slot pass) or (None, failure reason)."""
    from agent.intent import resolve
    from agent.runtime import RunContext
    from evaluation.intent_eval import adapt_result, score_case
    inputs = row_inputs(example)
    seen = {}
    real = resolve.parse_turn_intent

    def recording(query, **kwargs):
        seen['proposal'] = real(query, **kwargs)
        return seen['proposal']

    with patch.object(resolve, 'parse_turn_intent', recording):
        result = resolve.resolve_turn_intent(**inputs, mode='llm_only', run=RunContext())
    reason = result.trace.get('fallback_reason')
    if reason or 'proposal' not in seen:
        return None, reason or 'no_proposal'
    score = score_case(adapt_result(result, inputs['known_fields']), example['gold'])
    keys = json.loads(example['messages'][1]['content'])
    return teacher_label(keys, seen['proposal']), score['pass']


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--subset', type=Path, required=True)
    args = parser.parse_args(argv)
    for name in ('AGENT_INTENT_MODEL', 'AGENT_INTENT_PROMPT', 'AGENT_INTENT_SCHEMA'):
        os.environ.pop(name, None)  # the shared qwen3:4b, long prompt, schema decoding
    train = json.loads((args.data / 'train.json').read_text(encoding='utf-8'))
    indices = json.loads((args.subset / 'indices.json').read_text(encoding='utf-8'))
    for index in indices:  # fail fast, before any model call
        row_inputs(train[index])
    warm_up('qwen3:4b')
    kept, teacher_rows, program_rows = [], [], []
    failures, passes, exact = Counter(), Counter(), Counter()
    for step, index in enumerate(indices, 1):
        example = train[index]
        label, outcome = ask_teacher(example)
        if label is None:
            failures[outcome] += 1
        else:
            kept.append(index)
            program_rows.append(example)
            answer = json.dumps(label, ensure_ascii=False, separators=(',', ':'))
            teacher_rows.append(dict(example, messages=[example['messages'][0],
                                                        {'role': 'assistant', 'content': answer}]))
            passes[example['category'], outcome] += 1
            exact[label == json.loads(example['messages'][1]['content'])] += 1
        if step % 200 == 0:
            print(f'{step}/{len(indices)} kept={len(kept)} failures={sum(failures.values())}',
                  flush=True)
    categories = sorted({category for category, _ in passes})
    stats = {
        'teacher': 'qwen3:4b + prompts/intent_parser.txt, llm_only, schema decoding',
        'selected': len(indices), 'kept': len(kept), 'failures': dict(failures),
        'teacher_nine_slot_pass': sum(passes[c, True] for c in categories) / len(kept),
        'teacher_exact_label_match': exact[True] / len(kept),
        'teacher_pass_by_category': {
            c: passes[c, True] / (passes[c, True] + passes[c, False]) for c in categories},
    }
    size = len(indices)
    for tag, rows in (('t', teacher_rows), ('s', program_rows)):
        out = args.data.with_name(f'{args.data.name}_{tag}{size}')
        manifest = write_dataset(out, args.data, rows, kept,
                                 {'subset': args.subset.name, 'labels': 'teacher' if tag == 't'
                                  else 'program', **stats})
        print(out.name, manifest['splits'], manifest['sha256']['train.json'][:12])
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == '__main__':
    main()
