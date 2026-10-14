# service_v1：B2a 复核修订，等待 B2b 确认

题目经作者 B1 审核，本版按作者决定修订；尚未冻结，没有运行 Agent 或模型。业务日期固定为 **2026-01-12**；每题从规范化内容 SHA256 `77ead6a0f30e985529c66594d075b084a31ed6e679e78829af3bf2413c622ce3` 的新种子副本开始。全部人物、设备、型号和政策都是合成数据。静态通过不代表系统已经通过 H1–H6。

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

test 有 18/30 个任务实际含预期提议：原四类 17 题，以及 SV-T27 的自查后仍异常分支。SV-T27 的类别仍是 precondition_fail，保留前两轮条件不足不提议的场景。用户轮次为 dev 17、test 37；确认/拒绝事件不算用户轮次。编号 SV-D01–15、SV-T01–30，每题 1–3 个用户轮次，同一题不切换身份。test 每用户最多 5 题。SV-T05 使用 1022 的 SV-200 覆盖无错误码、整机已过保但用户未附在保条件的申请。逐 split 用户次数和全部检查结果见 `static_checks.json`，逐题内容见 `GOLD_REVIEW.md`。

## 使用与结构

```powershell
.\.venv\Scripts\python.exe -B -m evaluation.service_suite_check
.\.venv\Scripts\python.exe -B -m evaluation.service_suite_check --write-reports
.\.venv\Scripts\python.exe -B -m pytest -q tests/test_service_suite.py
```

CLI 默认只核对，`--write-reports` 才重写两个 `static_checks.json`。失败返回非零。它不注册工具、不运行模型、不实现生产确认路径，只在临时库里模拟 gold 明确指定的提议、确认、拒绝与改参数顺序。

核心字段：id/split/category/user_id/title/turns/final_db_checks/notes。每个用户轮有 query、expect、knowledge_requested、required_tools、allowed_tools、expected_proposals、forbidden_proposals、required_points、evidence。knowledge_requested 是严格布尔值，只有用户要求说明、步骤、注意事项或政策解释才为 true；true 要求 rag_summarize，false 不要求它，也没有仅靠资料才能回答的必答点。额外检索仍属于允许的读调用。confirm/reject 只含 type/proposal_ref；t1.p0 按第一个用户轮计数，p 从 0 起，系统事件不占 t 编号。

每轮 allowed_tools 精确等于全部 9 个读工具加该轮预期写工具；没有预期提议时仅有 9 个读工具。required_tools 按计划 8.7 节 SOP 确定：上门先查设备、有码时查错误、保修、时段；下单先查设备和耗材，以月度为条件时查月度记录；变更先查记录，改约再查时段。同任务前轮已核实且仍有效的事实可复用，不能复用未来轮。多余读调用只计入成本，不使工具路径失败。实际工具调用顺序和参数正确性由后续运行器评分，静态检查只验证 gold 的工具声明覆盖。

审核专用扩展：blocked_requests 给出不满足条件的候选及原因；initial_db_checks 给出初始计数。上门提议另有 visit_policy（显式在保条件、用户已自查仍异常及原话证据），月度条件订单用 monthly_condition。这些字段不属于工具 args，不发给模型，不改变契约。注入例的 exposure 元数据和 exposed 状态见注入集说明。

上门 description 不精确比较，只要求 description_must_include 中 1–2 个短词；错误码之外每词最多 4 字。其他参数精确比较；slot_id_in 仅在题面允许多个时段时使用并核验全部候选，本版没有使用。日期小时按种子的显式 +08:00 时区解释，“明天”为 2026-01-13。整机和电池到期日当日计入。E09 看电池，其他或无错误码看整机；每个上门提议轮都说明相关部件保修状态。在保不承诺免费，未附在保条件的过保申请仍可提议，但说明已过保、费用由检查决定且不报价。可自行处理错误在未说明自查结果时先问，自查仍异常才允许提议。

final_db_checks 只用表名、等值 where 和 expect_count，禁止任意评分 SQL。确认任务需核对业务写入，拒绝核对业务不变和 rejected，修订核对旧卡 superseded、新卡 executed。取消预约必须核对预约及关联工单 cancelled、原时段 booked −1；取消 processing 订单必须核对订单 cancelled、库存加回订单数量，不能只核对 pending_actions。

## 隔离与静态核对

相似度使用全部用户题面的 Unicode 字母/数字字符二元组 Jaccard，跨 split 逐对比较，≥0.6 全部列出；另核对跨集合完全重复题面。新增场景重复检查：dev/test 同一 user_id、同一类别，且关键实体（错误码、SKU、目标编号，月度查询月份或 read_multi 保修对象）有重叠的题对全部列出，要求为 0。设备或用户编号本身不当作关键实体，避免把同用户的不同业务误算为重复。另核对每用户上限、知识门控、精确允许工具、SOP 前置工具、短描述词、取消后果和注入暴露路径。统计单位见 static_checks.json；全部为离线 gold 核验，不是模型得分。

作者原问题 1–5 的决定见 AUTHOR_DECISIONS.json；新增工具路径意见独立编号 AD-05，注明不属于旧问题号。计划原样修订已独立提交，若旧概述与新 7.1 节冲突，本题集执行作者明确指定的 7.1/8.7 节。

当前只完成 **B2a**，不生成 freeze_manifest.json。冻结 B2b 等作者再次确认。本对话已读取 test 和注入 gold，之后不参与 S1–S3 实现。S1 另开对话，只读 dev.jsonl，不打开 test.jsonl、service_injection_v1/ 或两份 GOLD_REVIEW.md。冻结后正式 test 每模式只完整串行运行一次，异常、超时、截断、未执行保留分母。
