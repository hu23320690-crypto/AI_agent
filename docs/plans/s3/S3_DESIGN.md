# S3 设计：共用渲染器与 Plan → Execute → Verify

> 细化 [SERVICE_AGENT_PLAN.md](../SERVICE_AGENT_PLAN.md) 第 8 节。冲突时以本文为准，并在计划修订记录里登记。
> 设计依据只来自计划、契约和 `evaluation/service_v1/dev.jsonl`。实现和调优阶段不得打开 test、注入集和 GOLD_REVIEW。
>
> 2026-10-15 起草。

## 0. 总体思路

延续"LLM 提议，代码校验"：

- **planner（LLM）** 只做三件事：判断用户要什么（goals）、要查哪些工具（steps）、写操作的参数从哪里来（参数来源）。它**不写**任何编号（设备号、时段号、SKU、订单号）的字面值。
- **代码** 负责：校验计划、按依赖执行、从工具结果里解析出编号、检查用户附带的条件和写操作的前置条件、核对每个子目标是否都有证据，最后把回答渲染出来。
- react 和 plan 共用同一套**事实渲染**。区别在"结论说明"：react 用模型自己的文字（经过文本守卫过滤）；plan 用代码按子目标结果生成的固定句式。

## 1. 模式开关

- 新增 `config/agent_mode.yml`，内容为 `mode: react`（可选 `react | plan`）。可以用环境变量 `AGENT_MODE` 覆盖，校验方式与 `AGENT_TOOLSET` 相同。`config/toolset.yml` 不动。
- `plan` 必须配合 `toolset=service`，否则 doctor 报错。默认 `react`。

## 2. 共用渲染器（`service_desk/render.py`）

### 2.1 输入
本轮按调用顺序排列的工具结果列表，每项为 `{"tool": 名称, "args": 参数, "payload": 解析后的 JSON}`。失败时 payload 为 `{"status": "blocked" | "denied", "reason_code": ..., "message": ...}`。

### 2.2 事实块（`render_facts`）
- 每种工具一种固定格式，见附录 A。相同的 (tool, args) 只渲染一次。
- `fetch_external_data` 不在这里渲染，继续走现有的月度报告渲染（`utils/report_render.render_lookup`）。
- `rag_summarize` 的 answer 原样放在"资料说明"块里。
- 提议成功时渲染为待确认卡片的说明；失败时原样给出 message。

### 2.3 最终回答
- **react**：`guard_text(模型最终文本)` + 空行 + 事实块。模型文本被过滤空了，就只给事实块。
- **plan**：结论句（2.4 节）+ 空行 + 事实块。
- 两种模式都把待确认卡片的说明放在最后，并固定加一句"请在确认卡片上确认，确认前不会提交。"

### 2.4 plan 模式的结论句（按子目标结果生成）

| 子目标结果 | 句式 |
| --- | --- |
| 写操作已生成卡片 | 已为你准备{预约/订单/变更}的确认卡片。 |
| 用户条件不成立 | 按你的要求（{条件描述}），条件不成立，未生成{预约/订单/变更}卡片。 |
| 前置条件不满足 | {原因}，未生成{…}卡片。 |
| 指定时段没有名额 | 你指定的时段没有可约名额，未生成预约卡片。 |
| 需要用户选择 | 见 2.5 节 |
| 子目标没有拿到证据 | 未能完成：{goal.text}。 |

条件描述：`warranty_in_force` → "整机在保" / "电池在保"；`record_threshold` → "{月份}{字段}{不高于/低于/不低于/高于}{值}{单位}"。

### 2.5 需要用户补充信息时
`ask_user.type` 取值和模板：
- `which_device` → "你有多台设备：{设备列表}。请问是哪一台？"
- `which_slot` → "请从下面的可约时段里选一个。"（同时渲染时段事实块）
- `quantity` → "请告诉我需要的数量。"
- `other` → 使用 `ask_user.text`，并经过文本守卫。

### 2.6 文本守卫（`guard_text`）
按句切分（。！？；和换行），删除满足任一条件的句子，返回保留文本和被删句子：

