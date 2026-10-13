# 第二步：4道替换题与4条补充note

P0修订草稿，待作者复核，未冻结。只列本步8项；原版不动、第一步dev保留、Agent未修改。不是提示词或单元测试示例。

## 4道替换题

### IT052 · month_resolution

**新题**：刚查到的2025年11月先放一边，请改为我刚买机器那个月的完整报告。

**受信用户**：1005

**current查询上下文**：`[{"phase": "current", "month": "2025-11"}]`

**history / previous**：`{"history": [], "previous_intent": null}`

**完整gold**：
```json
{
  "fields": [],
  "unknown_fields": [],
  "limited": false,
  "full_report": true,
  "target_month": null,
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": true
}
```

**字段全序**：`[]`

**替换说明note**：替换题：沿用原ID与month_resolution类别，替代原版报告入口不可达的无查询题。本轮已查询用户1005的2025-11记录，但题面要求购机月完整报告，未提供购机日期；“刚买”不能换算为绝对年月。target_month=null、unresolved_month=true，不用today、current月或上一目标补选购机月。

### IT053 · month_resolution

**新题**：已经查到2025年12月了；这次只列我搬家前一个月的覆盖率。

**受信用户**：1001

**current查询上下文**：`[{"phase": "current", "month": "2025-12"}]`

**history / previous**：`{"history": [], "previous_intent": null}`

**完整gold**：
```json
{
  "fields": [
    "覆盖率"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": null,
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": true
}
```

**字段全序**：`["覆盖率"]`

**替换说明note**：替换题：沿用原ID与month_resolution类别。本轮已查询用户1001的2025-12记录，覆盖率属于授权目录；“搬家前一个月”缺少搬家事件日期，不能把current查询月当搬家月。target_month=null、unresolved_month=true；这是题面参照不可换算，不是缺少查询。

### IT054 · month_resolution

**新题**：不是刚查到的2025年10月，月份换一下；只给尘盒清理这一项。

**受信用户**：1007

**current查询上下文**：`[{"phase": "current", "month": "2025-10"}]`

**history / previous**：`{"history": [], "previous_intent": null}`

**完整gold**：
```json
{
  "fields": [
    "尘盒清理"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": null,
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": true
}
```

**字段全序**：`["尘盒清理"]`

**替换说明note**：替换题：沿用原ID与month_resolution类别。本轮已查询用户1007的2025-10记录，但用户否定该月且没有给出替代月份；尘盒清理仍是肯定请求。target_month=null、unresolved_month=true，不重新采用被否定的current月，不用today或上一目标猜替代月。

### IT067 · comparison_roles

**新题**：以刚查到的2025年5月为目标，只列滤网寿命，并和我刚买机器那个月作比较。

**受信用户**：1007

**current查询上下文**：`[{"phase": "current", "month": "2025-05"}]`

**history / previous**：`{"history": [], "previous_intent": null}`

**完整gold**：
```json
{
  "fields": [
    "滤网寿命"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-05",
  "compare": true,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": true
}
```

**字段全序**：`["滤网寿命"]`

**替换说明note**：替换题：沿用原ID与comparison_roles类别。本轮已查询用户1007的2025-05记录，题面明确该月为目标；购机月未提供日期，故只将comparison_month设null，保留target_month=2025-05及compare=true，unresolved_month=true。不能把current目标月、today或上一目标误当购机基准。

## 4条仅追加note（gold及题面均未改）

### IT013

P0 审核补充：题面直接写出目录名“胶刷更换”，该项不是字段改写；保留 field_rephrase 类别，但这题的改写难度较低。本轮仅追加说明，不改题面或 gold。

### IT047

P0 审核补充：“以刚查到的这份记录为起点”容易读成上一轮情境，表述略不自然；本题无 previous 目标，2025-08 是本轮唯一 current 查询月，所以前一个月按合同为 2025-07。本轮仅追加说明，不改题面或 gold。

### IT085

P0 审核补充：未知指标按题面原文“每天耗水量”精确比较，现行合同下“每日耗水量”不在接受集合内。允许原词或预先列出的等价写法是评分合同的修订建议，可能需要作者显式确认；本轮按已批准的仅补 note 范围保留题面、gold 和接受集合，不自行变更评分规则。

### IT088

P0 审核补充：历史字段为“胶刷缠绕 / 滤网更换”，当前说“只留”却改称“滤网寿命”，前后表达存在不一致；当前明确请求优先，且当前 2025-10 目录提供“滤网寿命”，因此保留该 gold。本轮仅追加说明，不改题面或其它标注。
