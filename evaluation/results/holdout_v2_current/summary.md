# holdout_v2_current 评测汇总

评分人：Codex 助手按题目与证据逐项复核，尚未经用户或领域专家复核。

这不是行业基准；文档内容的真实性与厂商适用性不在本轮验证范围。

## 完成情况

计划 40 个案例；执行 40；复核 40。

## 自动指标

{
  "statuses": {
    "ok": 38,
    "error": 0,
    "timeout": 0,
    "truncated": 2,
    "running": 0,
    "not_run": 0
  },
  "execution_outcomes": {
    "ok": 38,
    "error": 0,
    "timeout": 0,
    "truncated": 2,
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
    "reviewed": 27,
    "errors": 1,
    "execution_complete": 27,
    "not_run": 0,
    "unknown": 1,
    "full_correct": 21,
    "partial": 6,
    "incorrect": 0,
    "grounded": 26,
    "strict_pass": 21,
    "strict_fail": 6,
    "strict_pass_fraction_planned": 0.75,
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
    "reviewed": 5,
    "task_pass": 0,
    "task_fail": 5,
    "unknown": 1,
    "tool_selection_pass": 4,
    "planned_real_turns": 11,
    "synthetic_seeded_turns": 128,
    "observed_model_requests": 25
  },
  "latency": {
    "retrieval": {
      "count": 34,
      "median_seconds": 0.3484109500000159,
      "p95_seconds": 0.4694015000000036
    },
    "rag_generation": {
      "count": 33,
      "median_seconds": 29.697968000000003,
      "p95_seconds": 42.88319909999973
    },
    "agent_turn": {
      "count": 10,
      "median_seconds": 20.479059100000086,
      "p95_seconds": 89.22026549999987
    },
    "case_wall_all_statuses": {
      "count": 40,
      "median_seconds": 35.22901170000006,
      "p95_seconds": 111.48233300000015
    }
  },
  "model_usage": {
    "observed_requests": 59,
    "requests_by_status": {
      "ok": 59,
      "error": 0,
      "running": 0
    },
    "usage_records": 59,
    "input_tokens": 117675,
    "output_tokens": 98562,
    "request_input_message_counts": {
      "count": 59,
      "median_messages": 2,
      "p95_messages": 9
    },
    "note": "Includes actual summary/planner/RAG model calls. Synthetic seed history is input only, not model-generated interactions. Missing provider usage remains unmeasured."
  }
}

## 需改进案例

- V2K04：执行完成。正确否定水洗复用，并给出变硬、掉毛、影响效果和堵塞拖地模组风险，均有实际输入依据；题面问资料给出的理由，冻结必答的吸水性和清洁性按单次使用设计未回答，记部分正确。

- V2K13：正确说明不能作为所有机型保证，但回答采用另一扫地问答PDF的多数机型1.5-2cm、高端2.5cm，未明确冻结所问一般≤2cm口径，也遗漏先确认实际机型跨越范围。实际输入确有PDF数值以及非全机型条件相关资料，新增数值有据；因此内容部分正确、忠实度通过。题面明写扫地问答来源，但未指定文件名，保留一般值与多数机型范围之间的口径歧义。

- V2K19：每周轻刷、每1-2个月清水冲洗且不可揉搓、阴凉处晾干和3-6个月更换均正确且有实际输入维护保养HEPA条目支持；但题目要求完整日常清理安排，遗漏用软毛刷这一清理工具限定，故为部分完整。

- V2K21：断开充电座、每1-2个月补电正确，但将80%-90%与50%-70%并列为所问机器人补电目标，未给出明确适用值。实际输入维护保养第11条是长期存放机器人补电至80%-90%；另一条50%-70%是电池拆卸存放前电量。数字虽均在输入中，却把不同对象/阶段混成同条件的补电建议冲突，新增这个关联没有充分依据。该资料边界保留为争议。

- V2K22：派生execution_status为truncated且answer为null，没有完成交付的回答；即使实际输入含故障排除第30条，仍将内容与忠实度记未知，不能以检索证据或未完成生成计通过。

- V2K24：清洁仓清水刻度、污水满、水位传感器清理及加水/倒污水后重启均正确；未回答题面要求的全程断电安全条件。该安全锚未实际输入，拒绝补猜有据，内容部分分、忠实度真，与同题S058一致。

- V2K28：每层建图、专属参数、换楼层前清理底部与传感器并校准均正确，搬运保持开机也有实际PDF条目支持；遗漏冻结点中的手动搬至对应楼层后启动和不自动跨层，主评分1，与同题S059一致。

- V2A01：执行完成，实际查询1006、2025-10，三项请求值2次/周、80%、1.0个/月都正确且受本轮工具输入支持，并标为演示记录。交付完整报告额外列户型、边刷寿命及效率对比，违反用户只列三项的明确范围限制，任务未通过。

- V2A02：两轮derived执行完成并分别真实查询1007的2025-11和2025-12。最终交付模板准确给各月两项数据且有据，但首轮违反只要两个数的限制，第二轮漏两项增加量，故全轮任务失败。按turns.answer交付评分，不以内部生成文本替代。

- V2A03：第一轮完整且有据；第二轮实际RAG调用incomplete，出现IncompleteModelOutput，未提交第二轮答案。派生整案与第二轮均truncated，不能将未完成视为正确拒答，整案内容/忠实度/任务判分保持未知。

- V2A04：两轮执行完成且没有混淆成扫地滤网周期。第一轮明确不能装入拖地系统，实际第60条支持禁用及损坏风险；第二轮正确保持污水仓滤网、每周清水冲洗、6个月更换及破损立即更换，但遗漏冻结维护要求的晾干后再使用。第二轮实际输入有维护第11条和堵塞处理的晾干锚，属于答案遗漏，整案任务不通过。

- V2A05：两轮完成但均丢失污水仓滤网对象与种子约束。第一轮否认有具体维护部件，并把整理进度改成应先完成准备的提醒，未回忆晾干后再用和不足不猜；第二轮检索泛化为机器人维护，返回普通滤网/月洗3-6月更换等不同对象的信息，未答污水仓滤网每周冲洗、晾干、6个月更换与破损立即更换。摘要只保留整理文件主题，任务失败。

- V2A06：两轮均执行完成，但第一轮未回忆2025年9月与猫砂泼洒处理次数/自动回充成功率，第二轮再次要求补月份字段，未实际查1004的2025-09记录，未返回8次/月和88%。摘要仅保留整理文件主题，目标月份与字段在后续实际输入中丢失；无编造设备数值，但任务失败。