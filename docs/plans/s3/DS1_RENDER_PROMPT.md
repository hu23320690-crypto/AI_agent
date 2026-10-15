# 给 DeepSeek 的任务 DS-1：售后服务 Agent 的回答渲染器和文本守卫

请用 Python 3.12 写一个**纯函数模块** `render.py` 和对应的 pytest 测试 `test_render.py`。只用标准库，不要导入任何第三方包或项目内模块。所有面向用户的文字用简体中文。

## 背景
这是一个扫地机器人售后服务 Agent。模型通过工具查询设备、错误码、保修、可约时段、耗材和订单，还可以"提议"预约或下单（只生成待确认卡片，用户点卡片才会执行）。为了防止模型编造事实，回答里的关键事实一律由代码从工具结果渲染，模型自己写的文字要先经过文本守卫过滤。

全部数据都是合成的，型号为 SV-100（基础扫地型）、SV-200（扫拖一体型）、SV-300（宠物型）、SV-400（自集尘旗舰型）。

## 输入：一轮里的工具结果
按调用顺序排列的列表，每项为 `{"tool": str, "args": dict, "payload": dict}`。各工具成功时的 payload 形状如下：

```json
// list_my_devices
{"devices": [{"device_id": "D-1002-01", "model_code": "SV-200", "display_name": "扫拖一体型", "serial_suffix": "0000", "purchase_date": "2024-07-12", "firmware": "1.0.0"}]}

// lookup_error_code（status 取 ok、not_found 或 clarify）
{"status": "ok", "definitions": [{"model_code": "SV-200", "code": "E07", "title": "水箱供水检测异常", "severity": 2, "self_fixable": false, "requires_visit": true, "doc_ref": "errors.txt#SV-200-E07"}]}
{"status": "not_found", "definitions": [], "message": "该型号没有相应错误码定义。"}
{"status": "clarify", "definitions": [], "message": "请先选择要查询的设备。"}

// check_warranty（component 取 whole_machine、battery 或 consumables）
{"device_id": "D-1002-01", "business_date": "2026-01-12", "coverage": [
  {"component": "battery", "in_warranty": false, "expires_date": "2025-07-12", "basis": "…", "reason": "保修期限已届满。"},
  {"component": "consumables", "in_warranty": false, "expires_date": "2024-07-12", "basis": "…", "reason": "耗材正常磨损不在保。"},
  {"component": "whole_machine", "in_warranty": true, "expires_date": "2026-07-12", "basis": "…"}]}

// rag_summarize
{"answer": "可以多行的资料回答原文", "references": [{"doc_ref": "service_kb/sv-200_manual.txt#abc", "models": ["SV-200"]}]}

// get_daily_usage（metric 取 area_m2、duration_min 或 error_events）
{"device_id": "D-1001-01", "start": "2025-06-01", "end": "2025-06-07", "metric": "area_m2", "days_observed": 7, "total": 350.0, "daily_average": 50.0, "maximum": 52.0}

// find_service_slots
{"device_id": "D-1002-01", "slots": [{"slot_id": "S-east-20260113-2", "region": "east", "start_at": "2026-01-13T13:00:00+08:00", "end_at": "2026-01-13T15:00:00+08:00", "available": 2}]}

// find_consumables
{"device_id": "D-1006-01", "consumables": [
  {"sku": "SKU-FILTER", "name": "通用滤网", "kind": "filter", "price_cents": 3900, "stock": 80, "max_per_order": 2},
  {"sku": "SKU-MOP", "name": "清洁拖布", "kind": "mop_pad", "price_cents": 2900, "stock": 0}]}

// get_my_orders_and_tickets（records 里 kind 取 order、ticket 或 appointment）
{"records": [
  {"kind": "order", "id": "O-1007-01", "device_id": "D-1007-01", "sku": "SKU-MAIN", "qty": 1, "amount_cents": 6900, "status": "processing"},
  {"kind": "ticket", "id": "T-1008-01", "device_id": "D-1008-01", "error_code": "E07", "description": "拖地时显示 E07……", "notes": "……", "status": "scheduled"},
  {"kind": "appointment", "id": "A-1008-01", "ticket_id": "T-1008-01", "slot_id": "S-west-20260115-2", "status": "scheduled"}]}

// propose_service_visit / propose_order / propose_change（成功）
{"action_id": "uuid", "status": "pending", "tool": "propose_order", "args": {"device_id": "D-1007-01", "sku": "SKU-SIDE", "qty": 2}, "args_sha256": "…", "summary": "下单：设备D-1007-01，通用边刷（SKU-SIDE）×2；单价19.00元，金额38.00元；等待卡片确认。", "created_at": "2026-01-12T07:00:00+00:00", "expires_at": "2026-01-12T07:10:00+00:00", "amount_cents": 3800}

// 任何工具失败
{"status": "blocked", "reason_code": "out_of_stock", "message": "库存不足，未生成订单提议。"}
{"status": "denied", "reason_code": "identity_mismatch", "message": "对象不属于当前用户或不可见。"}
```

