# Intent component evaluation: llm_only / test

Planned records: 300; repeats: 3.

| Repeat | Exact | Dangerous | Fallback | p50 all (s) | p95 all (s) | p95 successful (s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 91.00% | 8 | 0.00% | 0.6292 | 0.8725 | 0.8725 |
| 2 | 91.00% | 8 | 0.00% | 0.6209 | 0.7292 | 0.7292 |
| 3 | 91.00% | 8 | 0.00% | 0.6111 | 0.7176 | 0.7176 |

| Metric | Mean | Worst repeat |
| --- | ---: | ---: |
| exact_accuracy | 91.00% | 91.00% |
| dangerous | 8.0000 | 8.0000 |
| dangerous_count | 8.0000 | 8.0000 |
| fallback_count | 0.0000 | 0.0000 |
| fallback_rate | 0.00% | 0.00% |
| budget_skip_count | 0.0000 | 0.0000 |
| budget_skip_rate | 0.00% | 0.00% |
| extra_model_calls | 100.0000 | 100.0000 |
| latency_all_p50 | 0.6204 | 0.6292 |
| latency_all_p95 | 0.7731 | 0.8725 |
| latency_successful_p50 | 0.6204 | 0.6292 |
| latency_successful_p95 | 0.7731 | 0.8725 |
| slot_fields_accuracy | 98.00% | 98.00% |
| slot_unknown_fields_accuracy | 98.00% | 98.00% |
| slot_requested_field_order_accuracy | 98.00% | 98.00% |
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

Severity: {"dangerous": 24, "wrong_scope": 0, "safe_fail": 0, "other_error": 3}

Execution states: {"ok": 300}

Conflict counts: {}

Budget skips: 0; extra model attempts: 300.

Latency: nearest-rank ceil(p*n), all states and successful execution states separately. Missing latency observations: 0.
