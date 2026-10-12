# intent_v1 test 金标准审核清单（100条）

P0候选，等待项目作者逐项审核。不是提示词示例、开发参考或P1/P2可用资料。字段目录由冻结CSV及本题lookups动态生成。已确认V8无有效previous/current锚不使用today猜月。

每条给出完整题面、受信身份、查询上下文、历史、上一意图、合并字段顺序与全部九槽金标准；金标理由和审核旗标一并保留。无数据月份合法不等于可输出数字。

## IT001 · field_rephrase

**问题**：把2025年1月主刷还能撑几天放在前面，再列平均每天清扫的面积，报告就这两项。

**受信用户**：1001；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-01", "phase": "current"}]`

**动态字段目录**：`["覆盖率", "日均清扫", "漏扫区域", "主刷寿命", "HEPA滤网"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["主刷寿命", "日均清扫"]`

**金标准**：
```json
{
  "fields": [
    "主刷寿命",
    "日均清扫"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-01",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：主刷可用天数对应主刷寿命；每日平均清扫面积对应日均清扫。按用户提及顺序输出。

**审核旗标**：`[]`

## IT002 · field_rephrase

**问题**：2025-03的记录里，过滤网离到期还有多少天？也列一下扫到的区域占比。只给这两个数。

**受信用户**：1007；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-03", "phase": "current"}]`

**动态字段目录**：`["覆盖率", "日均清扫", "滤网寿命", "尘盒清理"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["滤网寿命", "覆盖率"]`

**金标准**：
```json
{
  "fields": [
    "滤网寿命",
    "覆盖率"
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

**理由**：过滤网剩余可用天数与滤网寿命同指标；扫到区域占比与覆盖率同指标。

**审核旗标**：`[]`

## IT003 · field_rephrase

**问题**：我想看2025年2月躲开障碍物的成功比例，给这一项的记录就行。

**受信用户**：1008；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-02", "phase": "current"}]`

**动态字段目录**：`["覆盖率", "餐桌区域漏扫", "避障成功率", "主刷磨损", "水箱加水"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["避障成功率"]`

**金标准**：
```json
{
  "fields": [
    "避障成功率"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-02",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：躲开障碍物的成功比例对应避障成功率，不要求失败次数或处理建议。

**审核旗标**：`[]`

## IT004 · field_rephrase

**问题**：请从2025年12月取出跨楼层操作做成功的比例，单独列出来。

**受信用户**：1006；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-12", "phase": "current"}]`

**动态字段目录**：`["跨楼层成功率", "玩具避障率", "边刷寿命", "集尘袋消耗"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["跨楼层成功率"]`

**金标准**：
```json
{
  "fields": [
    "跨楼层成功率"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-12",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：跨楼层成功比例对应该月真实目录中的跨楼层成功率。不得替换成较早月份的失败次数。

**审核旗标**：`[]`

## IT005 · field_rephrase

**问题**：2025-08那份数据，我要边刷磨掉了多少的状态，以及遇到障碍没躲开的次数，按这个顺序列。

**受信用户**：1002；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-08", "phase": "current"}]`

**动态字段目录**：`["覆盖率", "避障失败", "边刷磨损", "尘盒清理"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["边刷磨损", "避障失败"]`

**金标准**：
```json
{
  "fields": [
    "边刷磨损",
    "避障失败"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-08",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：边刷磨损状态与避障失败次数是目录中的不同指标；措辞改写不能互换成寿命或成功率。

**审核旗标**：`[]`

## IT006 · field_rephrase

**问题**：2025年10月只看两个指标：胶刷被头发缠住的程度、机器自己回去充电的成功比例。

**受信用户**：1009；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-10", "phase": "current"}]`

**动态字段目录**：`["宠物毛发清理", "自动回充成功率", "胶刷缠绕", "滤网寿命"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["胶刷缠绕", "自动回充成功率"]`

**金标准**：
```json
{
  "fields": [
    "胶刷缠绕",
    "自动回充成功率"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-10",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：胶刷缠绕程度对应胶刷缠绕；自主回充成功比例对应自动回充成功率。

**审核旗标**：`[]`

## IT007 · field_rephrase

**问题**：把2025年5月胶刷还可以用多少天和地毯增压开了几次列成两行即可。

**受信用户**：1003；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-05", "phase": "current"}]`

**动态字段目录**：`["毛发清理", "地毯增压使用", "胶刷寿命", "尘盒清理"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["胶刷寿命", "地毯增压使用"]`

**金标准**：
```json
{
  "fields": [
    "胶刷寿命",
    "地毯增压使用"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-05",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：胶刷剩余可用天数对应胶刷寿命；地毯增压开启次数对应地毯增压使用。

**审核旗标**：`[]`

## IT008 · field_rephrase

**问题**：2025-04只摘出由我手动操作的比例，以及水箱被使用的比例。

**受信用户**：1005；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-04", "phase": "current"}]`

**动态字段目录**：`["手动操作占比", "定时清扫使用率", "电池衰减", "水箱使用率"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["手动操作占比", "水箱使用率"]`

**金标准**：
```json
{
  "fields": [
    "手动操作占比",
    "水箱使用率"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-04",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：手动操作比例对应手动操作占比；水箱使用比例对应水箱使用率，不询问加水频率。

**审核旗标**：`[]`

## IT009 · field_rephrase

**问题**：2025年11月帮我列人工辅助清扫发生几次，还有电池容量衰退的百分比。只要这两栏。

**受信用户**：1010；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-11", "phase": "current"}]`

**动态字段目录**：`["覆盖率", "手动辅助清扫", "定时清扫使用率", "电池衰减", "边刷寿命"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["手动辅助清扫", "电池衰减"]`

**金标准**：
```json
{
  "fields": [
    "手动辅助清扫",
    "电池衰减"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-11",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：人工辅助清扫频次对应手动辅助清扫；电池容量衰退百分比对应电池衰减，不推断续航。

**审核旗标**：`[]`

## IT010 · field_rephrase

**问题**：2025年6月这条记录，HEPA那张滤网还剩多少比例可用？报告列这一项即可。

**受信用户**：1001；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-06", "phase": "current"}]`

**动态字段目录**：`["覆盖率", "日均清扫", "漏扫区域", "主刷寿命", "HEPA滤网"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["HEPA滤网"]`

**金标准**：
```json
{
  "fields": [
    "HEPA滤网"
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

**理由**：该月HEPA滤网条目的值是剩余比例；用户保留HEPA限定且只请求此指标。

**审核旗标**：`[]`

## IT011 · field_rephrase

**问题**：我只要2025-09的猫砂洒出来以后处理了几次，以及过滤网还剩几天能用。

**受信用户**：1004；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-09", "phase": "current"}]`

**动态字段目录**：`["猫砂泼洒处理", "自动回充成功率", "主刷缠绕", "滤网寿命"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["猫砂泼洒处理", "滤网寿命"]`

**金标准**：
```json
{
  "fields": [
    "猫砂泼洒处理",
    "滤网寿命"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-09",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：猫砂洒出后的处理次数对应猫砂泼洒处理；过滤网剩余天数对应此月滤网寿命。

**审核旗标**：`[]`

## IT012 · field_rephrase

**问题**：2025年7月集尘袋用了多少个，单独做一个数据项给我。

**受信用户**：1006；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-07", "phase": "current"}]`

**动态字段目录**：`["跨楼层失败", "玩具避障率", "边刷更换", "集尘袋消耗"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["集尘袋消耗"]`

**金标准**：
```json
{
  "fields": [
    "集尘袋消耗"
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

**理由**：集尘袋使用数量与集尘袋消耗指同一记录指标，不要求集尘袋容量。

**审核旗标**：`[]`

## IT013 · field_rephrase

**问题**：2025-01先列毛发清理的完成比例，再列胶刷更换这一栏记的状态或剩余时间，就这两项。

**受信用户**：1003；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-01", "phase": "current"}]`

**动态字段目录**：`["毛发清理", "地毯增压使用", "胶刷更换", "尘盒容量"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["毛发清理", "胶刷更换"]`

**金标准**：
```json
{
  "fields": [
    "毛发清理",
    "胶刷更换"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-01",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：毛发清理完成比例取毛发清理；请求胶刷更换栏的原始记录信息，不推断是否曾实际更换，也不能改为胶刷寿命。

**审核旗标**：`[]`

## IT014 · field_rephrase

**问题**：请提取2025年3月餐桌区域每天漏掉没扫的次数，只给这一栏。

**受信用户**：1008；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-03", "phase": "current"}]`

