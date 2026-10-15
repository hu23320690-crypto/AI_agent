# 给 DeepSeek 的任务 DS-2：售后服务 Agent 的计划模型、校验与参数解析

请用 Python 3.12 写一个模块 `plan_core.py` 和对应的 pytest 测试 `test_plan_core.py`。除标准库外只允许使用 pydantic v2，不要导入项目内模块。

## 背景
这是一个扫地机器人售后服务 Agent 的 Plan → Execute → Verify 模式。一个小模型（planner）把用户请求翻译成结构化计划：要完成哪些子目标、调用哪些工具、参数从哪里来。planner **不允许写任何编号的字面值**（设备号、时段号、SKU、订单号），只能声明"从哪一步的结果里、按什么规则挑"。挑选由代码完成。你写的模块就是这层"代码校验"：校验计划、解析参数、判断用户附带的条件、在发起写操作前做预检。

业务日期（服务模式的"今天"）由调用方传入，例如 2026-01-12。全部数据都是合成的。

## 工具清单（TOOLS 常量请原样写进模块）

```python
TOOLS = {
  "list_my_devices": {"params": {}, "required": []},
  "lookup_error_code": {"params": {"code": {"type": "string"}, "device_id": {"type": "string"}}, "required": ["code"]},
  "check_warranty": {"params": {"device_id": {"type": "string"}, "component": {"type": "string", "enum": ["whole_machine", "battery", "consumables"]}}, "required": ["device_id"]},
  "rag_summarize": {"params": {"query": {"type": "string"}, "device_id": {"type": "string"}}, "required": ["query"]},
  "fetch_external_data": {"params": {"month": {"type": "string"}}, "required": ["month"]},
  "get_daily_usage": {"params": {"device_id": {"type": "string"}, "start": {"type": "string"}, "end": {"type": "string"}, "metric": {"type": "string", "enum": ["area_m2", "duration_min", "error_events"]}}, "required": ["device_id", "start", "end", "metric"]},
  "find_service_slots": {"params": {"device_id": {"type": "string"}, "from_date": {"type": "string"}, "days": {"type": "integer"}}, "required": ["device_id"]},
  "find_consumables": {"params": {"device_id": {"type": "string"}, "kind": {"type": "string", "enum": ["main_brush", "side_brush", "rubber_brush", "filter", "mop_pad", "dust_bag"]}}, "required": ["device_id"]},
  "get_my_orders_and_tickets": {"params": {"kind": {"type": "string", "enum": ["order", "ticket", "appointment"]}, "id": {"type": "string"}}, "required": []},
  "propose_service_visit": {"params": {"device_id": {"type": "string"}, "error_code": {"type": "string"}, "description": {"type": "string"}, "slot_id": {"type": "string"}}, "required": ["device_id", "description", "slot_id"]},
  "propose_order": {"params": {"device_id": {"type": "string"}, "sku": {"type": "string"}, "qty": {"type": "integer"}}, "required": ["device_id", "sku", "qty"]},
  "propose_change": {"params": {"target_id": {"type": "string"}, "change": {"type": "string", "enum": ["reschedule", "cancel_appointment", "cancel_order"]}, "new_slot_id": {"type": "string"}}, "required": ["target_id", "change"]},
}
WRITE_TOOLS = {"propose_service_visit", "propose_order", "propose_change"}
```

## 工具结果的形状（resolve、condition、precheck 会读取）
步骤结果存放在 `results: dict[str, dict]` 中，键为 step id，值为 `{"tool": str, "args": dict, "payload": dict}`。payload 示例：

```json
// list_my_devices
{"devices": [{"device_id": "D-1020-01", "model_code": "SV-400", "display_name": "自集尘旗舰型", "purchase_date": "2024-03-01"}, {"device_id": "D-1020-02", "model_code": "SV-100", "display_name": "基础扫地型", "purchase_date": "2024-05-01"}]}
// check_warranty
{"device_id": "D-1002-01", "business_date": "2026-01-12", "coverage": [{"component": "whole_machine", "in_warranty": true, "expires_date": "2026-07-12"}, {"component": "battery", "in_warranty": false, "expires_date": "2025-07-12"}]}
// fetch_external_data（注意：文本字段里的换行是字面量反斜杠加 n 这两个字符，也可能是真换行，两种都要支持）
{"status": "ok", "month": "2025-12", "data": {"特征": "65㎡公寓 | 单身 | 木地板", "效率": "覆盖率:90%\\n日均清扫:50㎡", "耗材": "主刷寿命:剩余30天\\nHEPA滤网:剩余10%", "对比": "优于85%同面积用户"}}
// find_service_slots（只列出还有名额的时段）
{"device_id": "D-1002-01", "slots": [{"slot_id": "S-east-20260113-2", "start_at": "2026-01-13T13:00:00+08:00", "end_at": "2026-01-13T15:00:00+08:00", "available": 2}]}
// find_consumables
{"device_id": "D-1006-01", "consumables": [{"sku": "SKU-FILTER", "name": "通用滤网", "kind": "filter", "price_cents": 3900, "stock": 80, "max_per_order": 2}, {"sku": "SKU-MOP", "name": "清洁拖布", "kind": "mop_pad", "price_cents": 2900, "stock": 0}]}
// get_my_orders_and_tickets
{"records": [{"kind": "order", "id": "O-1007-01", "device_id": "D-1007-01", "sku": "SKU-MAIN", "qty": 1, "amount_cents": 6900, "status": "processing"}, {"kind": "appointment", "id": "A-1004-01", "ticket_id": "T-1004-01", "slot_id": "S-west-20260113-2", "status": "scheduled"}, {"kind": "ticket", "id": "T-1004-01", "device_id": "D-1004-01", "error_code": "E09", "description": "…", "notes": "…", "status": "scheduled"}]}
```

