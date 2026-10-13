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


## Round 2

Changes: Prompt only: require every positive unknown metric as field=null; exact original mentions even for catalog synonyms; exclusions must be explicit and do not follow declined explanations; report value/category questions are not knowledge; continuing relative targets use previous_target unless a different starting point is explicitly selected. One fictional mixed known/unknown/qualifier example replaces the unknown-event example; six examples total. ID021 was not used.

| Mode | Exact / 40 | Dangerous | Fallback | p95 all (s) | p95 success (s) | Exact / 39 auxiliary | Dangerous / 39 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| rule | 10/40 (25.0%) | 8 | 0.0% | 0.0018 | 0.0018 | 9/39 (23.1%) | 8 |
| llm_only | 34/40 (85.0%) | 3 | 0.0% | 1.7708 | 1.7708 | 34/39 (87.2%) | 2 |
| hybrid | 30/40 (75.0%) | 3 | 0.0% | 1.7835 | 1.7835 | 30/39 (76.9%) | 2 |

Run source commit: `fa04a4c4484fcc58276dd166cfc6a3ecab1918fa`.
Prompt SHA256: `1100a20220955b0938ffdf13dcaf89b84e172c18bcda95741975b71dad661de4`.
Original dev SHA256: `f8f1a0cdddd717438b607007b2fe215591e8f4258c81e5042f38eec14312828a`.
Model: `qwen3:4b`, digest `359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`.

ID021 (not used for tuning): rule: exact=1/1, dangerous=0; llm_only: exact=0/1, dangerous=1; hybrid: exact=0/1, dangerous=1.

Artifacts: `evaluation/results/intent_v1_r1_dev_p2_r2_rule`, `evaluation/results/intent_v1_r1_dev_p2_r2_llm_only`, `evaluation/results/intent_v1_r1_dev_p2_r2_hybrid`.

rule: execution failures=0, budget skips=0, extra model calls=0; conflicts={}.
llm_only: execution failures=0, budget skips=0, extra model calls=40; conflicts={}.
hybrid: execution failures=0, budget skips=0, extra model calls=40; conflicts={"mention_not_in_text": 2, "month_unsupported": 3, "negated_field_selected": 1, "qualifier_dropped": 1}.

No validation, resolver, runner, model/runtime/configuration or gold changes were made in this round.

## Round 3

Changes: Prompt only: add concise Chinese verification rules for all positive unknowns, verbatim original noun phrases, independent target/baseline roles, report-vs-knowledge and ordinal history selection. Replace the relative-baseline knowledge example with a new fictional combined reference/target/ordinal/definition example. Six fictional examples total; no dev question copied or rewritten. ID021 was not used.

| Mode | Exact / 40 | Dangerous | Fallback | p95 all (s) | p95 success (s) | Exact / 39 auxiliary | Dangerous / 39 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| rule | 10/40 (25.0%) | 8 | 0.0% | 0.0019 | 0.0019 | 9/39 (23.1%) | 8 |
| llm_only | 32/40 (80.0%) | 1 | 0.0% | 1.3848 | 1.3848 | 32/39 (82.1%) | 0 |
| hybrid | 27/40 (67.5%) | 1 | 0.0% | 1.3970 | 1.3970 | 27/39 (69.2%) | 0 |

Run source commit: `2849fd23971ce324a5e4f0265fb3e9660c4312b0`.
Prompt SHA256: `ec7e3a7e507417ee775b59bfcfd030ff78fc605ff4305ad92c55bad7ddb1cfb4`.
Original dev SHA256: `f8f1a0cdddd717438b607007b2fe215591e8f4258c81e5042f38eec14312828a`.
Model: `qwen3:4b`, digest `359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`.

ID021 (not used for tuning): rule: exact=1/1, dangerous=0; llm_only: exact=0/1, dangerous=1; hybrid: exact=0/1, dangerous=1.

Artifacts: `evaluation/results/intent_v1_r1_dev_p2_r3_rule`, `evaluation/results/intent_v1_r1_dev_p2_r3_llm_only`, `evaluation/results/intent_v1_r1_dev_p2_r3_hybrid`.

