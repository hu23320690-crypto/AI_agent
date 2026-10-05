import argparse
import json
import statistics
from pathlib import Path
from evaluation.run import ROOT, read_rows, dump
from evaluation.metrics import percentile

def latency(values):
    return {"count":len(values), "median_seconds":statistics.median(values) if values else None,
            "p95_seconds":percentile(values,0.95)}

def summarize(cases, rows, retrieval, reviews):
    results={r["id"]:r for r in rows}
    reviews={r["id"]:r for r in reviews}
    knowledge=[c for c in cases if c["kind"]=="knowledge"]
    negatives=[c for c in cases if c["kind"]=="unanswerable"]
    agents=[c for c in cases if c["kind"]=="agent"]
    summary={"planned":len(cases),"completed":len(results),
             "statuses":{status:sum(r["status"]==status for r in rows) for status in ("ok","error","timeout")},
             "reviewed":len(reviews)}
    assessed=[retrieval[c["id"]] for c in knowledge if c["id"] in retrieval]
    summary["retrieval"]={"evaluated":len(assessed),"planned":len(knowledge),
        "hit_counts":{str(k):sum(r["metrics"]["hit"][str(k)] for r in assessed) for k in (1,3,5)},
        "mrr_at_5":statistics.mean(r["metrics"]["reciprocal_rank_at_5"] for r in assessed) if assessed else None}
    def answer_summary(group,negative=False):
        present=[c for c in group if c["id"] in results]
        graded=[reviews[c["id"]] for c in present if c["id"] in reviews]
        errors=sum(results[c["id"]]["status"]!="ok" for c in present)
        # Unreviewed successful answers remain unscored, never implicitly pass.
        scores=[r["answer_score"] for r in graded]
        return {"planned":len(group),"completed":len(present),"reviewed":len(graded),
                "errors":errors, "full_correct":sum(v==2 for v in scores),
                "partial":sum(v==1 for v in scores),"incorrect":sum(v==0 for v in scores),
                "grounded":sum(r.get("grounded") is True for r in graded),
                "strict_pass":sum(r["answer_score"]==2 and r.get("grounded") is True for r in graded)}
    summary["knowledge_answers"]=answer_summary(knowledge)
    summary["unanswerable_answers"]=answer_summary(negatives,True)
    agent_rows=[results[c["id"]] for c in agents if c["id"] in results]
    agent_reviews=[reviews[c["id"]] for c in agents if c["id"] in reviews]
    summary["agent"]={"planned":len(agents),"completed":len(agent_rows),
        "reviewed":len(agent_reviews),"task_pass":sum(r.get("task_pass") is True for r in agent_reviews),
        "tool_selection_pass":sum(r["status"]=="ok" and len(r.get("turns",[]))==len(next(c for c in agents if c["id"]==r["id"])["turns"])
            and all(t["tool_selection"]["pass"] for t in r["turns"]) for r in agent_rows)}
    summary["latency"]={
        "retrieval":latency([r["seconds"] for r in retrieval.values()]),
        "rag_generation":latency([r["inference_seconds"] for r in rows if r["mode"]=="qa" and r["status"]=="ok"]),
        "agent_turn":latency([t["seconds"] for r in agent_rows if r["status"]=="ok" for t in r["turns"]])}
    summary["failures"]=[{"id":c["id"],"status":results.get(c["id"],{}).get("status","not_run"),
        "review":reviews.get(c["id"])} for c in cases if
        (c["id"] in results and results[c["id"]]["status"]!="ok")
        or (c["id"] in reviews and (reviews[c["id"]].get("task_pass") is False
            or reviews[c["id"]].get("answer_score",2)<2 or reviews[c["id"]].get("grounded") is False))]
    return summary

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--run",default="evaluation/results/baseline_v1")
    args=parser.parse_args()
    run=ROOT/args.run
    cases=read_rows(run/'cases.jsonl' if (run/'cases.jsonl').exists() else ROOT/"evaluation/cases.jsonl")
    rows=read_rows(run/"results.jsonl")
    retrieval=json.loads((run/"retrieval.json").read_text(encoding="utf-8"))
    reviews=read_rows(run/"reviews.jsonl") if (run/"reviews.jsonl").exists() else []
    summary=summarize(cases,rows,retrieval,reviews)
    dump(run/"summary.json",summary)
    text=["# "+run.name+" 评测汇总",
          "评分人：Codex 助手按题目与证据逐项复核，尚未经用户或领域专家复核。",
          "这不是行业基准；文档内容的真实性与厂商适用性不在本轮验证范围。",
          "## 完成情况",f"计划 {summary['planned']} 个案例；执行 {summary['completed']}；复核 {summary['reviewed']}。",
          "## 自动指标",
          json.dumps({k:summary[k] for k in ('statuses','retrieval','knowledge_answers','unanswerable_answers','agent','latency')},ensure_ascii=False,indent=2),
          "## 需改进案例"]
    for failure in summary["failures"]:
        text.append("- "+failure["id"]+"："+str((failure["review"] or {}).get("note",failure["status"])))
    (run/"summary.md").write_text("\n\n".join(text),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
