# 检索改进实验与后续复验

本页保留第三阶段的历史检索对照，并说明如何在当前代码上开展新实验。文档整理于 2026-10-05；历史结果使用当时冻结的实现，不能直接当作当前上下文管理版本的完整问答验收。当前评测入口与最新结果见 [README.md](README.md)。

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

这一规则保留到当前版本，但图内部仍可能完成后续模型调用；它不保证消除调用或提高全部答案质量。RAG 工具本身仍会回答错误，未调用知识工具的回答也不受此规则保证。后续安全测试观察到恶意 mock 工具文本被原样转发的输出污染 2/2，说明此规则仍有明确边界，见 [当前安全复验](../docs/CONTEXT_MANAGEMENT_VERIFICATION.md)。

## 当前实现与历史算法的差异

当前检索继续使用 200 字分块、20 字重叠、向量 / BM25 各 20 候选及 RRF=60，但增加了：

- 先按来源清单、版本和内容摘要筛选获准资料，使两个召回通道使用相同的可用来源；检索后、生成前后和提交时继续复查来源。
- RRF 全候选融合后进行规则式查询覆盖排序，配合单来源最多 3 块及近重复去重，选择最终 Top-5；没有实现标准 MMR 或神经重排模型。
- RAG 生成前执行上下文准入，超预算时按排名移除末尾完整证据块，因此实际送入模型的数量可能少于检索 Top-5。
- Runtime 共享时间和调用预算，失败不提交本轮历史；长历史采用完整轮次裁剪与低信任结构化摘要。

来源配额与查询覆盖排序的历史消融见 [Runtime 第四阶段验收](../docs/RUNTIME_STAGE4_VERIFICATION.md)。最终上下文配置只复验了长历史、4 次正常提问与 23 条安全记录，未重跑全部 40 道知识回答；旧 38/40 不能替代当前预算后的上下文命中或回答评分。

## 当前代码的新实验

从项目根目录运行，准备 Python 3.12、锁定依赖、本地 Ollama 与获准知识索引。所有示例指定新的输出目录；不要向已保存的 baseline_v1、optimized_v1 或 holdout_optimized_v1 写入当前代码结果。

```powershell
.\.venv\Scripts\python.exe -B -m evaluation.run --run evaluation/results/my_current_experiment_v1 --stage all
.\.venv\Scripts\python.exe -B -m evaluation.report --run evaluation/results/my_current_experiment_v1
.\.venv\Scripts\python.exe -B -m evaluation.export --run evaluation/results/my_current_experiment_v1
```

这些命令测量当前实现，不会重建历史的纯向量 / 无来源治理条件。`report` 只汇总已有语义评分；新实验的答案需另外复核并记录理由，未评分项不能算通过。

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

[holdout_v1](holdout_v1/cases.jsonl) 包含 8 道知识题、4 道资料不足题，在选择第三阶段最终检索方案前冻结，没有用于参数选择。历史第三阶段只对优化后系统运行这组题，没有同组基线，因此不能据此证明相对提升。Runtime 第四阶段后来保存了该组的检索候选与排序消融，这一轮不包含 12 题真实答案复验。

复验当前系统使用新目录：

```powershell
.\.venv\Scripts\python.exe -B -m evaluation.run --dataset evaluation/holdout_v1/cases.jsonl --run evaluation/results/my_current_holdout_experiment_v1 --stage all
.\.venv\Scripts\python.exe -B -m evaluation.report --run evaluation/results/my_current_holdout_experiment_v1
.\.venv\Scripts\python.exe -B -m evaluation.export --run evaluation/results/my_current_holdout_experiment_v1
```

保留集现在已有公开历史结果，未来新增算法的独立泛化验证应另外冻结未用于调参的新题；不能一直在同一保留集上调整后再宣称没有见过。

## 比较与复核原则

原 baseline_v1 包含冻结业务代码和资料，当前代码不能继续写入该历史目录，这是版本保护。输入、模型、参数或代码改变时新建实验目录，保留失败、退步和未完成案例，不删除 manifest 绕过检查，不只重跑失败题以筛选最好成绩。

优先每次改变一个明确因素；必须同时改变多项时说明共同影响。语义评分按实际问题、参考证据和模型实际上下文完成，理由另存，不改写原模型输出。项目的“人工式复核”由 Codex 助手按人工判读流程执行，尚未经独立真人专家或盲评。

这些实验串行执行，语料较小且多数为单次推理；一次成功率不等于重复运行稳定性，不代表生产规模、真实用户分布或完整事实真实性。完整指标定义、超时分母与快照执行区别见 [评测入口](README.md)。