`fetch_external_data` 由别的模块渲染，这里直接跳过。

## 要实现的函数

```python
def render_facts(results: list[dict]) -> list[str]
```
按输入顺序为每个结果生成一个事实块字符串。相同的 (tool, 规范化后的 args) 只保留第一次。格式规则：

- 金额从分换算为"x.xx 元"；带时区的时间 `2026-01-13T13:00:00+08:00` 显示为"2026-01-13 13:00"；expires_at 换算到 +08:00 再显示。
- 状态中文：processing 处理中，completed 已完成，cancelled 已取消，scheduled 已预约。
- 指标：area_m2 是清扫面积（㎡），duration_min 是清扫时长（分钟），error_events 是错误事件（次）。数值去掉多余的 .0，日均保留两位小数。

| 工具 | 输出示例 |
| --- | --- |
| list_my_devices | 你的设备：D-1002-01（SV-200 扫拖一体型，购买日期 2024-07-12）。多台设备时用"；"分隔。 |
| lookup_error_code ok | 错误码 E07（SV-200）：水箱供水检测异常。严重程度 2；不建议自行处理，需要服务人员上门检查。self_fixable 为 true 时，后半句改成：可以先按手册自查，自查后仍异常再申请上门。 |
| lookup_error_code not_found | 型号 {model} 没有错误码 {code} 的定义，请核对屏幕上的编号。（model 取自 args 里没有、就写"该设备"；code 取自 args.code） |
| lookup_error_code clarify | 直接输出 message |
| check_warranty | 保修（D-1002-01，以 2026-01-12 为准）：整机在保，到期日 2026-07-12；电池已过保，到期日 2025-07-12；耗材正常磨损不在保。部件顺序固定为整机、电池、耗材。有任一部件在保时，末尾再加：在保不代表一定免费，故障原因需服务人员检查。 |
| rag_summarize | 资料说明：{answer 原文，保留换行} |
| get_daily_usage | D-1001-01 在 2025-06-01 至 2025-06-07（有记录 7 天）：清扫面积合计 350 ㎡，日均 50.00 ㎡，最大 52 ㎡。 |
| find_service_slots | 可约时段：1）2026-01-13 13:00–15:00（剩余 2）；2）……。没有时段时写：未查到可约时段。 |
| find_consumables | 兼容耗材：SKU-FILTER 通用滤网，39.00 元，库存 80，单次限购 2；SKU-MOP 清洁拖布，29.00 元，缺货。没有 max_per_order 时不写限购；库存为 0 时写"缺货"。 |
| get_my_orders_and_tickets | 订单 O-1007-01：SKU-MAIN × 1，69.00 元，处理中。工单 T-1008-01：E07，已预约。预约 A-1008-01：时段 S-west-20260115-2，已预约。没有记录时写：没有查到相关记录。 |
| propose_*（成功） | 待确认：{summary}（有效期至 2026-01-12 15:10）。 |
| 失败 | 直接输出 message |

```python
def guard_text(text: str, sources: list[str]) -> tuple[str, list[str]]
```
文本守卫。按句切分（。！？；和换行；保留原标点），删除满足任一条件的句子，返回（保留文本, 被删句子列表）：

