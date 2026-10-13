# P3 A：组件 test 正式评测

冻结运行时：`c105253026453bb203aab1186d68aae0bb10acd3`。作者已批准 d61a06a 冻结的金标准与本批次。每次100题；rule×1、llm_only×3、hybrid×3，共700条；未重跑、未筛选。所有原始状态留在分母。

| 模式/重复 | 完全正确/100 | 危险错误 | wrong_scope | safe_fail | other_error | 执行失败 | 回退 | p50/p95 秒（全部状态） |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| rule/r001 | 16 | 13 | 9 | 48 | 14 | 0 | 0 | 0.0011/0.0015 |
| llm_only/r001 | 79 | 15 | 1 | 3 | 2 | 0 | 0 | 1.2597/1.4298 |
| llm_only/r002 | 79 | 15 | 1 | 3 | 2 | 0 | 0 | 1.2742/1.5179 |
| llm_only/r003 | 79 | 15 | 1 | 3 | 2 | 0 | 0 | 1.2785/1.6775 |
| hybrid/r001 | 80 | 10 | 1 | 6 | 3 | 0 | 0 | 1.2803/1.7592 |
| hybrid/r002 | 80 | 10 | 1 | 6 | 3 | 0 | 0 | 1.2861/1.6826 |
| hybrid/r003 | 80 | 10 | 1 | 6 | 3 | 0 | 0 | 1.2854/1.6967 |

| 模式 | 正确率均值/最差 | 危险错误均值/最差（最大） |
|---|---:|---:|
| rule | 16.0%/16.0% | 13.00/13 |
| llm_only | 79.0%/79.0% | 15.00/15 |
| hybrid | 80.0%/80.0% | 10.00/10 |

| 槽位 | rule | llm_only 均值/最差 | hybrid 均值/最差 |
|---|---:|---:|---:|
| compare | 92.0% | 100.0%/100.0% | 100.0%/100.0% |
| comparison_month | 86.0% | 97.0%/97.0% | 97.0%/97.0% |
| fields | 60.0% | 88.0%/88.0% | 92.0%/92.0% |
| knowledge_requested | 95.0% | 100.0%/100.0% | 100.0%/100.0% |
| requested_field_order | 48.0% | 86.0%/86.0% | 89.0%/89.0% |
| scope | 91.0% | 99.0%/99.0% | 99.0%/99.0% |
| target_month | 72.0% | 95.0%/95.0% | 92.0%/92.0% |
| unknown_fields | 65.0% | 87.0%/87.0% | 90.0%/90.0% |
| unresolved_month | 94.0% | 96.0%/96.0% | 96.0%/96.0% |

全部冲突码计数（跨完整重复累计）：
- rule: `{}`
- llm_only: `{"field_not_in_catalog": 6}`
- hybrid: `{"field_not_in_catalog": 6, "fields_rule_fallback": 6, "mention_unanchored_kept": 15, "month_unsupported": 3, "negated_field_selected": 12, "negated_month_selected": 6, "qualifier_dropped": 24, "relative_month_recomputed": 12}`

每次额外模型调用/预算跳过：
- rule/r001: 0 / 0；证据 `evaluation\results\intent_v1_r1_test_p3_rule_r001/summary.json`。
- llm_only/r001: 100 / 0；证据 `evaluation\results\intent_v1_r1_test_p3_llm_only_r001/summary.json`。
- llm_only/r002: 100 / 0；证据 `evaluation\results\intent_v1_r1_test_p3_llm_only_r002/summary.json`。
- llm_only/r003: 100 / 0；证据 `evaluation\results\intent_v1_r1_test_p3_llm_only_r003/summary.json`。
- hybrid/r001: 100 / 0；证据 `evaluation\results\intent_v1_r1_test_p3_hybrid_r001/summary.json`。
- hybrid/r002: 100 / 0；证据 `evaluation\results\intent_v1_r1_test_p3_hybrid_r002/summary.json`。
- hybrid/r003: 100 / 0；证据 `evaluation\results\intent_v1_r1_test_p3_hybrid_r003/summary.json`。

## llm_only 危险、hybrid 无危险的逐题对照

同重复编号配对。两组模型提议可能不同；不能仅凭同题结果差异声称校验因果。下表单列 hybrid 自身原始提议经只保留 V1/V10/目录检查的确定性离线复算也危险的题；复算无模型调用，不计为新增评测或延迟样本。完整提议、分数和 SHA256 见 `evaluation/results/intent_p3_A_analysis/`。

