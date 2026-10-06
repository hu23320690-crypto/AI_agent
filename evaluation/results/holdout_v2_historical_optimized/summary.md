# holdout_v2_historical_optimized 评测汇总

评分人：Codex 助手按题目与证据逐项复核，尚未经用户或领域专家复核。

这不是行业基准；文档内容的真实性与厂商适用性不在本轮验证范围。

## 完成情况

计划 40 个案例；执行 40；复核 40。

## 自动指标

{
  "statuses": {
    "ok": 40,
    "error": 0,
    "timeout": 0,
    "truncated": 0,
    "running": 0,
    "not_run": 0
  },
  "execution_outcomes": {
    "ok": 40,
    "error": 0,
    "timeout": 0,
    "truncated": 0,
    "running": 0,
    "unknown": 0,
    "not_run": 0
  },
  "retrieval": {
    "evaluated": 28,
    "planned": 28,
    "hit_counts": {
      "1": 20,
      "3": 27,
      "5": 28
    },
    "all_required_hit_counts": {
      "1": 17,
      "3": 25,
      "5": 27
    },
    "all_required_metrics_observed": 28,
    "policy_hit_counts": {
      "1": 17,
      "3": 25,
      "5": 27
    },
    "mrr_at_5": 0.8345238095238096,
    "mrr_definition": "Legacy MRR measures the first rank with any annotated anchor; it does not require all cross-passage evidence."
  },
  "knowledge_answers": {
    "planned": 28,
    "completed": 28,
    "reviewed": 28,
    "errors": 0,
    "execution_complete": 28,
    "not_run": 0,
    "unknown": 0,
    "full_correct": 24,
    "partial": 4,
    "incorrect": 0,
    "grounded": 28,
    "strict_pass": 24,
    "strict_fail": 4,
    "strict_pass_fraction_planned": 0.8571428571428571,
    "actual_input_evidence": {
      "observed": 28,
      "any_hit": 28,
      "all_required_hit": 27,
      "policy_hit": 27
    }
  },
  "unanswerable_answers": {
    "planned": 6,
    "completed": 6,
    "reviewed": 6,
    "errors": 0,
    "execution_complete": 6,
    "not_run": 0,
    "unknown": 0,
    "full_correct": 6,
    "partial": 0,
    "incorrect": 0,
    "grounded": 6,
    "strict_pass": 6,
    "strict_fail": 0,
    "strict_pass_fraction_planned": 1.0,
    "actual_input_evidence": {
      "observed": 0,
      "any_hit": 0,
      "all_required_hit": 0,
      "policy_hit": 0
    }
  },
  "agent": {
    "planned": 6,
    "completed": 6,
    "reviewed": 6,
    "task_pass": 0,
    "task_fail": 6,
    "unknown": 0,
    "tool_selection_pass": 4,
    "planned_real_turns": 11,
    "synthetic_seeded_turns": 128,
    "observed_model_requests": 22
  },
  "latency": {
    "retrieval": {
      "count": 34,
      "median_seconds": 0.24651214999994409,
      "p95_seconds": 0.3265314000000217
    },
    "rag_generation": {
      "count": 34,
      "median_seconds": 26.929464750000193,
      "p95_seconds": 47.30553229999987
    },
    "agent_turn": {
      "count": 11,
      "median_seconds": 24.015340800000104,
      "p95_seconds": 64.6723423999997
    },
    "case_wall_all_statuses": {
      "count": 40,
      "median_seconds": 34.05963614999996,
      "p95_seconds": 58.236355
    }
  },
  "model_usage": {
    "observed_requests": 56,
    "requests_by_status": {
      "ok": 56,
      "error": 0,
      "running": 0
    },
    "usage_records": 56,
    "input_tokens": 101087,
    "output_tokens": 92657,
    "request_input_message_counts": {
      "count": 56,
      "median_messages": 1.0,
      "p95_messages": 130
    },
    "note": "Includes actual summary/planner/RAG model calls. Synthetic seed history is input only, not model-generated interactions. Missing provider usage remains unmeasured."
  }
}

## 需改进案例

- V2K04：正确劝阻一次性拖布水洗复用，并说明变硬、掉毛、影响拖地效果及可能堵塞模组，这些均有实际输入扫拖一体条目支持；但题目问资料给出的理由，遗漏吸水性和清洁性按单次使用设计的原因，未完整覆盖所求理由。

- V2K13：执行完成，正确指出不是所有机型保证。冻结口径要求一般≤2cm及确认实际机型跨越范围；回答采用另一实际输入PDF条目的多数1.5–2cm、高端2.5cm，未明确给出所问一般≤2cm口径及先确认机型范围。题面只称扫地问答，实际输入同时含两份扫地问答的不同范围表述，存在资料范围歧义，按冻结必答点记部分正确，不视为编造。部分机型无法跨越≤2cm的表述由实际故障条目支持。

- V2K24：清水刻度、污水是否满、清理水位传感器、重新加水/倒污水后重启均正确；但题面还要求通用清理安全条件，未回答全程断开电源。实际输入有水位异常条目，却没有通用断电锚；拒绝补猜该部分忠实于本次资料，因此内容部分分、忠实度真。

- V2K28：已回答每层建图、专属扫拖参数、搬运前清理底部/传感器并校准；保持开机避免地图丢失也有实际PDF第60条支持。按冻结步骤点，未明确手动搬至对应楼层后启动及不可自动跨层，故主评分1。

- V2A01：执行完成，实际查询1006、2025-10，三项请求值2次/周、80%、1.0个/月都正确且受本轮工具输入支持，并标为演示记录。交付完整报告额外列户型、边刷寿命及效率对比，违反用户只列三项的明确范围限制，任务未通过。

- V2A02：两轮执行完成，均实际查询同一当前账号1007的正确月份，事实得到工具输入支持。最终交付为完整报告模板，首轮违反只要两项限制，第二轮虽给出95%与40㎡却遗漏相对11月增加2个百分点和2㎡；内部generated_final_content中的差值未交付，不能代替任务完成。

- V2A03：两轮完成；第一轮只说手机离线仍执行，虽用户已说明定时任务安排，却漏掉题面明确要求保留的机器人已连接WiFi前提，扩大了资料中的有条件结论。第二轮说明资料不足，没有保证机器人断WiFi仍执行，但不能弥补第一轮遗漏；整案任务不通过。

- V2A04：两轮derived执行均完成并实际检索；首轮已正确拒绝混装，按题面范围主评分完整，与当前版同题一致。第二轮保持污水仓滤网并给出正确周期及破损立即更换，却遗漏晾干后使用，整案task_pass仍false。忠实度仅评用户实际收到的turns.answer，内部未交付的材质/工作原理措辞不计入交付评分。

- V2A05：两轮derived执行完成。实际输入保留污水仓滤网、晾干提醒、资料不足不能确认不猜的初始要求，未显示生成摘要。首轮恢复对象与晾干，但未明确不能确认/不猜；第二轮不检索即宣称维护资料未说明周期与破损规则，未完成可查有据任务。合成填充历史不计为64次真实模型交互。

- V2A06：两轮执行完成。首轮准确恢复2025年9月及两个字段，目标和约束确实仍在实际输入；第二轮未查表便断言无记录，既无工具依据又与冻结1004的2025-09演示记录矛盾，未交付8次/月与88%，任务失败。没有将64对合成历史算为真实交互。