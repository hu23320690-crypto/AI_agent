# 当前版本回归与新 40 案例对照

本页保留修复前版本的冻结实验与结果。后续按这些反例修改业务的实现和复测另见[Agent任务修复](AGENT_TASK_REPAIR.md)；holdout_v2 已用于调试，后续结果属于已见题回归。

本轮于 2026-10-06 开始，先在当前 main 的业务代码上重跑原 60 案例和旧 12 道保留题，再使用推理前冻结的新 40 案例比较历史混合检索版与当前版。于 2026-10-07 完成全部 152 条原始案例记录、分离语义复核与输入身份核对；执行完成、检索命中与答案通过分别统计。

## 固定输入与版本

- 当前业务版本：main `2d24de975db90d9d823e680690221f9f2375fa93`。本轮增强评测观测与汇总工具，不根据新题输出修改业务代码或参数。
- 历史对照：`evaluation/results/optimized_v1/snapshot/`，2026-09-18 历史混合检索版；23 个业务代码/配置/提示文件按历史 manifest 验证。它已包含 BM25 + 向量 + RRF，不称为最初纯向量版。
- 两版使用同一 6 份知识资料与演示 CSV，7 个来源 hash 与历史 manifest 一致。
- 本机 Qwen3:4b digest：`359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`；Qwen3-embedding:4b digest：`df5bd2e3c74cd8d069d21dc038f1b359fcdc9458fce1c99bd43c9eb1518ff907`。模型标签恢复时重新核对。
- 使用同一 Python 3.12 环境与核心依赖，temperature=0，串行推理，单案例外部墙钟上限 240 秒。当前版保留其 120 秒共享 Runtime 预算与生成上限；历史版保留其原有行为。

两版同为 200 字分块、20 字 overlap、Top-5、每路 20 候选、RRF 常数 60。当前版另包含来源治理、来源配额/覆盖排序/去重、低信任资料提示、Runtime、生成预算与历史压缩。总差异是版本整体对照，不能归因于一个单独算法。FastAPI 和容器的协议与运行验证见 [API](API.md) 和 [部署](DEPLOYMENT.md)，问答分数不用于替代并发、取消或容器验证。

## 样本与冻结

| 题集 | 案例 | 真实用户提问计划 | 本轮用途 |
| --- | ---: | ---: | --- |
| 原开发集 | 60：40 知识、8 不足、12 Agent | 62 | 当前版质量回归，保留原题及歧义 |
| 旧保留集 | 12：8 知识、4 不足 | 12 | 当前版旧题回归；已公开使用，不再视为全新盲测 |
| 新 holdout_v2 | 40：28 知识、6 不足、6 Agent | 45 / 版本 | 历史版与当前版同题对照 |

新题集 SHA256：`7c67b4c778c1f3297d6ac1aef8f993940f291b78bb7331078c0c1a3d2278a0d9`。评分规则 SHA256 由其 [manifest](../evaluation/holdout_v2/dataset_manifest.json) 固定；[逐题数据](../evaluation/holdout_v2/cases.jsonl)和[评分说明](../evaluation/holdout_v2/SCORING.md)在推理前完成审核。28 道知识题细分 18 道事实/同义/部件区分与 10 道操作/条件/跨段组合。

两例长历史每个版本各注入 64 对合成已完成消息，再执行真实摘要/追问。这不是 64 次真实模型交互。新集有少量通用规则复用和单问/多轮同事实复用，不能假设全部是独立同分布样本；范围限于同一项目资料，不证明跨领域泛化。原资料的厂商真实性未被验证。

## 采集与语义复核

QA 先保存该版本的检索结果，再仅回放检索到各版本的生产 `rag_summarize`。因此 RAG 生成耗时不含预先检索，不能称为在线端到端延迟。Agent 使用完整生产交互，不替换决策与工具结果。

观测在实际 Ollama 请求边界记录消息、工具、参数、响应和 usage；只有确实出现在该次输入中的完整资料块才计为实际上下文。分别保存原始 Top-K 证据命中与预算裁剪后模型输入中的证据命中。新多证据题使用全部必需锚覆盖；历史任一锚命中及 MRR 保留其定义，不混用名称。

当前版的请求预算估计、摘要准入与重试信息来自该版 Runtime trace。历史版没有 Runtime 或上下文预算功能，保存其实际消息、生成参数与 provider usage，不为它补造预算估计。usage 是实际模型调用记录，包括摘要、决策与 RAG 调用，不是答案质量判分。