1. 含"事实记号"，但该记号不在允许来源（本轮工具结果的 JSON 文本、用户本轮原话、会话里已有的最终回答）中出现。事实记号包括：
   - 编号：`D-…`、`T-…`、`A-…`、`O-…`、`S-…`、`SKU-…`、错误码 `E\d{2}`；
   - 日期：`YYYY-MM-DD`、`YYYY年M月D日`（两种写法视为同一日期）；
   - 时间 `HH:MM`；
   - 金额：`…元`、`…分`；
   - 百分比；
   - 带单位的数量：`\d+(天|个|件|次|㎡|分钟)`。
2. 声称写操作已完成：`已(为你|帮你)?(预约|下单|取消|提交|创建|改约)`，且前面没有"未""尚未""没有""不会"。

## 3. planner

### 3.1 输入（代码提供）
- 用户本轮原话；
- 最近 2 轮的用户原话和最终回答（截断，排除 `action_event`）；
- 本会话的 pending 卡片（tool、args、summary）；
- 业务日期；
- 工具清单（精简 schema）；
- 参数来源说明；
- JSON Schema。

输出用 JSON Schema 约束。输入超出上下文预算时，先删历史再删卡片摘要，不删本轮原话。

### 3.2 计划格式

```json
{
  "goals": [{"id": "g1", "type": "book", "text": "预约上门检查 E07"}],
  "steps": [
    {"id": "s1", "tool": "list_my_devices", "args": {}, "depends_on": [], "covers": ["g1"]},
    {"id": "s2", "tool": "lookup_error_code",
     "args": {"code": {"value": "E07", "evidence": "E07"},
              "device_id": {"from_step": "s1", "pick": "only_device"}},
     "depends_on": ["s1"], "covers": ["g1"]}
  ],
  "ask_user": null
}
```

- goal.type：`diagnose | warranty | knowledge | report | usage | slots | consumables | status | book | order | change`。
- step 可选字段 `condition`（3.4 节），只能用在 propose 步骤上。
- 最多 6 步，最多 2 个 propose 步骤。
- `ask_user`：`null` 或 `{"type": "which_device" | "which_slot" | "quantity" | "other", "text": "…"}`。

### 3.3 参数来源（planner 不写编号的字面值）

| 来源 | 写法 | 用途 |
| --- | --- | --- |
| 原话取值 | `{"value": 值, "evidence": "原话片段"}` | 错误码、月份、日期、数量、枚举以外的短值 |
| 枚举 | `{"enum": "filter"}` | 工具定义里的枚举参数 |
| 原话文本 | `{"text": "原话片段"}` | 上门描述 description |
| 检索问题 | `{"free_text": "…"}` | 只用于 rag_summarize.query |
| 唯一设备 | `{"from_step": "sK", "pick": "only_device"}` | sK 是 list_my_devices |
| 按提示选设备 | `{"from_step": "sK", "pick": "device_matching", "hint": "宠物"}` | 匹配 display_name 或 model_code |
| 按时间选时段 | `{"from_step": "sK", "pick": "slot_at", "date": 原话取值, "start": 原话取值}` | sK 是 find_service_slots；start 写成 HH:MM |
| 按种类选耗材 | `{"from_step": "sK", "pick": "consumable_kind", "kind": "filter"}` | sK 是 find_consumables |
| 选记录 | `{"from_step": "sK", "pick": "record", "kind": "order" 或 "appointment", "id": 原话取值（可选）, "status": "processing" 或 "scheduled"（可选）, "hint": "主刷"（可选）}` | sK 是 get_my_orders_and_tickets；hint 匹配 SKU、名称或工单描述 |
| 沿用卡片 | `{"from_pending": "参数名", "tool": "propose_service_visit"}` | 改主意时沿用本会话唯一一张同类 pending 卡片的参数 |

解析规则：
- 必须**唯一**命中才算成功。
- 0 个命中：`unresolved`。
- 多个命中：`ambiguous`。设备歧义转成 `ask_user=which_device`；时段歧义转成 `which_slot`。

### 3.4 条件（只描述用户明确说出的条件）

