# Intent component evaluation: llm_only / test

Planned records: 300; repeats: 3.

| Repeat | Exact | Dangerous | Fallback | p50 all (s) | p95 all (s) | p95 successful (s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 88.00% | 11 | 0.00% | 0.6281 | 0.8616 | 0.8616 |
| 2 | 88.00% | 11 | 0.00% | 0.6225 | 0.7173 | 0.7173 |
| 3 | 88.00% | 11 | 0.00% | 0.6091 | 0.7217 | 0.7217 |

| Metric | Mean | Worst repeat |
| --- | ---: | ---: |
| exact_accuracy | 88.00% | 88.00% |
| dangerous | 11.0000 | 11.0000 |
| dangerous_count | 11.0000 | 11.0000 |
| fallback_count | 0.0000 | 0.0000 |
| fallback_rate | 0.00% | 0.00% |
| budget_skip_count | 0.0000 | 0.0000 |
| budget_skip_rate | 0.00% | 0.00% |
| extra_model_calls | 100.0000 | 100.0000 |
| latency_all_p50 | 0.6199 | 0.6281 |
| latency_all_p95 | 0.7669 | 0.8616 |
| latency_successful_p50 | 0.6199 | 0.6281 |
| latency_successful_p95 | 0.7669 | 0.8616 |
| slot_fields_accuracy | 95.00% | 95.00% |
| slot_unknown_fields_accuracy | 95.00% | 95.00% |
| slot_requested_field_order_accuracy | 95.00% | 95.00% |
| slot_target_month_accuracy | 95.00% | 95.00% |
| slot_comparison_month_accuracy | 98.00% | 98.00% |
| slot_compare_accuracy | 99.00% | 99.00% |
| slot_scope_accuracy | 100.00% | 100.00% |
| slot_knowledge_requested_accuracy | 100.00% | 100.00% |
| slot_unresolved_month_accuracy | 96.00% | 96.00% |
| wrong_scope | 0.0000 | 0.0000 |
| safe_fail | 0.0000 | 0.0000 |
| other_error | 1.0000 | 1.0000 |
| execution_failure_count | 0.0000 | 0.0000 |

All planned records remain in denominators. Slot rates measure final semantic selectors; overall passes additionally require execution success.

Severity: {"dangerous": 33, "wrong_scope": 0, "safe_fail": 0, "other_error": 3}

Execution states: {"ok": 300}

Conflict counts: {}

Budget skips: 0; extra model attempts: 300.

Latency: nearest-rank ceil(p*n), all states and successful execution states separately. Missing latency observations: 0.
