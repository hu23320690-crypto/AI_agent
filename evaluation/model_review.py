"""Label-hidden paired review for two chat models run on the same code and inputs.

evaluation.compare rejects differing model identities, which is the point of a
model comparison, so this keeps its other input checks and its result binding.

pack:    per case, both answers are shown as X/Y in a seeded random order; the
         label key is written to a separate directory the reviewer does not open.
unblind: after blind_scores.jsonl is locked, map labels back, write each run's
         reviews.jsonl bound to result_sha256, and write the paired comparison.
No model is called and no score is produced automatically.
"""
import argparse
import json
import random
from pathlib import Path

from evaluation.run import ROOT, digest, dump
from evaluation.report import (load_run, validate_reviews, semantic_outcome, result_sha256,
                               review_toolchain, execution_outcome, turn_execution_outcome)

CONTROLLED = ('dataset_sha256', 'dataset_manifest_sha256', 'source_sha256', 'dependencies', 'python',
              'execution_month', 'timeout_seconds', 'evaluation_sha256', 'temperature', 'ollama_host')
REVIEWER = ('Claude 助手语义复核（标签隐藏、配对呈现；非真人领域专家；同一助手参与了本次环境与计数器搭建，'
            '并在冒烟测试中见过 3 题输出，风格差异可能暴露模型）')


def resolve(value):
    path = Path(value)
    return path if path.is_absolute() else ROOT/path


def load_pair(left, right):
    lc, lr, _, _, lm = load_run(left)
    rc, rr, _, _, rm = load_run(right)
    changed = [key for key in CONTROLLED if lm.get(key) != rm.get(key)]
    if changed or lc != rc:
        raise ValueError('Runs differ in controlled inputs: ' + ', '.join(changed or ['cases']))
    code = {k for k in set(lm['code_sha256']) | set(rm['code_sha256'])
            if lm['code_sha256'].get(k) != rm['code_sha256'].get(k)}
    if code - {'config/rag.yml'}:
        raise ValueError('Runs differ in business code beyond config/rag.yml: ' + ', '.join(sorted(code)))
    left_rows = validate_reviews(lc, lr, [], True)[0]
    right_rows = validate_reviews(rc, rr, [], True)[0]
    return lc, left_rows, right_rows, lm, rm


def model_evidence(row):
    """Documents in the actual model input, plus program-validated citations."""
    blocks = []
    for request in row.get('model_requests', []):
        for context in request.get('rag_contexts') or []:
            try:
                docs = json.loads(context.get('formatted_context', '[]'))
            except (TypeError, ValueError):
                docs = []
            for doc in docs:
                blocks.append(f"[{doc.get('reference')}] {Path(str(doc.get('source', ''))).name}: {doc.get('content', '')}")
    cited = []
    if not row.get('model_requests'):
        for answer in row.get('rag_answers', []):
            for doc in answer.get('docs', []):
                cited.append(f"{Path(str(doc.get('metadata', {}).get('source', ''))).name}: {doc.get('text', '')}")
    return blocks, cited


def clip(text, limit):
    text = text if isinstance(text, str) else json.dumps(text, ensure_ascii=False)
    return text if len(text) <= limit else text[:limit] + f'…[截断，原长 {len(text)}]'


def tool_lines(turn):
    lines = []
    for call in turn.get('tool_calls', []):
        lines.append(f"  - 调用 `{call.get('name')}` {json.dumps(call.get('args', {}), ensure_ascii=False)}")
    for result in turn.get('tool_results', []):
        lines.append(f"  - 结果 `{result.get('name')}` ({result.get('status')}): {clip(result.get('content', ''), 1500)}")
    return lines or ['  - （无工具调用）']