**动态字段目录**：`["覆盖率", "餐桌区域漏扫", "避障成功率", "主刷磨损", "水箱加水"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["餐桌区域漏扫"]`

**金标准**：
```json
{
  "fields": [
    "餐桌区域漏扫"
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

**理由**：餐桌区域漏扫频次对应目录中的餐桌区域漏扫，保留餐桌区域限定。

**审核旗标**：`[]`

## IT015 · field_rephrase

**问题**：2025年8月只查尘盒隔几天清空一次，其他数据不用展开。

**受信用户**：1007；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-08", "phase": "current"}]`

**动态字段目录**：`["覆盖率", "日均清扫", "滤网寿命", "尘盒清理"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["尘盒清理"]`

**金标准**：
```json
{
  "fields": [
    "尘盒清理"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-08",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：尘盒清空间隔与尘盒清理为同指标；不请求尘盒容积或清洁方法。

**审核旗标**：`[]`

## IT016 · field_rephrase

**问题**：2025-02这份数据只摘出尝试使用定时清扫的频次。

**受信用户**：1005；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-02", "phase": "current"}]`

**动态字段目录**：`["手动操作占比", "定时清扫尝试使用", "电池衰减"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["定时清扫尝试使用"]`

**金标准**：
```json
{
  "fields": [
    "定时清扫尝试使用"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-02",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：该用户此月目录有定时清扫尝试使用而没有定时清扫使用率，保留尝试的阶段语义。

**审核旗标**：`[]`

## IT017 · field_rephrase

**问题**：请给我2025年3月第一次激活水箱的使用记录，报告仅列这个指标。

**受信用户**：1005；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-03", "phase": "current"}]`

**动态字段目录**：`["手动操作占比", "定时清扫使用率", "电池衰减", "水箱首次激活"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["水箱首次激活"]`

**金标准**：
```json
{
  "fields": [
    "水箱首次激活"
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

**理由**：第一次激活水箱与水箱首次激活为同事件指标，不替换成水箱使用率。

**审核旗标**：`[]`

## IT018 · field_rephrase

**问题**：2025-04只把主刷被毛发绕住的严重程度列给我。

**受信用户**：1004；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-04", "phase": "current"}]`

**动态字段目录**：`["猫砂泼洒处理", "自动回充成功率", "主刷缠绕", "滤网寿命"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["主刷缠绕"]`

**金标准**：
```json
{
  "fields": [
    "主刷缠绕"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-04",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：主刷缠绕程度对应主刷缠绕，保留主刷部件限定，不请求寿命或处理建议。

**审核旗标**：`[]`

## IT019 · field_rephrase

**问题**：我要2025年9月没清扫到的是哪些地方这一项，按记录写出来即可。

**受信用户**：1001；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-09", "phase": "current"}]`

**动态字段目录**：`["覆盖率", "日均清扫", "漏扫区域", "主刷寿命", "HEPA滤网"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["漏扫区域"]`

**金标准**：
```json
{
  "fields": [
    "漏扫区域"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-09",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：未清扫到的位置对应漏扫区域，而非总体覆盖比例。只请求位置指标。

**审核旗标**：`[]`

## IT020 · field_rephrase

**问题**：2025年12月水箱一天补几回水？我只想提取记录里的这项频率。

**受信用户**：1008；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-12", "phase": "current"}]`

**动态字段目录**：`["覆盖率", "避障成功率", "主刷寿命", "水箱加水"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["水箱加水"]`

**金标准**：
```json
{
  "fields": [
    "水箱加水"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-12",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：水箱补水频率与水箱加水为同指标，不扩展到水箱使用率或补水建议。

**审核旗标**：`[]`

## IT021 · qualifier_distractor

**问题**：2025年2月只列厨房覆盖率这一栏。

**受信用户**：1001；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-02", "phase": "current"}]`

**动态字段目录**：`["覆盖率", "日均清扫", "漏扫区域", "主刷寿命", "HEPA滤网"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["厨房覆盖率"]`

**金标准**：
```json
{
  "fields": [],
  "unknown_fields": [
    "厨房覆盖率"
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

**理由**：授权目录只有整体覆盖率，没有厨房范围的覆盖率；保留完整指标名为未知。

**审核旗标**：`[]`

## IT022 · qualifier_distractor

**问题**：2025-04报告先列滤网寿命，再列污水仓滤网寿命，仅这两个。

**受信用户**：1007；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-04", "phase": "current"}]`

**动态字段目录**：`["覆盖率", "日均清扫", "滤网寿命", "尘盒清理"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["滤网寿命", "污水仓滤网寿命"]`

**金标准**：
```json
{
  "fields": [
    "滤网寿命"
  ],
  "unknown_fields": [
    "污水仓滤网寿命"
  ],
  "limited": true,
  "full_report": false,
  "target_month": "2025-04",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：通用滤网寿命存在；污水仓部件限定的滤网寿命不存在，不合并两项。

**审核旗标**：`[]`

## IT023 · qualifier_distractor

**问题**：帮我单独提取2025年5月基站胶刷缠绕的记录。

**受信用户**：1009；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-05", "phase": "current"}]`

**动态字段目录**：`["宠物毛发清理", "自动回充成功率", "胶刷缠绕", "滤网寿命"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["基站胶刷缠绕"]`

**金标准**：
```json
{
  "fields": [],
  "unknown_fields": [
    "基站胶刷缠绕"
  ],
  "limited": true,
  "full_report": false,
  "target_month": "2025-05",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：目录胶刷缠绕没有基站范围限定；基站胶刷是不同部件，不丢弃限定词。

**审核旗标**：`[]`

## IT024 · qualifier_distractor

**问题**：2025年6月只给餐桌区域覆盖率，不用其他指标。

**受信用户**：1008；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-06", "phase": "current"}]`

**动态字段目录**：`["覆盖率", "餐桌区域漏扫", "避障成功率", "主刷磨损", "水箱加水"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["餐桌区域覆盖率"]`

**金标准**：
```json
{
  "fields": [],
  "unknown_fields": [
    "餐桌区域覆盖率"
  ],
  "limited": true,
  "full_report": false,
  "target_month": "2025-06",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：餐桌区域漏扫与整体覆盖率均存在，但不能拼接或反推餐桌区域覆盖率。

**审核旗标**：`[]`

## IT025 · qualifier_distractor

**问题**：提取2025-07的遥控器电池衰减，一项就够。

**受信用户**：1010；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-07", "phase": "current"}]`

**动态字段目录**：`["覆盖率", "手动辅助清扫", "定时清扫使用率", "电池衰减", "边刷寿命"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["遥控器电池衰减"]`

**金标准**：
```json
{
  "fields": [],
  "unknown_fields": [
    "遥控器电池衰减"
  ],
  "limited": true,
  "full_report": false,
  "target_month": "2025-07",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：目录电池衰减指机器人记录；没有遥控器电池衰减，不能丢弃遥控器限定。

**审核旗标**：`[]`

## IT026 · qualifier_distractor

**问题**：2025年8月请按顺序列玩具避障率和充电线避障率。

**受信用户**：1006；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-08", "phase": "current"}]`

**动态字段目录**：`["跨楼层失败", "玩具避障率", "边刷更换", "集尘袋消耗"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["玩具避障率", "充电线避障率"]`

**金标准**：
```json
{
  "fields": [
    "玩具避障率"
  ],
  "unknown_fields": [
    "充电线避障率"
  ],
  "limited": true,
  "full_report": false,
  "target_month": "2025-08",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：玩具避障率有记录；充电线避障率没有记录，不能用玩具指标代替。

**审核旗标**：`[]`

## IT027 · qualifier_distractor

**问题**：我只想看2025年9月湿拖模式自动回充成功率。

**受信用户**：1004；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-09", "phase": "current"}]`

**动态字段目录**：`["猫砂泼洒处理", "自动回充成功率", "主刷缠绕", "滤网寿命"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["湿拖模式自动回充成功率"]`