题目金标准不传给受测模型。内容完整性与忠实度分别复核，资料不足和 Agent 任务单列。错误、超时、截断、缺失轮次及未复核项留在计划分母，不默认通过。历史 Agent 可能在一次正常结束的决策后直出截断的 RAG 文本，汇总使用原始响应派生执行分类，同时保留原始状态。

评分另存 `reviews.jsonl`，每项绑定最终原始结果 SHA256；汇总拒绝错配、重复 ID 或非法评分。[本轮统一规则](../evaluation/SEMANTIC_REVIEW_V2.md)在推理前确定。隐藏版本标签和打乱次序仅是辅助复核措施；评分由同一 Codex 助手团队完成，尚无独立真人/领域专家标注或盲评。

`summary.agent.tool_selection_pass` 是全部真实轮次都满足工具选择规则的案例数，分母是该题集计划 Agent 案例数（原集 12，新集 6），不是成功案例数。`planned_real_turns` 另列原集 14、新集 11 次计划真实 Agent 提问；不能将案例通过数除以轮数作为工具选择率。逐轮工具选择保存在原始 `turns[].tool_selection` 中；若另外汇总逐轮比例，应同时列计划轮数、已观测轮数、通过轮数与未知轮数。

旧题有题面与金标准范围歧义，评分理由会明确标注。历史原评分保持原样；当前按题面复核的分数变化不能直接当成算法提升。新集版本对照使用同一冻结标准，分别报告进步、退步、共同失败及未知。

## 可复现入口

真实模型运行前完成环境 doctor 与获准索引准备。每次使用新的运行目录；历史失败和未完成项不可覆盖成最好成绩。

在当前项目根目录选择已经安装锁定依赖的 Python 3.12 环境，并保存解释器绝对路径。以下示例使用项目内 `.venv`；若使用现有外部环境，直接将 `$evalPython` 改为该环境的绝对 `python.exe` 路径。本轮实际环境为 `E:\pycharm\AI_agent\.venv\Scripts\python.exe`。两版和四份运行使用同一解释器与 Ollama，按下列顺序串行完成；不要同时运行多个真实推理进程，以免改变等待时间与模型资源竞争。

```powershell
$evalPython = (Resolve-Path '.\.venv\Scripts\python.exe').Path
& $evalPython -B -m evaluation.run --dataset evaluation/cases.jsonl --run evaluation/results/my_current_regression --stage all --timeout 240
& $evalPython -B -m evaluation.run --dataset evaluation/holdout_v1/cases.jsonl --run evaluation/results/my_legacy_holdout --stage all --timeout 240
& $evalPython -B -m evaluation.run --dataset evaluation/holdout_v2/cases.jsonl --run evaluation/results/my_new_holdout_current --stage all --timeout 240

# 创建全新的隔离历史业务目录，不复制索引、环境或日志。
& $evalPython -B scripts/prepare_evaluation_variant.py --target ../historical_optimized_experiment --dataset evaluation/holdout_v2/cases.jsonl
# 在该新目录使用同一绝对解释器；历史配置从空索引重建。
Push-Location '../historical_optimized_experiment'
try {
    & $evalPython -B -m evaluation.run --dataset evaluation/holdout_v2/cases.jsonl --run evaluation/results/my_new_holdout_historical --stage all --timeout 240
} finally {
    Pop-Location
}
```

各版采集后另行进行语义复核，不能用 `report` 自动生成评分。新集两版还没有 `reviews.jsonl` 时，先回到当前项目生成隐藏版本标签、随机排列的辅助复核包：

```powershell
& $evalPython -B -m evaluation.compare --before ../historical_optimized_experiment/evaluation/results/my_new_holdout_historical --after evaluation/results/my_new_holdout_current --output evaluation/results/my_paired_comparison
```

只用 `blind_cases.jsonl` 中的问题、冻结参考、实际输入和回答复核，暂时隐藏 `blind_key.jsonl`。复核完成后再按 `sample_id` 映射回版本与案例，将评分分别保存到两份运行目录的 `reviews.jsonl`。模型请求提示可能暴露版本行为，隐藏标签不能保证完全盲化；如果此前已看过带版本名称的 audit，则不能将复核描述为盲式评分。

