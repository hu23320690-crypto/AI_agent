# 检索改进实验与后续复验

本页保留第三阶段的历史检索对照，并记录当前代码的新题同题实验。文档整理于 **2026-10-07**；本轮于 2026-10-06 开始，2026-10-07 完成原 60 例、旧 12 题和新 40 题两版的记录与辅助复核。新题当前版的 2 个截断案例保持未知，不能视为任务成功。方法与结果见 [EVALUATION_V2.md](../docs/EVALUATION_V2.md)，命令入口见 [README.md](README.md)。历史结果使用当时冻结的实现和评分口径，分别保留。

## 第三阶段历史实验

当时保持知识文档、向量模型、聊天模型、生成提示词及 overlap=20 不变，先比较递归分块长度 200/400/600 与 Top-K 1/3/5，随后在 200 字分块上比较字符二元组 BM25 和向量 + BM25 混合检索。没有训练额外重排模型，也没有根据题号返回预设答案。

| 分块 / 检索 | Hit@1 | Hit@3 | Hit@5 | Top-5 平均正文字符 |
| --- | --- | --- | --- | --- |
| 200 字 / 向量 | 19/40 | 31/40 | 33/40 | 820 |
| 400 字 / 向量 | 15/40 | 30/40 | 34/40 | 1704 |
| 600 字 / 向量 | 13/40 | 21/40 | 26/40 | 2248 |
| 200 字 / BM25 | 13/40 | 26/40 | 32/40 | 859 |
| 200 字 / 混合 | 26/40 | 33/40 | 38/40 | 850 |

历史结果保存在 [分块实验汇总](results/retrieval_experiment_v1/summary.json)、[BM25 记录](results/retrieval_experiment_v1/bm25.json) 和 [混合检索记录](results/retrieval_experiment_v1/hybrid.json)。指标是标注证据字符覆盖达到阈值的命中，不是答案正确率或穷尽的语义 Recall。

当时选择 200 字分块、overlap=20、混合 Top-5，索引为 326 块。两个召回通道各取 20 候选，RRF 常数 60、等权；BM25 k1=1.2、b=0.75。中文使用连续二字片段，英文和数字保留词项，是字符级词法检索。未遍历调整 RRF 权重和参数。

向量 Top-3 的 31/40 与混合 Top-5 的 38/40 同时改变了 K 和召回方法；同为 Top-5 的对照是 33/40 与 38/40。增加 K 也增加生成上下文，不能把检索收益直接写成答案收益。历史完整问答及 Agent 结果见 [optimized_v1 汇总](results/optimized_v1/summary.md)，其中同时包含混合检索、K 变化与 Agent 输出边界修复，不能将全部变化归因于某个单一算法。