**金标准**：
```json
{
  "fields": [],
  "unknown_fields": [
    "湿拖模式自动回充成功率"
  ],
  "limited": true,
  "full_report": false,
  "target_month": "2025-09",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：目录有自动回充成功率但没有湿拖模式分组指标，不忽略模式限定。

**审核旗标**：`[]`

## IT028 · qualifier_distractor

**问题**：2025-10只列前边刷寿命和后边刷寿命这两项。

**受信用户**：1002；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-10", "phase": "current"}]`

**动态字段目录**：`["覆盖率", "避障失败", "边刷寿命", "尘盒清理"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["前边刷寿命", "后边刷寿命"]`

**金标准**：
```json
{
  "fields": [],
  "unknown_fields": [
    "前边刷寿命",
    "后边刷寿命"
  ],
  "limited": true,
  "full_report": false,
  "target_month": "2025-10",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：目录仅有不区分前后的边刷寿命，两项带方位的部件指标均未知，不能去重成通用寿命。

**审核旗标**：`[]`

## IT029 · qualifier_distractor

**问题**：我要2025年11月HEPA滤网PM2.5过滤效率的报告项，只列这个指标。

**受信用户**：1001；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-11", "phase": "current"}]`

**动态字段目录**：`["覆盖率", "日均清扫", "主刷寿命", "HEPA滤网"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["HEPA滤网PM2.5过滤效率"]`

**金标准**：
```json
{
  "fields": [],
  "unknown_fields": [
    "HEPA滤网PM2.5过滤效率"
  ],
  "limited": true,
  "full_report": false,
  "target_month": "2025-11",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：目录HEPA滤网记录剩余比例，不等于PM2.5过滤效率；不能因部件名包含而接受映射。

**审核旗标**：`[]`

## IT030 · qualifier_distractor

**问题**：2025年12月请单列卧室手动操作占比。

**受信用户**：1005；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-12", "phase": "current"}]`

**动态字段目录**：`["手动操作占比", "定时清扫使用率", "电池衰减", "水箱使用率"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["卧室手动操作占比"]`

**金标准**：
```json
{
  "fields": [],
  "unknown_fields": [
    "卧室手动操作占比"
  ],
  "limited": true,
  "full_report": false,
  "target_month": "2025-12",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：目录只有总体手动操作占比，卧室范围的占比未提供。

**审核旗标**：`[]`

## IT031 · unknown_field

**问题**：2025-02报告只需要电费金额这一个数据项。

**受信用户**：1003；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-02", "phase": "current"}]`

**动态字段目录**：`["毛发清理", "地毯增压使用", "胶刷更换", "尘盒容量"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["电费金额"]`

**金标准**：
```json
{
  "fields": [],
  "unknown_fields": [
    "电费金额"
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

**理由**：该查询目录没有电费金额；未知费用指标不由清扫或耗材指标代替。

**审核旗标**：`[]`

## IT032 · unknown_field

**问题**：从2025年5月取噪声峰值，我只要这一个数值指标。

**受信用户**：1007；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-05", "phase": "current"}]`

**动态字段目录**：`["覆盖率", "日均清扫", "滤网寿命", "尘盒清理"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["噪声峰值"]`

**金标准**：
```json
{
  "fields": [],
  "unknown_fields": [
    "噪声峰值"
  ],
  "limited": true,
  "full_report": false,
  "target_month": "2025-05",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：授权目录没有噪声峰值，保持用户具体指标名为未知。

**审核旗标**：`[]`

## IT033 · unknown_field

**问题**：2025年7月只列储水温度和水箱加水，顺序照我说的来。

**受信用户**：1008；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-07", "phase": "current"}]`

**动态字段目录**：`["覆盖率", "餐桌区域漏扫", "避障成功率", "主刷磨损", "水箱加水"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["储水温度", "水箱加水"]`

**金标准**：
```json
{
  "fields": [
    "水箱加水"
  ],
  "unknown_fields": [
    "储水温度"
  ],
  "limited": true,
  "full_report": false,
  "target_month": "2025-07",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：储水温度未知，水箱加水是已有频次指标；已知与未知各自按提及顺序记录，不因水箱关联混同。

**审核旗标**：`[]`

## IT034 · unknown_field

**问题**：2025-08这条记录只查路线长度。

**受信用户**：1004；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-08", "phase": "current"}]`

**动态字段目录**：`["猫砂泼洒处理", "自动回充成功率", "主刷缠绕", "滤网更换"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["路线长度"]`

**金标准**：
```json
{
  "fields": [],
  "unknown_fields": [
    "路线长度"
  ],
  "limited": true,
  "full_report": false,
  "target_month": "2025-08",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：目录没有路线长度，不能用清扫频次、覆盖率等相关统计替代。

**审核旗标**：`[]`

## IT035 · unknown_field

**问题**：2025年1月给我网络断连次数这一项即可。

**受信用户**：1005；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-01", "phase": "current"}]`

**动态字段目录**：`["手动操作占比", "电池衰减"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["网络断连次数"]`

**金标准**：
```json
{
  "fields": [],
  "unknown_fields": [
    "网络断连次数"
  ],
  "limited": true,
  "full_report": false,
  "target_month": "2025-01",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：网络断连次数不在此月此用户字段目录中，保持未知。

**审核旗标**：`[]`

## IT036 · unknown_field

**问题**：2025年4月的报告仅摘出地图重建次数和集尘袋消耗。

**受信用户**：1006；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-04", "phase": "current"}]`

**动态字段目录**：`["跨楼层失败", "玩具避障率", "边刷寿命", "集尘袋消耗"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["地图重建次数", "集尘袋消耗"]`

**金标准**：
```json
{
  "fields": [
    "集尘袋消耗"
  ],
  "unknown_fields": [
    "地图重建次数"
  ],
  "limited": true,
  "full_report": false,
  "target_month": "2025-04",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：地图重建次数没有记录，集尘袋消耗有记录；不扩展到跨楼层事件。

**审核旗标**：`[]`

## IT037 · unknown_field

**问题**：2025-03只给累计运行时长，不要展开报告。

**受信用户**：1002；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-03", "phase": "current"}]`

**动态字段目录**：`["覆盖率", "避障失败", "边刷磨损", "尘盒清理"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["累计运行时长"]`

**金标准**：
```json
{
  "fields": [],
  "unknown_fields": [
    "累计运行时长"
  ],
  "limited": true,
  "full_report": false,
  "target_month": "2025-03",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：累计运行时长不在授权目录中；时间类统计不能映射为尘盒清理间隔。

**审核旗标**：`[]`

## IT038 · unknown_field

**问题**：我要2025年6月的驱动轮转速和固件更新次数，报告只放这两项。

**受信用户**：1009；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-06", "phase": "current"}]`

**动态字段目录**：`["宠物毛发清理", "自动回充成功率", "胶刷缠绕", "滤网更换"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["驱动轮转速", "固件更新次数"]`

**金标准**：
```json
{
  "fields": [],
  "unknown_fields": [
    "驱动轮转速",
    "固件更新次数"
  ],
  "limited": true,
  "full_report": false,
  "target_month": "2025-06",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：两个具体指标均不在授权目录中，按提及顺序保留原名，不映射到胶刷或回充指标。

**审核旗标**：`[]`

## IT039 · month_resolution

**问题**：我查的是 2025-09 这一期，麻烦单独列电池衰减。

**受信用户**：1005；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-09", "phase": "current"}]`

**动态字段目录**：`["手动操作占比", "定时清扫使用率", "电池衰减", "水箱首次激活"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["电池衰减"]`

**金标准**：
```json
{
  "fields": [
    "电池衰减"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-09",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：ISO 绝对月份明确，字段只列电池衰减，不从 today 取年份。

**审核旗标**：`[]`

## IT040 · month_resolution

**问题**：把二〇二五年五月的自动回充成功率单独给我。

**受信用户**：1004；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-05", "phase": "current"}]`

**动态字段目录**：`["猫砂泼洒处理", "自动回充成功率", "主刷缠绕", "滤网寿命"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["自动回充成功率"]`

**金标准**：
```json
{
  "fields": [
    "自动回充成功率"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-05",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：中文逐位年份二〇二五与五月唯一对应 2025-05。

**审核旗标**：`[]`

## IT041 · month_resolution

**问题**：只取 2025 年十一月的玩具避障率，我不需要其它项。

**受信用户**：1006；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-11", "phase": "current"}]`

**动态字段目录**：`["跨楼层失败", "玩具避障率", "边刷寿命", "集尘袋消耗"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["玩具避障率"]`

