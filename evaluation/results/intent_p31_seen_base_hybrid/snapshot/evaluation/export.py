"""Export a readable audit trail from raw outputs and assistant reviews."""
import argparse
import json
from pathlib import Path
from evaluation.run import ROOT, read_rows
from evaluation.report import (load_run,validate_reviews,result_sha256,review_toolchain,
                               execution_outcome,turn_execution_outcome,semantic_outcome)

def export(run=None):
    run=Path(run or ROOT/"evaluation/results/baseline_v1")
    cases,rows,retrieval,review_rows,manifest=load_run(run)
    results,reviews=validate_reviews(cases,rows,review_rows,require_bound=manifest.get('identity_version',1)>=2)
    lines=["# 逐题评测记录",
           "本文件保留原始问题、参考答案、实际模型输入、系统回答和独立复核理由。尚未复核的项目保持未知；辅助评分尚未经用户或领域专家独立审核。",
           "原始截断状态保持原样。只有完整成功 RAG 工具输出确已交付、最后截断的 planner 未被交付且未出现截断异常时，派生执行结果才纠正为 ok；真实交付的 RAG 截断和当前版本拒绝截断的异常继续保持未知。",
           '后处理身份：```json\n'+json.dumps(review_toolchain(),ensure_ascii=False,indent=2)+'\n```']
    for case in cases:
        row=results.get(case["id"])
        review=reviews.get(case["id"])
        lines.append("## "+case["id"]+" · "+case["category"])
        if row is None:
            lines.append("尚未运行。")
            continue
        lines.append("运行状态："+row["status"])
        lines.append('派生执行结果：'+execution_outcome(row)+'（按实际交付答案检查截断，保留原始状态）')
        lines.append('派生语义判分：'+semantic_outcome(case,row,review)+'（执行不完整或缺少评分时为 unknown）')
        lines.append('原始结果 SHA256：'+result_sha256(row))
        if row.get('error'):
            lines.append('执行错误：'+row['error'])
        if case["kind"]=="agent":
            if row.get('seeded_turns'):
                lines.append(f"注入 {row['seeded_turns']} 对合成已完成历史；不计为真实模型交互。种子规则：\n\n```json\n"+
                    json.dumps(row.get('seed_history_spec'),ensure_ascii=False,indent=2)+'\n```')
            for i,turn in enumerate(row.get("turns",[]),1):
                expected=case['turns'][i-1] if i<=len(case['turns']) else {}
                lines.append(f"### 第{i}轮\n\n问题：{turn['query']}\n\n原始状态：{turn.get('status',row['status'])}\n\n派生执行结果：{turn_execution_outcome(turn,row)}\n\n系统回答：\n\n{turn.get('answer','未生成完整回答')}")
                lines.append('预期要求：```json\n'+json.dumps(expected,ensure_ascii=False,indent=2)+'\n```')
                lines.append("实际调用："+", ".join(c["name"] for c in turn.get("tool_calls",[])))
                lines.append("工具选择判定："+json.dumps(turn.get("tool_selection"),ensure_ascii=False))
                lines.append('实际上下文证据指标：'+json.dumps(turn.get('actual_input_evidence'),ensure_ascii=False))
                lines.append('摘要/Runtime：```json\n'+json.dumps({'summary':turn.get('summary'),'runtime':turn.get('runtime'),
                    'retained_messages':turn.get('retained_messages')},ensure_ascii=False,indent=2)+'\n```')
            if review:
                lines.append("任务通过："+str(review.get("task_pass"))+"；"+review.get('note',''))
        else:
            lines.append("问题："+case["query"])
            lines.append("参考答案："+case["reference_answer"])
            for evidence in case.get("evidence",[]):
                lines.append("来源："+evidence["source"]+" 第"+str(evidence["line_start"])+"行")
            lines.append("系统回答："+row.get("answer",row.get("error","没有生成回答")))
            lines.append('实际上下文证据指标：'+json.dumps(row.get('actual_input_evidence'),ensure_ascii=False))
            if review:
                lines.append(f"内容分：{review.get('answer_score')}/2；忠实于实际输入资料：{review.get('grounded')}。")
                lines.append("复核："+review.get('note',''))
        if not review:
            lines.append('语义判分：未知，尚未独立复核。')
        if row.get('model_requests'):
            lines.append('<details><summary>实际模型调用、输入与原始输出（包括预算裁剪后资料）</summary>\n\n```json\n'+
                json.dumps(row['model_requests'],ensure_ascii=False,indent=2)+'\n```\n\n</details>')
        lines.append("单案例进程墙钟时间："+str(round(row.get("wall_seconds",0),2))+"秒（不是纯推理时间）")
    (run/"audit.md").write_text("\n\n".join(lines),encoding="utf-8")

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--run",default="evaluation/results/baseline_v1")
    args=parser.parse_args()
    run=Path(args.run)
    export(run if run.is_absolute() else ROOT/run)

