# Intent component evaluation: hybrid / test

Planned records: 300; repeats: 3.

| Repeat | Exact | Dangerous | Fallback | p50 all (s) | p95 all (s) | p95 successful (s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 90.00% | 7 | 0.00% | 0.3679 | 0.4903 | 0.4903 |
| 2 | 90.00% | 7 | 0.00% | 0.3491 | 0.4046 | 0.4046 |
| 3 | 90.00% | 7 | 0.00% | 0.3531 | 0.4175 | 0.4175 |

| Metric | Mean | Worst repeat |
| --- | ---: | ---: |
| exact_accuracy | 90.00% | 90.00% |
| dangerous | 7.0000 | 7.0000 |
| dangerous_count | 7.0000 | 7.0000 |
| fallback_count | 0.0000 | 0.0000 |
| fallback_rate | 0.00% | 0.00% |
| budget_skip_count | 0.0000 | 0.0000 |
| budget_skip_rate | 0.00% | 0.00% |
| extra_model_calls | 100.0000 | 100.0000 |
| latency_all_p50 | 0.3567 | 0.3679 |
| latency_all_p95 | 0.4375 | 0.4903 |
| latency_successful_p50 | 0.3567 | 0.3679 |
| latency_successful_p95 | 0.4375 | 0.4903 |
| slot_fields_accuracy | 97.00% | 97.00% |
| slot_unknown_fields_accuracy | 96.00% | 96.00% |
| slot_requested_field_order_accuracy | 96.00% | 96.00% |
| slot_target_month_accuracy | 96.00% | 96.00% |
| slot_comparison_month_accuracy | 98.00% | 98.00% |
| slot_compare_accuracy | 99.00% | 99.00% |
| slot_scope_accuracy | 100.00% | 100.00% |
| slot_knowledge_requested_accuracy | 100.00% | 100.00% |
| slot_unresolved_month_accuracy | 96.00% | 96.00% |
| wrong_scope | 0.0000 | 0.0000 |
| safe_fail | 1.0000 | 1.0000 |
| other_error | 2.0000 | 2.0000 |
| execution_failure_count | 0.0000 | 0.0000 |

All planned records remain in denominators. Slot rates measure final semantic selectors; overall passes additionally require execution success.

Severity: {"dangerous": 21, "wrong_scope": 0, "safe_fail": 3, "other_error": 6}

Execution states: {"ok": 300}

Conflict counts: {"qualifier_dropped": 6, "relative_month_recomputed": 6}

Budget skips: 0; extra model attempts: 300.

Latency: nearest-rank ceil(p*n), all states and successful execution states separately. Missing latency observations: 0.