```json
{"type": "warranty_in_force", "from_step": "sK", "component": "whole_machine"}
{"type": "record_threshold", "from_step": "sK", "field_hint": "HEPA", "op": "<=", "value": 15, "unit": "%", "evidence": "不高于15%"}
```

- `warranty_in_force`：sK 是 check_warranty，读取对应部件的 `in_warranty`。
- `record_threshold`：sK 是 fetch_external_data。在记录的四个文本字段里，找含 field_hint 的那一行，取其中第一个数值和单位，与 value 比较。op 取 `<= < >= >`。单位必须一致，找不到或单位不一致时视为 `unknown`。

### 3.5 日期、时间、数量的规范化（P3 用）
以业务日期为准：
- 日期："今天/明天/后天/大后天"、"M月D日/号"、"YYYY年M月D日"，未写年份时取业务日期所在年份。
- 月份："上个月/这个月/本月/下个月"、"YYYY年M月"、"M月"，"M月"取最近一个不晚于业务月份的该月。
- 时间："N点"、"下午N点"（N<12 时加 12）、"HH:MM"、"N点到M点"（取开始时间）。
- 数字：阿拉伯数字和中文数字（一到十二、两）。

evidence 能按上述规则解析时，必须等于 value；解析不了时，只要求 evidence 出现在原话里。

## 4. validate_plan（确定性校验）

| 编号 | 检查 |
| --- | --- |
| P1 | 结构合法（strict、禁止额外键、长度限制），没有截断 |
| P2 | 工具都属于 service 工具集；参数名与工具定义一致；必填参数齐全；没有 user_id |
| P3 | 参数来源合法：evidence 和 text 必须出现在本轮或历史的用户原话里；日期、月份、数量按 3.5 节复算一致；from_step 指向更早、且工具类型匹配的步骤；from_pending 指向存在的唯一 pending 卡片；枚举值合法 |
| P4 | 依赖无环；depends_on 包含所有 from_step；不超过 6 步 |
| P5 | 每个 goal 至少被一个步骤覆盖，或者有 ask_user；book、order、change 必须由对应的 propose 步骤覆盖 |
| P6 | propose 步骤没有后继步骤；最多 2 个 |
| P7 | 服务流程规则（计划 8.7 节）：propose 之前必须已有该规则要求的读步骤。参数来自 from_pending 时，设备、错误码、保修这类信息视为复用，但新时段仍要 find_service_slots |
| P8 | 预计的模型调用（每个 rag_summarize 记 1 次）和工具调用都在剩余预算内 |

校验不通过时，把失败码和简短说明反馈给 planner，重新规划 1 次；还不通过就回退 react（第 7 节）。

## 5. 执行
1. 按依赖顺序逐步执行。每次工具调用都走现有工具路径：policy、Runtime 预算和轨迹记录，与 react 完全相同。
2. 执行前解析参数来源（3.3 节）。结果为 unresolved 或 ambiguous 时，这一步标为 skipped 并记录原因，依赖它的步骤也跳过。
3. propose 步骤执行前还要做两件事：
   1. 判断 condition：结果为 false 或 unknown 时跳过，并记录 `condition_false` 或 `condition_unknown`；
   2. 用已有的读取结果预检前置条件，不满足就不调用工具，记录原因：
      - 下单：兼容、库存 ≥ 数量、不超过限购（依据 find_consumables）；
      - 上门：时段在 find_service_slots 的结果里（依据 slot_at 的解析）；
      - 变更：目标记录状态为 processing 或 scheduled（依据 get_my_orders_and_tickets）。
   这样可以避免发出注定失败的 propose 调用。工具自身的前置检查仍然保留。
4. 每一步的结果状态：`done | skipped(原因) | error`。

## 6. verify
- 每个 goal 都要有 done 状态的证据步骤。book、order、change 类 goal 的情况有两种：已生成卡片；或者有明确的跳过原因（条件不成立、前置条件不满足、时段无名额），这也算已处理。
- 缺少证据时（步骤缺失、或因 error 失败），带着缺失清单重新规划 1 次，只补缺失的部分，已完成的结果复用。
- 仍有缺失就照常回答，缺失的子目标渲染成"未能完成：……"。

