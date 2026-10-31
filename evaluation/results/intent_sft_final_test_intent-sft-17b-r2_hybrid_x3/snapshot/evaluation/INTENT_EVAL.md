# Intent component evaluation

`python -B -m evaluation.intent_eval` evaluates the production `resolve_turn_intent` entry point. It does not query report tools, change intent defaults, or grant access to data. P2 uses only the allowed dev JSONL; P3 test execution requires the explicit approval flag.

```powershell
python -B -m evaluation.intent_eval --dataset evaluation/intent_v1_r1/dev.jsonl --split dev --mode rule --repeat 1 --run evaluation/results/fictional_intent_dev_rule
python -B -m evaluation.intent_eval --dataset evaluation/intent_v1_r1/dev.jsonl --split dev --mode llm_only --repeat 1 --run evaluation/results/fictional_intent_dev_llm
python -B -m evaluation.intent_eval --dataset evaluation/intent_v1_r1/dev.jsonl --split dev --mode hybrid --repeat 1 --run evaluation/results/fictional_intent_dev_hybrid
```

Use a new directory every time. An existing result directory is rejected before reading the dataset. `--split test` without `--p3-approved` is rejected before opening data or importing inference code. The flag records authorization at the CLI; it does not constitute approval on behalf of the author. Select the correct Python interpreter for the project's installed dependencies.

## Inputs and selector adaptation

The source CSV path comes from `config/agent.yml`; `utils.records.load_records` loads its exact bytes. For each case, the dynamic catalog uses only successful CSV rows matching the trusted `user_id` and the array's lookup months. Field extraction follows the frozen SCORING contract: in lookup order, parse efficiency then consumables, restore literal `\\n` to newlines, split at the first Chinese/English colon, take nonempty left-hand names, and retain first occurrence. Missing rows contribute no fields. No global catalog, hand-written field list, gold, aliases, neighboring month or other user contributes to inputs.

`fallback_month` is the last valid `phase=current` request month even when its row is not found. History lookups contribute catalog fields but do not themselves set this anchor. `today`, user-only `history` and `previous_intent` come from the case. History must satisfy the existing three-query / 1024 UTF-8-byte contract; invalid inputs are execution failures, rather than silently rewritten cases. Previous fields are reconstructed as the production `ReportIntent` tuple. The explicit CLI mode is passed to the resolver.

The adapter receives only the final result and dynamic catalog. All three modes read `TurnIntentResult.final_scope` and `final_excluded_fields`; diagnostic LLM proposals never determine scope or exclusions. `full_report` is true exactly when final scope is `full_report`. Its semantic `limited` is false and its requested fields, unknown fields and mixed order are empty, even when the renderer carries a remaining-field list or an empty-list safety guard to support exclusions. Exclusions remain a separate diagnostic list; the frozen nine-slot contract does not add an exclusion accuracy slot.

Outside full scope, `limited` is true when final scope is `only_listed` or the final `ReportIntent.limited` is true. Thus `unspecified` proposals with a real restricted field selection retain that selection. The final mixed sequence is deduplicated in order and split by exact membership in the per-case catalog. It supplies `fields`, `unknown_fields` and `requested_field_order`; the adapter neither applies unknown aliases nor repairs a month/baseline/compare inconsistency. Unrestricted unspecified output has empty request lists. Target, baseline, comparison, knowledge request and unresolved-month slots retain final selectors.

## Scoring and denominators

The scorer, separately from adaptation, reads nine gold slots and `requested_field_order` (accepted beside gold or inside it). Known and unknown field metrics compare sets; mixed order compares the complete known/unknown sequence. The other metrics are target month, comparison month, compare, combined scope (`limited` and `full_report`), knowledge request and unresolved month. Whole-intent correctness requires all nine metric checks and successful execution. Boolean slots require actual booleans; null and empty strings differ.

String normalization is limited to surrounding whitespace and newline consistency. Unknown names additionally ignore whitespace, per SCORING. Only the case's predeclared `unknown_aliases` may equate unknown names, and the same equivalence applies at the same mixed-order position. It cannot rename known fields, change catalog membership or expand a global synonym table. A flat alias list applies only to a single gold unknown; an object may map declared gold unknown names to lists. Aliases when no gold unknown exists cannot authorize a known field.

