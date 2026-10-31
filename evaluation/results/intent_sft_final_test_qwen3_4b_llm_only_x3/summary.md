# Intent component evaluation: llm_only / test

Planned records: 300; repeats: 3.

| Repeat | Exact | Dangerous | Fallback | p50 all (s) | p95 all (s) | p95 successful (s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 78.00% | 16 | 0.00% | 1.0731 | 1.4697 | 1.4697 |
| 2 | 78.00% | 16 | 0.00% | 1.0609 | 1.2012 | 1.2012 |
| 3 | 78.00% | 16 | 0.00% | 1.0529 | 1.2071 | 1.2071 |

| Metric | Mean | Worst repeat |
| --- | ---: | ---: |
| exact_accuracy | 78.00% | 78.00% |
| dangerous | 16.0000 | 16.0000 |
| dangerous_count | 16.0000 | 16.0000 |
| fallback_count | 0.0000 | 0.0000 |
| fallback_rate | 0.00% | 0.00% |
| budget_skip_count | 0.0000 | 0.0000 |
| budget_skip_rate | 0.00% | 0.00% |
| extra_model_calls | 100.0000 | 100.0000 |
| latency_all_p50 | 1.0623 | 1.0731 |
| latency_all_p95 | 1.2927 | 1.4697 |
| latency_successful_p50 | 1.0623 | 1.0731 |
| latency_successful_p95 | 1.2927 | 1.4697 |
| slot_fields_accuracy | 87.00% | 87.00% |
| slot_unknown_fields_accuracy | 86.00% | 86.00% |
| slot_requested_field_order_accuracy | 85.00% | 85.00% |
| slot_target_month_accuracy | 95.00% | 95.00% |
| slot_comparison_month_accuracy | 98.00% | 98.00% |
| slot_compare_accuracy | 100.00% | 100.00% |
| slot_scope_accuracy | 99.00% | 99.00% |
| slot_knowledge_requested_accuracy | 100.00% | 100.00% |
| slot_unresolved_month_accuracy | 96.00% | 96.00% |
| wrong_scope | 1.0000 | 1.0000 |
| safe_fail | 3.0000 | 3.0000 |
| other_error | 2.0000 | 2.0000 |
| execution_failure_count | 0.0000 | 0.0000 |

All planned records remain in denominators. Slot rates measure final semantic selectors; overall passes additionally require execution success.

Severity: {"dangerous": 48, "wrong_scope": 3, "safe_fail": 9, "other_error": 6}

Execution states: {"ok": 300}

Conflict counts: {"field_not_in_catalog": 6}

Budget skips: 0; extra model attempts: 300.

Latency: nearest-rank ceil(p*n), all states and successful execution states separately. Missing latency observations: 0.
