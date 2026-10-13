# intent_agent_v1_r1_test_p3_hybrid 评测汇总

评分人：Codex 助手按题目与证据逐项复核，尚未经用户或领域专家复核。

这不是行业基准；文档内容的真实性与厂商适用性不在本轮验证范围。

## 完成情况

计划 12 个案例；执行 12；复核 12。

## 自动指标

{
  "statuses": {
    "ok": 12,
    "error": 0,
    "timeout": 0,
    "truncated": 0,
    "running": 0,
    "not_run": 0
  },
  "execution_outcomes": {
    "ok": 12,
    "error": 0,
    "timeout": 0,
    "truncated": 0,
    "running": 0,
    "unknown": 0,
    "not_run": 0
  },
  "retrieval": {
    "evaluated": 0,
    "planned": 0,
    "hit_counts": {
      "1": 0,
      "3": 0,
      "5": 0
    },
    "all_required_hit_counts": {
      "1": 0,
      "3": 0,
      "5": 0
    },
    "all_required_metrics_observed": 0,
    "policy_hit_counts": {
      "1": 0,
      "3": 0,
      "5": 0
    },
    "mrr_at_5": null,
    "mrr_definition": "Legacy MRR measures the first rank with any annotated anchor; it does not require all cross-passage evidence."
  },
  "knowledge_answers": {
    "planned": 0,
    "completed": 0,
    "reviewed": 0,
    "errors": 0,
    "execution_complete": 0,
    "not_run": 0,
    "unknown": 0,
    "full_correct": 0,
    "partial": 0,
    "incorrect": 0,
    "grounded": 0,
    "strict_pass": 0,
    "strict_fail": 0,
    "strict_pass_fraction_planned": null,
    "actual_input_evidence": {
      "observed": 0,
      "any_hit": 0,
      "all_required_hit": 0,
      "policy_hit": 0
    }
  },
  "unanswerable_answers": {
    "planned": 0,
    "completed": 0,
    "reviewed": 0,
    "errors": 0,
    "execution_complete": 0,
    "not_run": 0,
    "unknown": 0,
    "full_correct": 0,
    "partial": 0,
    "incorrect": 0,
    "grounded": 0,
    "strict_pass": 0,
    "strict_fail": 0,
    "strict_pass_fraction_planned": null,
    "actual_input_evidence": {
      "observed": 0,
      "any_hit": 0,
      "all_required_hit": 0,
      "policy_hit": 0
    }
  },
  "agent": {
    "planned": 12,
    "completed": 12,
    "reviewed": 12,
    "task_pass": 4,
    "task_fail": 8,
    "unknown": 0,
    "tool_selection_pass": 9,
    "planned_real_turns": 24,
    "synthetic_seeded_turns": 0,
    "observed_model_requests": 70
  },
  "latency": {
    "retrieval": {
      "count": 0,
      "median_seconds": null,
      "p95_seconds": null
    },
    "rag_generation": {
      "count": 0,
      "median_seconds": null,
      "p95_seconds": null
    },
    "agent_turn": {
      "count": 24,
      "median_seconds": 23.221462949997658,
      "p95_seconds": 70.53596480000124
    },
    "case_wall_all_statuses": {
      "count": 12,
      "median_seconds": 63.61347359999854,
      "p95_seconds": 98.36259189999691
    }
  },
  "model_usage": {
    "observed_requests": 70,
    "requests_by_status": {
      "ok": 70,
      "error": 0,
      "running": 0
    },
    "usage_records": 70,
    "input_tokens": 106595,
    "output_tokens": 49261,
    "request_input_message_counts": {
      "count": 70,
      "median_messages": 3.0,
      "p95_messages": 9
    },
    "note": "Includes actual summary/planner/RAG model calls. Synthetic seed history is input only, not model-generated interactions. Missing provider usage remains unmeasured."
  }
}

## 需改进案例

- IA001：全轮任务通过要求执行完整、每轮内容2、忠实度真且该轮必需要求成立。本样本至少一项未满足；具体原因见逐轮理由。

- IA002：全轮任务通过要求执行完整、每轮内容2、忠实度真且该轮必需要求成立。本样本至少一项未满足；具体原因见逐轮理由。

- IA004：全轮任务通过要求执行完整、每轮内容2、忠实度真且该轮必需要求成立。本样本至少一项未满足；具体原因见逐轮理由。

- IA005：全轮任务通过要求执行完整、每轮内容2、忠实度真且该轮必需要求成立。本样本至少一项未满足；具体原因见逐轮理由。

- IA006：全轮任务通过要求执行完整、每轮内容2、忠实度真且该轮必需要求成立。本样本至少一项未满足；具体原因见逐轮理由。

- IA007：全轮任务通过要求执行完整、每轮内容2、忠实度真且该轮必需要求成立。本样本至少一项未满足；具体原因见逐轮理由。

- IA010：全轮任务通过要求执行完整、每轮内容2、忠实度真且该轮必需要求成立。本样本至少一项未满足；具体原因见逐轮理由。

- IA012：全轮任务通过要求执行完整、每轮内容2、忠实度真且该轮必需要求成立。本样本至少一项未满足；具体原因见逐轮理由。