**金标准**：
```json
{
  "fields": [
    "玩具避障率"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-11",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：十一月是 11 月，显式年份 2025；范围是只列。

**审核旗标**：`[]`

## IT042 · month_resolution

**问题**：把月份换到同年三月，只要滤网寿命。

**受信用户**：1007；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-10", "phase": "history"}, {"month": "2025-03", "phase": "current"}]`

**动态字段目录**：`["覆盖率", "日均清扫", "滤网寿命", "尘盒清理"]`

**历史用户原话**：`["上一轮只列 2025 年十月的滤网寿命。"]`

**上一意图**：`{"fields": ["滤网寿命"], "target_month": "2025-10", "comparison_month": null, "compare": false, "limited": true}`

**请求字段全序**：`["滤网寿命"]`

**金标准**：
```json
{
  "fields": [
    "滤网寿命"
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

**理由**：同年继承上一轮目标的 2025 年，月份由本轮三月明确替换。

**审核旗标**：`[]`

## IT043 · month_resolution

**问题**：这回只列六月的日均清扫。

**受信用户**：1001；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-02", "phase": "history"}, {"month": "2025-06", "phase": "current"}]`

**动态字段目录**：`["覆盖率", "日均清扫", "漏扫区域", "主刷寿命", "HEPA滤网"]`

**历史用户原话**：`["先看 2025 年二月的日均清扫这一项。"]`

**上一意图**：`{"fields": ["日均清扫"], "target_month": "2025-02", "comparison_month": null, "compare": false, "limited": true}`

**请求字段全序**：`["日均清扫"]`

**金标准**：
```json
{
  "fields": [
    "日均清扫"
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

**理由**：裸月六月沿用有效上一轮目标年份 2025，不取 today 的 2026。

**审核旗标**：`[]`

## IT044 · month_resolution

**问题**：翻到下个月，仍然只列避障成功率。

**受信用户**：1008；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-07", "phase": "history"}, {"month": "2025-08", "phase": "current"}]`

**动态字段目录**：`["覆盖率", "餐桌区域漏扫", "避障成功率", "主刷磨损", "水箱加水"]`

**历史用户原话**：`["只列 2025 年七月的避障成功率。"]`

**上一意图**：`{"fields": ["避障成功率"], "target_month": "2025-07", "comparison_month": null, "compare": false, "limited": true}`

**请求字段全序**：`["避障成功率"]`

**金标准**：
```json
{
  "fields": [
    "避障成功率"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-08",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：下个月以 previous_intent.target_month=2025-07 为锚，得到 2025-08。

**审核旗标**：`[]`

## IT045 · month_resolution

**问题**：退回上个月，只看手动辅助清扫。

**受信用户**：1010；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-11", "phase": "history"}, {"month": "2025-10", "phase": "current"}]`

**动态字段目录**：`["覆盖率", "手动辅助清扫", "定时清扫使用率", "电池衰减", "边刷寿命"]`

**历史用户原话**：`["十一月报告里只列手动辅助清扫。"]`

**上一意图**：`{"fields": ["手动辅助清扫"], "target_month": "2025-11", "comparison_month": null, "compare": false, "limited": true}`

**请求字段全序**：`["手动辅助清扫"]`

**金标准**：
```json
{
  "fields": [
    "手动辅助清扫"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-10",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：上个月由 2025-11 减一个月，是 2025-10；字段显式指定。

**审核旗标**：`[]`

## IT046 · month_resolution

**问题**：前一个月的地毯增压使用也给我一行就好。

**受信用户**：1003；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-06", "phase": "history"}, {"month": "2025-05", "phase": "current"}]`

**动态字段目录**：`["毛发清理", "地毯增压使用", "胶刷更换", "尘盒容量", "胶刷寿命", "尘盒清理"]`

**历史用户原话**：`["先看 2025-06 的地毯增压使用。"]`

**上一意图**：`{"fields": ["地毯增压使用"], "target_month": "2025-06", "comparison_month": null, "compare": false, "limited": true}`

**请求字段全序**：`["地毯增压使用"]`

**金标准**：
```json
{
  "fields": [
    "地毯增压使用"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-05",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：前一个月从上一轮六月目标回退至五月；一行就好表示只列字段。

**审核旗标**：`[]`

## IT047 · month_resolution

**问题**：以刚查到的这份记录为起点，前一个月只列尘盒清理。

**受信用户**：1007；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-08", "phase": "current"}]`

**动态字段目录**：`["覆盖率", "日均清扫", "滤网寿命", "尘盒清理"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["尘盒清理"]`

**金标准**：
```json
{
  "fields": [
    "尘盒清理"
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

**理由**：没有 previous_intent，但唯一 current 查询月 2025-08 是有效锚，前一个月=2025-07。selector only：目标未查询，不授权新增查询或交付该月数字。

**审核旗标**：`["selector_target_not_currently_fetched"]`

## IT048 · month_resolution

**问题**：从上一轮的目标往后一个月，只给覆盖率。

**受信用户**：1002；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-05", "phase": "history"}, {"month": "2025-06", "phase": "current"}]`

**动态字段目录**：`["覆盖率", "避障失败", "边刷寿命", "尘盒清理", "边刷磨损"]`

**历史用户原话**：`["我上一轮要的是 2025 年五月的覆盖率。"]`

**上一意图**：`{"fields": ["覆盖率"], "target_month": "2025-05", "comparison_month": null, "compare": false, "limited": true}`

**请求字段全序**：`["覆盖率"]`

**金标准**：
```json
{
  "fields": [
    "覆盖率"
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

**理由**：明指上一轮目标，锚为 previous 的五月，不以新 current 六月再加一个月。

**审核旗标**：`[]`

## IT049 · month_resolution

**问题**：继续下一月，只保留主刷寿命。

**受信用户**：1001；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-12", "phase": "history"}, {"month": "2026-01", "phase": "current"}]`

**动态字段目录**：`["覆盖率", "日均清扫", "主刷寿命", "HEPA滤网"]`

**历史用户原话**：`["只列 2025-12 的主刷寿命。"]`

**上一意图**：`{"fields": ["主刷寿命"], "target_month": "2025-12", "comparison_month": null, "compare": false, "limited": true}`

**请求字段全序**：`["主刷寿命"]`

**金标准**：
```json
{
  "fields": [
    "主刷寿命"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2026-01",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：十二月下一月跨年到 2026-01；该月无 CSV 行不改变用户目标。字段目录由已授权历史十二月记录提供。

**审核旗标**：`["target_lookup_not_found"]`

## IT050 · month_resolution

**问题**：回到前一个月，只列覆盖率即可。

**受信用户**：1007；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-01", "phase": "history"}, {"month": "2024-12", "phase": "current"}]`

**动态字段目录**：`["覆盖率", "日均清扫", "滤网寿命", "尘盒清理"]`

**历史用户原话**：`["一月那期是 2025 年，刚才只查覆盖率。"]`

**上一意图**：`{"fields": ["覆盖率"], "target_month": "2025-01", "comparison_month": null, "compare": false, "limited": true}`

**请求字段全序**：`["覆盖率"]`

**金标准**：
```json
{
  "fields": [
    "覆盖率"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2024-12",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：2025-01 向前一个月是 2024-12，数据缺失不能把目标改回 2025-01。字段目录来自授权历史记录。

**审核旗标**：`["target_lookup_not_found"]`

## IT051 · month_resolution

**问题**：现在只问二月的自动回充成功率。

**受信用户**：1004；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-12", "phase": "history"}, {"month": "2026-02", "phase": "current"}]`

**动态字段目录**：`["猫砂泼洒处理", "自动回充成功率", "主刷寿命", "滤网寿命"]`

**历史用户原话**：`["已经换到 2026 年一月了，仍然只看自动回充成功率。"]`

**上一意图**：`{"fields": ["自动回充成功率"], "target_month": "2026-01", "comparison_month": null, "compare": false, "limited": true}`

**请求字段全序**：`["自动回充成功率"]`

**金标准**：
```json
{
  "fields": [
    "自动回充成功率"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2026-02",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：裸月二月继承上一轮绝对目标 2026-01 的年份，即 2026-02；授权目录可来自 2025-12，不能反过来把历史年份当目标年份。

**审核旗标**：`["target_lookup_not_found"]`

## IT052 · month_resolution

**问题**：请给上个月的完整报告。

**受信用户**：1005；**today**：2026-10-13

**查询上下文**：`[]`

**动态字段目录**：`[]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`[]`

