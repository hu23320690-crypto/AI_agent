# S0-A 售后服务合成数据与契约

**全部为合成数据，型号、错误码、政策均为虚构。** 七份知识资料是原创草稿，不代表现实产品的维修说明或服务承诺。本阶段只准备 SQLite 数据、Pydantic 契约、离线管理命令和资料；没有 Agent、API、界面或工具实现，没有注册工具，没有调用 Ollama，没有建索引或 collection。

## 配置与生成

独立配置为 `config/service.yml`：业务日期 `2026-01-12`，默认数据库 `service_data/service.db`，资料目录 `service_kb`，待确认动作有效期为 600 秒，`seed_content_sha256` 记录规范化种子内容哈希。数据库目录已加入 `.gitignore`，历史 `outputs/` 不提交。

```powershell
.\.venv\Scripts\python.exe -B scripts/manage.py service-db init
.\.venv\Scripts\python.exe -B scripts/manage.py service-db init --path C:\temp\a.db
.\.venv\Scripts\python.exe -B scripts/manage.py service-db init --path C:\temp\b.db
.\.venv\Scripts\python.exe -B scripts/manage.py service-db hash --path C:\temp\a.db
.\.venv\Scripts\python.exe -B scripts/manage.py service-db hash --path C:\temp\b.db
```

已有数据库默认拒绝覆盖并返回非零退出码；仅 `--force` 明确允许替换。先在目标目录的临时数据库中生成并执行断言，全部成功后再发布；无 force 时排他创建目标文件，防止并发初始化覆盖已有数据库。不要在其他读者使用数据库时执行初始化；默认发布的文件复制过程中不提供并发读取保证。强制重建使用同目录原子替换。失败不发布半成品，哈希命令只读且不会创建不存在的文件。

`service_desk.db.init_db(path)` 生成完整种子；可传 `business_date`、`csv_path` 供离线测试。`seed_database` 仅使用标准库、固定种子的 `random.Random(20260112)` 和显式业务日期，不读取系统时间，不使用随机 UUID。CLI 的相对 `--path` 按调用者工作目录解释，省略路径时按仓库根目录读取配置。

## 表与规模

| 表 | 主键 | 主要事实 | 种子行数 |
| --- | --- | --- | ---: |
| users | user_id | 1001–1050，region、created_at | 50 |
| models | model_code | 4 型号、族、发布日期、components_json | 4 |
| devices | device_id | 用户、型号、序列号、购买日期、固件 | 58 |
| warranty_policies | model_code, component | 整机、电池、耗材月份与排除条款 | 12 |
| error_codes | model_code, code | 名称、严重度、自行处理、上门、资料引用 | 48 |
| consumables | sku | 名称、类别、整数分单价、库存、限购 | 6 |
| consumable_models | sku, model_code | 耗材兼容关系 | 15 |
| orders | order_id | 用户、设备、型号、SKU、数量、整数分金额、状态 | 18 |
| tickets | ticket_id | 用户、设备、型号、错误码、描述、正常备注、状态 | 146 |
| service_slots | slot_id | 区域、开始结束时间、容量、已占名额 | 176 |
| appointments | appointment_id | 工单、时段、用户、状态 | 136 |
| telemetry_daily | device_id, date | 面积、时长、错误事件 | 5090 |
| pending_actions | action_id | 会话、用户、工具、参数 JSON/哈希、摘要、有效期、状态、结果 | 0 |
| audit_log | id | 时间、会话、用户、动作、事件、工具、参数哈希、详情 | 0 |

用户沿用 CSV 的数字标识；型号使用 SV-，设备 D-、工单 T-、订单 O-、预约 A-、时段 S-、审计 L-，SKU 使用 SKU-。待确认动作遵循计划的 UUID 标识设计，本阶段该表为空，不生成 UUID。金额是整数分，日期为 ISO 日期字符串，时间带显式 `+08:00` 偏移。`components_json` 是用于一致性核对的静态型号能力；订单与工单增加型号列，以复合外键约束设备型号、耗材兼容性与错误码。

