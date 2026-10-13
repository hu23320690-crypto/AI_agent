import argparse
import json
import statistics
import hashlib
from pathlib import Path
from evaluation.run import ROOT, read_rows, dump, digest
from evaluation.metrics import percentile

def result_sha256(row):
    return hashlib.sha256(json.dumps(row,ensure_ascii=False,sort_keys=True,
        separators=(',',':')).encode('utf-8')).hexdigest()

def unique_records(rows, allowed, label):
    result={}
    for row in rows:
        key=row['id']
        if key not in allowed or key in result:
            raise ValueError(f'Unknown or duplicate {label} case ID: {key}')
        result[key]=row
    return result

def validate_reviews(cases, rows, reviews, require_bound=False):
    allowed={c['id'] for c in cases}
    results=unique_records(rows,allowed,'result')
    reviewed=unique_records(reviews,allowed,'review')
    for key,review in reviewed.items():
        score=review.get('answer_score')
        if score is not None and (type(score) is not int or score not in (0,1,2)):
            raise ValueError('Invalid answer_score: '+key)
        for name in ('grounded','task_pass'):
            if review.get(name) is not None and type(review[name]) is not bool:
                raise ValueError('Invalid '+name+': '+key)
        bound=review.get('result_sha256')
        if require_bound and not bound:
            raise ValueError('New semantic review must bind result_sha256: '+key)
        if bound and (key not in results or bound!=result_sha256(results[key])):
            raise ValueError('Semantic review/result hash mismatch: '+key)
    return results,reviewed

def execution_complete(case,row):
    if row is None or execution_outcome(row)!='ok':
        return False
    if case['kind']=='agent':
        turns=row.get('turns',[])
        return len(turns)==len(case.get('turns',[])) and all(
            turn_execution_outcome(t,row)=='ok' and isinstance(t.get('answer'),str) and bool(t['answer'].strip()) for t in turns)
    return isinstance(row.get('answer'),str) and bool(row['answer'].strip())

def clean_model_text(content):
    if not isinstance(content,str):
        return None
    return content.rsplit('</think>',1)[-1].strip()

def output_is_incomplete(answer,requests,tool_results=None):
    """Inspect the generation actually returned, not an optional summary failure.

    Historical code can return a length-truncated RAG tool result after a
    complete planner response. Exact successful tool output matching identifies
    that path; later complete retries supersede their earlier incomplete output.
    """
    answer=clean_model_text(answer)
    if not answer:
        return False
    outputs=[clean_model_text(t.get('content')) for t in (tool_results or [])
             if t.get('name')=='rag_summarize' and t.get('status','success')=='success']
    for index,request in enumerate(requests):
        if not request.get('incomplete') or not request.get('rag_contexts'):
            continue
        for generation in request.get('generations',[]):
            text=clean_model_text(generation.get('message',{}).get('content'))
            if not text:
                continue
            returned=(text==answer if tool_results is None else text in outputs and text in answer)
            superseded=any(not later.get('incomplete') and later.get('status')=='ok'
                and later.get('rag_contexts') and any(clean_model_text(g.get('message',{}).get('content'))==text
                for g in later.get('generations',[])) for later in requests[index+1:])
            if returned and not superseded:
                return True
    return False

def turn_execution_outcome(turn,row):
    raw=turn.get('status',row.get('status','unknown'))
    requests=row.get('model_requests',[])
    selected=[requests[i] for i in turn.get('model_request_indices',range(len(requests))) if 0<=i<len(requests)]
    if raw=='truncated' and unused_planner_truncation(turn,row,selected):
        return 'ok'
    if raw!='ok':
        return raw
    return 'truncated' if output_is_incomplete(turn.get('answer'),selected,turn.get('tool_results',[])) else 'ok'