## 7. 回退 react
计划两次校验都不通过时，在同一轮、同一个 RunContext、剩余预算内转用 react。运行记录写 `plan_fallback`，回答按 react 的方式组装。

## 8. 预算
沿用计划 8.6 节：planner 最多 3 次（首次、校验失败重规划、verify 重规划），加上每个 rag 步骤 1 次，总计仍受每轮 8 次模型调用、12 次工具调用的限制。运行快照里记录 planner_calls、replans、fallback、skipped_steps。

## 9. 历史
本轮结束后，只把用户原话和最终回答提交进会话历史，与 react 相同，不写入计划和中间结果。

## 10. 分工

| 部分 | 负责 | 交付 |
| --- | --- | --- |
| DS-1 渲染器和文本守卫 | DeepSeek | 纯函数模块 + 单元测试，见 `DS1_RENDER_PROMPT.md` |
| DS-2 计划模型、校验、参数解析、条件判断、预检 | DeepSeek | 纯函数模块 + 单元测试，见 `DS2_PLAN_CORE_PROMPT.md` |
| S3-C 集成 | Codex | 审核并接入 DS-1/DS-2；模式开关；planner 提示和调用；图的执行、verify、回退；react 渲染修复；运行器 --mode plan；离线测试 |
| S3-D dev 调优 | Codex | 本机 Qwen 在 dev 上跑 react 和 plan，按第 11 节记录，冻结实现 |

## 11. dev 调优规则（S3-D）
- 只用 dev.jsonl。每一轮调优都记录到 `evaluation/SERVICE_DEV_LOG.md`：改了什么、依据哪些 dev 失败、两种模式的自动判分结果。
- 每次修改都必须是通用规则，不能按题号写分支。最多 5 轮。
- 结束时冻结实现：记录提交哈希和模型 digest。之后到 S5 之前不再改 Agent 行为。

## 附录 A：事实块格式

金额从分换算为"x.xx 元"；时间 `2026-01-13T13:00:00+08:00` 显示为"2026-01-13 13:00"。

| 工具 | 格式示例 |
| --- | --- |
| list_my_devices | 你的设备：D-1002-01（SV-200 扫拖一体型，购买日期 2024-07-12）。 |
| lookup_error_code（ok） | 错误码 E07（SV-200）：水箱供水检测异常。严重程度 2；不建议自行处理，需要服务人员上门检查。（可自行处理时写：可以先按手册自查，自查后仍异常再申请上门。） |
| lookup_error_code（not_found） | 型号 SV-300 没有错误码 E42 的定义，请核对屏幕上的编号。 |
| check_warranty | 保修（D-1002-01，以 2026-01-12 为准）：整机在保，到期日 2026-07-12；电池已过保，到期日 2025-07-12；耗材正常磨损不在保。有部件在保时再加一句：在保不代表一定免费，故障原因需服务人员检查。 |
| find_service_slots | 可约时段：1）2026-01-13 13:00–15:00（剩余 2）；2）……没有时写：未查到可约时段。 |
| find_consumables | 兼容耗材：SKU-FILTER 通用滤网，39.00 元，库存 80，单次限购 2；SKU-MOP 清洁拖布，29.00 元，缺货。 |
| get_my_orders_and_tickets | 订单 O-1007-01：SKU-MAIN × 1，69.00 元，处理中。工单 T-1008-01：E07，已预约上门。预约 A-1008-01：时段 S-west-20260115-2，已预约。 |
| get_daily_usage | D-1001-01 在 2025-06-01 至 2025-06-07（有记录 7 天）：清扫面积合计 350 ㎡，日均 50.00 ㎡，最大 52 ㎡。（数字仅示意格式） |
| rag_summarize | 资料说明：{answer 原文} |
| propose_*（成功） | 待确认：{summary}（有效期至 {expires_at 本地时间}）。 |
| 失败（blocked/denied） | {message} |

状态中文：processing 处理中，completed 已完成，cancelled 已取消，scheduled 已预约。指标：area_m2 清扫面积（㎡），duration_min 清扫时长（分钟），error_events 错误事件（次）。
