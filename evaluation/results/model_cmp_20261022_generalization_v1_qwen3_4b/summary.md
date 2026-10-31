# model_cmp_20261022_generalization_v1_qwen3_4b 评测汇总

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
      "1": 21,
      "3": 28,
      "5": 28
    },
    "all_required_hit_counts": {
      "1": 18,
      "3": 27,
      "5": 27
    },
    "all_required_metrics_observed": 28,
    "policy_hit_counts": {
      "1": 18,
      "3": 27,
      "5": 27
    },
    "mrr_at_5": 0.8630952380952381,
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
    "full_correct": 22,
    "partial": 6,
    "incorrect": 0,
    "grounded": 24,
    "strict_pass": 19,
    "strict_fail": 9,
    "strict_pass_fraction_planned": 0.6785714285714286,
    "actual_input_evidence": {
      "observed": 28,
      "any_hit": 25,
      "all_required_hit": 23,
      "policy_hit": 23
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
    "task_pass": 5,
    "task_fail": 1,
    "unknown": 0,
    "tool_selection_pass": 6,
    "planned_real_turns": 11,
    "synthetic_seeded_turns": 64,
    "observed_model_requests": 25
  },
  "latency": {
    "retrieval": {
      "count": 34,
      "median_seconds": 0.12035460000015519,
      "p95_seconds": 0.1758720000007088
    },
    "rag_generation": {
      "count": 34,
      "median_seconds": 1.4751937999999427,
      "p95_seconds": 3.5052276000005804
    },
    "agent_turn": {
      "count": 11,
      "median_seconds": 22.703017799999543,
      "p95_seconds": 55.89933329999985
    },
    "case_wall_all_statuses": {
      "count": 40,
      "median_seconds": 4.35993899999994,
      "p95_seconds": 65.3511712999998
    }
  },
  "model_usage": {
    "observed_requests": 55,
    "requests_by_status": {
      "ok": 55,
      "error": 0,
      "running": 0
    },
    "usage_records": 55,
    "input_tokens": 86663,
    "output_tokens": 18825,
    "request_input_message_counts": {
      "count": 55,
      "median_messages": 2,
      "p95_messages": 9
    },
    "note": "Includes actual summary/planner/RAG model calls. Synthetic seed history is input only, not model-generated interactions. Missing provider usage remains unmeasured."
  }
}

## 需改进案例

- G1K01：ok

- G1K11：ok

- G1K14：ok

- G1K16：ok

- G1K17：ok

- G1K19：ok

- G1K20：ok

- G1K27：ok

- G1K28：ok

- G1A05：ok