**金标准**：
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

**理由**：存在上个月但无 previous 目标或 current 查询月，按用户确认的 V8 强制 unresolved_month，today 不作月份锚。完整报告无显式字段清单。

**审核旗标**：`[]`

## IT053 · month_resolution

**问题**：现在想看下一月的覆盖率，仅列这一项。

**受信用户**：1001；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-12", "phase": "history"}]`

**动态字段目录**：`["覆盖率", "日均清扫", "主刷寿命", "HEPA滤网"]`

**历史用户原话**：`["此前查到过一份记录，这回先确认可选字段。"]`

**上一意图**：`null`

**请求字段全序**：`["覆盖率"]`

**金标准**：
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

**理由**：只有 history 查询目录，没有 previous_intent.target_month 和 current 查询月；历史目录不自动授予相对月份锚，按 V8 unresolved_month。

**审核旗标**：`[]`

## IT054 · month_resolution

**问题**：前一个月的尘盒清理，单独列给我。

**受信用户**：1007；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-10", "phase": "history"}]`

**动态字段目录**：`["覆盖率", "日均清扫", "滤网寿命", "尘盒清理"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["尘盒清理"]`

**金标准**：
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

**理由**：授权 history 目录可确认尘盒清理字段，但不提供 current 月份锚；无上一轮意图时前一个月无法确定，不能使用 today。

**审核旗标**：`[]`

## IT055 · comparison_roles

**问题**：只列 2025 年五月的覆盖率，并给出相对 2025 年四月的差值。

**受信用户**：1001；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-05", "phase": "current"}, {"month": "2025-04", "phase": "current"}]`

**动态字段目录**：`["覆盖率", "日均清扫", "主刷寿命", "HEPA滤网", "漏扫区域"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["覆盖率"]`

**金标准**：
```json
{
  "fields": [
    "覆盖率"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-05",
  "compare": true,
  "comparison_month": "2025-04",
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：五月为目标，四月为基准；差值要求意味着 compare=true，最后查询的四月不成为目标。

**审核旗标**：`[]`

## IT056 · comparison_roles

**问题**：先把 2025-02 当参照，再看 2025-04：我只要滤网寿命及两期差额。

**受信用户**：1007；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-02", "phase": "current"}, {"month": "2025-04", "phase": "current"}]`

**动态字段目录**：`["覆盖率", "日均清扫", "滤网寿命", "尘盒清理"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["滤网寿命"]`

**金标准**：
```json
{
  "fields": [
    "滤网寿命"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-04",
  "compare": true,
  "comparison_month": "2025-02",
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：参照明确为二月，当前被查看的四月为目标；句子和工具查询顺序不替代基准语义。

**审核旗标**：`[]`

## IT057 · comparison_roles

**问题**：以 2025 年三月为起点，2025 年五月为本期，仅列自动回充成功率的变化。

**受信用户**：1004；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-05", "phase": "current"}, {"month": "2025-03", "phase": "current"}]`

**动态字段目录**：`["猫砂泼洒处理", "自动回充成功率", "主刷缠绕", "滤网寿命", "滤网更换"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["自动回充成功率"]`

**金标准**：
```json
{
  "fields": [
    "自动回充成功率"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-05",
  "compare": true,
  "comparison_month": "2025-03",
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：起点即基准三月，本期即目标五月；只列一个字段并比较。

**审核旗标**：`[]`

## IT058 · comparison_roles

**问题**：2025 年十月的电池衰减，只这一项；拿同年七月作对照。

**受信用户**：1005；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-10", "phase": "current"}, {"month": "2025-07", "phase": "current"}]`

**动态字段目录**：`["手动操作占比", "定时清扫使用率", "电池衰减", "水箱使用率"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["电池衰减"]`

**金标准**：
```json
{
  "fields": [
    "电池衰减"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-10",
  "compare": true,
  "comparison_month": "2025-07",
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：同年限定由本轮显式 2025 年继承，目标十月、基准七月，不能由 today 换年。

**审核旗标**：`[]`

## IT059 · comparison_roles

**问题**：本期仍只列玩具避障率，另外给我环比。

**受信用户**：1006；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-07", "phase": "current"}, {"month": "2025-06", "phase": "current"}]`

**动态字段目录**：`["跨楼层失败", "玩具避障率", "边刷更换", "集尘袋消耗"]`

**历史用户原话**：`["本期定在 2025 年七月，只看玩具避障率。"]`

**上一意图**：`{"fields": ["玩具避障率"], "target_month": "2025-07", "comparison_month": null, "compare": false, "limited": true}`

**请求字段全序**：`["玩具避障率"]`

**金标准**：
```json
{
  "fields": [
    "玩具避障率"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-07",
  "compare": true,
  "comparison_month": "2025-06",
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：本期仍沿用上一轮七月目标，环比基准为目标前一月六月，不把最后查询的六月当当前期。

**审核旗标**：`[]`

## IT060 · comparison_roles

**问题**：单独比较 2025 年五月的毛发清理，参照三个月前的那一期。

**受信用户**：1003；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-05", "phase": "current"}, {"month": "2025-02", "phase": "current"}]`

**动态字段目录**：`["毛发清理", "地毯增压使用", "胶刷寿命", "尘盒清理", "胶刷更换", "尘盒容量"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["毛发清理"]`

**金标准**：
```json
{
  "fields": [
    "毛发清理"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-05",
  "compare": true,
  "comparison_month": "2025-02",
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：三个月前相对本轮明示目标五月计算为二月，不对 today 或查询列表最后月份计算。

**审核旗标**：`[]`

## IT061 · comparison_roles

**问题**：比较 2025 年十二月和 2026 年一月的覆盖率，后者是本期；只列这项。

**受信用户**：1007；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-12", "phase": "history"}, {"month": "2026-01", "phase": "current"}, {"month": "2025-12", "phase": "current"}]`

**动态字段目录**：`["覆盖率", "日均清扫", "滤网寿命", "尘盒清理"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["覆盖率"]`

**金标准**：
```json
{
  "fields": [
    "覆盖率"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2026-01",
  "compare": true,
  "comparison_month": "2025-12",
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：后者明确为本期 2026-01，基准 2025-12；目标无记录仍不得反转为有记录的旧月。

**审核旗标**：`["target_lookup_not_found"]`

## IT062 · comparison_roles

**问题**：拿 2025-09 对 2025-05，只算覆盖率的差别：前者为本期，后者为参照。

**受信用户**：1010；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-09", "phase": "current"}, {"month": "2025-05", "phase": "current"}]`

**动态字段目录**：`["覆盖率", "手动辅助清扫", "定时清扫使用率", "电池衰减", "边刷寿命"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["覆盖率"]`

**金标准**：
```json
{
  "fields": [
    "覆盖率"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-09",
  "compare": true,
  "comparison_month": "2025-05",
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：前者本期与后者参照明示两个月的角色；字段限定为覆盖率。

**审核旗标**：`[]`

## IT063 · comparison_roles

**问题**：2025 年五月只列主刷寿命，并与同年二月比；不要拿上个月当基准。

**受信用户**：1001；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-05", "phase": "current"}, {"month": "2025-02", "phase": "current"}]`

**动态字段目录**：`["覆盖率", "日均清扫", "主刷寿命", "HEPA滤网", "漏扫区域"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["主刷寿命"]`

**金标准**：
```json
{
  "fields": [
    "主刷寿命"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-05",
  "compare": true,
  "comparison_month": "2025-02",
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：明示同年二月为基准且否定上个月；否定基准不得覆盖有效二月比较请求。

**审核旗标**：`[]`

## IT064 · comparison_roles

**问题**：取消两期对照，2025 年五月只列滤网寿命当前值。

**受信用户**：1007；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-04", "phase": "history"}, {"month": "2025-05", "phase": "current"}]`

**动态字段目录**：`["覆盖率", "日均清扫", "滤网寿命", "尘盒清理"]`

**历史用户原话**：`["刚才把 2025 年五月和四月的滤网寿命作过比较。"]`

**上一意图**：`{"fields": ["滤网寿命"], "target_month": "2025-05", "comparison_month": "2025-04", "compare": true, "limited": true}`

