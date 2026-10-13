# P2 intent dev log

Date: 2026-10-13 (Australia/Sydney). Only `evaluation/intent_v1_r1/dev.jsonl` is used. No test, merged cases, Agent dataset or review/check reports are opened. Default mode remains rule; P3 has not run.

P1 correction: `886a62b615ca5550b92056397ef9901cf66dec62` separates `_explicit_scope` from `_rule_final_scope` in `agent/intent/resolve.py`. Only positive explicit scope words override hybrid; rule final scope can additionally describe `rule.limited`.

The affected `bd18172` test `test_rule_limited_scope_overrides_even_without_a_scope_marker` was replaced by `test_rule_limited_without_scope_words_preserves_llm_scope`: full_report now stays full with an empty requested list, only_listed stays restricted, and unspecified stays unspecified while preserving its selected fields. Two fictional full-report paraphrases with a named field were added. Earlier test assertions were unchanged. P1 verification: 886 passed, 291 subtests passed, three Windows symlink privilege skips; offline doctor 149 checks passed.

Evaluator implementation: `9aecb2b`; offline tests: `686fd55`. Before real dev: 952 passed, 291 subtests passed, three symlink privilege skips; offline doctor passed. The evaluator's 66 new tests use only fictional inputs and scripted models. All modes adapt final_scope/final_excluded_fields; code, settings, runtime and model options are fixed during prompt rounds.

Metrics below retain the full 40-case denominator, including the separately listed ID021. Auxiliary 39-case scores do not replace it. ID021 is not used to select prompt changes. p95 is nearest-rank wall time in seconds; all-state and successful-state latencies are both recorded in each sealed summary. All execution states, semantic differences, conflicts and repeat statistics remain in raw artifacts. Per round: rule x1, llm_only x1, hybrid x1, sequentially, each in a fresh directory, without extra warmup model calls.

## Round 1

Changes: Baseline: unchanged P1 prompt. Establish all three modes before tuning; no prompt change in round 1.

| Mode | Exact / 40 | Dangerous | Fallback | p95 all (s) | p95 success (s) | Exact / 39 auxiliary | Dangerous / 39 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| rule | 10/40 (25.0%) | 8 | 0.0% | 0.0018 | 0.0018 | 9/39 (23.1%) | 8 |
| llm_only | 30/40 (75.0%) | 1 | 0.0% | 1.9772 | 1.9772 | 30/39 (76.9%) | 0 |
| hybrid | 26/40 (65.0%) | 2 | 0.0% | 1.9913 | 1.9913 | 26/39 (66.7%) | 1 |

Run source commit: `686fd55417604ea3a81fcd2e0ea56e189a30decd`.
Prompt SHA256: `3e3df64ccb257d6d834e2f086bf98a164cb297584f4ce43036ead9251187769c`.
Original dev SHA256: `f8f1a0cdddd717438b607007b2fe215591e8f4258c81e5042f38eec14312828a`.
Model: `qwen3:4b`, digest `359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`.

ID021 (not used for tuning): rule: exact=1/1, dangerous=0; llm_only: exact=0/1, dangerous=1; hybrid: exact=0/1, dangerous=1.

Artifacts: `evaluation/results/intent_v1_r1_dev_p2_r1_rule`, `evaluation/results/intent_v1_r1_dev_p2_r1_llm_only`, `evaluation/results/intent_v1_r1_dev_p2_r1_hybrid`.

rule: execution failures=0, budget skips=0, extra model calls=0; conflicts={}.
llm_only: execution failures=0, budget skips=0, extra model calls=40; conflicts={"field_not_in_catalog": 2}.
hybrid: execution failures=0, budget skips=0, extra model calls=40; conflicts={"exclusion_not_in_text": 4, "field_not_in_catalog": 2, "mention_not_in_text": 3, "month_unsupported": 3, "negated_field_selected": 1, "qualifier_dropped": 2, "relative_month_recomputed": 1, "scope_rule_override": 1}.

No validation, resolver, runner, model/runtime/configuration or gold changes were made in this round.

