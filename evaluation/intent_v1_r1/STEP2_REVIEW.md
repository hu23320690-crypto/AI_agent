# 第二步：4道替换题、4条note及IT085预列等价写法

本版是待作者复核草稿；未冻结，未运行意图解析器或模型。

## IT052 · month_resolution

**完整题面**：这轮2025年11月的记录已经查过了。请单列玩具避障率，改看我首次购入机器的那个月。

**完整上下文及gold**：
```json
{
  "id": "IT052",
  "split": "test",
  "category": "month_resolution",
  "user_id": "1006",
  "today": "2026-10-13",
  "lookups": [
    {
      "month": "2025-11",
      "phase": "current"
    }
  ],
  "history": [],
  "previous_intent": null,
  "query": "这轮2025年11月的记录已经查过了。请单列玩具避障率，改看我首次购入机器的那个月。",
  "gold": {
    "fields": [
      "玩具避障率"
    ],
    "unknown_fields": [],
    "limited": true,
    "full_report": false,
    "target_month": null,
    "compare": false,
    "comparison_month": null,
    "knowledge_requested": false,
    "unresolved_month": true
  },
  "note": "r1 替换题，原题见 intent_v1。本轮已成功查询用户1006的2025-11记录，玩具避障率来自该记录目录，因此报告分支可达。首次购机日期在题面、历史和上一意图中均未提供；购机月不是查询月或today的别称，也没有可计算偏移，故目标月不能确定。today=2026-10-13不能给出购机日期；current=2025-11只标记已查记录；previous_intent=null，没有事件锚。",
  "review_flags": [
    "r1_replacement_current_lookup_unresolved_from_query"
  ],
  "requested_field_order": [
    "玩具避障率"
  ]
}
```

**理由**：本轮已成功查询用户1006的2025-11记录，玩具避障率来自该记录目录，因此报告分支可达。首次购机日期在题面、历史和上一意图中均未提供；购机月不是查询月或today的别称，也没有可计算偏移，故目标月不能确定。today=2026-10-13不能给出购机日期；current=2025-11只标记已查记录；previous_intent=null，没有事件锚。

## IT053 · month_resolution

**完整题面**：我要搬家前一个月的地毯增压使用这一栏，输出就限定这一栏；2025年十月那份是这轮刚查到的记录。

**完整上下文及gold**：
```json
{
  "id": "IT053",
  "split": "test",
  "category": "month_resolution",
  "user_id": "1003",
  "today": "2026-10-13",
  "lookups": [
    {
      "month": "2025-10",
      "phase": "current"
    }
  ],
  "history": [],
  "previous_intent": null,
  "query": "我要搬家前一个月的地毯增压使用这一栏，输出就限定这一栏；2025年十月那份是这轮刚查到的记录。",
  "gold": {
    "fields": [
      "地毯增压使用"
    ],
    "unknown_fields": [],
    "limited": true,
    "full_report": false,
    "target_month": null,
    "compare": false,
    "comparison_month": null,
    "knowledge_requested": false,
    "unresolved_month": true
  },
  "note": "r1 替换题，原题见 intent_v1。本轮已成功查询用户1003的2025-10记录，地毯增压使用来自该记录目录，因此报告分支可达。前一个月修饰的是搬家事件而非查询月，未给搬家日期，不能把2025-10减一月当成目标；目标月不能确定。today与current均未被声明为搬家时间；previous_intent=null。缺的是事件日期，不是查询。",
  "review_flags": [
    "r1_replacement_current_lookup_unresolved_from_query"
  ],
  "requested_field_order": [
    "地毯增压使用"
  ]
}
```

**理由**：本轮已成功查询用户1003的2025-10记录，地毯增压使用来自该记录目录，因此报告分支可达。前一个月修饰的是搬家事件而非查询月，未给搬家日期，不能把2025-10减一月当成目标；目标月不能确定。today与current均未被声明为搬家时间；previous_intent=null。缺的是事件日期，不是查询。

## IT054 · month_resolution

**完整题面**：月份别沿用上一轮的月份，也别用这轮刚查到的2025年七月；水箱加水只列这一项，月份另换一个。

**完整上下文及gold**：
```json
{
  "id": "IT054",
  "split": "test",
  "category": "month_resolution",
  "user_id": "1008",
  "today": "2026-10-13",
  "lookups": [
    {
      "month": "2025-06",
      "phase": "history"
    },
    {
      "month": "2025-07",
      "phase": "current"
    }
  ],
  "history": [
    "2025年六月只列水箱加水。"
  ],
  "previous_intent": {
    "fields": [
      "水箱加水"
    ],
    "target_month": "2025-06",
    "comparison_month": null,
    "compare": false,
    "limited": true
  },
  "query": "月份别沿用上一轮的月份，也别用这轮刚查到的2025年七月；水箱加水只列这一项，月份另换一个。",
  "gold": {
    "fields": [
      "水箱加水"
    ],
    "unknown_fields": [],
    "limited": true,
    "full_report": false,
    "target_month": null,
    "compare": false,
    "comparison_month": null,
    "knowledge_requested": false,
    "unresolved_month": true
  },
  "note": "r1 替换题，原题见 intent_v1。本轮已成功查询用户1008的2025-07记录，水箱加水属于授权目录，因此报告分支可达。用户明确排除上一轮目标2025-06及current月2025-07，只说另换一个，未给新月份或方向、步长；剩余月份不唯一，故目标月不能确定。previous=2025-06与current=2025-07均已被否定；另换一个不等于上个月或下个月，today没有被指定为替代月。",
  "review_flags": [
    "r1_replacement_current_lookup_unresolved_from_query"
  ],
  "requested_field_order": [
    "水箱加水"
  ]
}
```