每条评分的 `result_sha256` 必须针对 `results.jsonl` 内最终、完整的原始结果对象计算，而非答案字符串、格式化文件字节或未追加墙钟时间的 worker 中间记录。以下 Python 示例只展示构造和校验步骤，不执行语义评分、不写入示例满分：

```python
from pathlib import Path
from evaluation.run import read_rows
from evaluation.report import result_sha256, validate_reviews

run = Path('evaluation/results/my_new_holdout_current')
cases = read_rows(run / 'cases.jsonl')
results = read_rows(run / 'results.jsonl')
row = next(r for r in results if r['id'] == 'V2K01')
review = {
    'id': row['id'],
    'result_sha256': result_sha256(row),
    'answer_score': None,   # 独立复核后填写 0、1 或 2；未复核保持未知。
    'grounded': None,       # 核对实际输入后填写 True 或 False。
    'note': '待复核',
    'method': 'Codex 辅助复核，尚未经用户或领域专家独立审核',
}
validate_reviews(cases, results, [review], require_bound=True)
# Agent 使用 task_pass，并逐轮保留理由；不以工具选择或 usage 自动给分。
```

保存完整独立评分后，重新运行两版的汇总、导出和同题比较；前一次无评分比较的未知项不会被自动判为通过：

```powershell
& $evalPython -B -m evaluation.report --run evaluation/results/my_new_holdout_current
& $evalPython -B -m evaluation.export --run evaluation/results/my_new_holdout_current
& $evalPython -B -m evaluation.report --run ../historical_optimized_experiment/evaluation/results/my_new_holdout_historical
& $evalPython -B -m evaluation.export --run ../historical_optimized_experiment/evaluation/results/my_new_holdout_historical
& $evalPython -B -m evaluation.compare --before ../historical_optimized_experiment/evaluation/results/my_new_holdout_historical --after evaluation/results/my_new_holdout_current --output evaluation/results/my_paired_comparison
```

compare 核对题集、来源、模型、依赖、执行工具、温度和外部超时等控制输入；允许业务配置的有意差别。未评分结果保持未知。产物包括比较 JSON/Markdown、隐藏标签的辅助复核输入和版本映射，完整原始记录仍独立保留。

完成 `report`、`export` 和比较后、首次 seal 前，运行 [complete_evaluation_assets.py](../scripts/complete_evaluation_assets.py) 补全归档资产。原采集的 suffix 白名单漏掉 gzip：冻结身份已绑定 tokenizer 描述文件及其缓存 SHA，但原快照没有保存 gzip 资产字节。补档检查冻结描述文件和缓存 SHA，侧录 `capture_phase=post_collection` 与补档日期，不将此次补档冒充事前新增冻结。不能据此声称原始快照在任意时刻都保存了完整资产字节。预算方法、模型 digest、模板 hash 和事件数仅从实际 Runtime trace 按 run ID 去重统计；历史版无描述文件、无 Runtime 时侧录 `asset=null`，不补造 trace。

```powershell
& $evalPython -B scripts/complete_evaluation_assets.py --run evaluation/results/my_new_holdout_current
& $evalPython -B scripts/complete_evaluation_assets.py --run ../historical_optimized_experiment/evaluation/results/my_new_holdout_historical
& $evalPython -B scripts/seal_evaluation_run.py --run evaluation/results/my_new_holdout_current
& $evalPython -B scripts/seal_evaluation_run.py --run ../historical_optimized_experiment/evaluation/results/my_new_holdout_historical
```

`--run` 接受相对本项目根目录或绝对运行路径；`--assets-from` 可指定包含 `config/` 的资产源项目根目录，默认本项目。首次补档的日期默认当前 UTC 日期，也可用 `--capture-date YYYY-MM-DD` 明确记录；已有合法 sidecar 优先保留原捕获日期和原始字节。已有不一致资产或 sidecar 拒绝覆盖；原始结果必须完整覆盖唯一计划 ID，允许错误、超时或截断终态，补档不代表答对。脚本不修改 raw、manifest、reviews 或业务代码，也不调用模型；已 seal 的归档只允许验证已有一致文件，不新增补档。

## 本轮结果

本轮结果没有证明当前版问答质量全面提升。新题检索指标两版相同，当前版知识严格通过从历史版 24/28 降到 21/28；不足题两版均 6/6。新增 Agent 约束题两版均没有整案通过，必须先处理这些反例，再描述质量收益。所有分母按计划案例计，截断不算通过。

