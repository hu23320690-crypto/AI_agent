# Intent component evaluation: llm_only / test

Planned records: 100; repeats: 1.

| Repeat | Exact | Dangerous | Fallback | p50 all (s) | p95 all (s) | p95 successful (s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 79.00% | 15 | 0.00% | 1.2785 | 1.6775 | 1.6775 |

| Metric | Mean | Worst repeat |
| --- | ---: | ---: |
| exact_accuracy | 79.00% | 79.00% |
| dangerous | 15.0000 | 15.0000 |
| dangerous_count | 15.0000 | 15.0000 |
| fallback_count | 0.0000 | 0.0000 |
| fallback_rate | 0.00% | 0.00% |
| budget_skip_count | 0.0000 | 0.0000 |
| budget_skip_rate | 0.00% | 0.00% |
| extra_model_calls | 100.0000 | 100.0000 |
| latency_all_p50 | 1.2785 | 1.2785 |
| latency_all_p95 | 1.6775 | 1.6775 |
| latency_successful_p50 | 1.2785 | 1.2785 |
| latency_successful_p95 | 1.6775 | 1.6775 |
| slot_fields_accuracy | 88.00% | 88.00% |
| slot_unknown_fields_accuracy | 87.00% | 87.00% |
| slot_requested_field_order_accuracy | 86.00% | 86.00% |
| slot_target_month_accuracy | 95.00% | 95.00% |
| slot_comparison_month_accuracy | 97.00% | 97.00% |
| slot_compare_accuracy | 100.00% | 100.00% |
| slot_scope_accuracy | 99.00% | 99.00% |
| slot_knowledge_requested_accuracy | 100.00% | 100.00% |
| slot_unresolved_month_accuracy | 96.00% | 96.00% |
| wrong_scope | 1.0000 | 1.0000 |
| safe_fail | 3.0000 | 3.0000 |
| other_error | 2.0000 | 2.0000 |
| execution_failure_count | 0.0000 | 0.0000 |

All planned records remain in denominators. Slot rates measure final semantic selectors; overall passes additionally require execution success.

Severity: {"dangerous": 15, "wrong_scope": 1, "safe_fail": 3, "other_error": 2}

Execution states: {"ok": 100}

Conflict counts: {"field_not_in_catalog": 2}

Budget skips: 0; extra model attempts: 100.

Latency: nearest-rank ceil(p*n), all states and successful execution states separately. Missing latency observations: 0.
