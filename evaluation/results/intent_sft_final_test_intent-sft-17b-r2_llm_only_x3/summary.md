# Intent component evaluation: llm_only / test

Planned records: 300; repeats: 3.

| Repeat | Exact | Dangerous | Fallback | p50 all (s) | p95 all (s) | p95 successful (s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 76.00% | 14 | 0.00% | 0.9093 | 1.2188 | 1.2188 |
| 2 | 76.00% | 14 | 0.00% | 0.9006 | 1.0077 | 1.0077 |
| 3 | 75.00% | 14 | 0.00% | 0.8976 | 1.0048 | 1.0048 |

| Metric | Mean | Worst repeat |
| --- | ---: | ---: |
| exact_accuracy | 75.67% | 75.00% |
| dangerous | 14.0000 | 14.0000 |
| dangerous_count | 14.0000 | 14.0000 |
| fallback_count | 0.0000 | 0.0000 |
| fallback_rate | 0.00% | 0.00% |
| budget_skip_count | 0.0000 | 0.0000 |
| budget_skip_rate | 0.00% | 0.00% |
| extra_model_calls | 100.0000 | 100.0000 |
| latency_all_p50 | 0.9025 | 0.9093 |
| latency_all_p95 | 1.0771 | 1.2188 |
| latency_successful_p50 | 0.9025 | 0.9093 |
| latency_successful_p95 | 1.0771 | 1.2188 |
| slot_fields_accuracy | 89.00% | 89.00% |
| slot_unknown_fields_accuracy | 90.00% | 90.00% |
| slot_requested_field_order_accuracy | 89.00% | 89.00% |
| slot_target_month_accuracy | 94.00% | 94.00% |
| slot_comparison_month_accuracy | 90.67% | 90.00% |
| slot_compare_accuracy | 99.00% | 99.00% |
| slot_scope_accuracy | 100.00% | 100.00% |
| slot_knowledge_requested_accuracy | 100.00% | 100.00% |
| slot_unresolved_month_accuracy | 96.00% | 96.00% |
| wrong_scope | 0.0000 | 0.0000 |
| safe_fail | 8.3333 | 9.0000 |
| other_error | 2.0000 | 2.0000 |
| execution_failure_count | 0.0000 | 0.0000 |

All planned records remain in denominators. Slot rates measure final semantic selectors; overall passes additionally require execution success.

Severity: {"dangerous": 42, "wrong_scope": 0, "safe_fail": 25, "other_error": 6}

Execution states: {"ok": 300}

Conflict counts: {"field_not_in_catalog": 81}

Budget skips: 0; extra model attempts: 300.

Latency: nearest-rank ceil(p*n), all states and successful execution states separately. Missing latency observations: 0.
