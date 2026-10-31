# Intent component evaluation: hybrid / test

Planned records: 300; repeats: 3.

| Repeat | Exact | Dangerous | Fallback | p50 all (s) | p95 all (s) | p95 successful (s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 83.00% | 10 | 0.00% | 0.6530 | 0.8920 | 0.8920 |
| 2 | 84.00% | 10 | 0.00% | 0.6289 | 0.7343 | 0.7343 |
| 3 | 84.00% | 10 | 0.00% | 0.6251 | 0.7347 | 0.7347 |

| Metric | Mean | Worst repeat |
| --- | ---: | ---: |
| exact_accuracy | 83.67% | 83.00% |
| dangerous | 10.0000 | 10.0000 |
| dangerous_count | 10.0000 | 10.0000 |
| fallback_count | 0.0000 | 0.0000 |
| fallback_rate | 0.00% | 0.00% |
| budget_skip_count | 0.0000 | 0.0000 |
| budget_skip_rate | 0.00% | 0.00% |
| extra_model_calls | 100.0000 | 100.0000 |
| latency_all_p50 | 0.6357 | 0.6530 |
| latency_all_p95 | 0.7870 | 0.8920 |
| latency_successful_p50 | 0.6357 | 0.6530 |
| latency_successful_p95 | 0.7870 | 0.8920 |
| slot_fields_accuracy | 91.00% | 91.00% |
| slot_unknown_fields_accuracy | 94.00% | 94.00% |
| slot_requested_field_order_accuracy | 91.00% | 91.00% |
| slot_target_month_accuracy | 96.67% | 96.00% |
| slot_comparison_month_accuracy | 97.00% | 97.00% |
| slot_compare_accuracy | 99.00% | 99.00% |
| slot_scope_accuracy | 100.00% | 100.00% |
| slot_knowledge_requested_accuracy | 100.00% | 100.00% |
| slot_unresolved_month_accuracy | 95.67% | 95.00% |
| wrong_scope | 0.0000 | 0.0000 |
| safe_fail | 4.3333 | 5.0000 |
| other_error | 2.0000 | 2.0000 |
| execution_failure_count | 0.0000 | 0.0000 |

All planned records remain in denominators. Slot rates measure final semantic selectors; overall passes additionally require execution success.

Severity: {"dangerous": 30, "wrong_scope": 0, "safe_fail": 13, "other_error": 6}

Execution states: {"ok": 300}

Conflict counts: {"anchor_lookup_consistency": 12, "field_not_in_catalog": 3, "fields_rule_fallback": 3, "mention_unanchored_kept": 18, "month_unsupported": 4, "negated_field_selected": 6, "negated_month_selected": 3, "non_metric_unknown_dropped": 8, "qualifier_dropped": 15, "relative_month_recomputed": 6}

Budget skips: 0; extra model attempts: 300.

Latency: nearest-rank ceil(p*n), all states and successful execution states separately. Missing latency observations: 0.
