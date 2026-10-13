# 第二步 dev × test 相似度核对

Python difflib.SequenceMatcher, character level, autojunk=False; whitespace/punctuation removed. Second view masks calendar phrases and Arabic numbers before normalizing.

精确复现第一步4000对记录后，重算本版全部4000对；双视图top3及全部配对保存在step2_checks.json。

| 新题 | 排名 | dev | 原字符 | 日期数字屏蔽 |
| --- | ---: | --- | ---: | ---: |
| IT052 | 1 | ID005 | 33.33% | 30.51% |
| IT052 | 2 | ID015 | 32.14% | 28.57% |
| IT052 | 3 | ID024 | 25.81% | 28.57% |
| IT053 | 1 | ID017 | 16.39% | 25.45% |
| IT053 | 2 | ID006 | 22.86% | 24.62% |
| IT053 | 3 | ID008 | 26.09% | 22.22% |
| IT054 | 1 | ID039 | 27.40% | 28.57% |
| IT054 | 2 | ID002 | 31.25% | 27.59% |
| IT054 | 3 | ID016 | 25.40% | 27.59% |
| IT067 | 1 | ID026 | 31.03% | 26.92% |
| IT067 | 2 | ID023 | 29.03% | 25.00% |
| IT067 | 3 | ID008 | 28.57% | 24.56% |

排名以日期数字屏蔽相似度优先、原字符相似度次之、dev ID打破平局；原字符视图top3另存JSON。

```json
{
  "pairs": 4000,
  "literal_max": 0.604651,
  "masked_max": 0.666667,
  "literal_at_least_0_80": 0,
  "masked_at_least_0_80": 0,
  "exact_normalized_query_duplicates": 0,
  "exact_masked_query_duplicates": 0
}
```

0.80 is a predeclared review flag, not an automatic leakage/proof threshold. Similarity is lexical, not semantic independence.
