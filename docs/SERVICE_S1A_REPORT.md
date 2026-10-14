# S1-A service 工具集交付记录

基于 PR #6 合并后的 main 613ceb1，分支 feat/service-agent-s1a。仅实现本阶段；不合并 PR。
全部业务数据、型号、错误码、政策和资料均为合成演示数据。

## 配置与接入

config/toolset.yml 默认 toolset: legacy；AGENT_TOOLSET=legacy|service 覆盖，非法值使 doctor 非零退出。
ReactAgent 新增 session_id（省略则生成 UUID）及 service_db_path（省略使用 config/service.yml 的 db_path）。
service 的今天固定为业务日期 2026-01-12，提议的创建和过期时间使用真实 UTC 时钟。
业务数据库须先用 scripts/manage.py service-db init 生成；工具不会创建或初始化缺失数据库。
每次调用独立打开连接，读使用 mode=ro，提议使用 mode=rw、BEGIN IMMEDIATE。
模型侧 schema 完全来自 model_tool_schemas()；policy 使用冻结的严格参数模型，字段集合一致。
身份、会话、路径、日期不能由公开参数提供。查询会话用户不存在时也统一拒绝，不能探测存在性。

## 工具行为与 token

所有成功返回均通过 contracts.py 对应结果模型严格验证，再输出 JSON。
所有归属失败统一 identity_mismatch，不回显输入，不区分编号不存在和属于其他人。
公共拒绝码还有 tool_not_allowed、arguments_invalid、injected_argument、schema_mismatch、identity_missing；
提议缺少会话标识为 session_missing。固定失败 JSON 只包含 status、reason_code、message。

| 工具 | 参数（? 可省略） | 归属或可见性 | 成功返回 | tokens |
| --- | --- | --- | --- | ---: |
| list_my_devices | 无 | 会话用户 | 设备、型号、序列号尾四位、购买日期、固件 | 46 |
| lookup_error_code | code, device_id? | 指定设备归属；不指定且多设备先 clarify | 型号对应定义，或 not_found/clarify | 69 |
| check_warranty | device_id, component? | 设备归属 | 部件在保、到期日、条款与原因 | 82 |
| rag_summarize | query, device_id? | 指定设备归属 | 原检索 answer，references 暂为空 | 70 |
| fetch_external_data | month | 用户从会话注入 | 原月度 ok/not_found JSON；同步报告上下文 | 60 |
| get_daily_usage | device_id, start, end, metric | 设备归属 | 首尾包含、至多31天的观察天数、合计、日均、最大 | 117 |
| find_service_slots | device_id, from_date?, days? | 设备归属；仅用户区域 | 未来有名额时段，默认次日起7天、最多14天 | 93 |
| find_consumables | device_id, kind? | 设备归属及型号兼容 | 名称、整数分单价、库存、限购 | 100 |
| get_my_orders_and_tickets | kind?, id? | 订单/工单/预约归属 | 固定公开字段的状态记录 | 80 |
| propose_service_visit | device_id, error_code?, description, slot_id | 设备归属、时段同区域 | pending 提议、规范参数、哈希、代码摘要、真实有效期 | 107 |
| propose_order | device_id, sku, qty | 设备归属；SKU兼容用户至少一台设备才可见 | pending 提议及整数分金额 | 95 |
| propose_change | target_id, change, new_slot_id? | 目标归属、新时段同区域 | pending 变更提议 | 112 |

实际 ChatOllama.bind_tools(build_service_tools()).kwargs['tools']，按 HTTPX 的紧凑 Unicode JSON、
保留插入顺序序列化，用 model/token_count.py 的 local_qwen2_bpe 计数：
**总数 1033 tokens / 4762 UTF-8 字节**，小于1200目标；各工具独立计数之和1031，
列表边界与相邻分词导致总数相差2。未包含聊天模板边界。
模型摘要 359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7。
与 S0 文档1017的差异来自 S0 使用 sort_keys=True，而本次使用绑定请求的实际插入顺序。
复现：.\.venv\Scripts\python.exe -B scripts/count_service_tools.py。没有调用 Ollama、下载模型或新增依赖。

保修复用冻结种子中的 add_months：购买日期加月份，目标月份没有对应日取月末；
购买日到到期日均包含，零月耗材正常磨损不在保，E09摘要看电池、其他看整机。
缺失日记录返回零观察天数和零聚合值，不推算缺失日期。
报告上下文使用 lookup_result、lookup_results、report_data、report，与 legacy 相同。

## 提议前置条件与验证

归属先于业务状态检查，并在提议事务内重新校验，防止检查和写入之间状态变化。
成功只插入一行 pending_actions 和一行 event=proposed 的 audit_log，同一事务提交。
args_json 使用 sort_keys=True、ensure_ascii=False、separators=(',', ':')、allow_nan=False，
省略为 None 的可选参数；args_sha256 对其 UTF-8 字节计算。摘要不采用模型文本或问题描述。
时段/库存不预占，重复提议不取代旧动作，不实现确认、拒绝、过期、取代或业务执行。

