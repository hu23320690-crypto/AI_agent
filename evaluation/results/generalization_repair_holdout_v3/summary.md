# generalization_repair_holdout_v3 评测汇总

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
    "full_correct": 23,
    "partial": 5,
    "incorrect": 0,
    "grounded": 23,
    "strict_pass": 22,
    "strict_fail": 6,
    "strict_pass_fraction_planned": 0.7857142857142857,
    "actual_input_evidence": {
      "observed": 28,
      "any_hit": 26,
      "all_required_hit": 25,
      "policy_hit": 25
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
    "task_pass": 6,
    "task_fail": 0,
    "unknown": 0,
    "tool_selection_pass": 6,
    "planned_real_turns": 11,
    "synthetic_seeded_turns": 128,
    "observed_model_requests": 25
  },
  "latency": {
    "retrieval": {
      "count": 34,
      "median_seconds": 0.33992109999996956,
      "p95_seconds": 0.46274469999980283
    },
    "rag_generation": {
      "count": 34,
      "median_seconds": 2.606233500000144,
      "p95_seconds": 6.213645000000042
    },
    "agent_turn": {
      "count": 11,
      "median_seconds": 19.33706159999997,
      "p95_seconds": 28.36991820000003
    },
    "case_wall_all_statuses": {
      "count": 40,
      "median_seconds": 7.517487650000021,
      "p95_seconds": 43.45455650000008
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
    "input_tokens": 102284,
    "output_tokens": 14633,
    "request_input_message_counts": {
      "count": 56,
      "median_messages": 2.0,
      "p95_messages": 9
    },
    "note": "Includes actual summary/planner/RAG model calls. Synthetic seed history is input only, not model-generated interactions. Missing provider usage remains unmeasured."
  }
}

## 需改进案例

- V2K05：不能混用、功能与规格不同、拖地滤网过滤污水、可能损坏设备几个主体要点正确，但未明确需要专用滤网，将资料的专用滤网要求替换为专用清洗液。另新增拖地滤网结构更密实、孔径更小、需专用清洗液，本次全部实际模型资料均未提供这些规格差异或清洁剂要求，属于无据具体扩展。

- V2K06：薄地毯可能无法识别和检查功能是否开启已回答，但遗漏确认具体机型支持及APP已开启这一所求前提。把另一故障条目“无法跨越地毯”的过厚和驱动轮打滑检查关联到“地毯增压无反应”，这些事实虽出现在本次输入，却没有资料支持该故障条件关联，不能因关键词存在就判忠实。

- V2K13：回答PDF多数机型1.5-2cm、高端2.5cm并保留不同机型能力差异及按实际机型适配，均有真实输入依据。答案也出现了“门槛高度≤2cm需选越障≥2cm机型”，不能说完全没有≤2cm；但该句是选购条件，未明确冻结TXT所问的一般跨越范围≤2cm。按既定原标注口径记部分并保留宽泛扫地问答题面、PDF范围与TXT一般值之间的歧义，不按输出修改金标。

- V2K17：主体完整保留并非每台支持、支持机型APP绘制路径及重点区域精准扫拖，来自本次实际输入扫拖问答87。但新增的具体设置方法将另一个问答2的先扫后拖流程与路线绘制混为一项功能，并新增宠物/儿童区域用途；本次输入未提供这种等同及场景依据，忠实度不通过。

- V2K24：水位异常的清水刻度/污水满检查、清水位传感器、加水倒污水后重启完整，但遗漏明确所求清理时全程断电。实际输入没有断电规则；新增“清理机器人前需确保拖布干净无硬化物”来自安装拖布前的卫生条件，移成清理整机前的通用安全要求，操作和范围不一致。

- V2K28：每层建图、各层专属参数与使用前清底部/传感器校准正确，保留搬运语境而未声称自动跨层，但漏搬至对应楼层后启动清扫。实际输入维护多楼层14、扫拖问答70和PDF60支持这些主步骤；新增APP手动切换地图及搬运时无积水泥沙避免影响传感器未获本次直接支持：PDF25只说明保存不同地图、传感器自动识别楼层，维护阳台13只讨论轮组泥沙。