def render_case(case, labeled):
    out = [f"## {case['id']}（{case['kind']}）"]
    if case['kind'] != 'agent':
        out += [f"**问题**：{case['query']}", f"**参考答案**：{case.get('reference_answer')}",
                f"**必答点**：{'；'.join(case.get('required_points', []))}"]
        if case.get('unanswerable_reason'):
            out.append(f"**资料不足原因**：{case['unanswerable_reason']}")
        answers = {label: row.get('answer') for label, row in labeled}
        if len(set(answers.values())) == 1:
            out.append(f"**X 与 Y 回答逐字相同**：{answers['X']}")
        for label, row in labeled:
            route = '模型生成' if row.get('model_requests') else '无模型调用（程序校验引用）'
            if len(set(answers.values())) > 1:
                out.append(f"**{label}**（{execution_outcome(row)}，{route}）：{row.get('answer')}")
            else:
                out.append(f"- {label}：{execution_outcome(row)}，{route}")
        return '\n\n'.join(out)
    out.append(f"用户 {case.get('user_id')}；故障注入：{bool(case.get('fault_injection'))}")
    for index, turn in enumerate(case['turns'], 1):
        out += [f"### 第 {index} 轮：{turn['query']}", f"参考：{turn.get('reference_answer')}",
                f"必答点：{'；'.join(turn.get('required_points', []))}",
                f"必需工具 {turn.get('required_tools')}；允许工具 {turn.get('allowed_tools')}"]
        for label, row in labeled:
            turns = row.get('turns', [])
            actual = turns[index-1] if index <= len(turns) else {}
            outcome = turn_execution_outcome(actual, row) if actual else 'not_run'
            out.append(f"**{label}**（{outcome}，工具选择 {actual.get('tool_selection', {}).get('pass')}）：")
            out += tool_lines(actual)
            summary = actual.get('summary')
            if summary:
                out.append(f"  - 上下文摘要：{clip(summary, 1200)}")
            out.append(f"  - 回答：{actual.get('answer')}")
    return '\n\n'.join(out)