## 1. 计划的数据模型（pydantic v2，strict，所有模型都 extra="forbid"）

```json
{
  "goals": [{"id": "g1", "type": "book", "text": "预约上门检查 E07"}],
  "steps": [{"id": "s1", "tool": "list_my_devices", "args": {}, "depends_on": [], "covers": ["g1"], "condition": null}],
  "ask_user": null
}
```

- **Goal**：
  - id 形如 g1、g2；
  - type 取 diagnose、warranty、knowledge、report、usage、slots、consumables、status、book、order、change；
  - text 为 1–60 个字符。
- **Step**：
  - id 形如 s1、s2；
  - tool 为 TOOLS 的键；
  - args 的值都是"参数来源"；
  - depends_on、covers 是列表；
  - condition 为 null 或"条件"。
- **ask_user**：null 或 `{"type": "which_device" | "which_slot" | "quantity" | "other", "text": 1–80 个字符}`。
- **数量限制**：goals 1–4 个，steps 0–6 个。
- **参数来源**（互斥，用 pydantic 判别联合或等价实现）：
  - `{"value": str | int, "evidence": str}`：原话取值；
  - `{"enum": str}`：枚举；
  - `{"text": str}`：原话文本；
  - `{"free_text": str}`：自由文本，只允许用于 rag_summarize.query；
  - `{"from_step": "sK", "pick": "only_device"}`；
  - `{"from_step": "sK", "pick": "device_matching", "hint": str}`；
  - `{"from_step": "sK", "pick": "slot_at", "date": 原话取值, "start": 原话取值}`，start 写成 HH:MM；
  - `{"from_step": "sK", "pick": "consumable_kind", "kind": 枚举中的一个}`；
  - `{"from_step": "sK", "pick": "record", "kind": "order" | "appointment", "id": 原话取值或 null, "status": "processing" | "scheduled" | null, "hint": str 或 null}`；
  - `{"from_pending": 参数名, "tool": 写工具名}`。
- **条件**：
  - `{"type": "warranty_in_force", "from_step": "sK", "component": "whole_machine" | "battery"}`；
  - `{"type": "record_threshold", "from_step": "sK", "field_hint": str, "op": "<=" | "<" | ">=" | ">", "value": int 或 float, "unit": "%" | "天", "evidence": str}`。
- 提供 `plan_json_schema() -> dict`，返回给 Ollama 结构化输出用的 JSON Schema（由模型生成即可）。

## 2. 规范化函数（以业务日期为准；先把全角字符转成半角，中文数字支持一到十二和"两"）

- `parse_date(evidence, business_date) -> str | None`：
  - 支持"今天、明天、后天、大后天"、"M月D日"、"M月D号"、"YYYY年M月D日"、"YYYY-MM-DD"；
  - 没写年份时取业务日期所在年份；
  - 返回 YYYY-MM-DD。
- `parse_month(evidence, business_date) -> str | None`：
  - 支持"上个月、这个月、本月、下个月"、"YYYY年M月"、"YYYY-MM"；
  - 单独的"M月"取最近一个不晚于业务月份的该月（业务日期 2026-01-12 时，"12月"是 2025-12，"1月"是 2026-01）；
  - 返回 YYYY-MM。
- `parse_time(evidence) -> str | None`：
  - 支持"N点"、"上午N点"、"下午N点"、"晚上N点"（下午和晚上在 N<12 时加 12）、"H:MM"、"N点到M点"和"N:MM–M:MM"（取开始时间）；
  - 返回 HH:MM。
- `parse_number(evidence) -> int | None`："两个"得 2，"3件"得 3，"一个"得 1。

## 3. validate_plan

```python
def validate_plan(plan: dict, ctx: dict) -> dict
```
ctx 的内容：
- `user_text`：本轮原话；
- `history_user_texts`：历史用户原话列表；
- `business_date`；
- `pending_cards`：`[{"action_id", "tool", "args"}]`；
- `remaining_model_calls`、`remaining_tool_calls`。