### 当前版原题回归

| 运行 | 知识严格通过 | 资料不足严格通过 | Agent 严格任务 | 执行完成 |
| --- | ---: | ---: | ---: | ---: |
| [原 60 例](../evaluation/results/current_main_regression_v2/summary.json) | 33/40；7 部分 | 8/8 | 10/12；2 未通过 | 60/60 |
| [旧 12 题](../evaluation/results/current_main_legacy_holdout_v2/summary.json) | 8/8 | 4/4 | 无 | 12/12 |

原题知识实际输入标注证据覆盖 38/40，所有 40 个已交付回答忠实于本次输入；覆盖和忠实不能替代内容完整性。Agent 工具名称路径为 12/12。A04/A05 无记录查询本身正确（`functional_task_completed=true`），附加的 2025 年数据覆盖范围不在该次工具结果中，严格实际证据任务口径未通过。A08 的错误跨用户参数被控制器阻止，最终任务通过，模型参数提案本身仍不合规。旧 H06 只问功能名称，主评分完整，参考中未请求的扩展作为替代口径保留。原题历史评分未覆盖或重写，不能把前后评分范围差异称为算法提升。

### 新 40 例同题对照

| 指标 | 历史混合检索版 | 当前 main 业务版 |
| --- | ---: | ---: |
| 案例原始记录 | 40/40 | 40/40 |
| 执行完整案例 | 40/40 | 38/40；2 截断 |
| 知识严格通过 | 24/28（85.7%） | 21/28（75.0%） |
| 知识部分 / 截断未知 | 4 / 0 | 6 / 1 |
| 已完整交付知识答案忠实 | 28/28 | 26/27；1 条件混同 |
| 资料不足严格通过 | 6/6 | 6/6 |
| Agent 全轮任务通过 | 0/6；6 未通过 | 0/6；5 未通过、1 未完成未知 |
| Agent 工具选择案例通过 | 4/6 | 4/6 |
| 知识 Top-5 任一标注锚命中 | 28/28 | 28/28 |
| 知识 Top-5 全部必需锚覆盖 | 27/28 | 27/28 |
| 知识实际模型输入全部必需锚覆盖 | 27/28 | 27/28 |

两版 Top-1/3/5 全部必需锚覆盖为 17/28、25/28、27/28；任一锚命中为 20/28、27/28、28/28。任一锚 MRR@5 均 0.8345，不是多证据完整性 MRR。28 道知识题均已观测实际输入；V2K24 缺通用断电锚，属于检索证据缺口，不能以另一个水位故障锚命中宣称证据完整。

同题知识结果为 21 共同通过、2 退步（V2K19、V2K21）、4 共同失败、1 未知（V2K22）；没有通过状态进步。资料不足 6 共同通过；Agent 5 共同失败、1 未知（V2A03）。完整对照见 [comparison.json](../evaluation/results/holdout_v2_comparison/comparison.json) 和 [逐题比较](../evaluation/results/holdout_v2_comparison/comparison.md)，逐项理由及替代评分留在各版 `reviews.jsonl`。

- V2K19 当前答案漏软毛刷限定；V2K21 将长期存放机器人补电 80–90% 与拆下电池存放前 50–70% 混为同一条件的冲突。数值出现在资料中，不代表适用对象和阶段正确。
- V2K22 与 V2A03 当前输出被提供方标记截断，Runtime 拒绝提交；没有重新运行选择更好答案，也没有以未交付的生成内容判通过。
- V2A01 两版查询月份、账号、三个数值正确，但完整报告模板额外列出未请求字段，违反“只列三项”。V2A02 两版正确查询两个月，却未向用户交付差值并违反字段限制；内部曾生成差值不代表用户收到差值。
- V2A04 两版维护回答漏晾干提醒。历史 V2A03 第一轮漏 WiFi 前提；当前第一轮完整，但第二轮截断，整案仍未知。
- 两版长历史 V2A05/V2A06 都未完成后续任务。历史版首轮基本保留目标，但第二轮未实际检索/查表即声称资料未说明或无记录。当前版摘要只保留整理文件主题，丢失污水仓滤网/晾干约束或月份/字段，后续泛化检索或要求用户再次补充。

