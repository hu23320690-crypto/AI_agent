# 新题泛化测试 generalization_v1

2026-10-07 在 Agent 修复后构造的新题集。先审核并冻结问题、参考答案、必答点、来源行号、评分规则与业务代码身份，再执行当前版一次串行测量。本轮不根据答案调参或修复，不选最好一次重跑。

| 类别 | 案例 | 真实用户提问 |
| --- | ---: | ---: |
| 知识事实、条件和操作组合 | 28 | 28 |
| 资料不足 | 6 | 6 |
| Agent 报告、多轮与长历史任务 | 6 | 11 |
| 合计 | 40 | 45 |

一组长历史注入 64 对合成已完成消息、128 条消息；它们不计入 45 次真实提问，也不等于 64 次真实模型交互。真实模型调用数量包含实际摘要、Agent 规划与 RAG 生成，另由运行轨迹统计。

新题使用现有 6 个知识资料与演示 CSV，覆盖旧题未请求的事实以及已知能力的新对象、字段、顺序和约束组合。每题 `novelty_note` 说明区别；[construction_audit.json](construction_audit.json) 保存旧题 hash、辅助相似度排查和构造方法。部分基础机制与旧题相同，不能把改月份或换部件单独宣称为全新能力；同域新题表现也不能证明跨域泛化。

- [cases.jsonl](cases.jsonl)：题目、逐轮金标准、工具允许路径和证据；生成时只传用户输入、受信身份及历史，不给金标准。
- [dataset_manifest.json](dataset_manifest.json)：冻结时刻、源与题集 hash、业务身份、数量。
- [SCORING.md](SCORING.md)：固定评分规则，分别检查完整性、实际证据支持和 Agent 全轮完成。

在模型、索引与依赖准备好后，从项目根目录运行：

```powershell
.\.venv\Scripts\python.exe -X utf8 -B -m evaluation.run --dataset evaluation/generalization_v1/cases.jsonl --run evaluation/results/generalization_v1_current --stage all --timeout 300
```

为每条原始结果保存包含 `result_sha256` 的独立复核记录后汇总、导出和封存：

```powershell
.\.venv\Scripts\python.exe -X utf8 -B -m evaluation.report --run evaluation/results/generalization_v1_current
.\.venv\Scripts\python.exe -X utf8 -B -m evaluation.export --run evaluation/results/generalization_v1_current
.\.venv\Scripts\python.exe -X utf8 -B scripts/seal_evaluation_run.py --run evaluation/results/generalization_v1_current
```

评测器会冻结代码、数据、参数与身份，并在每题前后核验；QA 采用冻结检索结果调用生产 RAG 入口，Agent 执行真实多轮工具流程。现有 runner 未自动复制 gzip tokenizer 缓存及评分文本，归档时需依据冻结 descriptor/manifest 核验字节 hash 后补入快照，再封存。超时、错误和未复核项仍保留原分母。新环境另选运行目录，不覆盖此轮。

G1N03/G1N04 是对“仅凭演示数据作不支持的推断”的拒答测试，但此 QA 入口只接收知识检索资料，不会将 CSV 或金标准喂给模型；拒答成功不能证明模型实际查阅并分析了全年 CSV。真正的 CSV 工具及知识/记录指标区分在 G1A01–G1A04 的 Agent 流程中检查。

标注和语义复核由 Codex 助手团队完成，未经独立真人或领域专家审核；资料未核实为真实厂商手册。只有当前版的这一轮，没有旧版同题对照，不能从与旧集的不同分数推断优化增益。以后若按这些题修复，必须将本集标为已见回归集，并另建未见测试。