算法参考：[RRF 定义](https://www.elastic.co/docs/reference/elasticsearch/rest-apis/reciprocal-rank-fusion)、[BM25 参数](https://www.elastic.co/docs/reference/elasticsearch/index-settings/similarity)。项目实现轻量评分和融合，没有接入 Elasticsearch 服务。

## 历史 Agent 输出边界修复

原基线 A11 暴露了知识工具拒答后，Agent 再次生成无依据品牌与电话号码的问题。第三阶段增加了最终输出规则：本轮成功的知识工具结果作为最终知识回答，多结果合并去重；错误和报告使用确定性分支，只读取本轮 ToolMessage。

这一规则保留到当前版本，但图内部仍可能完成后续模型调用；它不保证消除调用或提高全部答案质量。RAG 工具本身仍会回答错误，未调用知识工具的回答也不受此规则保证。2026-10-01 安全复验观察到恶意 mock 工具文本被原样转发的输出污染 2/2，说明此规则仍有明确边界，见 [历史安全复验](../docs/CONTEXT_MANAGEMENT_VERIFICATION.md)。

## 当前实现与历史算法的差异

当前检索继续使用 200 字分块、20 字重叠、向量 / BM25 各 20 候选及 RRF=60，但增加了：

- 先按来源清单、版本和内容摘要筛选获准资料，使两个召回通道使用相同的可用来源；检索后、生成前后和提交时继续复查来源。
- RRF 全候选融合后进行规则式查询覆盖排序，配合单来源最多 3 块及近重复去重，选择最终 Top-5；没有实现标准 MMR 或神经重排模型。
- RAG 生成前执行上下文准入，超预算时按排名移除末尾完整证据块，因此实际送入模型的数量可能少于检索 Top-5。
- Runtime 共享时间和调用预算，失败不提交本轮历史；长历史采用完整轮次裁剪与低信任结构化摘要。

来源配额与查询覆盖排序的历史消融见 [Runtime 第四阶段验收](../docs/RUNTIME_STAGE4_VERIFICATION.md)。2026-10-01 的上下文验收当时只复验了长历史、4 次正常提问与 23 条安全记录，没有重跑全部 40 道知识回答。本轮已完整重跑原题并复核：知识严格通过 33/40（7 题部分正确），模型实际输入标注证据覆盖 38/40，资料不足 8/8，Agent 严格任务 10/12、工具名称路径 12/12，14 次真实 Agent 提问。历史检索 38/40 与本轮实际输入 38/40 测量位置不同；历史知识 33/40 与本轮 33/40 也来自不同版本和运行，不能因数字相同而合并口径。

A04／A05 核心无记录查询正确（`functional=true`），程序额外附加的 2025 年覆盖范围未包含在本次实际工具结果中，严格实际证据评分因此未通过。A08 的模型越权参数被控制器成功拦截；工具名称路径通过不表示参数合规。完整逐题说明见 [本轮评测](../docs/EVALUATION_V2.md)。

## 新 40 题的同题版本结果

在推理前冻结 28 道知识、6 道资料不足和 6 个 Agent 场景，历史 `optimized_v1` 业务版与当前版分别使用同一题集、知识资料和模型 digest，保留各自真实业务配置。结果、语义理由及原始记录分别保存于[历史版](results/holdout_v2_historical_optimized/summary.json)、[当前版](results/holdout_v2_current/summary.json)和[逐题对照](results/holdout_v2_comparison/comparison.json)。

| 指标 | 历史混合检索版 | 当前版 |
| --- | --- | --- |
| 知识严格通过，原计划 28 题 | 24/28；4 部分正确 | 21/28；6 部分正确、1 截断未知 |
| 资料不足，原计划 6 题 | 6/6 | 6/6 |
| Agent 全轮任务，原计划 6 例 | 0/6；6 失败 | 0/6；5 失败、1 截断未知 |
| Agent 工具名称路径 | 4/6 | 4/6 |
| Top-5 任一标注锚命中 | 28/28 | 28/28 |
| Top-5 全部必需锚命中 | 27/28 | 27/28 |
| 实际输入全部必需锚覆盖 | 27/28 | 27/28 |

知识配对为 21 题共同通过、2 题退步、4 题共同失败、1 题未知，无进步题。V2K19 当前答案漏软毛刷限定，V2K21 将机器人长期存放补电目标与拆卸电池存放电量混成同一条件；V2K22 生成截断，不能与完整失败或通过混为一项。V2K13 的一般越障口径、V2K28 的搬运准备范围存在已记录评分歧义，主评分仍使用冻结口径，不重写 gold 或移出分母。

Agent 配对为 5 例共同失败和 1 例未知。两版 V2A01 查对用户、月份和三个值，却由最终模板追加未请求字段；V2A02 查对11月与下一月，却未交付2个百分点和2㎡的差值；V2A04 漏晾干步骤。当前 V2A05/V2A06 摘要丢失污水仓滤网目标、晾干/不足不猜限制，或2025年9月及两个字段；摘要生成成功不能代替目标保持。历史版同样有未检索便拒答、未查表便断言无记录的问题。当前 V2A03 首轮有据，但第二轮生成截断，整案未知。

这一小样本对照不支持当前版全面提升；相同 Top-5 证据覆盖也不保证模型完整作答。排序、提示、来源治理、请求预算、报告和历史管理均随整体版本变化，不能把成绩差异归因于单一算法。版本标签隐藏及乱序由助手完成，但提示与行为可能透露实现特征；这是 Codex 辅助语义复核，未经独立真人专家审核。本轮未据新题输出修改业务实现，字段范围、差值交付、完整维护步骤和长历史目标保持作为后续改进项。

本轮离线程序检查为 pytest 367 通过、3 项权限跳过、270 个子断言通过，离线 doctor 146 项通过、pip check 无冲突，见[本轮检查](../artifacts/evaluation_v2/checks.json)。对应提交的 Windows/Linux 与 Docker 结果见 [Actions](https://github.com/hu23320690-crypto/AI_agent/actions) / PR 检查，本机验证不替代 CI 或真实语义评测。

## 当前代码的新实验

从项目根目录运行，准备 Python 3.12、锁定依赖、本地 Ollama 与获准知识索引。所有示例指定新的输出目录；不要向已保存的 baseline_v1、optimized_v1 或 holdout_optimized_v1 写入当前代码结果。

```powershell
.\.venv\Scripts\python.exe -B -m evaluation.run --run evaluation/results/my_current_experiment_v1 --stage all
.\.venv\Scripts\python.exe -B -m evaluation.report --run evaluation/results/my_current_experiment_v1
.\.venv\Scripts\python.exe -B -m evaluation.export --run evaluation/results/my_current_experiment_v1
```

这些命令测量当前实现，不会重建历史的纯向量 / 无来源治理条件。`report` 只汇总已有语义评分；新实验的答案需另外复核并记录理由，未评分项不能算通过。

新 40 题为 28 道知识题、6 道资料不足题、6 个 Agent 场景，每版计划 45 次真实用户提问。2 个长历史场景各注入 64 对合成已完成历史，这些种子不计为 128 轮真实模型交互。两版对照须使用同一 [冻结题集与评分规则](holdout_v2/README.md)，整体业务版本同时变化多项功能，不能将版本差异归因于单一算法。

历史版本隔离准备使用 [prepare_evaluation_variant.py](../scripts/prepare_evaluation_variant.py)，校验并复制 `optimized_v1` 的原样历史业务文件，配合当前评测观察代码；不移植当前 Runtime/上下文功能，不复制模型、索引或环境。CLI 和独立环境准备约定见 [同题版本对照](README.md#同题版本对照)。完成全部记录、复核、报告与导出后，使用 [seal_evaluation_run.py](../scripts/seal_evaluation_run.py) 生成或校验离线 SHA256 归档清单；它不是防篡改签名，也不替代恢复推理时的实时身份保护，见 [归档约定](README.md#证据快照与恢复约定)。

历史分块脚本 `evaluation.experiment` 和混合脚本 `evaluation.hybrid_experiment` 的当前入口已显式冻结，直接运行会抛出说明异常；它们不提供 `--run`。保留脚本与原结果供审查，重建历史实验需使用对应历史快照和当时环境，不能直接套用当前来源治理代码。

当前排序消融使用单独入口，保留候选、代码 hash 和各方案证据指标：

```powershell
# 从当前获准索引采集向量/BM25候选，比较配额和查询覆盖排序
.\.venv\Scripts\python.exe -B -m evaluation.retrieval_ablation --run evaluation/results/my_current_ablation_v1

# 回放历史候选，不调用 Ollama
.\.venv\Scripts\python.exe -B -m evaluation.retrieval_ablation --cache artifacts/runtime_stage4_retrieval_dev/candidate_cache.json --run evaluation/results/my_ablation_replay_v1
```

首次采集需要正式嵌入模型和已同步的索引；回放只描述捕获的候选字节，不证明来源当前仍被授权，也不产生答案准确率。

## 固定保留集

[holdout_v1](holdout_v1/cases.jsonl) 包含 8 道知识题、4 道资料不足题，在选择第三阶段最终检索方案前冻结，没有用于参数选择。历史第三阶段只对优化后系统运行这组题，没有同组基线，因此不能据此证明相对提升。Runtime 第四阶段后来保存了该组的检索候选与排序消融，当时不包含 12 题真实答案复验。本轮已在当前版本完整运行并复核这 12 题，全部通过；H06 题面只问功能名称而参考答案包含扩展解释，已保存歧义及判分理由。

复验当前系统使用新目录：

```powershell
.\.venv\Scripts\python.exe -B -m evaluation.run --dataset evaluation/holdout_v1/cases.jsonl --run evaluation/results/my_current_holdout_experiment_v1 --stage all
.\.venv\Scripts\python.exe -B -m evaluation.report --run evaluation/results/my_current_holdout_experiment_v1
.\.venv\Scripts\python.exe -B -m evaluation.export --run evaluation/results/my_current_holdout_experiment_v1
```

保留集现在已有公开历史结果，未来新增算法的独立泛化验证应另外冻结未用于调参的新题；不能一直在同一保留集上调整后再宣称没有见过。

## 比较与复核原则

原 baseline_v1 包含冻结业务代码和资料，当前代码不能继续写入该历史目录，这是版本保护。输入、模型、参数或代码改变时新建实验目录，保留失败、退步和未完成案例，不删除 manifest 绕过检查，不只重跑失败题以筛选最好成绩。

优先每次改变一个明确因素；必须同时改变多项时说明共同影响。语义评分按实际问题、参考证据和模型实际上下文完成，理由另存，不改写原模型输出。项目的语义复核由 Codex 助手执行，助手团队之间复查仍不属于独立真人专家标注或盲评。

这些实验串行执行，语料较小且多数为单次推理；一次成功率不等于重复运行稳定性，不代表生产规模、真实用户分布或完整事实真实性。完整指标定义、超时分母与快照执行区别见 [评测入口](README.md)。
