"""Same-case paired comparison and label-hidden auxiliary review exports.

This does not call a model, create semantic scores, or change reference answers.
"""
import argparse
import json
import random
from pathlib import Path
from evaluation.run import ROOT, dump, digest
from evaluation.report import (load_run, summarize, validate_reviews, semantic_outcome,
                               result_sha256, review_toolchain, latency, execution_outcome,
                               turn_execution_outcome)


def comparable(left, right):
    """Allow intentional business/config changes; reject changed test inputs."""
    keys=('dataset_sha256','dataset_manifest_sha256','source_sha256','model_identity','dependencies','python','execution_month',
          'timeout_seconds','evaluation_sha256','temperature','ollama_host')
    changed=[k for k in keys if left.get(k)!=right.get(k)]
    if changed:
        raise ValueError('Cannot compare changed controlled inputs: '+', '.join(changed))
    if left.get('identity_version',1)<2 or right.get('identity_version',1)<2:
        raise ValueError('Paired v2 comparison requires captured identity_version >= 2')


def compare_cases(cases, left_rows, right_rows, left_reviews, right_reviews):
    left,lreviews=validate_reviews(cases,left_rows,left_reviews,True)
    right,rreviews=validate_reviews(cases,right_rows,right_reviews,True)
    transitions=[]
    for case in cases:
        key=case['id']
        before=semantic_outcome(case,left.get(key),lreviews.get(key))
        after=semantic_outcome(case,right.get(key),rreviews.get(key))
        transition=('unknown' if 'unknown' in (before,after) else
                    'improved' if (before,after)==('fail','pass') else
                    'regressed' if (before,after)==('pass','fail') else
                    'stable_pass' if after=='pass' else 'stable_fail')
        transitions.append({'id':key,'kind':case['kind'],'before':before,'after':after,
            'transition':transition,'before_status':left.get(key,{}).get('status','not_run'),
            'after_status':right.get(key,{}).get('status','not_run'),
            'before_execution_outcome':execution_outcome(left[key]) if key in left else 'not_run',
            'after_execution_outcome':execution_outcome(right[key]) if key in right else 'not_run',
            'before_result_sha256':result_sha256(left[key]) if key in left else None,
            'after_result_sha256':result_sha256(right[key]) if key in right else None})
    return transitions


def blind_bundle(cases, left_rows, right_rows, seed=20261006):
    left=validate_reviews(cases,left_rows,[],True)[0]
    right=validate_reviews(cases,right_rows,[],True)[0]
    candidates=[(side,case,rows[case['id']]) for side,rows in (('before',left),('after',right))
                for case in cases if case['id'] in rows]
    random.Random(seed).shuffle(candidates)
    bundle,key=[],[]
    for index,(side,case,row) in enumerate(candidates,1):
        sample=f'S{index:03d}'
        bundle.append({'sample_id':sample,'case':case,'raw_status':row['status'],'execution_status':execution_outcome(row),
            'answer':row.get('answer'),'turns':row.get('turns',[]),
            'turn_execution_outcomes':[{'turn_index':index,'raw_status':turn.get('status',row['status']),
                'execution_status':turn_execution_outcome(turn,row)}
                for index,turn in enumerate(row.get('turns',[]),1)],
            'model_requests':row.get('model_requests',[]),
            'tool_results':row.get('tool_results',[]),
            'actual_input_evidence':row.get('actual_input_evidence'),
            'seeded_history':row.get('seeded_history',[]),
            'review_instruction':'Score against frozen references and actual inputs; do not infer pass from execution or keyword hits.'})
        key.append({'sample_id':sample,'variant':side,'id':case['id'],
                    'result_sha256':result_sha256(row)})
    return bundle,key


def write_jsonl(path,rows):
    Path(path).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before',required=True)
    parser.add_argument('--after',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--blind-seed',type=int,default=20261006)
    args=parser.parse_args()
    paths=[Path(v) if Path(v).is_absolute() else ROOT/v for v in (args.before,args.after,args.output)]
    before,after,output=paths
    output.mkdir(parents=True,exist_ok=True)
    lc,lr,lt,lv,lm=load_run(before)
    rc,rr,rt,rv,rm=load_run(after)
    comparable(lm,rm)
    if lc!=rc or digest(before/'cases.jsonl')!=lm['dataset_sha256'] or digest(after/'cases.jsonl')!=rm['dataset_sha256']:
        raise ValueError('Stored cases differ from manifest or each other')
    transitions=compare_cases(lc,lr,rr,lv,rv)
    lsummary=summarize(lc,lr,lt,lv,True)
    rsummary=summarize(rc,rr,rt,rv,True)
    groups={kind:{'planned':sum(c['kind']==kind for c in lc),
        **{name:sum(t['kind']==kind and t['transition']==name for t in transitions)
           for name in ('improved','regressed','stable_pass','stable_fail','unknown')}}
        for kind in ('knowledge','unanswerable','agent')}
    result={'before_run':before.name,'after_run':after.name,
        'dataset_sha256':lm['dataset_sha256'],'before_manifest_sha256':digest(before/'manifest.json'),
        'after_manifest_sha256':digest(after/'manifest.json'),'review_toolchain':review_toolchain(),
        'groups':groups,'before':lsummary,'after':rsummary,'transitions':transitions,
        'latency_note':'Sequential local runs; successful QA/turn latency and all-status wall time are separate. No statistical significance or isolated algorithm attribution is claimed.',
        'blinding_note':'Only labels/order are hidden. Request prompts may reveal version behavior; this is assistant-assisted auxiliary review, not independent human blind evaluation.'}
    dump(output/'comparison.json',result)
    bundle,key=blind_bundle(lc,lr,rr,args.blind_seed)
    write_jsonl(output/'blind_cases.jsonl',bundle)
    write_jsonl(output/'blind_key.jsonl',key)
    dump(output/'blind_manifest.json',{'seed':args.blind_seed,'samples':len(bundle),
        'blind_cases_sha256':digest(output/'blind_cases.jsonl'),
        'blind_key_sha256':digest(output/'blind_key.jsonl'),'review_toolchain':review_toolchain()})
    table=['| 案例 | 前版 | 后版 | 对照 |','| --- | --- | --- | --- |']
    table.extend(f"| {t['id']} | {t['before']} | {t['after']} | {t['transition']} |" for t in transitions)
    lines=['# 同题版本对照',f'前版：{before.name}；后版：{after.name}。',
        '未评分、缺失、报错、超时与截断保持未知，计划分母不变。',
        '```json\n'+json.dumps(groups,ensure_ascii=False,indent=2)+'\n```',
        '\n'.join(table)]
    lines.extend([result['latency_note'],result['blinding_note']])
    (output/'comparison.md').write_text('\n\n'.join(lines),encoding='utf-8')
    print(json.dumps(groups,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
