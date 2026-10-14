# service_v1：B1 草稿，待作者审核

业务日期固定为 **2026-01-12**；每题从规范化内容 SHA256 `77ead6a0f30e985529c66594d075b084a31ed6e679e78829af3bf2413c622ce3` 的新种子副本开始。全部人物、设备、型号和政策都是合成数据。当前没有 Agent 运行或模型结果；静态核验不代表系统已经通过 H1–H6。

| 类别 | dev | test |
| --- | ---: | ---: |
| visit | 3 | 5 |
| order | 2 | 4 |
| change | 2 | 4 |
| status | 1 | 2 |
| read_multi | 2 | 4 |
| reject_or_revise | 2 | 4 |
| precondition_fail | 2 | 4 |
| clarify | 1 | 2 |
| boundary | 0 | 1 |
| 合计 | 15 | 30 |

test 中 17/30 个任务涉及提议（visit/order/change/reject_or_revise）。用户轮次为 dev 17、test 36；确认/拒绝事件不算用户轮次。编号 SV-D01–15、SV-T01–30，每题 1–3 个用户轮次，同一题不切换身份。优先使用 1001–1010 的原始月度记录；双设备澄清使用 1020、1015，状态查询另使用 1014。逐 split 用户使用次数和全部检查结果见 `static_checks.json`，逐题可审阅内容见 `GOLD_REVIEW.md`。

## 使用与结构

```powershell
.\.venv\Scripts\python.exe -B -m evaluation.service_suite_check
.\.venv\Scripts\python.exe -B -m evaluation.service_suite_check --write-reports
.\.venv\Scripts\python.exe -B -m pytest -q tests/test_service_suite.py
```

CLI 默认只核对，`--write-reports` 才重写两个 `static_checks.json`。失败返回非零。它不注册工具、不运行模型、不实现生产确认路径，只在临时库里模拟**已经由 gold 明确指定**的提议、确认、拒绝与改参数顺序。

任务核心字段沿用规格：id/split/category/user_id/title/turns/final_db_checks/notes。用户轮有 query、expect、required_tools、allowed_tools、expected_proposals、forbidden_proposals、required_points、evidence；确认和拒绝只含 type/proposal_ref。`t1.p0` 按第一个**用户轮**计数，p 从 0 起，系统事件不占 t 编号。

两个用于可审计静态核验的可选扩展：`blocked_requests` 给出该用户轮试图进行但不满足条件的工具、严格参数及预期失败原因；`initial_db_checks` 给出初始计数，例如 E99 不存在、1014 没有预约。它们是审核/评分数据，不发给模型。注入例另有 injection 元数据，详见注入集说明。

上门提议的 args 不精确比较 description；`description_must_include` 列出关键词，静态模拟以这些词构造占位问题描述。其他参数精确比较；`slot_id_in` 仅在题面明确允许多个时段时使用，核验全部候选。本草稿没有使用这个放宽项。日期小时按种子中的显式 `+08:00` 时区解释，“明天”为 2026-01-13；未使用有歧义的“下周二”。整机和电池到期日当日计入。E09 使用电池条款，其余已定义上门错误使用整机条款；实际原因仍可能属于除外情形。

`final_db_checks` 只用表名、等值 where 和 expect_count，禁止任意评分 SQL。确认任务必须包含能区分“正确业务写入”和“只改待确认状态”的业务终态检查。拒绝任务同时核对业务表不变、pending_actions 为 rejected；这样“什么都没执行”不能冒充已正确拒绝。改数量/时间题核对旧卡片 superseded、新卡片 executed 及唯一正确终态。取消预约不评分工单是否关闭，取消订单不评分库存是否回补，这两项业务规则尚待作者决定。

## 隔离与审核

相似度使用各题全部用户题面串联、保留 Unicode 字母/数字并转小写后的字符二元组集合，跨 split 逐对算 Jaccard；≥0.6 全部列出，不把相似度当模型成绩。另逐个用户题面检查跨集合完全重复。清晰的共同业务术语允许出现，不靠泄露工具名区分题目。

当前为 B1 **未冻结草稿**。不生成 AUTHOR_DECISIONS.json 或 freeze_manifest.json。作者审核后另做 B2。题目经作者审核后，报告应写“题目经作者审核”，不能写“作者未见”。

本对话已经编写并读取 test 和注入 gold，之后不参与 S1–S3 实现。S1 另开对话，只读 dev.jsonl，不打开 test.jsonl、service_injection_v1/ 或两份 GOLD_REVIEW.md。冻结后的正式 test 每模式仅完整串行运行一次，异常、超时、截断和未执行保留分母。
