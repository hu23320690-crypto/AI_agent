# 第三步验收记录

日期：2026-10-01。第三步代码与必要控制验证已完成；正常知识回答仍有失败，不等于全面防护或所有问答正确。

## 交付

- 来源清单、稳定 ID、版本/SHA256、演示允许/审批/隔离/撤销状态；同字节解析、越界/链接拒绝、原子审批更新。
- 向量与 BM25 均先过滤当前合法片段；来源变化立即失效，sync 物理清理，去重和每文件最多 3 块。
- 系统消息与低信任资料 JSON 分离；RAG 子模型没有工具；每次请求/重试、生成后和提交前复核。
- 历史来源失效时不再传给后续模型；历史及提交检查进入有界等待，阻塞校验不延迟取消或提交迟到结果。
- 7 工具白名单、严格公开参数、内部参数注入拒绝、当前用户范围和本轮报告校验；拒绝先于执行。
- 管理 CLI、配置、必要测试、README 和边界说明。保留原始资料、旧集合和历史评测。

操作说明见 [RUNTIME_STAGE3.md](RUNTIME_STAGE3.md)。

## 离线和环境

最终 `scripts/manage.py test`：**153 项运行，152 项通过，1 项跳过，退出码 0**。相对第二步增加 66 项测试；它们不是 66 个真实模型攻击样本。

| 新增测试文件 | 项数 | 验证重点 |
| --- | ---: | --- |
| test_knowledge_security.py | 28 | 审批/坏清单、摘要、版本、路径、风险与误拦截复核、并发和原子写入 |
| test_governed_retrieval.py | 14 | 真实 Chroma 两路过滤、热缓存撤销、去重/来源配额、生成/重试/历史期间撤销 |
| test_tool_policy.py | 21 | 真实 LangChain 图中的白名单、类型/额外参数、内部参数注入、身份、报告、隐私 |
| test_commit_boundary.py | 3 | 阻塞校验下取消、最终提交截止时间、下一轮历史校验截止时间及迟到结果 |

实际符号链接创建测试因 Windows 权限不足跳过；模拟链接拒绝测试通过，不据此声称全部真实链接环境已测试。第一次回归暴露路径大小写断言和新 mock 写法问题，已修正并重跑；文件写权限失效的失败日志也保留，不能算通过结果。

`doctor`：139 项检查通过，两个 Ollama 模型可用。`pip check` 在本阶段通过，依赖版本未变。新来源清单和策略等文件已确认在源码打包选择范围中；本步没有重新生成交付 ZIP。

## 索引与检索对比

现有 6 份资料只标记 `demo_allowed`，风险规则未命中；不是事实或厂商适用性核验。新集合 `agent_chunks_qwen3_governed_v1` 首次同步 6 份、326 块、0 失败；最终同步检查跳过 6 份、没有隔离来源。

最终冻结复核包含 40 道知识题和 8 道资料不足题，使用原始数据集/资料摘要，不改标注和旧记录：

| 指标 | 历史 optimized_v1 | 第三步收尾版本 |
| --- | ---: | ---: |
| 标注证据 Top5 命中 | 38/40 | 38/40 |
| Top5 未命中题 | K32、K37 | K32、K37 |
| Top1 / Top3 命中 | 26/40、33/40 | 25/40、33/40 |
| 48 题检索耗时中位数 | 0.220 秒 | 0.273 秒 |
| 第三步检索 P95 | — | 0.366 秒 |

同机单次串行结果，增加授权/摘要核验有时间成本，不是大规模吞吐基准。资料不足题仍可能返回主题相近片段，不能用检索非空当作可回答。

最终代码和模型 digest 位于 `artifacts/runtime_stage3_completion/manifest.json`，结果位于该目录的 `retrieval.json`。来源清单 JSON 已纳入代码快照和恢复一致性检查，QA 的固定片段评测也复核当前来源权限。旧的检索实验脚本冻结，不再直接访问旧索引做当前安全验收。

## 真实模型和质量限制

提示隔离/治理上线后，先运行 K02/K14/K22/A02/A11，5 案例、6 提问都运行结束。原始记录在 `artifacts/runtime_stage3_final_verification/results.jsonl`，对应代码快照单独保存。随后仅对新增历史有界检查影响的 A11 做收尾版本复验，并保存本次实际召回片段；没有反复重跑到通过再删除失败。

| 案例 | 内容判断 |
| --- | --- |
| K02 | 三个必要点完整，2 分；原优化记录漏掉删除旧地图，1 分 |
| K14 | 木地板低档、瓷砖中档均有资料支持；未完整表达瓷砖中高档范围，保守记 1 分 |
| K22 | 断电与型号匹配完整，2 分；原也是 2 分 |
| A02 | 用户 1001、2025-08，报告所有字段匹配冻结 CSV，任务通过 |
| A11 | 首轮清理步骤有依据；第二轮“未提及断电要求”，未达到参考答案，任务失败；两轮工具选择均通过 |

K14 的旧记录对等价答法给了 2 分，本次保守的范围完整性评分与旧口径不一致，不能据此量化治理造成的退步。上述评分由 Codex 助手结合参考答案与片段复核，未经过独立专家评审；没有重跑 40 道回答，因此不更新旧 33/40 回答通过率。

第一次 A11 没有保存实际检索片段，不能事后将独立重检当作它的上下文；独立重检保存在 `artifacts/runtime_stage3_current_retrieval_diagnostic.json`。收尾复验见 `artifacts/runtime_stage3_completion/agent_recheck.json` 和 `agent_recheck_contexts.json`：两轮运行完成，历史核验进入有界 retrieval 调用，代码摘要全程一致。第二轮仍返回“未提及清理主刷前断开电源的要求”，任务未通过。此次实际 Top5 为维护保养 3 块、故障排除 2 块，没有 K19 的断电锚点；相近的“关闭电源”语句只对应更换集尘袋，不能直接作为主刷依据。该次证据不足是已确认的召回问题；尚未通过消融确定排序、来源配额和问题改写的各自影响。。

当前证据证明来源/执行控制按这些测试工作，不能证明资料事实真实、不能给出真实投毒攻击成功率。已知风险是正常追问召回与安全来源配额的质量取舍、规则误拦截、PDF 无独立进程硬内存限制，以及非生产认证。第四步应优先覆盖这些失败和正常对照，并固定评分口径。

## 复现

```powershell
.\.venv\Scripts\python.exe -B scripts/manage.py doctor
.\.venv\Scripts\python.exe -B scripts/manage.py test
.\.venv\Scripts\python.exe -B scripts/manage.py knowledge status
# 新目录：旧目录拒绝用不同代码续跑
.\.venv\Scripts\python.exe -B -m evaluation.run --stage retrieval --run artifacts/your_stage3_run
.\.venv\Scripts\python.exe -B -m evaluation.run --stage all --run artifacts/your_stage3_run --ids K02 K14 K22 A02 A11
# 可选：额外保存两轮 A11 的实际召回片段；拒绝覆盖已有复验
.\.venv\Scripts\python.exe -B artifacts/runtime_stage3_completion/recorded_agent_smoke.py --run artifacts/your_stage3_run
```

收尾复验的额外观测脚本和日志在 `artifacts/runtime_stage3_completion/`。生产 Runtime trace 不记录问题、参数和资料原文；该目录的观测数据是本地合成演示的专门评测产物。
