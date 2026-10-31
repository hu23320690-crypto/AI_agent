# Intent component evaluation: llm_only / test

Planned records: 300; repeats: 3.

| Repeat | Exact | Dangerous | Fallback | p50 all (s) | p95 all (s) | p95 successful (s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 77.00% | 17 | 0.00% | 0.6343 | 0.8450 | 0.8450 |
| 2 | 76.00% | 17 | 0.00% | 0.6276 | 0.7286 | 0.7286 |
| 3 | 76.00% | 17 | 0.00% | 0.6254 | 0.7135 | 0.7135 |

| Metric | Mean | Worst repeat |
| --- | ---: | ---: |
| exact_accuracy | 76.33% | 76.00% |
| dangerous | 17.0000 | 17.0000 |
| dangerous_count | 17.0000 | 17.0000 |
| fallback_count | 0.0000 | 0.0000 |
| fallback_rate | 0.00% | 0.00% |
| budget_skip_count | 0.0000 | 0.0000 |
| budget_skip_rate | 0.00% | 0.00% |
| extra_model_calls | 100.0000 | 100.0000 |
| latency_all_p50 | 0.6291 | 0.6343 |
| latency_all_p95 | 0.7623 | 0.8450 |
| latency_successful_p50 | 0.6291 | 0.6343 |
| latency_successful_p95 | 0.7623 | 0.8450 |
| slot_fields_accuracy | 89.00% | 89.00% |
| slot_unknown_fields_accuracy | 88.33% | 88.00% |
| slot_requested_field_order_accuracy | 85.33% | 85.00% |
| slot_target_month_accuracy | 94.00% | 94.00% |
| slot_comparison_month_accuracy | 97.00% | 97.00% |
| slot_compare_accuracy | 99.00% | 99.00% |
| slot_scope_accuracy | 99.00% | 99.00% |
| slot_knowledge_requested_accuracy | 100.00% | 100.00% |
| slot_unresolved_month_accuracy | 96.00% | 96.00% |
| wrong_scope | 1.0000 | 1.0000 |
| safe_fail | 2.0000 | 2.0000 |
| other_error | 3.6667 | 4.0000 |
| execution_failure_count | 0.0000 | 0.0000 |

All planned records remain in denominators. Slot rates measure final semantic selectors; overall passes additionally require execution success.

Severity: {"dangerous": 51, "wrong_scope": 3, "safe_fail": 6, "other_error": 11}

Execution states: {"ok": 300}

Conflict counts: {"field_not_in_catalog": 3}

Budget skips: 0; extra model attempts: 300.

Latency: nearest-rank ceil(p*n), all states and successful execution states separately. Missing latency observations: 0.
