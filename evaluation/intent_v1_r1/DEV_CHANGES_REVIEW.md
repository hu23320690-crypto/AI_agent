# 第一步：仅4道dev改动，待作者复核

本文件是P0作者审核清单，不是提示词few-shot或单元测试示例；test及Agent仍逐字保持原版。

## ID010 · qualifier_distractor

**原题**：2025-05只需要滤网寿命和污水仓滤网寿命。

**新题**：请把2025年二月的“基站尘盒清理”和“尘盒清理”列成两个独立条目，按引号中出现的先后排列。

**受信用户**：1002

**查询上下文**：`[{"month": "2025-02", "phase": "current"}]`

**历史**：`[]`

**上一意图**：`null`

**字段全序**：`["基站尘盒清理", "尘盒清理"]`

**完整金标准**：
```json
{
  "fields": [
    "尘盒清理"
  ],
  "unknown_fields": [
    "基站尘盒清理"
  ],
  "limited": true,
  "full_report": false,
  "target_month": "2025-02",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：要求两个独立条目且未知项在前；当前用户二月目录提供尘盒清理，但不提供带基站限定的尘盒清理，不能丢限定词合并。相对原dev及IT022更换用户、字段组合、混合顺序和句式，不使用滤网。标签由题面与CSV目录人工编制。

## ID028 · negation_correction

**原题**：2025-05不要覆盖率，只需日均清扫及滤网剩余天数。

**新题**：2025年七月这份报告，请删除主刷缠绕这一栏，输出内容限定为猫砂泼洒处理、自动回充成功率。

**受信用户**：1004

**查询上下文**：`[{"month": "2025-07", "phase": "current"}]`

**历史**：`[]`

**上一意图**：`null`

**字段全序**：`["猫砂泼洒处理", "自动回充成功率"]`

**完整金标准**：
```json
{
  "fields": [
    "猫砂泼洒处理",
    "自动回充成功率"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-07",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：删除一栏明确排除目录中存在的主刷缠绕，只保留依次列出的两个肯定请求；被排除项不进入已知或未知字段。相对原dev及IT069更换用户、全部字段和否定句式，被否定项不使用覆盖率。标签由题面与CSV目录人工编制。

## ID029 · negation_correction

**原题**：不是2025年八月，是四月；只要玩具避障率。

**新题**：撤回2025年三月那份报告的请求；更正后的月份定为2025年六月，列出胶刷缠绕、宠物毛发清理这两栏。

**受信用户**：1009

**查询上下文**：`[{"month": "2025-06", "phase": "current"}, {"month": "2025-03", "phase": "current"}]`

**历史**：`[]`

**上一意图**：`null`

**字段全序**：`["胶刷缠绕", "宠物毛发清理"]`

**完整金标准**：
```json
{
  "fields": [
    "胶刷缠绕",
    "宠物毛发清理"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-06",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：撤回明确取消三月，更正后的完整年月明确选定六月；最后一次current查询为三月不覆盖肯定更正。两栏按题面顺序选择，不比较。相对原dev及IT071更换用户、字段组合和撤回后重新指定的句式，不使用不是八月是某月模板。标签由题面与CSV目录人工编制。

## ID039 · multi_turn_reference

**原题**：同样两项换到2025年四月，保持刚才的顺序。

**新题**：刚才那三行中，只留下排在末尾的一行；报告月份沿用我上一轮选定的月份。

**受信用户**：1005

**查询上下文**：`[{"month": "2025-03", "phase": "history"}, {"month": "2025-04", "phase": "current"}]`

**历史**：`["2025年三月请把手动操作占比、定时清扫使用率、电池衰减依次列成三行。"]`

**上一意图**：`{"fields": ["手动操作占比", "定时清扫使用率", "电池衰减"], "target_month": "2025-03", "comparison_month": null, "compare": false, "limited": true}`

**字段全序**：`["电池衰减"]`

**完整金标准**：
```json
{
  "fields": [
    "电池衰减"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-03",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：末尾一行唯一指代上一轮已排序的电池衰减，限定范围从三项缩为一项；明确沿用上一轮已选三月，不能被current四月替代。相对原dev及IT097更换用户、字段组合、指代操作和月份语义，不沿用两项换月保持顺序模板。标签由用户原话、previous_intent与CSV目录人工编制。