def unused_planner_truncation(turn,row,requests):
    """Correct only the legacy worker's last-call flag for undelivered planning.

    The historical public entry point returns deduplicated successful RAG tool
    outputs. Require that exact delivered text and complete observed generations
    for every output; an exception or an actually returned partial stays unknown.
    """
    if turn.get('status')!='truncated' or not requests:
        return False
    if any(record.get('error') or record.get('error_type') for record in (turn,row)):
        return False
    if any(request.get('error_type')=='IncompleteModelOutput' for request in requests):
        return False
    last=requests[-1]
    if last.get('status')!='ok' or last.get('incomplete') is not True or last.get('rag_contexts'):
        return False
    answer=clean_model_text(turn.get('answer'))
    outputs=[clean_model_text(tool.get('content')) for tool in turn.get('tool_results',[])
             if tool.get('name')=='rag_summarize' and tool.get('status')=='success']
    if not outputs or any(not output for output in outputs):
        return False
    if answer!='\n\n'.join(dict.fromkeys(outputs)):
        return False
    if output_is_incomplete(answer,requests,turn.get('tool_results',[])):
        return False
    return all(any(request.get('status')=='ok' and request.get('incomplete') is False
        and request.get('rag_contexts') and any(
            clean_model_text(generation.get('message',{}).get('content'))==output
            for generation in request.get('generations',[])) for request in requests) for output in outputs)

def execution_outcome(row):
    raw=row.get('status','unknown')
    agent=row.get('mode')=='agent' or row.get('turns')
    if raw!='ok' and not (raw=='truncated' and agent):
        return row.get('status','unknown')
    if agent:
        if raw=='truncated' and (row.get('error') or row.get('error_type')):
            return raw
        outcomes=[turn_execution_outcome(t,row) for t in row.get('turns',[])]
        if raw=='truncated' and not any(t.get('status')=='truncated' for t in row.get('turns',[])):
            return raw
        return next((v for v in outcomes if v!='ok'),'ok')
    return 'truncated' if output_is_incomplete(row.get('answer'),row.get('model_requests',[])) else 'ok'

def semantic_outcome(case,row,review):
    if not execution_complete(case,row) or review is None:
        return 'unknown'
    if case['kind']=='agent':
        value=review.get('task_pass')
        return 'pass' if value is True else 'fail' if value is False else 'unknown'
    if review.get('answer_score') is None or review.get('grounded') is None:
        return 'unknown'
    return 'pass' if review['answer_score']==2 and review['grounded'] is True else 'fail'

def review_toolchain():
    rule=ROOT/'evaluation/SEMANTIC_REVIEW_V2.md'
    return {'rule_sha256':digest(rule) if rule.exists() else None,
        'analysis_sha256':{'evaluation/'+name:digest(ROOT/'evaluation'/name)
            for name in ('report.py','export.py','compare.py') if (ROOT/'evaluation'/name).exists()},
        'result_binding':'SHA256 of sorted-key compact UTF-8 JSON of final result row',
        'review_note':'Assistant-assisted review is independent from inference; user/domain-expert review is still recommended.'}

def load_run(run):
    run=Path(run)
    manifest=json.loads((run/'manifest.json').read_text(encoding='utf-8'))
    cases=read_rows(run/'cases.jsonl' if (run/'cases.jsonl').exists() else ROOT/'evaluation/cases.jsonl')
    rows=read_rows(run/'results.jsonl') if (run/'results.jsonl').exists() else []
    retrieval=json.loads((run/'retrieval.json').read_text(encoding='utf-8')) if (run/'retrieval.json').exists() else {}
    reviews=read_rows(run/'reviews.jsonl') if (run/'reviews.jsonl').exists() else []
    return cases,rows,retrieval,reviews,manifest

def latency(values):
    return {"count":len(values), "median_seconds":statistics.median(values) if values else None,
            "p95_seconds":percentile(values,0.95)}