Every result preserves raw per-slot differences, including original list order and alias spelling, independently of scored semantic differences. Error flags retain every applicable error class. Exclusive severity follows `dangerous > wrong_scope > safe_fail > other_error`: unrequested catalog fields or wrong legal target/baseline months are dangerous (also when gold is null); a wrong range is wrong_scope; omitted answerable fields or a visible null/unresolved refusal on a determinable month is safe_fail; remaining ordering/unknown/knowledge/compare errors are other_error. Execution failure is a separate dimension and cannot pass merely because a rule fallback happens to match gold.

Timeout, model exception, truncated/illegal structure, rejected task proposal, unavailable dependency, circuit skip and budget skip are retained as unsuccessful execution states. Recoverable fallbacks still preserve their final rule intent and semantic score. Validated slot conflicts that result in a normal merged intent are successful execution. No planned row is removed from any denominator. Slot rates describe final semantic selectors even for a failed execution that returned a fallback; missing predictions fail every slot. Overall exact accuracy additionally requires `status=ok`.

`SCORING_AMENDMENT_01.md` changes the first-turn relative-month anchor contract. The affected dev ID021 (also recognized as IT021) stays in the full dev denominator, is separately reported, and is excluded only from an explicitly labeled auxiliary table. Neither it nor that auxiliary table changes gold or the main denominator; it must not guide prompt tuning.

## Cost, repeat summaries and records

`results.jsonl` has one unique record ID per case and repeat, the case ID, repeat index, raw model response, raw parsed proposal, deterministic validation result, checked proposal, merged proposal, final intent/scope/exclusions, adapted prediction, privacy-safe production trace, wall-clock time, model attempts, runtime codes, and scoring. Raw responses are kept only in the explicit evaluation evidence artifact, never added to production runtime trace or console logs. Structurally invalid responses remain raw evidence even when no parsed proposal exists. The local observer wraps parser/validator functions during sequential evaluation; it does not alter production implementation or model settings.

Summary files report exact accuracy, every slot rate, severity counts, execution failures/states, fallback count/rate, each conflict count, budget skips/count/rate and extra model attempts from the production run counter. Budget skips include model, time and context budget reasons. Latency is per-case selector wall time, excluding manifest checks and sealing. It uses nearest-rank `ceil(p*n)` for p50/p95, separately for all measured states and successful states. Missing observations and empty successful populations remain missing rather than becoming zero. Complete repeats are preserved, with mean and worst exact/slot accuracy (minimum), dangerous/error counts and costs/latency (maximum); none is assembled by choosing the best individual cases.

## Manifest and sealing

`manifest.json` binds business code, prompt, all configuration including the actual tokenizer cache, evaluation code/rules, source CSV, selected model name/digest, explicit effective mode, repeat count, execution timestamps, platform and Git commit. Input identities are checked before and after each case. If an identity changes, completed rows remain unsuccessful and the rest of the planned records are marked failed; the run is not silently resumed against changed inputs.

The unchanged `scripts/seal_evaluation_run.py` requires a unique-ID execution plan plus results and reviews. To satisfy it without opening prohibited frozen files, this runner creates its own minimal `cases.jsonl` containing only `{id, case_id, repeat}` and a derived `snapshot/dataset_manifest.json` containing source CSV hashes and the planned count. Its `dataset_sha256` binds that derived execution plan. The separate `input_dataset_sha256` binds the exact original `--dataset`, copied to `snapshot/input_dataset.jsonl`; it is never substituted by the plan hash. The frozen dataset manifest is not read. Source, code, rules, prompt, configuration and tokenizer cache are copied into the snapshot. Deterministic `reviews.jsonl` binds each row's scoring pass and exact result SHA256; it is clearly labeled as automatic component scoring rather than human review.

Before sealing, the runner explicitly verifies that the original dataset snapshot matches `input_dataset_sha256`. The general seal validates its existing plan/source contract and inventories this additional snapshot; it does not interpret the added input-hash key. At completion the runner calls the existing seal function, producing `seal.json`. Execution failures still produce a complete sealed archive and a nonzero CLI exit status; ordinary semantic failures produce a complete archive without pretending a system failure. Verify later with:

```powershell
python -B scripts/seal_evaluation_run.py --run evaluation/results/fictional_intent_dev_rule --verify
```
