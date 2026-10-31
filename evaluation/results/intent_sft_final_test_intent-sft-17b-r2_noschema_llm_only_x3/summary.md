# Intent component evaluation: llm_only / test

Planned records: 300; repeats: 3.

| Repeat | Exact | Dangerous | Fallback | p50 all (s) | p95 all (s) | p95 successful (s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 94.00% | 5 | 0.00% | 0.6675 | 0.9063 | 0.9063 |
| 2 | 94.00% | 5 | 0.00% | 0.6421 | 0.7469 | 0.7469 |
| 3 | 94.00% | 5 | 0.00% | 0.6422 | 0.7393 | 0.7393 |

| Metric | Mean | Worst repeat |
| --- | ---: | ---: |
| exact_accuracy | 94.00% | 94.00% |
| dangerous | 5.0000 | 5.0000 |
| dangerous_count | 5.0000 | 5.0000 |
| fallback_count | 0.0000 | 0.0000 |
| fallback_rate | 0.00% | 0.00% |
| budget_skip_count | 0.0000 | 0.0000 |
| budget_skip_rate | 0.00% | 0.00% |
| extra_model_calls | 100.0000 | 100.0000 |
| latency_all_p50 | 0.6506 | 0.6675 |
| latency_all_p95 | 0.7975 | 0.9063 |
| latency_successful_p50 | 0.6506 | 0.6675 |
| latency_successful_p95 | 0.7975 | 0.9063 |
| slot_fields_accuracy | 99.00% | 99.00% |
| slot_unknown_fields_accuracy | 99.00% | 99.00% |
| slot_requested_field_order_accuracy | 99.00% | 99.00% |
| slot_target_month_accuracy | 97.00% | 97.00% |
| slot_comparison_month_accuracy | 99.00% | 99.00% |
| slot_compare_accuracy | 99.00% | 99.00% |
| slot_scope_accuracy | 100.00% | 100.00% |
| slot_knowledge_requested_accuracy | 100.00% | 100.00% |
| slot_unresolved_month_accuracy | 97.00% | 97.00% |
| wrong_scope | 0.0000 | 0.0000 |
| safe_fail | 0.0000 | 0.0000 |
| other_error | 1.0000 | 1.0000 |
| execution_failure_count | 0.0000 | 0.0000 |

All planned records remain in denominators. Slot rates measure final semantic selectors; overall passes additionally require execution success.

Severity: {"dangerous": 15, "wrong_scope": 0, "safe_fail": 0, "other_error": 3}

Execution states: {"ok": 300}

Conflict counts: {}

Budget skips: 0; extra model attempts: 300.

Latency: nearest-rank ceil(p*n), all states and successful execution states separately. Missing latency observations: 0.
