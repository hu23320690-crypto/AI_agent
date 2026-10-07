# 同题版本对照

前版：generalization_v1_current；后版：generalization_repair_v3。

未评分、缺失、报错、超时与截断保持未知，计划分母不变。

```json
{
  "knowledge": {
    "planned": 28,
    "improved": 4,
    "regressed": 2,
    "stable_pass": 16,
    "stable_fail": 6,
    "unknown": 0
  },
  "unanswerable": {
    "planned": 6,
    "improved": 1,
    "regressed": 0,
    "stable_pass": 5,
    "stable_fail": 0,
    "unknown": 0
  },
  "agent": {
    "planned": 6,
    "improved": 3,
    "regressed": 0,
    "stable_pass": 1,
    "stable_fail": 2,
    "unknown": 0
  }
}
```

| 案例 | 前版 | 后版 | 对照 |
| --- | --- | --- | --- |
| G1K01 | fail | fail | stable_fail |
| G1K02 | pass | pass | stable_pass |
| G1K03 | fail | pass | improved |
| G1K04 | pass | pass | stable_pass |
| G1K05 | pass | pass | stable_pass |
| G1K06 | pass | pass | stable_pass |
| G1K07 | fail | pass | improved |
| G1K08 | pass | pass | stable_pass |
| G1K09 | pass | pass | stable_pass |
| G1K10 | pass | pass | stable_pass |
| G1K11 | fail | fail | stable_fail |
| G1K12 | fail | fail | stable_fail |
| G1K13 | pass | pass | stable_pass |
| G1K14 | pass | fail | regressed |
| G1K15 | pass | fail | regressed |
| G1K16 | fail | pass | improved |
| G1K17 | fail | fail | stable_fail |
| G1K18 | pass | pass | stable_pass |
| G1K19 | pass | pass | stable_pass |
| G1K20 | pass | pass | stable_pass |
| G1K21 | fail | fail | stable_fail |
| G1K22 | fail | pass | improved |
| G1K23 | pass | pass | stable_pass |
| G1K24 | pass | pass | stable_pass |
| G1K25 | pass | pass | stable_pass |
| G1K26 | pass | pass | stable_pass |
| G1K27 | fail | fail | stable_fail |
| G1K28 | pass | pass | stable_pass |
| G1N01 | pass | pass | stable_pass |
| G1N02 | pass | pass | stable_pass |
| G1N03 | pass | pass | stable_pass |
| G1N04 | pass | pass | stable_pass |
| G1N05 | fail | pass | improved |
| G1N06 | pass | pass | stable_pass |
| G1A01 | pass | pass | stable_pass |
| G1A02 | fail | pass | improved |
| G1A03 | fail | pass | improved |
| G1A04 | fail | pass | improved |
| G1A05 | fail | fail | stable_fail |
| G1A06 | fail | fail | stable_fail |

Sequential local runs; successful QA/turn latency and all-status wall time are separate. No statistical significance or isolated algorithm attribution is claimed.

Only labels/order are hidden. Request prompts may reveal version behavior; this is assistant-assisted auxiliary review, not independent human blind evaluation.