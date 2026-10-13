# intent_p31_seen_generalization_v1_hybrid 评测汇总

评分人：Codex 助手按题目与证据逐项复核，尚未经用户或领域专家复核。

这不是行业基准；文档内容的真实性与厂商适用性不在本轮验证范围。

## 完成情况

计划 6 个案例；执行 6；复核 6。

## 自动指标

{
  "statuses": {
    "ok": 6,
    "error": 0,
    "timeout": 0,
    "truncated": 0,
    "running": 0,
    "not_run": 0
  },
  "execution_outcomes": {
    "ok": 6,
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
    "planned": 6,
    "completed": 6,
    "reviewed": 6,
    "task_pass": 4,
    "task_fail": 2,
    "unknown": 0,
    "tool_selection_pass": 5,
    "planned_real_turns": 11,
    "synthetic_seeded_turns": 64,
    "observed_model_requests": 31
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
      "count": 11,
      "median_seconds": 22.503412899997784,
      "p95_seconds": 52.647497599995404
    },
    "case_wall_all_statuses": {
      "count": 6,
      "median_seconds": 49.102840849998756,
      "p95_seconds": 81.1531313000014
    }
  },
  "model_usage": {
    "observed_requests": 31,
    "requests_by_status": {
      "ok": 31,
      "error": 0,
      "running": 0
    },
    "usage_records": 31,
    "input_tokens": 53334,
    "output_tokens": 15707,
    "request_input_message_counts": {
      "count": 31,
      "median_messages": 4,
      "p95_messages": 9
    },
    "note": "Includes actual summary/planner/RAG model calls. Synthetic seed history is input only, not model-generated interactions. Missing provider usage remains unmeasured."
  }
}

## 需改进案例

- G1A02：全轮任务通过要求执行完整、每轮内容2、忠实度真且该轮必需要求成立。本样本至少一项未满足；具体原因见逐轮理由。

- G1A05：全轮任务通过要求执行完整、每轮内容2、忠实度真且该轮必需要求成立。本样本至少一项未满足；具体原因见逐轮理由。