1. 句子含"事实记号"，但这个记号没有出现在任何 source 中。事实记号包括：
   - 编号：`D-…`、`T-…`、`A-…`、`O-…`、`S-…`、`SKU-…`、错误码 `E` 加两位数字；
   - 日期 `YYYY-MM-DD` 和 `YYYY年M月D日`。两种写法视为同一日期：source 里有任一写法即可，月和日可以有或没有前导零；
   - 时间 `HH:MM` 或 `H:MM`；
   - 金额：数字后跟"元"或"分"；
   - 百分比：数字后跟"%"；
   - 带单位的数量：数字后跟 天、个、件、次、㎡、分钟。

   比较前先把全角数字和全角符号转成半角。
2. 声称写操作已经完成：匹配 `已(为你|帮你)?(预约|下单|取消|提交|创建|改约)`，且这个匹配前面同一句里没有"未""尚未""没有""不会"。

```python
def render_outcomes(outcomes: list[dict]) -> list[str]
```
plan 模式的结论句。每个 outcome 为 `{"goal_type": str, "goal_text": str, "status": str, "action": "visit" | "order" | "change" | None, "condition": dict | None, "reason": str | None}`。action 对应的中文：visit 预约，order 订单，change 变更。status 与句式：

- proposed → 已为你准备{动作}的确认卡片。
- condition_false → 按你的要求（{条件描述}），条件不成立，未生成{动作}卡片。
- condition_unknown → 无法判断你的条件（{条件描述}）是否成立，未生成{动作}卡片。
- precheck_failed → {reason}，未生成{动作}卡片。
- slot_unavailable → 你指定的时段没有可约名额，未生成预约卡片。
- missing → 未能完成：{goal_text}。
- done → 不输出句子（事实块已经覆盖）。

条件描述：
- `{"type": "warranty_in_force", "component": "whole_machine" | "battery"}` → "整机在保" / "电池在保"；
- `{"type": "record_threshold", "month": "2025-12", "field_hint": "HEPA", "op": "<=", "value": 15, "unit": "%"}` → "2025-12 HEPA 不高于 15%"。op 的中文：<= 不高于，< 低于，>= 不低于，> 高于。

```python
def render_ask(ask: dict, results: list[dict]) -> str
```
`ask` 为 `{"type": "which_device" | "which_slot" | "quantity" | "other", "text": str}`：
- which_device → "你有多台设备：{从 results 里 list_my_devices 的结果列出编号和型号}。请问是哪一台？"
- which_slot → "请从下面的可约时段里选一个。"
- quantity → "请告诉我需要的数量。"
- other → 返回 guard_text(text, …) 的保留部分；被过滤空时返回"请补充更多信息。"

```python
def compose_answer(*, mode: str, results: list[dict], model_text: str | None = None,
                   outcomes: list[dict] | None = None, ask: dict | None = None,
                   report_text: str | None = None, sources: list[str] = ()) -> str
```
组装最终回答：
- mode="react"：`guard_text(model_text, sources + [每个结果 payload 的 JSON 文本])` 的保留部分 + 空行 + report_text（如果有）+ 事实块。
- mode="plan"：render_ask（如果有 ask）+ render_outcomes + 空行 + report_text（如果有）+ 事实块。
- 两种模式下，只要本轮有成功的 propose 结果，最后都固定加一句："请在确认卡片上确认，确认前不会提交。"
- 各部分之间用空行分隔，空的部分不输出，结尾不留多余空行。

## 测试（pytest）
每个函数至少覆盖：
- 每种工具的正常格式（使用上面的示例数据）；
- 去重；
- 多设备；
- 缺货和限购；
- 没有可约时段；
- 没有记录；
- 失败 message；
- expires_at 时区换算；
- guard_text 的每类记号：在 source 中出现时保留、不出现时删除；
- 两种日期写法等价；
- 全角数字；
- "已为你预约"被删、"尚未为你预约"被保留；
- render_outcomes 的每种状态；
- render_ask 的四种类型；
- compose_answer 两种模式的拼接顺序，以及固定结尾句。

## 交付
只输出两个完整文件：`render.py` 和 `test_render.py`。每个公开函数写简短的 docstring。不要省略代码，不要用占位符。
