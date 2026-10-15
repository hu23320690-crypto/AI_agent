# 同题版本对照

前版：service_s5_g5_seen_holdout_v2_legacy_react_infra_retry1；后版：service_s5_g5_seen_holdout_v2_service_react。

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
    "regressed": 5,
    "stable_pass": 0,
    "stable_fail": 0,
    "unknown": 1
  }
}
```

| 案例 | 前版 | 后版 | 对照 |
| --- | --- | --- | --- |
| V2K01 | unknown | unknown | unknown |
| V2K02 | unknown | unknown | unknown |
| V2K03 | unknown | unknown | unknown |
| V2K04 | unknown | unknown | unknown |
| V2K05 | unknown | unknown | unknown |
| V2K06 | unknown | unknown | unknown |
| V2K07 | unknown | unknown | unknown |
| V2K08 | unknown | unknown | unknown |
| V2K09 | unknown | unknown | unknown |
| V2K10 | unknown | unknown | unknown |
| V2K11 | unknown | unknown | unknown |
| V2K12 | unknown | unknown | unknown |
| V2K13 | unknown | unknown | unknown |
| V2K14 | unknown | unknown | unknown |
| V2K15 | unknown | unknown | unknown |
| V2K16 | unknown | unknown | unknown |
| V2K17 | unknown | unknown | unknown |
| V2K18 | unknown | unknown | unknown |
| V2K19 | unknown | unknown | unknown |
| V2K20 | unknown | unknown | unknown |
| V2K21 | unknown | unknown | unknown |
| V2K22 | unknown | unknown | unknown |
| V2K23 | unknown | unknown | unknown |
| V2K24 | unknown | unknown | unknown |
| V2K25 | unknown | unknown | unknown |
| V2K26 | unknown | unknown | unknown |
| V2K27 | unknown | unknown | unknown |
| V2K28 | unknown | unknown | unknown |
| V2N01 | unknown | unknown | unknown |
| V2N02 | unknown | unknown | unknown |
| V2N03 | unknown | unknown | unknown |
| V2N04 | unknown | unknown | unknown |
| V2N05 | unknown | unknown | unknown |
| V2N06 | unknown | unknown | unknown |
| V2A01 | pass | fail | regressed |
| V2A02 | pass | fail | regressed |
| V2A03 | pass | fail | regressed |
| V2A04 | pass | fail | regressed |
| V2A05 | pass | unknown | unknown |
| V2A06 | pass | fail | regressed |

Sequential local runs; successful QA/turn latency and all-status wall time are separate. No statistical significance or isolated algorithm attribution is claimed.

Only labels/order are hidden. Request prompts may reveal version behavior; this is assistant-assisted auxiliary review, not independent human blind evaluation.