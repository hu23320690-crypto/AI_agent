# model_cmp_20261022_holdout_v2_gemma4_12b 评测汇总

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
      "3": 27,
      "5": 28
    },
    "all_required_hit_counts": {
      "1": 18,
      "3": 25,
      "5": 27
    },
    "all_required_metrics_observed": 28,
    "policy_hit_counts": {
      "1": 18,
      "3": 25,
      "5": 27
    },
    "mrr_at_5": 0.8523809523809524,
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
    "full_correct": 25,
    "partial": 3,
    "incorrect": 0,
    "grounded": 26,
    "strict_pass": 24,
    "strict_fail": 4,
    "strict_pass_fraction_planned": 0.8571428571428571,
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
      "median_seconds": 0.11047894999956043,
      "p95_seconds": 0.1466757999987749
    },
    "rag_generation": {
      "count": 34,
      "median_seconds": 2.331107800000609,
      "p95_seconds": 3.358463099999426
    },
    "agent_turn": {
      "count": 11,
      "median_seconds": 13.151704699999755,
      "p95_seconds": 22.031092699999135
    },
    "case_wall_all_statuses": {
      "count": 40,
      "median_seconds": 5.366662249999536,
      "p95_seconds": 30.811607300000105
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
    "input_tokens": 102153,
    "output_tokens": 7367,
    "request_input_message_counts": {
      "count": 56,
      "median_messages": 2.0,
      "p95_messages": 9
    },
    "note": "Includes actual summary/planner/RAG model calls. Synthetic seed history is input only, not model-generated interactions. Missing provider usage remains unmeasured."
  }
}

## 需改进案例

- V2K21：ok

- V2K24：ok

- V2K26：ok

- V2K28：ok