# Intent component evaluation: llm_only / test

Planned records: 300; repeats: 3.

| Repeat | Exact | Dangerous | Fallback | p50 all (s) | p95 all (s) | p95 successful (s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 81.00% | 16 | 0.00% | 0.6305 | 0.8862 | 0.8862 |
| 2 | 81.00% | 16 | 0.00% | 0.6200 | 0.7145 | 0.7145 |
| 3 | 81.00% | 16 | 0.00% | 0.6235 | 0.7164 | 0.7164 |

| Metric | Mean | Worst repeat |
| --- | ---: | ---: |
| exact_accuracy | 81.00% | 81.00% |
| dangerous | 16.0000 | 16.0000 |
| dangerous_count | 16.0000 | 16.0000 |
| fallback_count | 0.0000 | 0.0000 |
| fallback_rate | 0.00% | 0.00% |
| budget_skip_count | 0.0000 | 0.0000 |
| budget_skip_rate | 0.00% | 0.00% |
| extra_model_calls | 100.0000 | 100.0000 |
| latency_all_p50 | 0.6247 | 0.6305 |
| latency_all_p95 | 0.7724 | 0.8862 |
| latency_successful_p50 | 0.6247 | 0.6305 |
| latency_successful_p95 | 0.7724 | 0.8862 |
| slot_fields_accuracy | 89.00% | 89.00% |
| slot_unknown_fields_accuracy | 89.00% | 89.00% |
| slot_requested_field_order_accuracy | 89.00% | 89.00% |
| slot_target_month_accuracy | 95.00% | 95.00% |
| slot_comparison_month_accuracy | 97.00% | 97.00% |
| slot_compare_accuracy | 99.00% | 99.00% |
| slot_scope_accuracy | 100.00% | 100.00% |
| slot_knowledge_requested_accuracy | 100.00% | 100.00% |
| slot_unresolved_month_accuracy | 96.00% | 96.00% |
| wrong_scope | 0.0000 | 0.0000 |
| safe_fail | 2.0000 | 2.0000 |
| other_error | 1.0000 | 1.0000 |
| execution_failure_count | 0.0000 | 0.0000 |

All planned records remain in denominators. Slot rates measure final semantic selectors; overall passes additionally require execution success.

Severity: {"dangerous": 48, "wrong_scope": 0, "safe_fail": 6, "other_error": 3}

Execution states: {"ok": 300}

Conflict counts: {"field_not_in_catalog": 3}

Budget skips: 0; extra model attempts: 300.

Latency: nearest-rank ceil(p*n), all states and successful execution states separately. Missing latency observations: 0.