def pack(args):
    left, right, out, key_dir = map(resolve, (args.left, args.right, args.output, args.key_dir))
    for path in (out, key_dir):
        if path.exists():
            raise ValueError(f'{path} exists; choose a new directory')
    cases, lrows, rrows, lm, rm = load_pair(left, right)
    rng = random.Random(args.seed)
    readable, evidence, blind, key = [f'# {args.title} 盲评包（X/Y 每题随机）'], [f'# {args.title} 实际模型输入证据'], [], []
    for case in cases:
        pair = [('left', lrows[case['id']]), ('right', rrows[case['id']])]
        rng.shuffle(pair)
        labeled = [(label, row) for label, (_, row) in zip('XY', pair)]
        readable.append(render_case(case, labeled))
        if case['kind'] != 'agent':
            per = {label: model_evidence(row) for label, row in labeled}
            evidence.append(f"## {case['id']}")
            if per['X'] == per['Y']:
                per = {'X/Y 相同': per['X']}
            for label, (blocks, cited) in per.items():
                evidence.append(f'### {label}：模型输入 {len(blocks)} 块' + ('' if blocks else '（无）'))
                evidence.extend(blocks)
                if cited:
                    evidence.append('程序校验引用（不计模型输入）：\n' + '\n'.join(cited))
        for label, (side, row) in zip('XY', pair):
            blind.append({'id': case['id'], 'label': label, 'kind': case['kind'], 'execution_status': execution_outcome(row)})
            key.append({'id': case['id'], 'label': label, 'side': side,
                        'run': (left if side == 'left' else right).name, 'result_sha256': result_sha256(row)})
    out.mkdir(parents=True)
    key_dir.mkdir(parents=True)
    (out/'blind_cases.md').write_text('\n\n'.join(readable) + '\n', encoding='utf-8')
    (out/'blind_evidence.md').write_text('\n\n'.join(evidence) + '\n', encoding='utf-8')
    (out/'blind_cases.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in blind), encoding='utf-8')
    (key_dir/'blind_key.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in key), encoding='utf-8')
    dump(out/'blind_manifest.json', {'seed': args.seed, 'cases': len(cases), 'samples': len(blind),
         'left_manifest_sha256': digest(left/'manifest.json'), 'right_manifest_sha256': digest(right/'manifest.json'),
         'blind_cases_md_sha256': digest(out/'blind_cases.md'), 'blind_evidence_sha256': digest(out/'blind_evidence.md'),
         'blind_key_sha256': digest(key_dir/'blind_key.jsonl'), 'key_location': 'separate directory, unopened until scores locked',
         'review_toolchain': review_toolchain()})
    print(json.dumps({'cases': len(cases), 'output': str(out), 'key_dir': str(key_dir)}, ensure_ascii=False))


def unblind(args):
    left, right, blind_dir, key_dir, out = map(resolve, (args.left, args.right, args.blind, args.key_dir, args.output))
    cases, lrows, rrows, lm, rm = load_pair(left, right)
    manifest = json.loads((blind_dir/'blind_manifest.json').read_text(encoding='utf-8'))
    scores_path = blind_dir/'blind_scores.jsonl'
    lock = {'blind_scores_sha256': digest(scores_path), 'blind_manifest_sha256': digest(blind_dir/'blind_manifest.json')}
    if digest(key_dir/'blind_key.jsonl') != manifest['blind_key_sha256']:
        raise ValueError('blind key changed since pack')
    key = {(r['id'], r['label']): r for r in map(json.loads, (key_dir/'blind_key.jsonl').read_text(encoding='utf-8').splitlines())}
    scores = [json.loads(line) for line in scores_path.read_text(encoding='utf-8').splitlines() if line.strip()]
    if sorted((s['id'], s['label']) for s in scores) != sorted(key):
        raise ValueError('blind scores must cover every id/label exactly once')
    reviews = {'left': [], 'right': []}
    for score in scores:
        entry = key[(score['id'], score['label'])]
        rows = lrows if entry['side'] == 'left' else rrows
        if result_sha256(rows[score['id']]) != entry['result_sha256']:
            raise ValueError('result changed since pack: ' + score['id'])
        review = {k: v for k, v in score.items() if k not in ('label',)}
        review.update(result_sha256=entry['result_sha256'], reviewer=REVIEWER, blind_label=score['label'],
                      review_method='按冻结 SCORING、题面、必答点、实际模型输入与工具结果逐题复核；X/Y 配对隐藏模型标签，评分锁定后揭盲。')
        reviews[entry['side']].append(review)
    for side, run in (('left', left), ('right', right)):
        rows = sorted(reviews[side], key=lambda r: [c['id'] for c in cases].index(r['id']))
        validate_reviews(cases, list((lrows if side == 'left' else rrows).values()), rows, True)
        (run/'reviews.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
    lreviews = {r['id']: r for r in reviews['left']}
    rreviews = {r['id']: r for r in reviews['right']}
    transitions = []
    for case in cases:
        before = semantic_outcome(case, lrows.get(case['id']), lreviews.get(case['id']))
        after = semantic_outcome(case, rrows.get(case['id']), rreviews.get(case['id']))
        transitions.append({'id': case['id'], 'kind': case['kind'], 'left': before, 'right': after,
                            'transition': 'unknown' if 'unknown' in (before, after) else
                            'right_only' if (before, after) == ('fail', 'pass') else
                            'left_only' if (before, after) == ('pass', 'fail') else
                            'both_pass' if after == 'pass' else 'both_fail'})
    groups = {kind: {'planned': sum(c['kind'] == kind for c in cases),
                     'left_pass': sum(t['kind'] == kind and t['left'] == 'pass' for t in transitions),
                     'right_pass': sum(t['kind'] == kind and t['right'] == 'pass' for t in transitions),
                     **{name: sum(t['kind'] == kind and t['transition'] == name for t in transitions)
                        for name in ('right_only', 'left_only', 'both_pass', 'both_fail', 'unknown')}}
              for kind in ('knowledge', 'unanswerable', 'agent')}
    out.mkdir(parents=True, exist_ok=True)
    dump(out/'comparison.json', {'left_run': left.name, 'right_run': right.name,
         'left_model': lm['model_identity']['chat'], 'right_model': rm['model_identity']['chat'],
         'score_lock': lock, 'groups': groups, 'transitions': transitions, 'review_toolchain': review_toolchain()})
    print(json.dumps(groups, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest='action', required=True)
    for name in ('pack', 'unblind'):
        command = sub.add_parser(name)
        command.add_argument('--left', required=True)
        command.add_argument('--right', required=True)
        command.add_argument('--key-dir', required=True)
        if name == 'pack':
            command.add_argument('--output', required=True)
            command.add_argument('--seed', type=int, required=True)
            command.add_argument('--title', default='模型对照')
        else:
            command.add_argument('--blind', required=True)
            command.add_argument('--output', required=True)
    args = parser.parse_args()
    pack(args) if args.action == 'pack' else unblind(args)


if __name__ == '__main__':
    main()