rule: execution failures=0, budget skips=0, extra model calls=0; conflicts={}.
llm_only: execution failures=0, budget skips=0, extra model calls=40; conflicts={"field_not_in_catalog": 1}.
hybrid: execution failures=0, budget skips=0, extra model calls=40; conflicts={"field_not_in_catalog": 1, "mention_not_in_text": 3, "month_unsupported": 3, "negated_field_selected": 1, "qualifier_dropped": 2}.

No validation, resolver, runner, model/runtime/configuration or gold changes were made in this round.

## P2 freeze declaration

Final code and prompt commit (the sole P3 runtime version): `babeaa6049f008534a8d76b859ecbd04f7bd8fee`.
Final prompt SHA256: `ec7e3a7e507417ee775b59bfcfd030ff78fc605ff4305ad92c55bad7ddb1cfb4`.
Model: qwen3:4b, digest `359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`.

The final version is round 3. Its full dev score is 27/40 (67.5%), dangerous=1; the amended ID021 alone accounts for that dangerous mark. The unchanged 39-case auxiliary score is 27/39 (69.23%), dangerous=0. Round 2 had higher exact accuracy (30/40) and dangerous=3; all three prompt versions and every raw result remain committed. No further prompt tuning or fourth dev round is planned. A single dev run does not establish safety or generalization.

Round records: R1 `fa04a4c`, R2 `2849fd23971ce324a5e4f0265fb3e9660c4312b0`, R3 `babeaa6049f008534a8d76b859ecbd04f7bd8fee`. Run manifests record Git HEAD at invocation; prompt changes were committed with their completed round records. Every measured live prompt is independently bound by SHA256 and its frozen snapshot. The final source files match the round 3 snapshot byte for byte.

Final verification: 952 passed, 291 subtests passed, three Windows symlink privilege skips; 60.87 seconds. `doctor --offline`: 149 checks, no failures. All nine completed archives verify through scripts/seal_evaluation_run.py, each has 40 planned/result/review records. Across nine runs every non-prompt code, evaluation, configuration, CSV, dev dataset and model identity is identical. All 360 executions were ok; budget skips and whole-proposal fallbacks were zero; additional model calls total 240. No protected test/merged/Agent/review/check files were opened and no push was performed.

Frozen round 3 hybrid conflicts:

| Code | Count | Evidence / interpretation |
| --- | ---: | --- |
| month_unsupported | 3 | ID017/019/024: otherwise correct months conservatively rejected by narrow date evidence extraction; coverage limitation, not a new arithmetic or merge defect. |
| mention_not_in_text | 3 | ID002/006/008: standard names substituted for original mentions; correct field mappings removed as required by V3. Not harmless. |
| qualifier_dropped | 2 | ID010: effective correction, final pass. ID012: component qualifier protected, but the model's unknown name still included request wording and remained incorrect. |
| field_not_in_catalog | 1 | ID028: the model supplied a month as a field. Catalog enforcement downgrades the invalid selection; the proposal was already incorrect. |
| negated_field_selected | 1 | ID031: an excluded selected field removed; final pass. |

Across the three hybrid rounds the top counts are month_unsupported=9, mention_not_in_text=8, qualifier_dropped=5, exclusion_not_in_text=4, field_not_in_catalog=3 (tied with negated_field_selected=3). The four exclusion_not_in_text firings did not add errors; R1's two catalog firings only cleared unsupported exclusions. Four of five qualifier firings corrected the final result completely. These classes are not blanket harmless: judgment follows each raw proposal and final difference. R1's sole relative_month_recomputed firing amplified an incorrect model anchor declaration into a wrong month; the final prompt strengthens the anchor declaration instructions.

Before P3 the author must decide whether to authorize the registered test batch and confirm held-out gold approval. The batch remains rule x1, llm_only x3, hybrid x3 on the exact frozen runtime commit, with fresh directories and full-repeat mean/worst statistics. Planned repeat identities are r001/r002/r003. Sampling remains the frozen factory configuration: temperature=0, reasoning=False, num_predict capped at384, JSON schema format, no explicitly configured seed. The model tag/digest and all source/config hashes must remain fixed. The author should accept the documented conservative date refusals and remaining field omissions as limitations of this frozen version, or pause P3 for a separately versioned P1 review; no test-based repair is allowed. Default mode stays rule until P3 G1-G6 are evaluated.

P2 is complete. P3 has not started. This final entry freezes the runtime source commit above; the following commit records this declaration only.