返回值：
- `{"ok": bool, "errors": [{"code": "P1".."P8", "step_id": str | None, "detail": str}], "plan": 解析后的 dict 或 None}`；
- 收集所有错误，不在第一个错误处停止；但 P1 失败时直接返回。

| 编号 | 规则 |
| --- | --- |
| P1 | 能按模型解析（strict、禁止额外键、数量和长度限制）；goal id 和 step id 都唯一 |
| P2 | tool 在 TOOLS 里；args 的键都是该工具的参数名；必填参数都有；args 里出现 user_id 就报错 |
| P3 | 参数来源合法（见下） |
| P4 | depends_on 只引用已存在的步骤，且包含该步所有 from_step 和条件里的 from_step；依赖图无环 |
| P5 | 每个 goal 至少被一个步骤的 covers 覆盖，或者 ask_user 不为 null；book、order、change 类 goal 必须分别被 propose_service_visit、propose_order、propose_change 覆盖（有 ask_user 时可以例外）；covers 只能引用已存在的 goal |
| P6 | 写步骤不能被任何步骤依赖；最多 2 个写步骤；condition 只能出现在写步骤上 |
| P7 | 服务流程规则（见下） |
| P8 | rag_summarize 步骤数不超过 remaining_model_calls；步骤总数不超过 remaining_tool_calls |

**P3 细则**：
- **原话取值**：evidence 规范化后必须出现在 user_text 或任一 history_user_texts 里。按参数类型复算并与 value 比较：
  - 日期类参数（start、end、from_date，以及 slot_at 的 date）用 parse_date；
  - month 用 parse_month；
  - slot_at 的 start 用 parse_time；
  - qty 和 days 用 parse_number；
  - code 必须等于 evidence 中的 `E\d{2}`；
  - id、target_id、device_id 用 value 时，value 必须原样出现在 evidence 里；
  - evidence 无法解析时，只要求 evidence 出现在原话里。
- **text**：必须是 user_text 的子串（规范化后）。
- **free_text**：只能用在 rag_summarize.query。
- **enum**：必须是该参数的枚举值。
- **from_step**：必须指向更早出现的步骤，工具类型要对应：
  - only_device、device_matching 对应 list_my_devices；
  - slot_at 对应 find_service_slots；
  - consumable_kind 对应 find_consumables；
  - record 对应 get_my_orders_and_tickets。
- **参数和来源的对应**：
  - device_id 只能用设备类 pick、原话取值或 from_pending；
  - slot_id、new_slot_id 只能用 slot_at 或 from_pending；
  - sku 只能用 consumable_kind 或 from_pending；
  - target_id 只能用 record 或原话取值；
  - description 只能用 text 或 from_pending；
  - 其他字符串参数可以用原话取值或 enum。
- **from_pending**：pending_cards 里恰好有一张该 tool 的卡片，且卡片 args 里有这个参数名。
- **条件**：from_step 的工具类型要对应（warranty_in_force 对应 check_warranty，record_threshold 对应 fetch_external_data）；record_threshold 的 evidence 必须出现在原话里，并且其中的数字等于 value。

**P7 服务流程**：写步骤之前（按依赖或步骤顺序都算"之前"），必须已有以下读步骤：

| 写步骤 | 需要的读步骤 |
| --- | --- |
| propose_service_visit | list_my_devices（device_id 来自 from_pending 时可以省略）；lookup_error_code（args 有 error_code 且不是 from_pending 时）；check_warranty（device_id 来自 from_pending 时可以省略）；find_service_slots（总是需要） |
| propose_order | list_my_devices（device_id 来自 from_pending 时可以省略）；find_consumables（总是需要）；fetch_external_data（有 record_threshold 条件时） |
| propose_change | get_my_orders_and_tickets（总是需要）；find_service_slots（change 为 reschedule 时） |

另外，goal 里有 knowledge 类型时，必须有 rag_summarize 步骤。

## 4. 参数解析

```python
def resolve_args(step: dict, results: dict, ctx: dict) -> dict
```
返回 `{"status": "ok", "args": {...}}`，或 `{"status": "unresolved" | "ambiguous", "param": str, "detail": str, "candidates": list}`。规则：

- 原话取值返回规范化后的值；enum、text、free_text 原样返回。
- **only_device**：设备恰好 1 台时取它；多于 1 台为 ambiguous（candidates 列出设备编号）；0 台为 unresolved。
- **device_matching**：hint 出现在 display_name 或 model_code 里的设备，唯一命中才成功。
- **slot_at**：先用 parse_date 和 parse_time 算出日期和开始时间，再在 slots 里找 start_at 的日期和 HH:MM 都相同的时段。找到就返回 slot_id，找不到为 unresolved（detail 写 slot_unavailable）。
- **consumable_kind**：在 consumables 里找该 kind，唯一命中才成功。
- **record**：
  - 先按 kind 过滤，再依次按 id（相等）、status（相等）、hint 过滤；
  - hint 匹配订单的 sku、工单的 description，或预约关联工单的 description（关联工单在同一结果的 records 里找）；
  - 唯一命中才成功。