**请求字段全序**：`["滤网寿命"]`

**金标准**：
```json
{
  "fields": [
    "滤网寿命"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-05",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：本轮明确取消比较，应 compare=false 且 comparison_month=null，旧比较状态不继承。

**审核旗标**：`[]`

## IT065 · comparison_roles

**问题**：2025 年十月的避障成功率比 2025 年七月多了还是少了多少？只列这一项。

**受信用户**：1008；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-10", "phase": "current"}, {"month": "2025-07", "phase": "current"}]`

**动态字段目录**：`["覆盖率", "避障成功率", "主刷寿命", "水箱加水", "餐桌区域漏扫", "主刷磨损"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["避障成功率"]`

**金标准**：
```json
{
  "fields": [
    "避障成功率"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-10",
  "compare": true,
  "comparison_month": "2025-07",
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：问多了还是少了多少是在请求变化，compare=true；十月目标减七月基准，数值计算由下游负责。

**审核旗标**：`[]`

## IT066 · comparison_roles

**问题**：本期选 2025 年四月，参照期用 2025 年五月。只比较覆盖率。

**受信用户**：1002；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-04", "phase": "current"}, {"month": "2025-05", "phase": "current"}]`

**动态字段目录**：`["覆盖率", "避障失败", "边刷磨损", "尘盒清理", "边刷寿命"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["覆盖率"]`

**金标准**：
```json
{
  "fields": [
    "覆盖率"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-04",
  "compare": true,
  "comparison_month": "2025-05",
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：基准允许晚于目标，不能为了时间排序擅自把五月变为目标；四月本期与五月参照角色唯一。

**审核旗标**：`[]`

## IT067 · comparison_roles

**问题**：只列滤网寿命，给我环比结果。

**受信用户**：1007；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-05", "phase": "history"}]`

**动态字段目录**：`["覆盖率", "日均清扫", "滤网寿命", "尘盒清理"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["滤网寿命"]`

**金标准**：
```json
{
  "fields": [
    "滤网寿命"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": null,
  "compare": true,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": true
}
```

**理由**：环比意图明确为 true，但没有 previous 目标或 current 查询月，目标与相对基准都无法确定。history 查询仅提供目录，按 V8 不使用 today。

**审核旗标**：`[]`

## IT068 · comparison_roles

**问题**：下一月只列电池衰减，基准仍用刚才那期。

**受信用户**：1010；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-01", "phase": "history"}, {"month": "2025-02", "phase": "current"}, {"month": "2025-01", "phase": "current"}]`

**动态字段目录**：`["覆盖率", "手动辅助清扫", "定时清扫使用率", "电池衰减", "边刷寿命"]`

**历史用户原话**：`["刚才这期是 2025 年一月，单独看电池衰减。"]`

**上一意图**：`{"fields": ["电池衰减"], "target_month": "2025-01", "comparison_month": null, "compare": false, "limited": true}`

**请求字段全序**：`["电池衰减"]`

**金标准**：
```json
{
  "fields": [
    "电池衰减"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-02",
  "compare": true,
  "comparison_month": "2025-01",
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：下一月以 previous 目标一月换算为二月；刚才那期明确继承一月为基准，当前查询顺序不换角色。

**审核旗标**：`[]`

## IT069 · negation_correction

**问题**：2025 年九月不要覆盖率，只给日均清扫。

**受信用户**：1001；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-09", "phase": "current"}]`

**动态字段目录**：`["覆盖率", "日均清扫", "漏扫区域", "主刷寿命", "HEPA滤网"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["日均清扫"]`

**金标准**：
```json
{
  "fields": [
    "日均清扫"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-09",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：覆盖率被明确否定，不出现在 fields 或 unknown_fields；仅日均清扫有效。

**审核旗标**：`[]`

## IT070 · negation_correction

**问题**：2025-05：覆盖率不看，只保留主刷寿命和 HEPA滤网，按这个顺序。

**受信用户**：1001；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-05", "phase": "current"}]`

**动态字段目录**：`["覆盖率", "日均清扫", "主刷寿命", "HEPA滤网"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["主刷寿命", "HEPA滤网"]`

**金标准**：
```json
{
  "fields": [
    "主刷寿命",
    "HEPA滤网"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-05",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：否定覆盖率并明确列出两项有效字段及顺序；HEPA滤网是当前授权目录精确字段。

**审核旗标**：`[]`

## IT071 · negation_correction

**问题**：不是 2025 年八月，是 2025 年九月，我只要覆盖率。

**受信用户**：1007；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-09", "phase": "current"}, {"month": "2025-08", "phase": "current"}]`

**动态字段目录**：`["覆盖率", "日均清扫", "滤网寿命", "尘盒清理"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["覆盖率"]`

**金标准**：
```json
{
  "fields": [
    "覆盖率"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-09",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：八月处于不是的否定范围，九月为最新明确正向目标；最后工具查到八月不改变角色。

**审核旗标**：`[]`

## IT072 · negation_correction

**问题**：2025 年五月不是问毛发清理，我说错了；只要地毯增压使用。

**受信用户**：1003；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-05", "phase": "current"}]`

**动态字段目录**：`["毛发清理", "地毯增压使用", "胶刷寿命", "尘盒清理"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["地毯增压使用"]`

**金标准**：
```json
{
  "fields": [
    "地毯增压使用"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-05",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：纠正字段指向地毯增压使用，前面被否定的毛发清理不得被保留。

**审核旗标**：`[]`

## IT073 · negation_correction

**问题**：刚才那两项里去掉电池衰减，2025 年十月只保留手动操作占比。

**受信用户**：1005；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-10", "phase": "current"}]`

**动态字段目录**：`["手动操作占比", "定时清扫使用率", "电池衰减", "水箱使用率"]`

**历史用户原话**：`["2025 年十月只列手动操作占比与电池衰减。"]`

**上一意图**：`{"fields": ["手动操作占比", "电池衰减"], "target_month": "2025-10", "comparison_month": null, "compare": false, "limited": true}`

**请求字段全序**：`["手动操作占比"]`

**金标准**：
```json
{
  "fields": [
    "手动操作占比"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-10",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：本轮明确删除上一轮的一项，gold 仅留手动操作占比；不能机械继承完整旧字段列表。

**审核旗标**：`[]`

## IT074 · negation_correction

**问题**：月份刚才说错了：本期不是 2025-05，是 2025-06；基准不是 2025-04，是 2025-03。只比滤网寿命。

**受信用户**：1007；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-06", "phase": "current"}, {"month": "2025-03", "phase": "current"}]`

**动态字段目录**：`["覆盖率", "日均清扫", "滤网寿命", "尘盒清理"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["滤网寿命"]`

**金标准**：
```json
{
  "fields": [
    "滤网寿命"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-06",
  "compare": true,
  "comparison_month": "2025-03",
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：目标和基准各有显式修正；被否定的五月、四月无效，新目标六月减新基准三月。

**审核旗标**：`[]`

## IT075 · negation_correction

**问题**：我不比较 2025 年四月了，2025 年五月只列主刷寿命。

**受信用户**：1001；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-05", "phase": "current"}, {"month": "2025-04", "phase": "current"}]`

**动态字段目录**：`["覆盖率", "日均清扫", "主刷寿命", "HEPA滤网", "漏扫区域"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["主刷寿命"]`

**金标准**：
```json
{
  "fields": [
    "主刷寿命"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-05",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：不比较明确取消基准请求；五月为正向目标，四月不得因文本中仍出现而生成 comparison_month。

**审核旗标**：`[]`

## IT076 · negation_correction

**问题**：2025 年十一月不用耗电量，只给电池衰减就可以。

**受信用户**：1005；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-11", "phase": "current"}]`

**动态字段目录**：`["手动操作占比", "定时清扫使用率", "电池衰减", "水箱使用率"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["电池衰减"]`

**金标准**：
```json
{
  "fields": [
    "电池衰减"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-11",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：耗电量虽目录不存在但被明确排除，不标 unknown_fields；有效请求仅为电池衰减。

**审核旗标**：`[]`

## IT077 · negation_correction

**问题**：2025 年五月，我口误说成主刷寿命了，改为只问边刷寿命。

**受信用户**：1006；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-05", "phase": "current"}]`

**动态字段目录**：`["跨楼层失败", "玩具避障率", "边刷寿命", "集尘袋消耗"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["边刷寿命"]`

