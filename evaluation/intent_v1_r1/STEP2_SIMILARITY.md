# 第二步相似度核对

Same step1 character SequenceMatcher, autojunk=False; whitespace/punctuation removed; optional calendar/Arabic-number masking.

All 40 revised dev x 100 test, before and after the step2 test changes.

Review flag only; lexical similarity does not prove semantic independence.

| 新题 | 最近dev | 原字符相似度 | 日期/数字屏蔽相似度 |
| --- | --- | ---: | ---: |
| IT052 | ID006 | 31.03% | 34.62% |
| IT053 | ID009 | 36.36% | 42.11% |
| IT054 | ID016 | 44.90% | 46.51% |
| IT067 | ID024 | 38.60% | 38.46% |

全部4000配对摘要：
```json
{
  "before": {
    "pairs": 4000,
    "literal_max": 0.604651,
    "masked_max": 0.666667,
    "literal_at_least_0_80": 0,
    "masked_at_least_0_80": 0,
    "exact_normalized_query_duplicates": 0
  },
  "after": {
    "pairs": 4000,
    "literal_max": 0.604651,
    "masked_max": 0.666667,
    "literal_at_least_0_80": 0,
    "masked_at_least_0_80": 0,
    "exact_normalized_query_duplicates": 0
  }
}
```

0.80只是复核提示阈值；无逐字/日期屏蔽完全重复不能证明无语义泄漏。保留全部配对和top20，不运行受测解析器或模型。