- **from_pending**：取对应卡片 args 中的该参数。

## 5. 条件判断

```python
def evaluate_condition(cond: dict, results: dict) -> tuple[str, str]
```
返回 ("true" | "false" | "unknown", 说明)。

- **warranty_in_force**：在 coverage 中找对应部件，取其 in_warranty；找不到为 unknown。
- **record_threshold**：
  1. 在 data 的四个文本字段里，按真换行和字面量 "\\n" 拆成行；
  2. 找出含 field_hint 的那一行（大小写不敏感），取冒号后的第一个数值和紧跟其后的单位（% 或 天）；
  3. 单位与 cond.unit 相同时，按 op 比较；
  4. 找不到对应的行、找不到数值、单位不同，或 payload 的 status 不是 ok，都返回 unknown。

## 6. 写操作预检

```python
def precheck(tool: str, args: dict, results: dict) -> dict | None
```
不满足时返回 `{"reason_code": str, "message": str}`，满足时返回 None。

**propose_order**：在 results 里找 find_consumables 的结果，要求该结果的 device_id 等于 args.device_id。
- 找不到这样的结果：`no_catalog_evidence`；
- sku 不在列表里：`incompatible_consumable`，message 为"耗材与所选设备型号不兼容"；
- stock < qty：`out_of_stock`，message 为"库存不足"；
- qty 超过 max_per_order：`purchase_limit`，message 为"数量超过单次限购"。

**propose_service_visit**：slot_id 必须出现在某个 find_service_slots 结果的 slots 里，否则为 `slot_unavailable`，message 为"所选时段没有可约名额"。

**propose_change**：在 get_my_orders_and_tickets 的结果里找 target_id。
- 找不到：`no_record_evidence`；
- cancel_order 要求订单为 processing，否则为 `order_not_processing`，message 为"该订单当前不能取消"；
- reschedule 和 cancel_appointment 要求预约为 scheduled，否则为 `appointment_not_scheduled`；
- reschedule 还要求 new_slot_id 出现在某个 find_service_slots 结果里，否则为 `slot_unavailable`。

## 7. 测试（pytest，业务日期统一用 2026-01-12）

- **规范化**：
  - "明天"得 2026-01-13；"1月15日"得 2026-01-15；"上个月"得 2025-12；"12月"得 2025-12；
  - "下午一点"得 13:00；"16点到18点"得 16:00；"13:00–15:00"得 13:00；
  - "两个"得 2；全角数字也能识别。
- **合法计划**：
  - 设备 D-1002-01 报 E07，有"在保才约明天下午一点"的条件：list_my_devices → lookup_error_code → check_warranty → find_service_slots → propose_service_visit，带 warranty_in_force 条件，通过；
  - 下单：list_my_devices → fetch_external_data（"上个月"）→ find_consumables → propose_order，带 record_threshold（"不高于15%"），通过。
- **每条规则至少一个失败例**：
  - P1：多余键、重复 id；
  - P2：未知工具、多余参数、缺必填参数、出现 user_id；
  - P3：evidence 不在原话里、日期复算不一致、qty 与 evidence 不一致、from_step 指向的工具类型不对、from_pending 没有对应卡片、free_text 用在 description 上；
  - P4：引用不存在的步骤、有环；
  - P5：goal 没被覆盖、book 没有被 propose 覆盖；
  - P6：写步骤被依赖、3 个写步骤、条件写在读步骤上；
  - P7：缺 find_service_slots、缺 find_consumables、有阈值条件却缺 fetch_external_data、reschedule 缺时段查询；
  - P8：预算不足。
- **resolve_args**：两台设备时 only_device 为 ambiguous；device_matching 用"旗舰"命中 SV-400；slot_at 命中和未命中；consumable_kind 用 filter 命中 SKU-FILTER；record 分别按 id、按 status 唯一、按 hint"主刷"命中订单；from_pending。
- **evaluate_condition**：电池过保为 false；"HEPA滤网:剩余10%"满足 <=15 为 true；单位不同为 unknown；找不到字段为 unknown；字面量 "\\n" 和真换行都能拆分。
- **precheck**：缺货（SKU-MOP）、超过限购（3 > 2）、不兼容、时段不在列表里、订单不是 processing、找不到记录。

## 交付
只输出两个完整文件：`plan_core.py` 和 `test_plan_core.py`。每个公开函数写简短的 docstring。不要省略代码，不要用占位符。
