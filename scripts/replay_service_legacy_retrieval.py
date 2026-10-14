"""Replay both protected legacy caches without indexing or any model call."""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
if __package__ in (None,''):
    sys.path.insert(0,str(ROOT))


def replay(root=ROOT):
    from evaluation.retrieval_ablation import evaluate
    reports=[]
    for name in ('runtime_stage4_retrieval_dev','runtime_stage4_retrieval_holdout'):
        directory=Path(root)/'artifacts'/name
        cache=json.loads((directory/'candidate_cache.json').read_text(encoding='utf-8'))
        recorded=json.loads((directory/'ablation.json').read_text(encoding='utf-8'))
        actual=evaluate(cache)['results']
        expected=recorded['results']
        differences=[]
        if actual.keys()!=expected.keys():
            raise ValueError('legacy variant set differs')
        for variant,rows in actual.items():
            previous=expected[variant]
            if len(rows)!=len(previous):
                raise ValueError('legacy replay row count differs')
            for left,right in zip(rows,previous):
                encode=lambda docs:json.dumps(docs,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
                if left['id']!=right['id'] or encode(left['docs'])!=encode(right['docs']):
                    differences.append({'variant':variant,'id':left['id']})
        reports.append({'cache':name,'queries':len(cache['rows']),'variants':len(actual),
                        'comparisons':sum(len(rows) for rows in actual.values()),'differences':differences})
    return {'ok':all(not r['differences'] for r in reports),'reports':reports,
            'queries':sum(r['queries'] for r in reports),'variants':reports[0]['variants'],
            'comparisons':sum(r['comparisons'] for r in reports),
            'mismatches':sum(len(r['differences']) for r in reports)}


if __name__=='__main__':
    result=replay()
    print(json.dumps(result,ensure_ascii=False,indent=2))
    raise SystemExit(0 if result['ok'] else 1)
