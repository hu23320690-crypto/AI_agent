# Intent component evaluation: hybrid / test

Planned records: 100; repeats: 1.

| Repeat | Exact | Dangerous | Fallback | p50 all (s) | p95 all (s) | p95 successful (s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 80.00% | 10 | 0.00% | 1.2861 | 1.6826 | 1.6826 |

| Metric | Mean | Worst repeat |
| --- | ---: | ---: |
| exact_accuracy | 80.00% | 80.00% |
| dangerous | 10.0000 | 10.0000 |
| dangerous_count | 10.0000 | 10.0000 |
| fallback_count | 0.0000 | 0.0000 |
| fallback_rate | 0.00% | 0.00% |
| budget_skip_count | 0.0000 | 0.0000 |
| budget_skip_rate | 0.00% | 0.00% |
| extra_model_calls | 100.0000 | 100.0000 |
| latency_all_p50 | 1.2861 | 1.2861 |
| latency_all_p95 | 1.6826 | 1.6826 |
| latency_successful_p50 | 1.2861 | 1.2861 |
| latency_successful_p95 | 1.6826 | 1.6826 |
| slot_fields_accuracy | 92.00% | 92.00% |
| slot_unknown_fields_accuracy | 90.00% | 90.00% |
| slot_requested_field_order_accuracy | 89.00% | 89.00% |
| slot_target_month_accuracy | 92.00% | 92.00% |
| slot_comparison_month_accuracy | 97.00% | 97.00% |
| slot_compare_accuracy | 100.00% | 100.00% |
| slot_scope_accuracy | 99.00% | 99.00% |
| slot_knowledge_requested_accuracy | 100.00% | 100.00% |
| slot_unresolved_month_accuracy | 96.00% | 96.00% |
| wrong_scope | 1.0000 | 1.0000 |
| safe_fail | 6.0000 | 6.0000 |
| other_error | 3.0000 | 3.0000 |
| execution_failure_count | 0.0000 | 0.0000 |

All planned records remain in denominators. Slot rates measure final semantic selectors; overall passes additionally require execution success.

Severity: {"dangerous": 10, "wrong_scope": 1, "safe_fail": 6, "other_error": 3}

Execution states: {"ok": 100}

Conflict counts: {"field_not_in_catalog": 2, "fields_rule_fallback": 2, "mention_unanchored_kept": 5, "month_unsupported": 1, "negated_field_selected": 4, "negated_month_selected": 2, "qualifier_dropped": 8, "relative_month_recomputed": 4}

Budget skips: 0; extra model attempts: 100.

Latency: nearest-rank ceil(p*n), all states and successful execution states separately. Missing latency observations: 0.
