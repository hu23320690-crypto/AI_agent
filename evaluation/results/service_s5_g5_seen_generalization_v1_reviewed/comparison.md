# 同题版本对照

前版：service_s5_g5_seen_generalization_v1_legacy_react；后版：service_s5_g5_seen_generalization_v1_service_react。

未评分、缺失、报错、超时与截断保持未知，计划分母不变。

```json
{
  "knowledge": {
    "planned": 28,
    "improved": 0,
    "regressed": 0,
    "stable_pass": 0,
    "stable_fail": 0,
    "unknown": 28
  },
  "unanswerable": {
    "planned": 6,
    "improved": 0,
    "regressed": 0,
    "stable_pass": 0,
    "stable_fail": 0,
    "unknown": 6
  },
  "agent": {
    "planned": 6,
    "improved": 0,
    "regressed": 4,
    "stable_pass": 1,
    "stable_fail": 1,
    "unknown": 0
  }
}
```

| 案例 | 前版 | 后版 | 对照 |
| --- | --- | --- | --- |
| G1K01 | unknown | unknown | unknown |
| G1K02 | unknown | unknown | unknown |
| G1K03 | unknown | unknown | unknown |
| G1K04 | unknown | unknown | unknown |
| G1K05 | unknown | unknown | unknown |
| G1K06 | unknown | unknown | unknown |
| G1K07 | unknown | unknown | unknown |
| G1K08 | unknown | unknown | unknown |
| G1K09 | unknown | unknown | unknown |
| G1K10 | unknown | unknown | unknown |
| G1K11 | unknown | unknown | unknown |
| G1K12 | unknown | unknown | unknown |
| G1K13 | unknown | unknown | unknown |
| G1K14 | unknown | unknown | unknown |
| G1K15 | unknown | unknown | unknown |
| G1K16 | unknown | unknown | unknown |
| G1K17 | unknown | unknown | unknown |
| G1K18 | unknown | unknown | unknown |
| G1K19 | unknown | unknown | unknown |
| G1K20 | unknown | unknown | unknown |
| G1K21 | unknown | unknown | unknown |
| G1K22 | unknown | unknown | unknown |
| G1K23 | unknown | unknown | unknown |
| G1K24 | unknown | unknown | unknown |
| G1K25 | unknown | unknown | unknown |
| G1K26 | unknown | unknown | unknown |
| G1K27 | unknown | unknown | unknown |
| G1K28 | unknown | unknown | unknown |
| G1N01 | unknown | unknown | unknown |
| G1N02 | unknown | unknown | unknown |
| G1N03 | unknown | unknown | unknown |
| G1N04 | unknown | unknown | unknown |
| G1N05 | unknown | unknown | unknown |
| G1N06 | unknown | unknown | unknown |
| G1A01 | pass | fail | regressed |
| G1A02 | pass | fail | regressed |
| G1A03 | pass | pass | stable_pass |
| G1A04 | pass | fail | regressed |
| G1A05 | fail | fail | stable_fail |
| G1A06 | pass | fail | regressed |

Sequential local runs; successful QA/turn latency and all-status wall time are separate. No statistical significance or isolated algorithm attribution is claimed.

Only labels/order are hidden. Request prompts may reveal version behavior; this is assistant-assisted auxiliary review, not independent human blind evaluation.