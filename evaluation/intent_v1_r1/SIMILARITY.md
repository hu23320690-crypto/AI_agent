# 第一步 dev/test 相似度核对

Python difflib.SequenceMatcher, character level, autojunk=False; whitespace/punctuation removed. Second view masks calendar phrases and Arabic numbers before normalizing.

All 40 dev x 100 unchanged test = 4000 pairs, before and after; no baseline parser, model, or extra corpora in step 1.

0.80 is a predeclared review flag, not an automatic leakage/proof threshold. Similarity is lexical, not semantic independence.

| 原审核指出的配对 | 原字符相似度 | 新字符相似度 | 原日期数字屏蔽相似度 | 新日期数字屏蔽相似度 |
| --- | ---: | ---: | ---: | ---: |
| ID010 / IT022 | 66.67% | 20.90% | 68.18% | 22.58% |
| ID028 / IT069 | 66.67% | 23.73% | 75.68% | 18.87% |
| ID029 / IT071 | 66.67% | 34.78% | 61.11% | 28.07% |
| ID039 / IT097 | 73.91% | 10.53% | 76.92% | 11.32% |

全部4000配对的摘要：
```json
{
  "before": {
    "pairs": 4000,
    "literal_max": 0.73913,
    "masked_max": 0.769231,
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

新dev仍可能与其它同类别test具有词汇相似；完整top20与全部配对在JSON中，不能据上述四对降低就宣称没有语义泄漏。只复核字符串、模板近似与来源身份，不运行任何意图解析器或模型。