def model_usage(rows):
    requests=[r for row in rows for r in row.get('model_requests',[])]
    message_counts=[len(r.get('messages',[])) for r in requests]
    usage=[]
    for request in requests:
        for generation in request.get('generations',[]):
            message=generation.get('message',{})
            metadata=message.get('response_metadata') or {}
            value=message.get('usage_metadata') or {}
            incoming=value.get('input_tokens',metadata.get('prompt_eval_count'))
            outgoing=value.get('output_tokens',metadata.get('eval_count'))
            if type(incoming) is int and type(outgoing) is int:
                usage.append((incoming,outgoing))
    return {'observed_requests':len(requests),'requests_by_status':{
        status:sum(r.get('status')==status for r in requests) for status in ('ok','error','running')},
        'usage_records':len(usage),'input_tokens':sum(i for i,o in usage),
        'output_tokens':sum(o for i,o in usage),
        'request_input_message_counts':{'count':len(message_counts),
            'median_messages':statistics.median(message_counts) if message_counts else None,
            'p95_messages':percentile(message_counts,0.95)},
        'note':'Includes actual summary/planner/RAG model calls. Synthetic seed history is input only, not model-generated interactions. Missing provider usage remains unmeasured.'}

def summarize(cases, rows, retrieval, reviews, require_bound=False):
    results,reviews=validate_reviews(cases,rows,reviews,require_bound)
    knowledge=[c for c in cases if c["kind"]=="knowledge"]
    negatives=[c for c in cases if c["kind"]=="unanswerable"]
    agents=[c for c in cases if c["kind"]=="agent"]
    summary={"planned":len(cases),"completed":len(results),
             "statuses":{status:sum(r["status"]==status for r in results.values()) for status in ("ok","error","timeout","truncated","running")},
             "reviewed":len(reviews),'review_binding':'required' if require_bound else 'legacy_optional'}
    summary['statuses']['not_run']=len(cases)-len(results)
    summary['execution_outcomes']={status:sum(execution_outcome(r)==status for r in results.values())
        for status in ('ok','error','timeout','truncated','running','unknown')}
    summary['execution_outcomes']['not_run']=len(cases)-len(results)
    assessed=[retrieval[c["id"]] for c in knowledge if c["id"] in retrieval and retrieval[c['id']].get('metrics') is not None]
    summary["retrieval"]={"evaluated":len(assessed),"planned":len(knowledge),
        "hit_counts":{str(k):sum(r["metrics"]["hit"][str(k)] for r in assessed) for k in (1,3,5)},
        "all_required_hit_counts":{str(k):sum(r['metrics'].get('all_required_hit',{}).get(str(k),False) for r in assessed) for k in (1,3,5)},
        'all_required_metrics_observed':sum('all_required_hit' in r['metrics'] for r in assessed),
        "policy_hit_counts":{str(k):sum(r['metrics'].get('policy_hit',r['metrics']['hit'])[str(k)] for r in assessed) for k in (1,3,5)},
        "mrr_at_5":statistics.mean(r["metrics"]["reciprocal_rank_at_5"] for r in assessed) if assessed else None,
        'mrr_definition':'Legacy MRR measures the first rank with any annotated anchor; it does not require all cross-passage evidence.'}
    def answer_summary(group,negative=False):
        present=[c for c in group if c["id"] in results]
        complete=[c for c in present if execution_complete(c,results[c['id']])]
        graded=[reviews[c["id"]] for c in complete if c["id"] in reviews]
        outcomes=[semantic_outcome(c,results.get(c['id']),reviews.get(c['id'])) for c in group]
        admitted=[results[c['id']].get('actual_input_evidence',{}).get('metrics') for c in present]
        admitted=[m for m in admitted if m is not None]
        errors=sum(execution_outcome(results[c["id"]])!='ok' for c in present)
        # Unreviewed successful answers remain unscored, never implicitly pass.
        scores=[r.get("answer_score") for r in graded]
        return {"planned":len(group),"completed":len(present),"reviewed":len(graded),
                "errors":errors,'execution_complete':len(complete),'not_run':len(group)-len(present),
                'unknown':outcomes.count('unknown'), "full_correct":sum(v==2 for v in scores),
                "partial":sum(v==1 for v in scores),"incorrect":sum(v==0 for v in scores),
                "grounded":sum(r.get("grounded") is True for r in graded),
                "strict_pass":outcomes.count('pass'),'strict_fail':outcomes.count('fail'),
                'strict_pass_fraction_planned':outcomes.count('pass')/len(group) if group else None,
                'actual_input_evidence':{'observed':len(admitted),
                    'any_hit':sum(m['any_hit'] for m in admitted),
                    'all_required_hit':sum(m['all_required_hit'] for m in admitted),
                    'policy_hit':sum(m['policy_hit'] for m in admitted)}}
    summary["knowledge_answers"]=answer_summary(knowledge)
    summary["unanswerable_answers"]=answer_summary(negatives,True)
    agent_rows=[results[c["id"]] for c in agents if c["id"] in results]
    agent_reviews=[reviews[c["id"]] for c in agents if c["id"] in reviews and execution_complete(c,results.get(c['id']))]
    agent_outcomes=[semantic_outcome(c,results.get(c['id']),reviews.get(c['id'])) for c in agents]
    summary["agent"]={"planned":len(agents),"completed":len(agent_rows),
        "reviewed":len(agent_reviews),"task_pass":agent_outcomes.count('pass'),
        'task_fail':agent_outcomes.count('fail'),'unknown':agent_outcomes.count('unknown'),
        "tool_selection_pass":sum(execution_complete(c,results.get(c['id']))
            and all(t.get('tool_selection',{}).get('pass') is True for t in results[c['id']]['turns']) for c in agents),
        'planned_real_turns':sum(len(c['turns']) for c in agents),
        'synthetic_seeded_turns':sum(r.get('seeded_turns',0) for r in agent_rows),
        'observed_model_requests':sum(len(r.get('model_requests',[])) for r in agent_rows)}
    summary["latency"]={
        "retrieval":latency([r["seconds"] for r in retrieval.values()]),
        "rag_generation":latency([r["inference_seconds"] for r in rows if r["mode"]=="qa" and execution_outcome(r)=='ok' and 'inference_seconds' in r]),
        "agent_turn":latency([t["seconds"] for r in agent_rows for t in r.get('turns',[]) if turn_execution_outcome(t,r)=='ok' and 'seconds' in t]),
        'case_wall_all_statuses':latency([r['wall_seconds'] for r in rows if 'wall_seconds' in r])}
    summary['model_usage']=model_usage(rows)
    summary["failures"]=[{"id":c["id"],"status":results.get(c["id"],{}).get("status","not_run"),
        "review":reviews.get(c["id"]),'execution_outcome':execution_outcome(results[c['id']]) if c['id'] in results else 'not_run',
        'outcome':semantic_outcome(c,results.get(c['id']),reviews.get(c['id']))} for c in cases
        if semantic_outcome(c,results.get(c['id']),reviews.get(c['id']))!='pass']
    return summary

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--run",default="evaluation/results/baseline_v1")
    args=parser.parse_args()
    run=ROOT/args.run
    cases,rows,retrieval,reviews,manifest=load_run(run)
    summary=summarize(cases,rows,retrieval,reviews,require_bound=manifest.get('identity_version',1)>=2)
    summary['review_toolchain']=review_toolchain()
    dump(run/"summary.json",summary)
    text=["# "+run.name+" 评测汇总",
          "评分人：Codex 助手按题目与证据逐项复核，尚未经用户或领域专家复核。",
          "这不是行业基准；文档内容的真实性与厂商适用性不在本轮验证范围。",
          "## 完成情况",f"计划 {summary['planned']} 个案例；执行 {summary['completed']}；复核 {summary['reviewed']}。",
          "## 自动指标",
          json.dumps({k:summary[k] for k in ('statuses','execution_outcomes','retrieval','knowledge_answers','unanswerable_answers','agent','latency','model_usage')},ensure_ascii=False,indent=2),
          "## 需改进案例"]
    for failure in summary["failures"]:
        text.append("- "+failure["id"]+"："+str((failure["review"] or {}).get("note",failure["status"])))
    (run/"summary.md").write_text("\n\n".join(text),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
