# agent_task_repair_delivery_v4 评测汇总

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
    "grounded": 24,
    "strict_pass": 23,
    "strict_fail": 5,
    "strict_pass_fraction_planned": 0.8214285714285714,
    "actual_input_evidence": {
      "observed": 28,
      "any_hit": 27,
      "all_required_hit": 26,
      "policy_hit": 26
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
    "grounded": 5,
    "strict_pass": 5,
    "strict_fail": 1,
    "strict_pass_fraction_planned": 0.8333333333333334,
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
      "median_seconds": 0.34134719999929075,
      "p95_seconds": 0.4809209999984887
    },
    "rag_generation": {
      "count": 34,
      "median_seconds": 2.5494070000022475,
      "p95_seconds": 3.811440900000889
    },
    "agent_turn": {
      "count": 11,
      "median_seconds": 18.320437599999423,
      "p95_seconds": 36.341715899998235
    },
    "case_wall_all_statuses": {
      "count": 40,
      "median_seconds": 7.312249349999547,
      "p95_seconds": 53.90383169999768
    }
  },
  "model_usage": {
    "observed_requests": 57,
    "requests_by_status": {
      "ok": 57,
      "error": 0,
      "running": 0
    },
    "usage_records": 57,
    "input_tokens": 107397,
    "output_tokens": 13409,
    "request_input_message_counts": {
      "count": 57,
      "median_messages": 2,
      "p95_messages": 9
    },
    "note": "Includes actual summary/planner/RAG model calls. Synthetic seed history is input only, not model-generated interactions. Missing provider usage remains unmeasured."
  }
}

## 需改进案例

- V2K01：ok

- V2K05：ok

- V2K13：ok

- V2K17：ok

- V2K24：ok

- V2N01：ok