**理由**：本轮已成功查询用户1008的2025-07记录，水箱加水属于授权目录，因此报告分支可达。用户明确排除上一轮目标2025-06及current月2025-07，只说另换一个，未给新月份或方向、步长；剩余月份不唯一，故目标月不能确定。previous=2025-06与current=2025-07均已被否定；另换一个不等于上个月或下个月，today没有被指定为替代月。

## IT067 · comparison_roles

**完整题面**：对照基期用我第一次给机器换边刷的那个月，目标期定为2025年四月，只比较边刷磨损。

**完整上下文及gold**：
```json
{
  "id": "IT067",
  "split": "test",
  "category": "comparison_roles",
  "user_id": "1002",
  "today": "2026-10-13",
  "lookups": [
    {
      "month": "2025-04",
      "phase": "current"
    }
  ],
  "history": [],
  "previous_intent": null,
  "query": "对照基期用我第一次给机器换边刷的那个月，目标期定为2025年四月，只比较边刷磨损。",
  "gold": {
    "fields": [
      "边刷磨损"
    ],
    "unknown_fields": [],
    "limited": true,
    "full_report": false,
    "target_month": "2025-04",
    "compare": true,
    "comparison_month": null,
    "knowledge_requested": false,
    "unresolved_month": true
  },
  "note": "r1 替换题，原题见 intent_v1。本轮已成功查询用户1002的2025-04记录，边刷磨损来自该记录目录，因此报告分支可达。题面明确目标期2025-04并要求比较；首次换边刷的日期未提供，记录里的磨损状态不能推出换刷时间，故仅基准月不能确定。target/current=2025-04不代表首次换刷月；today及previous_intent=null均不能给出该事件日期。",
  "review_flags": [
    "r1_replacement_current_lookup_unresolved_from_query"
  ],
  "requested_field_order": [
    "边刷磨损"
  ]
}
```

**理由**：本轮已成功查询用户1002的2025-04记录，边刷磨损来自该记录目录，因此报告分支可达。题面明确目标期2025-04并要求比较；首次换边刷的日期未提供，记录里的磨损状态不能推出换刷时间，故仅基准月不能确定。target/current=2025-04不代表首次换刷月；today及previous_intent=null均不能给出该事件日期。

## 4条补充note（gold不变）

### IT013

P0 审核补充：题面直接写出目录名“胶刷更换”，该项不是字段改写；保留 field_rephrase 类别，但这题的改写难度较低。本轮仅追加说明，不改题面或 gold。

### IT047

P0 审核补充：“以刚查到的这份记录为起点”容易读成上一轮情境，表述略不自然；本题无 previous 目标，2025-08 是本轮唯一 current 查询月，所以前一个月按合同为 2025-07。本轮仅追加说明，不改题面或 gold。

### IT085

P0 审核补充：未知指标保留题面原词“每天耗水量”，gold 不变；依据本轮作者授权，本题 unknown_aliases 预先登记“每日耗水量”为等价写法，去除空白后接受原词或该等价写法。此规则仅用于未知字段，不接受将其映射到目录字段“水箱使用率”，也不放宽已知字段的精确匹配。

### IT088

P0 审核补充：历史字段为“胶刷缠绕 / 滤网更换”，当前说“只留”却改称“滤网寿命”，前后表达存在不一致；当前明确请求优先，且当前 2025-10 目录提供“滤网寿命”，因此保留该 gold。本轮仅追加说明，不改题面或其它标注。

## SCORING新增规则

未知字段在去除空白后，与题面原词或该题 unknown_aliases 中列出的等价写法一致即可。

只给IT085增加 unknown_aliases=["每日耗水量"]。接受未知别名时保持原未知项在混排全序中的位置；已知字段精确匹配不变。

## 基线与限制

按作者要求原样提交；任务开始时目录已包含第二步草稿。此提交不是纯第一步快照，另与原冻结test及第一步test字节核对。

CSV全部10用户均已在dev出现，无法使用全新真实用户；4题用户+字段组合全新，4字段在dev题面/历史/上一意图/gold均零提及，句式不复刻dev。

相对执行基线95/96整行一致，仅IT085获授权note/alias有差异；相对第一步原test92/96整行一致，仅4条note及IT085 alias有差异。其余96题受保护JSON值全部逐字节一致。