订单、工单、预约的 `source_action_id` 均有允许 NULL 的 UNIQUE 和待确认动作外键，历史记录全部为 NULL。外键约束用户与设备归属、预约与工单归属。审计表有拒绝 UPDATE、DELETE 的触发器，仅追加。该设计不代替 S1/S2 的身份和执行前置检查。

1001–1010 各一台设备，覆盖 2025 全年每天；1011–1050 中逢 5 的用户有两台设备，共 8 个双设备用户。这些新增用户的所有设备仅覆盖业务日期之前 30 天，即 `2025-12-13` 至 `2026-01-11`，没有耗材寿命列。所有 CSV 月度面积目标通过零和配对变化生成，月均值保持一致。

未来时段覆盖 `2026-01-13` 至 `2026-01-26`，north/east/south/west 每天各有 3 个时段；每天的首个时段约满，其余有可约名额。另有每区域两条历史时段，供已完成和取消记录使用。所有名额占用都有对应预约，取消预约不占名额。历史订单有已完成、处理中和已取消；工单另含已预约、未安排时段的处理中记录；预约含已预约未上门、已完成和已取消。

## CSV 一致性与例外

扫描所有用户和月份的“清洁效率”“耗材”“对比”三列，将字面量 `\n` 解为行分隔符；关键词映射包括主刷、边刷、胶刷、滤网/HEPA、尘盒、水箱/拖地、集尘袋、电池、机械臂、跨楼层、毛发、地毯增压。证据保留原月份、原列名和命中的词。

| 用户 | 设备 | 型号 | CSV 实际部件/功能关键词（所有月份取并集） |
| --- | --- | --- | --- |
| 1001 | D-1001-01 | SV-100 基础扫地型 | 主刷、HEPA、滤网 |
| 1002 | D-1002-01 | SV-200 扫拖一体型 | 边刷、尘盒、拖地 |
| 1003 | D-1003-01 | SV-300 宠物型 | 胶刷、尘盒、毛发、地毯增压 |
| 1004 | D-1004-01 | SV-100 基础扫地型 | 主刷、滤网 |
| 1005 | D-1005-01 | SV-200 扫拖一体型 | 电池、水箱 |
| 1006 | D-1006-01 | SV-400 自集尘旗舰型 | 边刷、集尘袋、跨楼层、机械臂 |
| 1007 | D-1007-01 | SV-100 基础扫地型 | 滤网、尘盒 |
| 1008 | D-1008-01 | SV-200 扫拖一体型 | 主刷、水箱 |
| 1009 | D-1009-01 | SV-300 宠物型 | 胶刷、滤网、毛发 |
| 1010 | D-1010-01 | SV-100 基础扫地型 | 电池、边刷 |

唯一例外：1006 的“对比”列短语“建议增加机械臂配件”，因为新增建议不证明已安装。只删除该短语，同单元格的“跨楼层”仍参与检查。2025-03 的“机械臂配件已加装”、2025-07 的“机械臂配件故障”、2025-08 的“机械臂配件已更换”不是例外，必须满足型号能力；因此 SV-400 支持这一合成配件。计划 4.3 表只简列集尘袋和跨楼层，这里保留全文 CSV 的实际证据，没有修改计划。

生成时始终执行（即使 Python 使用 `-O`）以下断言：

1. CSV 用户的设备型号符合计划分配，具备所有实际提及部件。
2. 有“日均清扫:N㎡”的用户月份完整覆盖该月；日均值按 ROUND_HALF_UP 四舍五入后等于 N。目前共有 24 个用户月份。
3. 1001–1010 各设备有完整的 365 天记录。
4. 整机在保、过保同时存在，且至少一台设备整机与电池保修状态不同。
5. 四个型号都有 E07，至少一个错误码跨型号名称不同；存在缺货和限购耗材。
6. 每区域未来 14 天的每一天同时有可约和约满时段。
7. 所有外键一致；pending_actions、audit_log 的种子内容为空。

例如在业务日期当天：D-1002-01 整机在保（2026-07-12 到期），电池过保（2025-07-12 到期）；D-1001-01 整机过保（2025-07-12 到期），电池在保（2026-07-12 到期）。D-1003-01 整机在保（2026-02-20 到期）；D-1004-01 整机过保（2024-10-05 到期）。期限按日历月增加，目标月没有对应日时取月末，到期日当天计入，正常耗材磨损不在保；未评估实际损坏原因。