**金标准**：
```json
{
  "fields": [
    "边刷寿命"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-05",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：口误并改为表明主刷寿命被撤回，即使它不在目录也不能列为未知；边刷寿命为当前真实目录成员。

**审核旗标**：`[]`

## IT078 · negation_correction

**问题**：2025 年七月覆盖率先不问了，只列滤网寿命；也不要解释这个字段的含义。

**受信用户**：1007；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-07", "phase": "current"}]`

**动态字段目录**：`["覆盖率", "日均清扫", "滤网寿命", "尘盒清理"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["滤网寿命"]`

**金标准**：
```json
{
  "fields": [
    "滤网寿命"
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

**理由**：覆盖率明确取消，滤网寿命仍有效；含义处于不要解释范围，knowledge_requested=false。

**审核旗标**：`[]`

## IT079 · negation_correction

**问题**：不要整份报告了，2025 年九月改成只列自动回充成功率、滤网寿命。

**受信用户**：1004；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-09", "phase": "current"}]`

**动态字段目录**：`["猫砂泼洒处理", "自动回充成功率", "主刷缠绕", "滤网寿命"]`

**历史用户原话**：`["先给 2025 年九月的完整报告。"]`

**上一意图**：`{"fields": [], "target_month": "2025-09", "comparison_month": null, "compare": false, "limited": false}`

**请求字段全序**：`["自动回充成功率", "滤网寿命"]`

**金标准**：
```json
{
  "fields": [
    "自动回充成功率",
    "滤网寿命"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-09",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：明确撤回完整范围后只列两个字段；limited=true/full_report=false 不继承旧完整范围。

**审核旗标**：`[]`

## IT080 · negation_correction

**问题**：取消以 2025 年四月为参照的安排，改成 2025 年五月和 2025 年三月比较；五月是本期，仅列覆盖率。

**受信用户**：1001；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-05", "phase": "current"}, {"month": "2025-03", "phase": "current"}]`

**动态字段目录**：`["覆盖率", "日均清扫", "主刷寿命", "HEPA滤网", "漏扫区域"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["覆盖率"]`

**金标准**：
```json
{
  "fields": [
    "覆盖率"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-05",
  "compare": true,
  "comparison_month": "2025-03",
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：取消的只是旧四月基准，后续正向改成五月对三月仍是比较；不能让取消一词抹掉最新比较请求。

**审核旗标**：`[]`

## IT081 · report_scope

**问题**：把2025年10月的完整报告给我，清洁效率和耗材都展开。

**受信用户**：1001；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-10", "phase": "current"}]`