V2K02 的油种、V2K05 的损坏风险、V2K25 的遮挡成因、V2K26 的升级按钮等未被题面单独要求的扩展，主评分按推理前 rubric 不机械要求复述；V2K13 来源口径、V2K28 楼层步骤等保留主评分与替代范围解释。相同题目的两版使用相同标准。这些范围歧义和助手评分限制不能被隐藏；详细解释见各项 `annotation_ambiguity` / `note`。

### 长历史、调用和运行边界

每版两例各注入 64 对合成完成历史，共 128 对 / 256 条消息；每例只执行 2 次真实用户提问。历史版两个场景实际模型请求各为 130、132 条输入消息；当前版请求为 V2A05 的 2、7、9、2、11 条和 V2A06 的 2、7、9 条，包含摘要和后续决策/工具请求。消息量缩小可被观测，但目标保留失败，不能将其描述为上下文压缩成功或任务质量提升。

新40所有实际模型调用：历史版 56 次、provider 输入 101087 / 输出 92657 tokens；当前版 59 次、输入 117675 / 输出 98562 tokens。包括摘要、决策和 RAG，不是每个答案一次调用；当前本轮总输入/输出均更多。provider usage 记录完整，不含模型加载、embedding 调用或运行前准备成本。耗时见各 summary，QA 生成与 Agent 交互口径不同，单次本机串行不支持显著性、吞吐量或单算法收益结论。

当前新40在 2026-10-06 的第7条已提交记录后遇到外部进程中断，V2K08 有未提交尝试。完整 worker/诊断日志先保存在本地私有目录，已完成7条保留不重跑，2026-10-07 核对模型 digest 后续跑其余案例。[interrupted_attempts.json](../evaluation/results/holdout_v2_current/interrupted_attempts.json) 保存该不完整尝试的 hash 与说明；它不是完成答案，不计额外评分或最好结果。两条最终截断保留，未以重试替换。其他三份运行亦保留各自 manifest/raw。

### 实现检查与后续使用

2026-10-07 完整离线 pytest：**367 通过、3 个 Windows 符号链接权限场景跳过，270 个 unittest 子断言通过**；offline doctor 146 项通过，`pip check` 无冲突。见 [checks.json](../artifacts/evaluation_v2/checks.json)、[pytest.log](../artifacts/evaluation_v2/pytest.log) 和 [doctor](../artifacts/evaluation_v2/doctor_offline.json)。首次 sandbox Temp 原子替换失败，以及随后两例来源撤销测试的绝对路径预算失败，均保留私有完整诊断和 checks 中的 hash/摘要。只为这两例配置既有 scripted context policy，保留撤销异常、调用次数和重试边界断言；没有修改冻结业务预算或通过放宽业务规则改变本轮答案。首次 PR CI 的 Linux 与 Docker 检查通过，Windows 的四个排除目录模拟链接子断言因 fixture 路径身份未经规范化而失败；测试 fixture 已先 resolve 再构造模拟路径，归档脚本与拒绝边界未变。本机完整回归再次通过，首次CI失败见 [ci_history.json](../artifacts/evaluation_v2/ci_history.json)。Windows/Linux 和 Docker 对应提交的 CI 见 [GitHub Actions](https://github.com/hu23320690-crypto/AI_agent/actions)，本机离线通过不替代真实模型质量或容器推理验证。

同题范围一致性核查纠正了历史 V2A04 首轮初评：拒绝混装已满足该轮题面，主分由1改2，与当前版一致；第二轮遗漏晾干，整案仍未通过。原评分与旧seal完整保留，裁决理由、前后评分与未变raw hash见 [review_adjudication.json](../evaluation/results/holdout_v2_historical_optimized/review_adjudication.json)；没有修改题面或选择重跑答案。

四份运行在评分、报告、实际 tokenizer 资产补档后生成 SHA256 seal；seal 不要求全部答对，也不是签名或事实正确证明。运行目录为 [原60](../evaluation/results/current_main_regression_v2/)、[旧12](../evaluation/results/current_main_legacy_holdout_v2/)、[新40历史版](../evaluation/results/holdout_v2_historical_optimized/)、[新40当前版](../evaluation/results/holdout_v2_current/)。本轮未依据新题改业务，当前 main 业务仍是 2d24de9。

后续将公开的 v2 案例作为回归反例，优先调整报告字段选择与差值交付、长期目标和约束记忆、维护步骤完整性及资料条件区分；另冻结新的验证题再评估改动。不能再次使用已看过的同一40题宣称全新保留集收益。新增质量测试不替代既有故障、安全、API并发及部署验证。
