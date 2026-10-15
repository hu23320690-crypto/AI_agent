# 同题版本对照

前版：service_s5_g5_seen_base_legacy_react；后版：service_s5_g5_seen_base_service_react。

未评分、缺失、报错、超时与截断保持未知，计划分母不变。

```json
{
  "knowledge": {
    "planned": 40,
    "improved": 0,
    "regressed": 0,
    "stable_pass": 0,
    "stable_fail": 0,
    "unknown": 40
  },
  "unanswerable": {
    "planned": 8,
    "improved": 0,
    "regressed": 0,
    "stable_pass": 0,
    "stable_fail": 0,
    "unknown": 8
  },
  "agent": {
    "planned": 12,
    "improved": 0,
    "regressed": 7,
    "stable_pass": 4,
    "stable_fail": 1,
    "unknown": 0
  }
}
```

| 案例 | 前版 | 后版 | 对照 |
| --- | --- | --- | --- |
| K01 | unknown | unknown | unknown |
| K02 | unknown | unknown | unknown |
| K03 | unknown | unknown | unknown |
| K04 | unknown | unknown | unknown |
| K05 | unknown | unknown | unknown |
| K06 | unknown | unknown | unknown |
| K07 | unknown | unknown | unknown |
| K08 | unknown | unknown | unknown |
| K09 | unknown | unknown | unknown |
| K10 | unknown | unknown | unknown |
| K11 | unknown | unknown | unknown |
| K12 | unknown | unknown | unknown |
| K13 | unknown | unknown | unknown |
| K14 | unknown | unknown | unknown |
| K15 | unknown | unknown | unknown |
| K16 | unknown | unknown | unknown |
| K17 | unknown | unknown | unknown |
| K18 | unknown | unknown | unknown |
| K19 | unknown | unknown | unknown |
| K20 | unknown | unknown | unknown |
| K21 | unknown | unknown | unknown |
| K22 | unknown | unknown | unknown |
| K23 | unknown | unknown | unknown |
| K24 | unknown | unknown | unknown |
| K25 | unknown | unknown | unknown |
| K26 | unknown | unknown | unknown |
| K27 | unknown | unknown | unknown |
| K28 | unknown | unknown | unknown |
| K29 | unknown | unknown | unknown |
| K30 | unknown | unknown | unknown |
| K31 | unknown | unknown | unknown |
| K32 | unknown | unknown | unknown |
| K33 | unknown | unknown | unknown |
| K34 | unknown | unknown | unknown |
| K35 | unknown | unknown | unknown |
| K36 | unknown | unknown | unknown |
| K37 | unknown | unknown | unknown |
| K38 | unknown | unknown | unknown |
| K39 | unknown | unknown | unknown |
| K40 | unknown | unknown | unknown |
| N01 | unknown | unknown | unknown |
| N02 | unknown | unknown | unknown |
| N03 | unknown | unknown | unknown |
| N04 | unknown | unknown | unknown |
| N05 | unknown | unknown | unknown |
| N06 | unknown | unknown | unknown |
| N07 | unknown | unknown | unknown |
| N08 | unknown | unknown | unknown |
| A01 | pass | pass | stable_pass |
| A02 | pass | pass | stable_pass |
| A03 | pass | fail | regressed |
| A04 | pass | fail | regressed |
| A05 | pass | fail | regressed |
| A06 | pass | fail | regressed |
| A07 | pass | fail | regressed |
| A08 | fail | fail | stable_fail |
| A09 | pass | pass | stable_pass |
| A10 | pass | pass | stable_pass |
| A11 | pass | fail | regressed |
| A12 | pass | fail | regressed |

Sequential local runs; successful QA/turn latency and all-status wall time are separate. No statistical significance or isolated algorithm attribution is claimed.

Only labels/order are hidden. Request prompts may reveal version behavior; this is assistant-assisted auxiliary review, not independent human blind evaluation.