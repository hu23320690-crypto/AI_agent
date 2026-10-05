"""Export a readable audit trail from raw outputs and assistant reviews."""
import argparse
import json
from pathlib import Path
from evaluation.run import ROOT, read_rows

def export(run=None):
    run=Path(run or ROOT/"evaluation/results/baseline_v1")
    cases=read_rows(run/'cases.jsonl' if (run/'cases.jsonl').exists() else ROOT/"evaluation/cases.jsonl")
    results={r["id"]:r for r in read_rows(run/"results.jsonl")}
    reviews={r["id"]:r for r in read_rows(run/"reviews.jsonl")}
    lines=["# 逐题评测记录",
           "本文件保留原始问题、参考答案、系统回答和复核理由。语义评分由 Codex 助手完成，尚未经用户或领域专家独立复核。"]
    for case in cases:
        row=results.get(case["id"])
        review=reviews.get(case["id"])
        lines.append("## "+case["id"]+" · "+case["category"])
        if row is None:
            lines.append("尚未运行。")
            continue
        lines.append("运行状态："+row["status"])
        if case["kind"]=="agent":
            for i,turn in enumerate(row.get("turns",[]),1):
                lines.append(f"### 第{i}轮\n\n问题：{turn['query']}\n\n系统回答：\n\n{turn['answer']}")
                lines.append("实际调用："+", ".join(c["name"] for c in turn["tool_calls"]))
                lines.append("工具选择判定："+json.dumps(turn["tool_selection"],ensure_ascii=False))
            if review:
                lines.append("任务通过："+str(review.get("task_pass"))+"；"+review["note"])
        else:
            lines.append("问题："+case["query"])
            lines.append("参考答案："+case["reference_answer"])
            for evidence in case["evidence"]:
                lines.append("来源："+evidence["source"]+" 第"+str(evidence["line_start"])+"行")
            lines.append("系统回答："+row.get("answer",row.get("error","没有生成回答")))
            if review:
                lines.append(f"内容分：{review['answer_score']}/2；忠实于检索资料：{review['grounded']}。")
                lines.append("复核："+review["note"])
        lines.append("单案例进程墙钟时间："+str(round(row.get("wall_seconds",0),2))+"秒（不是纯推理时间）")
    (run/"audit.md").write_text("\n\n".join(lines),encoding="utf-8")

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--run",default="evaluation/results/baseline_v1")
    args=parser.parse_args()
    run=Path(args.run)
    export(run if run.is_absolute() else ROOT/run)