## 内容哈希

`content_sha256` 以只读事务读取全部非 SQLite 内部表，按表名排序；每张表按完整主键及声明顺序排序，将行转成键值对象。规范 JSON 使用 `sort_keys=True`、`ensure_ascii=False`、`separators=(',', ':')`、`allow_nan=False`，包含空表，再对其 UTF-8 内容计算 SHA256。没有主键的表拒绝哈希。哈希不包含 SQLite 文件字节、schema 或触发器；表结构与约束由独立测试核对。

本次规范化种子 SHA256 为 `330d9dda773f97f8bc72da0561c6e1b5bcde504ff2b01d3920984052262983ef`。Windows、Linux CI 均独立生成两份并与配置比较，打印本机 SQLite 版本和两个哈希。不同 SQLite 版本不要求文件字节相同。

## 工具契约初测

`service_desk/contracts.py` 定义 12 个参数模型、返回模型和三个工具集合常量。所有模型继承 strict=True、extra="forbid"，所有参数都不接收 user_id。日期参数是严格 ISO 字符串，兼顾 Python 字典和 JSON 验证；真实日期另行校验。日用量区间按包含首尾两天计数，最多 31 天；查时段 days 为 1–14，省略默认 7 天。改约必须提供新时段且目标为预约，取消订单/预约必须匹配对象前缀且不得带新时段。归属、保修、库存等业务判定留在 S1。

`fetch_external_data` 返回模型保留旧 ok/not_found 字段和月度数据的中文键；序列化使用 `model_dump(by_alias=True, exclude_none=True)`。旧 rag_summarize 实际返回字符串，与计划的“所有返回结构化 JSON”存在包装层差别，因此结果模型以 `answer` 字段原样保留文本，外带 references；本阶段不改旧工具或返回路径。三个 propose 返回只允许 pending 状态，没有执行结果。

用 `langchain_core.utils.function_calling.convert_to_openai_tool` 转换 12 个参数模型，保留简短中文描述和完整校验 schema；按上述规范 JSON 序列化，UTF-8 长度 5052 字节。项目 `model/token_count.py` 的本地 Qwen 缓存计数为 **1407 tokens**，方法 `local_qwen2_bpe`，无需 Ollama 或网络，不含聊天模板边界开销。模型摘要为 `359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`。

该值超过 1200 的目标 207 tokens；本阶段保留全部 12 个工具，没有修改计划或合并工具。S1 可先压缩 schema 的冗余 title/default 元信息；若仍需要合并，建议将 find_service_slots 与 find_consumables 组合为带查询类别的设备资源查询，再评估总 schema 和模型调用行为，不保证简单相减即可达到目标。所有签名变动需作者确认和计划修订。

## 知识资料与检查

七份 UTF-8 TXT 位于独立 `service_kb/`，未加入旧来源清单，未建 collection。四份型号手册分别仅适用对应型号，错误码、保修上门政策、耗材指南适用范围为 `["all"]`。manifest 记录逐文件字节 SHA256、范围和说明。错误码条目的 doc_ref 能解析到错误手册标题；所有耗材名称和兼容范围与数据库一致。资料不写保修月数、价格、库存数字，动态事实均要求查询系统。

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q
.\.venv\Scripts\python.exe -B scripts/manage.py doctor --offline
```

doctor 在原检查之外新增独立的配置合法性、schema 存在、资料清单与文件一致性三项，不要求数据库已生成。容器只增加资料/数据包的打包与可写数据库目录，仍保持原启动入口；CI 另验证非 root 用户可运行离线 doctor 和数据库命令。

Windows 沙箱默认临时目录可能不允许测试所需的文件替换。遇到该环境问题，可将 TEMP、TMP 指向有写权限的工作区临时目录再运行原命令，无需修改旧代码或测试。旧测试、旧配置、data、Agent、API、RAG 和模型文件均保持原样。S0-B 的题集、来源审批/独立 collection、工具实现与两段式执行均为后续阶段，不在本次交付内。