| 条件失败 | 码 | 对应新增测试 |
| --- | --- | --- |
| 设备、SKU、时段、订单或预约无归属/可见性 | identity_mismatch | test_unknown_and_foreign_ids_have_identical_denials；test_proposals_check_ownership_before_state |
| 严格类型、必填、前缀或控制字符非法 | arguments_invalid/injected_argument | test_invalid_proposals_write_nothing；test_graph_rejects_identity_argument_before_dispatch |
| 上门错误码不属于当前型号定义 | error_code_not_found | test_each_failed_precondition_writes_nothing |
| 上门/改约时段不是业务日期之后 | slot_not_future | test_each_failed_precondition_writes_nothing |
| 上门/改约时段无名额 | slot_unavailable | test_each_failed_precondition_writes_nothing |
| 设备已有 scheduled 预约 | appointment_exists | test_each_failed_precondition_writes_nothing |
| SKU可见但与所选设备不兼容 | incompatible_consumable | test_each_failed_precondition_writes_nothing（1015双设备） |
| 库存小于数量，包括零库存 | out_of_stock | test_each_failed_precondition_writes_nothing |
| 超单次限购 | purchase_limit | test_each_failed_precondition_writes_nothing |
| 改约/取消预约不是 scheduled | appointment_not_scheduled | test_each_failed_precondition_writes_nothing（completed/cancelled） |
| 取消订单不是 processing | order_not_processing | test_each_failed_precondition_writes_nothing（completed/cancelled） |

每种失败都比较全部表行，确保无写入。
test_success_adds_only_pending_and_audit 覆盖上门有/无错误码、下单、改约、取消预约、取消订单六条成功路径：
逐行比较全部业务表，验证两个新增行、用户与会话、状态、金额、SHA256及真实600秒期限。
test_audit_failure_rolls_back_pending 强制审计插入失败，确认待确认行也回滚。
test_cancel_between_checks_and_commit_rolls_back_both_inserts 取消发生在检查之后，两个插入均回滚。
运行锁保护提交点，已取消的工具不能晚到写入；已成功提交提议后图执行失败时，
待确认动作可能留存，但历史不会提交且业务表不变，生命周期处理属于S2。

## 验证数字

| 组 | pytest | doctor --offline |
| --- | --- | --- |
| origin/main基线（没有service实现，默认legacy） | 1338 passed，291 subtests passed，3 skipped | 152/152 |
| 完成后默认legacy完整回归（含新增service测试） | 1473 passed，291 subtests passed，3 skipped | 153/153 |
| 完成后 AGENT_TOOLSET=service，四个新增测试文件 | 135 passed | 153/153 |

service环境只运行新增测试组；旧测试本来就按legacy契约编写，完整回归在默认legacy下运行。
没有将service测试组宣称为全仓service环境回归。运行后删除 AGENT_TOOLSET。
135项新增测试包含两种工具集、所有成功结果模型、归属与非存在性、月末与到期日、
前置条件、事务、哈希、真实图绑定、月度报告与RAG、预算、取消及只提交成功轮次。
基线首次受沙箱写日志权限阻挡，授权重跑得到上述基线数字。
实现中发现旧测试用 object.__new__(ReactAgent) 绕过构造函数，缺少新状态；
使用缺少状态即legacy的兼容分支修复，未修改旧测试。

## legacy与保护路径核对

- test_legacy_tools_and_prompt_exactly_unchanged 对默认和显式legacy逐字比较完整系统提示，
  比较原七工具的绑定顺序；旧报告/RAG/安全/Runtime全仓回归全部通过。
- 旧检索实现、配置、知识资料、索引清单未改。原候选缓存
  artifacts/runtime_stage4_retrieval_dev/candidate_cache.json 回放与已提交的 ablation.json 比较，
  49查询×3方案所有Top-5文档完全相同。回放没有调用模型或重新建索引。
- 已有测试文件未修改：相对origin/main仅新增四个测试文件。
- 不改冻结清单内文件、不改旧评测、data、已有配置键、requirements或全局Git配置。
  冻结路径通过Git差异名称/对象元数据核对，隔离题集不由实现者读取。
- pytest内已有静态题集测试正常执行；没有依据题集调整代码，也没有读取本阶段dev题集。
- 原未跟踪outputs/保留，不纳入提交。

## 契约差异、取舍与后续范围

冻结contracts只有成功结构；不修改它，新增StrictModel失败封套用于policy拒绝和前置条件失败。
服务RAG保持旧检索，只在工具层包answer、最终旧RAG路径解包；型号过滤与独立service集合留S1-B。
旧rule报告解析不使用today作为首次相对目标参照；service单独注入业务月作为首次相对目标参照，
legacy参数与行为不变，后续相对月份保持已提交目标参照。错月工具结果不能代替所要求的月份。
自查后仍异常、在保才约等自然语言服务条件写在共用服务提示中；工具严格执行7.1业务效果表
的数据库前置条件，不增加冻结契约没有的自然语言证据参数，也不宣称提示是结构性安全保证。
共用事实渲染器、确认卡片界面/API、确认/拒绝/执行及待确认生命周期按原安排留S2/S3。
其他售后回答仍使用模型文本，本阶段仅做离线功能验证，不声称真实Qwen服务任务评测通过。