| 题/重复 | hybrid 冲突码 | hybrid 完全正确 | 同一 hybrid 提议危险被去除 |
|---|---|---|---|
| IT021/r001 | qualifier_dropped | True | True |
| IT024/r001 | qualifier_dropped | True | True |
| IT025/r001 | qualifier_dropped | True | True |
| IT027/r001 | qualifier_dropped | False | True |
| IT028/r001 | qualifier_dropped | True | True |
| IT030/r001 | qualifier_dropped | True | True |
| IT047/r001 | relative_month_recomputed | True | True |
| IT057/r001 | month_unsupported | False | True |
| IT021/r002 | qualifier_dropped | True | True |
| IT024/r002 | qualifier_dropped | True | True |
| IT025/r002 | qualifier_dropped | True | True |
| IT027/r002 | qualifier_dropped | False | True |
| IT028/r002 | qualifier_dropped | True | True |
| IT030/r002 | qualifier_dropped | True | True |
| IT047/r002 | relative_month_recomputed | True | True |
| IT057/r002 | month_unsupported | False | True |
| IT021/r003 | qualifier_dropped | True | True |
| IT024/r003 | qualifier_dropped | True | True |
| IT025/r003 | qualifier_dropped | True | True |
| IT027/r003 | qualifier_dropped | False | True |
| IT028/r003 | qualifier_dropped | True | True |
| IT030/r003 | qualifier_dropped | True | True |
| IT047/r003 | relative_month_recomputed | True | True |
| IT057/r003 | month_unsupported | False | True |

## 同一原始提议的校验效果

| 题/重复 | 移除危险 | 原本正确反而变错 | 冲突码 |
|---|---|---|---|
| IT021/r001 | True | False | qualifier_dropped |
| IT024/r001 | True | False | qualifier_dropped |
| IT025/r001 | True | False | qualifier_dropped |
| IT027/r001 | True | False | qualifier_dropped |
| IT028/r001 | True | False | qualifier_dropped |
| IT030/r001 | True | False | qualifier_dropped |
| IT041/r001 | False | True | qualifier_dropped |
| IT044/r001 | False | True | relative_month_recomputed |
| IT047/r001 | True | False | relative_month_recomputed |
| IT049/r001 | False | True | relative_month_recomputed |
| IT057/r001 | True | False | month_unsupported |
| IT072/r001 | False | True | qualifier_dropped, negated_field_selected, negated_month_selected, fields_rule_fallback |
| IT076/r001 | False | True | negated_field_selected, negated_month_selected, fields_rule_fallback |
| IT021/r002 | True | False | qualifier_dropped |
| IT024/r002 | True | False | qualifier_dropped |
| IT025/r002 | True | False | qualifier_dropped |
| IT027/r002 | True | False | qualifier_dropped |
| IT028/r002 | True | False | qualifier_dropped |
| IT030/r002 | True | False | qualifier_dropped |
| IT041/r002 | False | True | qualifier_dropped |
| IT044/r002 | False | True | relative_month_recomputed |
| IT047/r002 | True | False | relative_month_recomputed |
| IT049/r002 | False | True | relative_month_recomputed |
| IT057/r002 | True | False | month_unsupported |
| IT072/r002 | False | True | qualifier_dropped, negated_field_selected, negated_month_selected, fields_rule_fallback |
| IT076/r002 | False | True | negated_field_selected, negated_month_selected, fields_rule_fallback |
| IT021/r003 | True | False | qualifier_dropped |
| IT024/r003 | True | False | qualifier_dropped |
| IT025/r003 | True | False | qualifier_dropped |
| IT027/r003 | True | False | qualifier_dropped |
| IT028/r003 | True | False | qualifier_dropped |
| IT030/r003 | True | False | qualifier_dropped |
| IT041/r003 | False | True | qualifier_dropped |
| IT044/r003 | False | True | relative_month_recomputed |
| IT047/r003 | True | False | relative_month_recomputed |
| IT049/r003 | False | True | relative_month_recomputed |
| IT057/r003 | True | False | month_unsupported |
| IT072/r003 | False | True | qualifier_dropped, negated_field_selected, negated_month_selected, fields_rule_fallback |
| IT076/r003 | False | True | negated_field_selected, negated_month_selected, fields_rule_fallback |

所有耗时按 nearest-rank；各次成功状态 p50/p95 和缺测数保留于 sealed summary.json，未删除失败。合同补充说明：[SCORING_AMENDMENT_01](../docs/plans/SCORING_AMENDMENT_01.md)；未改 test gold。

运行前证据：`evaluation/results/intent_p3_preflight/`。原669项离线测试通过；首次沙箱临时目录权限失败保留，改用授权工作区临时目录后通过。这是离线环境检查，正式 test 未重跑。