**动态字段目录**：`["覆盖率", "日均清扫", "漏扫区域", "主刷寿命", "HEPA滤网"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`[]`

**金标准**：
```json
{
  "fields": [],
  "unknown_fields": [],
  "limited": false,
  "full_report": true,
  "target_month": "2025-10",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：明确完整报告；不保留字段选择，不作比较。

**审核旗标**：`[]`

## IT082 · report_scope

**问题**：请查看2025年9月的报告。

**受信用户**：1003；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-09", "phase": "current"}]`

**动态字段目录**：`["毛发清理", "地毯增压使用", "胶刷寿命", "尘盒容量"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`[]`

**金标准**：
```json
{
  "fields": [],
  "unknown_fields": [],
  "limited": false,
  "full_report": false,
  "target_month": "2025-09",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：未明确只列或完整；字段空且 scope unspecified，full_report=false。

**审核旗标**：`[]`

## IT083 · report_scope

**问题**：2025年11月那份不要全部展开，这次只列边刷寿命。

**受信用户**：1006；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-11", "phase": "current"}]`

**动态字段目录**：`["跨楼层失败", "玩具避障率", "边刷寿命", "集尘袋消耗"]`

**历史用户原话**：`["请给我2025年11月完整报告。"]`

**上一意图**：`{"fields": [], "target_month": "2025-11", "comparison_month": null, "compare": false, "limited": false}`

**请求字段全序**：`["边刷寿命"]`

**金标准**：
```json
{
  "fields": [
    "边刷寿命"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-11",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：当前明确只列，覆盖历史完整报告范围。

**审核旗标**：`[]`

## IT084 · report_scope

**问题**：换成2025年10月，之前的两个字段限制取消，给完整报告。

**受信用户**：1002；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-10", "phase": "current"}]`

**动态字段目录**：`["覆盖率", "避障失败", "边刷寿命", "尘盒清理"]`

**历史用户原话**：`["2025年9月只列覆盖率和尘盒清理。"]`

**上一意图**：`{"fields": ["覆盖率", "尘盒清理"], "target_month": "2025-09", "comparison_month": null, "compare": false, "limited": true}`

**请求字段全序**：`[]`

**金标准**：
```json
{
  "fields": [],
  "unknown_fields": [],
  "limited": false,
  "full_report": true,
  "target_month": "2025-10",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：明确取消字段限制并要求完整报告；fields 和 unknown_fields 都空。

**审核旗标**：`[]`

## IT085 · report_scope

**问题**：2025年11月报告只留每天耗水量这一项，没有就写未提供。

**受信用户**：1005；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-11", "phase": "current"}]`

**动态字段目录**：`["手动操作占比", "定时清扫使用率", "电池衰减", "水箱使用率"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["每天耗水量"]`

**金标准**：
```json
{
  "fields": [],
  "unknown_fields": [
    "每天耗水量"
  ],
  "limited": true,
  "full_report": false,
  "target_month": "2025-11",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：only_listed 也适用于唯一未知字段；不能用水箱使用率替代。

**审核旗标**：`[]`

## IT086 · report_scope

**问题**：2025年12月按电池衰减、覆盖率、电池衰减的顺序列数值，不要其他项。

**受信用户**：1010；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-12", "phase": "current"}]`

**动态字段目录**：`["覆盖率", "手动辅助清扫", "定时清扫使用率", "电池衰减", "边刷寿命"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["电池衰减", "覆盖率"]`

**金标准**：
```json
{
  "fields": [
    "电池衰减",
    "覆盖率"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-12",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：指定顺序，重复字段有序去重，不追加目录字段。

**审核旗标**：`[]`

## IT087 · report_scope

**问题**：2025年5月要完整报告，但不用讲指标是什么意思。

**受信用户**：1004；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-05", "phase": "current"}]`

**动态字段目录**：`["猫砂泼洒处理", "自动回充成功率", "主刷缠绕", "滤网寿命"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`[]`

**金标准**：
```json
{
  "fields": [],
  "unknown_fields": [],
  "limited": false,
  "full_report": true,
  "target_month": "2025-05",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：完整范围不代表知识请求；明确不用释义，knowledge_requested=false。

**审核旗标**：`[]`

## IT088 · report_scope

**问题**：刚才列的两项先删去胶刷缠绕，只留2025年10月的滤网寿命。

**受信用户**：1009；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-10", "phase": "current"}]`

**动态字段目录**：`["宠物毛发清理", "自动回充成功率", "胶刷缠绕", "滤网寿命"]`

**历史用户原话**：`["查2025年9月，只列胶刷缠绕和滤网更换。"]`

**上一意图**：`{"fields": ["胶刷缠绕", "滤网更换"], "target_month": "2025-09", "comparison_month": null, "compare": false, "limited": true}`

**请求字段全序**：`["滤网寿命"]`

**金标准**：
```json
{
  "fields": [
    "滤网寿命"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-10",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：当轮重新明确唯一字段，历史不同标签不继承。

**审核旗标**：`[]`

## IT089 · report_knowledge

**问题**：查2025年10月，只列电池衰减，再依据《维护保养》的电池条目说说哪些情况需要立即更换。

**受信用户**：1005；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-10", "phase": "current"}]`

**动态字段目录**：`["手动操作占比", "定时清扫使用率", "电池衰减", "水箱使用率"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["电池衰减"]`

**金标准**：
```json
{
  "fields": [
    "电池衰减"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-10",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": true,
  "unresolved_month": false
}
```

**理由**：既选择报告指标又有明确知识子问题；不能把衰减字段当当前续航比。

**审核旗标**：`[]`

## IT090 · report_knowledge

**问题**：2025年11月只给主刷寿命，不要解释寿命含义，也不用给保养建议。

**受信用户**：1001；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-11", "phase": "current"}]`

**动态字段目录**：`["覆盖率", "日均清扫", "主刷寿命", "HEPA滤网"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["主刷寿命"]`

**金标准**：
```json
{
  "fields": [
    "主刷寿命"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-11",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：否定所有解释与建议；knowledge_requested=false，不因寿命二字触发知识。

**审核旗标**：`[]`

## IT091 · report_knowledge

**问题**：给2025年9月的覆盖率；另据《选购指南》解释选购时建议的实测清洁覆盖率门槛。

**受信用户**：1007；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-09", "phase": "current"}]`

**动态字段目录**：`["覆盖率", "日均清扫", "滤网寿命", "尘盒清理"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["覆盖率"]`

**金标准**：
```json
{
  "fields": [
    "覆盖率"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-09",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": true,
  "unresolved_month": false
}
```

**理由**：报告选择和购买门槛说明是两个请求，选购门槛不能改写本月记录。

**审核旗标**：`[]`

## IT092 · report_knowledge

**问题**：2025年11月只列边刷寿命，还想知道《维护保养》中刷毛磨到多短要换边刷。

**受信用户**：1006；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-11", "phase": "current"}]`

**动态字段目录**：`["跨楼层失败", "玩具避障率", "边刷寿命", "集尘袋消耗"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["边刷寿命"]`

**金标准**：
```json
{
  "fields": [
    "边刷寿命"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-11",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": true,
  "unresolved_month": false
}
```

**理由**：只列限定报告字段；不禁止额外明确请求的知识门槛说明。

**审核旗标**：`[]`

## IT093 · report_knowledge

**问题**：2025年10月只列胶刷寿命和毛发清理。至于怎么养护胶刷，我不问，这轮无需说明。

**受信用户**：1003；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-10", "phase": "current"}]`

**动态字段目录**：`["毛发清理", "地毯增压使用", "胶刷寿命", "尘盒清理"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["胶刷寿命", "毛发清理"]`

**金标准**：
```json
{
  "fields": [
    "胶刷寿命",
    "毛发清理"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-10",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：知识样式子句被明确否定，不能把不问解析成知识要求。

**审核旗标**：`[]`

## IT094 · report_knowledge

**问题**：查2025年9月，只列覆盖率和故障原因；原因字段没有就写未提供，不要自行诊断。

**受信用户**：1002；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-09", "phase": "current"}]`

**动态字段目录**：`["覆盖率", "避障失败", "边刷磨损", "尘盒清理"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["覆盖率", "故障原因"]`

**金标准**：
```json
{
  "fields": [
    "覆盖率"
  ],
  "unknown_fields": [
    "故障原因"
  ],
  "limited": true,
  "full_report": false,
  "target_month": "2025-09",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：故障原因在这里是明确索取的未知报告字段，不是知识问答请求。

**审核旗标**：`[]`

## IT095 · report_knowledge

**问题**：2025年10月仅列主刷寿命和避障成功率，再查资料回答“边刷磨损会影响什么”。

**受信用户**：1008；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-10", "phase": "current"}]`

**动态字段目录**：`["覆盖率", "避障成功率", "主刷寿命", "水箱加水"]`

**历史用户原话**：`[]`

**上一意图**：`null`

**请求字段全序**：`["主刷寿命", "避障成功率"]`

**金标准**：
```json
{
  "fields": [
    "主刷寿命",
    "避障成功率"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-10",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": true,
  "unresolved_month": false
}
```

**理由**：边刷知识对象不同于报告主刷字段；仅列不屏蔽明确知识子问。

**审核旗标**：`[]`

## IT096 · report_knowledge

**问题**：我要2025年11月的自动回充成功率和滤网寿命，只展示数据；先前让你解释滤网保养的要求取消。

**受信用户**：1009；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-11", "phase": "current"}]`

**动态字段目录**：`["宠物毛发清理", "自动回充成功率", "胶刷缠绕", "滤网寿命"]`

**历史用户原话**：`["2025年10月列自动回充成功率和滤网寿命，再解释滤网保养。"]`

**上一意图**：`{"fields": ["自动回充成功率", "滤网寿命"], "target_month": "2025-10", "comparison_month": null, "compare": false, "limited": true}`

**请求字段全序**：`["自动回充成功率", "滤网寿命"]`

**金标准**：
```json
{
  "fields": [
    "自动回充成功率",
    "滤网寿命"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-11",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：取消历史知识要求，当前只展示数据。

**审核旗标**：`[]`

## IT097 · multi_turn_reference

**问题**：还是这两项，换到2025年11月；保持刚才列出的先后顺序。

**受信用户**：1001；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-10", "phase": "history"}, {"month": "2025-11", "phase": "current"}]`

**动态字段目录**：`["覆盖率", "日均清扫", "漏扫区域", "主刷寿命", "HEPA滤网"]`

**历史用户原话**：`["2025年10月只列主刷寿命，再列日均清扫。"]`

**上一意图**：`{"fields": ["主刷寿命", "日均清扫"], "target_month": "2025-10", "comparison_month": null, "compare": false, "limited": true}`

**请求字段全序**：`["主刷寿命", "日均清扫"]`

**金标准**：
```json
{
  "fields": [
    "主刷寿命",
    "日均清扫"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-11",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：这两项继承历史明确字段与顺序，显式当轮月份覆盖历史月份。

**审核旗标**：`[]`

## IT098 · multi_turn_reference

**问题**：同样的字段，查2025年12月，这次也只列数据。

**受信用户**：1006；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-11", "phase": "history"}, {"month": "2025-12", "phase": "current"}]`

**动态字段目录**：`["跨楼层失败", "玩具避障率", "边刷寿命", "集尘袋消耗", "跨楼层成功率"]`

**历史用户原话**：`["2025年11月只列玩具避障率和边刷寿命，不列集尘袋消耗。"]`

**上一意图**：`{"fields": ["玩具避障率", "边刷寿命"], "target_month": "2025-11", "comparison_month": null, "compare": false, "limited": true}`

**请求字段全序**：`["玩具避障率", "边刷寿命"]`

**金标准**：
```json
{
  "fields": [
    "玩具避障率",
    "边刷寿命"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-12",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：同样字段只继承有效选择；被排除的集尘袋字段不得恢复。

**审核旗标**：`[]`

## IT099 · multi_turn_reference

**问题**：这两个指标在后一个月又是多少？不要和旧月份比较。

**受信用户**：1007；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-09", "phase": "history"}, {"month": "2025-10", "phase": "current"}]`

**动态字段目录**：`["覆盖率", "日均清扫", "滤网寿命", "尘盒清理"]`

**历史用户原话**：`["2025年9月只给覆盖率和滤网寿命。"]`

**上一意图**：`{"fields": ["覆盖率", "滤网寿命"], "target_month": "2025-09", "comparison_month": null, "compare": false, "limited": true}`

**请求字段全序**：`["覆盖率", "滤网寿命"]`

**金标准**：
```json
{
  "fields": [
    "覆盖率",
    "滤网寿命"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-10",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：以有效上一轮目标月做+1，不开启比较；历史选择有效。

**审核旗标**：`[]`

## IT100 · multi_turn_reference

**问题**：把这三项重新排成覆盖率、边刷寿命、电池衰减；仍查刚才的月。

**受信用户**：1010；**today**：2026-10-13

**查询上下文**：`[{"month": "2025-08", "phase": "current"}]`

**动态字段目录**：`["覆盖率", "手动辅助清扫", "定时清扫使用率", "电池衰减", "边刷寿命"]`

**历史用户原话**：`["查2025年8月，只列电池衰减、覆盖率、边刷寿命。"]`

**上一意图**：`{"fields": ["电池衰减", "覆盖率", "边刷寿命"], "target_month": "2025-08", "comparison_month": null, "compare": false, "limited": true}`

**请求字段全序**：`["覆盖率", "边刷寿命", "电池衰减"]`

**金标准**：
```json
{
  "fields": [
    "覆盖率",
    "边刷寿命",
    "电池衰减"
  ],
  "unknown_fields": [],
  "limited": true,
  "full_report": false,
  "target_month": "2025-08",
  "compare": false,
  "comparison_month": null,
  "knowledge_requested": false,
  "unresolved_month": false
}
```

**理由**：指标与月份指代有有效锚；当前明确的新顺序取代历史顺序。

**审核旗标**：`[]`
