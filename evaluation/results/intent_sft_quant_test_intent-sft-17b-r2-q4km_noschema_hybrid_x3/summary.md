# Intent component evaluation: hybrid / test

Planned records: 300; repeats: 3.

| Repeat | Exact | Dangerous | Fallback | p50 all (s) | p95 all (s) | p95 successful (s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 93.00% | 3 | 1.00% | 0.4753 | 0.6638 | 0.6739 |
| 2 | 93.00% | 3 | 1.00% | 0.4538 | 0.5215 | 0.5215 |
| 3 | 93.00% | 3 | 1.00% | 0.4510 | 0.5262 | 0.5262 |

| Metric | Mean | Worst repeat |
| --- | ---: | ---: |
| exact_accuracy | 93.00% | 93.00% |
| dangerous | 3.0000 | 3.0000 |
| dangerous_count | 3.0000 | 3.0000 |
| fallback_count | 1.0000 | 1.0000 |
| fallback_rate | 1.00% | 1.00% |
| budget_skip_count | 0.0000 | 0.0000 |
| budget_skip_rate | 0.00% | 0.00% |
| extra_model_calls | 100.0000 | 100.0000 |
| latency_all_p50 | 0.4600 | 0.4753 |
| latency_all_p95 | 0.5705 | 0.6638 |
| latency_successful_p50 | 0.4600 | 0.4753 |
| latency_successful_p95 | 0.5739 | 0.6739 |
| slot_fields_accuracy | 97.00% | 97.00% |
| slot_unknown_fields_accuracy | 97.00% | 97.00% |
| slot_requested_field_order_accuracy | 97.00% | 97.00% |
| slot_target_month_accuracy | 100.00% | 100.00% |
| slot_comparison_month_accuracy | 99.00% | 99.00% |
| slot_compare_accuracy | 99.00% | 99.00% |
| slot_scope_accuracy | 100.00% | 100.00% |
| slot_knowledge_requested_accuracy | 99.00% | 99.00% |
| slot_unresolved_month_accuracy | 98.00% | 98.00% |
| wrong_scope | 0.0000 | 0.0000 |
| safe_fail | 1.0000 | 1.0000 |
| other_error | 3.0000 | 3.0000 |
| execution_failure_count | 1.0000 | 1.0000 |

All planned records remain in denominators. Slot rates measure final semantic selectors; overall passes additionally require execution success.

Severity: {"dangerous": 9, "wrong_scope": 0, "safe_fail": 3, "other_error": 9}

Execution states: {"ok": 297, "error": 3}

Conflict counts: {"month_unsupported": 3, "no_anchor": 3, "qualifier_dropped": 9, "relative_month_recomputed": 3, "structure_invalid": 3}

Budget skips: 0; extra model attempts: 300.

Latency: nearest-rank ceil(p*n), all states and successful execution states separately. Missing latency observations: 0.
