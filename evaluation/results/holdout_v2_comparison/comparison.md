# 同题版本对照

前版：holdout_v2_historical_optimized；后版：holdout_v2_current。

未评分、缺失、报错、超时与截断保持未知，计划分母不变。

```json
{
  "knowledge": {
    "planned": 28,
    "improved": 0,
    "regressed": 2,
    "stable_pass": 21,
    "stable_fail": 4,
    "unknown": 1
  },
  "unanswerable": {
    "planned": 6,
    "improved": 0,
    "regressed": 0,
    "stable_pass": 6,
    "stable_fail": 0,
    "unknown": 0
  },
  "agent": {
    "planned": 6,
    "improved": 0,
    "regressed": 0,
    "stable_pass": 0,
    "stable_fail": 5,
    "unknown": 1
  }
}
```

| 案例 | 前版 | 后版 | 对照 |
| --- | --- | --- | --- |
| V2K01 | pass | pass | stable_pass |
| V2K02 | pass | pass | stable_pass |
| V2K03 | pass | pass | stable_pass |
| V2K04 | fail | fail | stable_fail |
| V2K05 | pass | pass | stable_pass |
| V2K06 | pass | pass | stable_pass |
| V2K07 | pass | pass | stable_pass |
| V2K08 | pass | pass | stable_pass |
| V2K09 | pass | pass | stable_pass |
| V2K10 | pass | pass | stable_pass |
| V2K11 | pass | pass | stable_pass |
| V2K12 | pass | pass | stable_pass |
| V2K13 | fail | fail | stable_fail |
| V2K14 | pass | pass | stable_pass |
| V2K15 | pass | pass | stable_pass |
| V2K16 | pass | pass | stable_pass |
| V2K17 | pass | pass | stable_pass |
| V2K18 | pass | pass | stable_pass |
| V2K19 | pass | fail | regressed |
| V2K20 | pass | pass | stable_pass |
| V2K21 | pass | fail | regressed |
| V2K22 | pass | unknown | unknown |
| V2K23 | pass | pass | stable_pass |
| V2K24 | fail | fail | stable_fail |
| V2K25 | pass | pass | stable_pass |
| V2K26 | pass | pass | stable_pass |
| V2K27 | pass | pass | stable_pass |
| V2K28 | fail | fail | stable_fail |
| V2N01 | pass | pass | stable_pass |
| V2N02 | pass | pass | stable_pass |
| V2N03 | pass | pass | stable_pass |
| V2N04 | pass | pass | stable_pass |
| V2N05 | pass | pass | stable_pass |
| V2N06 | pass | pass | stable_pass |
| V2A01 | fail | fail | stable_fail |
| V2A02 | fail | fail | stable_fail |
| V2A03 | fail | unknown | unknown |
| V2A04 | fail | fail | stable_fail |
| V2A05 | fail | fail | stable_fail |
| V2A06 | fail | fail | stable_fail |

Sequential local runs; successful QA/turn latency and all-status wall time are separate. No statistical significance or isolated algorithm attribution is claimed.

Only labels/order are hidden. Request prompts may reveal version behavior; this is assistant-assisted auxiliary review, not independent human blind evaluation.