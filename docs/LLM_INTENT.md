# LLM 意图解析与确定性校验

报告意图解析支持 `rule`、`llm_only` 和 `hybrid`。默认保持 `rule`，`hybrid` 是主动开启的可选模式。P3 正式评测没有满足全部准入条件，P3.1 的已见回归也未满足验收；现阶段到此收尾，不再迭代。依据：[evaluation/INTENT_P3_REPORT.md](../evaluation/INTENT_P3_REPORT.md)、[evaluation/INTENT_P31_REPORT.md](../evaluation/INTENT_P31_REPORT.md)。

## 动机：工具查对了，最终报告仍可能交付错

早期 `generalization_v1` 的首次未见测试中，Agent 全轮任务只通过 **1/6**。失败包括字段同义词没映射到记录字段、目标月与比较月混淆、报告加知识判断漏交付一部分。工具名称路径正确并不代表最终任务完成。来源：[docs/GENERALIZATION_EVALUATION.md](GENERALIZATION_EVALUATION.md)。

原来的报告选择器不断补充正则，能修好已知说法，却难以覆盖新的同义词、语序、部件限定、否定与多轮指代。本次把语义提取交给 LLM，再让代码验证能被客观证伪的事实，保留原解析器作为回退。设计及修订依据：[docs/plans/LLM_INTENT_PLAN.md](plans/LLM_INTENT_PLAN.md)、[evaluation/INTENT_DEV_LOG.md](../evaluation/INTENT_DEV_LOG.md)。

## 设计：结构化提议、校验、失败回退

现有接入点在报告查询之后、最终交付之前。输入包括用户原话、受限的用户历史、上一有效意图、本轮实际查询月、今天，以及从已授权查询结果提取的动态字段目录。模型只提出选择，不直接生成报告数字。

```mermaid
flowchart LR
    Q[本轮受权查询结果与用户原话] --> L[LLM 结构化提议]
    L --> V[确定性校验 V1–V10]
    V --> M[合并有效选择与槽位回退]
    L -->|结构或调用失败| R[原正则解析器]
    V -->|任务类型冲突| R
    R --> O[报告渲染与交付检查]
    M --> O
    O --> A[仅交付已授权且已查证的数据]
```

JSON Schema 限定任务类型、字段原文与目录名、范围、目标月、基准月、比较开关、排除字段、知识子问和月份无法确定标记；strict 校验拒绝额外键和类型混用。非法结构、截断、模型超时、熔断或预算不足时，整条提议回退；字段或日期冲突也可只撤销对应项、按槽位采用已有规则结果。来源与实现：[docs/plans/LLM_INTENT_PLAN.md](plans/LLM_INTENT_PLAN.md)、[agent/intent/schema.py](../agent/intent/schema.py)、[agent/intent/validate.py](../agent/intent/validate.py)、[agent/intent/resolve.py](../agent/intent/resolve.py)。

### V1–V10 的职责

下表概括当前实现；P3 的成绩对应其冻结版本，后文单列 P3.1 的修正，不能用当前代码替换正式成绩。

| 校验 | 可检查的事实与处理 |
| --- | --- |
| V1：结构 | JSON、必填键、重复键、类型、额外键及截断是否合法；不合法则回退。 |
| V2：目录 | 选择与排除字段必须属于当前授权目录；目录外选择降为未知。 |
| V3：原文依据 | 未知名称必须有用户原文依据；授权目录映射可保留改写后的 mention 并记录冲突，继续接受后续校验。 |
| V4：限定词 | 不把部件、区域或模式限定丢掉后映射到通用字段；日期与报告泛词的当前处理见 P3.1。 |
| V5：日历格式 | 校验目标及基准的合法年月；非法槽位采用规则结果。 |
| V6：月份有据 | 提议月份须有显式日期、历史有效目标或合法换算依据；不把所有背景、撤回日期强行设为目标。 |
| V7：月算术 | 按声明锚点做日历偏移，跨年计算由代码执行；查询一致性修正见 P3.1。 |
| V8：缺少锚点 | 缺少所声明的有效锚点时保留无法确定；不借用另一个日期猜测。 |
| V9：排除 | 当前否定与撤回限制优先，移除仍被选中的排除字段或月份。 |
| V10：任务边界 | 只接入报告分支；已查询报告却提出知识独立任务等冲突时回退。 |

规则编号及边界依据：[docs/plans/LLM_INTENT_PLAN.md](plans/LLM_INTENT_PLAN.md)；当前代码见 [agent/intent/](../agent/intent/)。这些校验能拒绝不成立的提议，无法证明模型已经完整理解用户意图。

### 意图不授予权限

提议没有 `user_id`、工具名或可修改的执行策略。身份来自服务端会话，工具参数和权限仍由原策略校验，模型调用与工具调用仍共用 Runtime 预算。意图选中一个月份，并不意味着该月记录已被查询；渲染器继续检查本轮查询、用户和月份，不能拿历史月或相邻月冒充目标月。

因此，未知字段可以明确交付“未提供”，缺记录可以明确拒答，但不能从别的指标推算数值，也不能因为意图解析正确就新增未经规划的工具调用。设计依据：[docs/plans/LLM_INTENT_PLAN.md](plans/LLM_INTENT_PLAN.md)；实测边界与失败见 [evaluation/INTENT_P3_REPORT.md](../evaluation/INTENT_P3_REPORT.md)。

### `target_anchor`：声明起点，再做算术

| 声明 | 起点与适用情境 |
| --- | --- |
| `previous_target` | 上一有效意图的目标月，多轮“继续下一月”等指代使用此起点。 |
| `current_lookup` | 本轮实际查询月，用户明确以刚查到的记录为起点。 |
| `today` | 今天所在月份，首轮以日历当前时间为起点的相对说法。 |
| `none` | 未知事件或无法确定起点，不能假装有日期锚点。 |

声明起点的语义判断由模型负责，偏移算术由代码负责；相对比较基准使用已校验的目标月。错误的起点声明仍会把正确算术带向错误月份，这正是正式评测暴露的失败类型。来源：[docs/plans/SCORING_AMENDMENT_01.md](plans/SCORING_AMENDMENT_01.md)、[evaluation/INTENT_P3_REPORT.md](../evaluation/INTENT_P3_REPORT.md)。

## 评测方法：冻结在先，开发与正式测量分开

题集与作者批准的金标准先冻结，再写实现。只用 dev 调优，之后冻结运行代码、提示词、模型身份与配置；P3 正式运行使用 `c105253026453bb203aab1186d68aae0bb10acd3`，不按 test 输出回改题目或挑选重跑。协议与版本来源：[evaluation/INTENT_P3_REPORT.md](../evaluation/INTENT_P3_REPORT.md)。

组件 dev 为 **40 题**，正式 test 为 **100 题**；dev 数量见 [evaluation/INTENT_DEV_LOG.md](../evaluation/INTENT_DEV_LOG.md)，test 分母见 [evaluation/INTENT_P3_A.md](../evaluation/INTENT_P3_A.md)。正式消融中，`rule` **运行一次**，`llm_only` 与 `hybrid` **各运行三次**；分别报告整体完全正确率的均值和最差一次，危险错误取最大一次。来源：[evaluation/INTENT_P3_A.md](../evaluation/INTENT_P3_A.md)。

| 模式 | 用途 |
| --- | --- |
| `rule` | 原正则基线，不调用意图模型。 |
| `llm_only` | 消融模式：保留结构、目录成员和任务边界检查，关闭其余语义校验，观察模型原始选择的风险。 |
| `hybrid` | LLM 提议经过完整确定性校验，与有效规则槽位合并，调用失败时回退。 |

组件整体通过要求所有意图槽位及已知/未知混排字段顺序正确。危险错误指选中了未请求的目录字段，或给出错误但合法的目标/基准月；它是解析层错误指标，不能等同于已经向用户泄露或伪造了数据。评分来源：[evaluation/intent_v1_r1/SCORING.md](../evaluation/intent_v1_r1/SCORING.md)；汇总见 [evaluation/INTENT_P3_A.md](../evaluation/INTENT_P3_A.md)。

Agent test 每模式 **12 个任务、24 个真实轮次**。逐轮内容分为 **0/1/2**，忠实度单独判断；全轮任务通过要求每个真实轮次完整交付、内容满分、事实有据，并满足该轮工具要求。来源：[evaluation/INTENT_P3_B.md](../evaluation/INTENT_P3_B.md)。

B/C 评审包去掉模式标签和成本事件，随机打乱完整任务样本。评分理由绑定 `result_sha256`，全部评分固定并锁定哈希后再揭盲。失败、超时、未执行和未知都保留在原计划分母；各运行目录串行产生、独立封存。此盲评为助手辅助的标签隐藏复核，不能声称独立真人专家审核。方法来源：[evaluation/INTENT_P3_REPORT.md](../evaluation/INTENT_P3_REPORT.md)。

### 事先约定的准入条件与正式判定

条件先于正式推理确定，全部通过才允许切换默认模式。阈值见 [docs/plans/LLM_INTENT_PLAN.md](plans/LLM_INTENT_PLAN.md)；下表全部实测数字、阈值对照及判定来源：[evaluation/INTENT_P3_REPORT.md](../evaluation/INTENT_P3_REPORT.md)。

| 条件 | 判定依据 | P3 判定 |
| --- | --- | --- |
| G1：rule 等价性 | 原有离线测试 669 passed、291 子测试通过，3 项 Windows 符号链接权限跳过。 | 通过 |
| G2：组件提升 | hybrid 最差 80.0%，rule 16.0%，提升 64.0 个百分点，达到至少 10 个百分点。 | 通过 |
| G3：危险错误 | hybrid 最大 10/100，不多于 rule 的 13/100。 | 通过 |
| G4：Agent 改善 | 全轮通过 1/12→4/12，同题进步 3、退步 0。 | 通过 |
| G5：既有能力回归 | 已见 Agent 基础集 12/12→10/12，generalization 5/6→3/6；报告任务退步。知识/资料不足非 Agent 题依据运行前代码路径等价证明不重跑，没有伪称新实测分数不变。 | **未通过** |
| G6：成本 | 各批次配对新增解析延迟 p95 最大 4.609 秒，限值 10 秒；预算跳过 0/343，限值 5%。 | 通过 |

## P3 正式结果：A/B 未见成绩与 C 已见回归

### A：意图组件 test，主要未见证据

| 模式 | 各次完全正确/100 | 准确率均值/最差 | 危险错误均值/最大 | 来源报告 |
| --- | --- | --- | --- | --- |
| rule | 16 | 16.0% / 16.0% | 13 / 13 | [evaluation/INTENT_P3_A.md](../evaluation/INTENT_P3_A.md) |
| llm_only | 79 / 79 / 79 | 79.0% / 79.0% | 15 / 15 | [evaluation/INTENT_P3_A.md](../evaluation/INTENT_P3_A.md) |
| hybrid | 80 / 80 / 80 | 80.0% / 80.0% | 10 / 10 | [evaluation/INTENT_P3_A.md](../evaluation/INTENT_P3_A.md) |

只用 LLM 时，准确率提高，但危险错误 **15/100** 反而多于 rule 的 **13/100**；完整校验将最大危险错误降为 **10/100**。来源：[evaluation/INTENT_P3_A.md](../evaluation/INTENT_P3_A.md)。

### 校验保护与误伤同时存在

每次完整重复中，校验拦下 **8 题**危险错误：IT021、IT024、IT025、IT027、IT028、IT030、IT047、IT057；也把原本正确的 **5 题**变错：IT041、IT044、IT049、IT072、IT076。拦下危险不等于整题已经正确；同一原始提议的无模型调用复算支持校验归因，不只靠两次模型输出的差异。来源：[evaluation/INTENT_P3_A.md](../evaluation/INTENT_P3_A.md)、[evaluation/INTENT_P3_REPORT.md](../evaluation/INTENT_P3_REPORT.md)。

下表例句使用虚构字段与日期，只说明机制，不复制冻结题面，也不计入任何成绩；实测对应类型与冲突码均有报告可核查。

| 类型 | 虚构机制例子 | P3 中的行为与冲突码 | 实测类型来源 |
| --- | --- | --- | --- |
| 拦下丢限定词的映射 | 目录只有“星辉率”，用户要“同年五月的北舱星辉率”，模型映射为通用“星辉率”。 | 保留“北舱星辉率”为未知，不用通用值代替；`qualifier_dropped`。 | IT021 等，[evaluation/INTENT_P3_REPORT.md](../evaluation/INTENT_P3_REPORT.md) |
| 拦下月份算错 | 用户以刚查到的虚构月为起点，要求前一个月，模型的目标与该起点的偏移不符。 | 根据已声明起点重算；`relative_month_recomputed`。这仍不授予未查月份的数据权限。 | IT047，[evaluation/INTENT_P3_REPORT.md](../evaluation/INTENT_P3_REPORT.md) |
| 日期造成误伤 | 用户说“只要同年五月的星辉率”，mention 把日期也包进字段原话。 | P3 的 V4 将日期误当限定词，把可答字段降为未知；`qualifier_dropped`。 | IT041，[evaluation/INTENT_P3_REPORT.md](../evaluation/INTENT_P3_REPORT.md) |
| 锚点重算放大错误 | 多轮“继续下一月”，模型给出正确目标，却声明起点为已查询的目标月。 | P3 的 V7 又移动一次，造成错误合法月；`relative_month_recomputed`。 | IT044/IT049，[evaluation/INTENT_P3_A.md](../evaluation/INTENT_P3_A.md)、[evaluation/INTENT_P3_REPORT.md](../evaluation/INTENT_P3_REPORT.md) |

### B：Agent test，未见端到端任务

| 模式 | 全轮通过 | 内容分 0/1/2 的轮数 | 忠实轮数 | 来源报告 |
| --- | --- | --- | --- | --- |
| rule | 1/12 | 8 / 6 / 10 | 21/24 | [evaluation/INTENT_P3_B.md](../evaluation/INTENT_P3_B.md) |
| hybrid | 4/12 | 4 / 4 / 16 | 23/24 | [evaluation/INTENT_P3_B.md](../evaluation/INTENT_P3_B.md) |

同题对照为进步 **3**、退步 **0**、共同通过 **1**、共同失败 **8**、未知 **0**。来源：[evaluation/INTENT_P3_B.md](../evaluation/INTENT_P3_B.md)。

### C：已见题回归，只用于检查退步

| 数据集 | rule 全轮通过 | hybrid 全轮通过 | 同题进步/退步 | 来源报告 |
| --- | --- | --- | --- | --- |
| 原开发集 Agent 阶段 | 12/12 | 10/12 | 0 / 2 | [evaluation/INTENT_P3_C.md](../evaluation/INTENT_P3_C.md) |
| generalization_v1 Agent 阶段 | 5/6 | 3/6 | 0 / 2 | [evaluation/INTENT_P3_C.md](../evaluation/INTENT_P3_C.md) |
| holdout_v2 Agent 阶段 | 6/6 | 6/6 | 0 / 0 | [evaluation/INTENT_P3_C.md](../evaluation/INTENT_P3_C.md) |

这些题在更早的修复中已见过，不能并入 A/B 未见成绩。P3 回归中的 A03/A10 将日期当成未知字段而没有交付已查记录；G1A03 在正确查询跨年目标后又重算月份；G1A02 首轮则是结构化提议遗漏字段。来源：[evaluation/INTENT_P3_REPORT.md](../evaluation/INTENT_P3_REPORT.md)。

## P3.1：已见，不作为未见成绩

P3.1 位于 P3 正式测量之后，只依据 C 与 dev 做通用修正，不用 test 题目开发。修正运行版本为 `95a1d476992a1999cadd75aea15c9e656a43262f`；没有修改提示词、其他校验、金标准或默认模式。来源：[evaluation/INTENT_P31_REPORT.md](../evaluation/INTENT_P31_REPORT.md)。

- V4 比较前去掉 mention 中的月份与尾部报告泛词；日期/泛词组成的未知标签不生成未知字段，记录 `non_metric_unknown_dropped`。显式的用户范围与真实部件限定继续保留。
- 查询一致性：存在有效上一目标时，若按声明 `current_lookup`/`today` 算出的目标不等于本轮实际查询月，而 `previous_target` 加相同偏移恰好等于查询月，则采用后者，记录 `anchor_lookup_consistency`。无上一目标或两种计算均不匹配时不调整。

修正边界、虚构正反例与验证依据：[evaluation/INTENT_P31_REPORT.md](../evaluation/INTENT_P31_REPORT.md)。

### dev 前后对照（已见）

| 模式 | P2.1 正确/40 | P3.1 正确/40 | 危险错误前→后 | 来源报告 |
| --- | --- | --- | --- | --- |
| rule | 10（25.0%） | 10（25.0%） | 8→8 | [evaluation/INTENT_P31_REPORT.md](../evaluation/INTENT_P31_REPORT.md) |
| llm_only | 31（77.5%） | 31（77.5%） | 1→1 | [evaluation/INTENT_P31_REPORT.md](../evaluation/INTENT_P31_REPORT.md) |
| hybrid | 32（80.0%） | 33（82.5%） | 1→1 | [evaluation/INTENT_P31_REPORT.md](../evaluation/INTENT_P31_REPORT.md) |

### C 前后对照（已见）

| 数据集 | P3 hybrid 全轮通过 | P3.1 hybrid 全轮通过 | P3.1 rule 基线 | 来源报告 |
| --- | --- | --- | --- | --- |
| 原开发集 Agent 阶段 | 10/12 | 12/12 | 12/12 | [evaluation/INTENT_P31_REPORT.md](../evaluation/INTENT_P31_REPORT.md) |
| generalization_v1 Agent 阶段 | 3/6 | 4/6 | 5/6 | [evaluation/INTENT_P31_REPORT.md](../evaluation/INTENT_P31_REPORT.md) |
| holdout_v2 Agent 阶段 | 6/6 | 6/6 | 6/6 | [evaluation/INTENT_P31_REPORT.md](../evaluation/INTENT_P31_REPORT.md) |

generalization 的 hybrid 仍低于 rule，因此本轮验收未通过。G1A05 虽然全轮任务原本已失败，仍有新增逐轮退步：hybrid 内容分从 **2/1 变为 0/0**，且两轮意图解析调用均为 **0**；不把这个长历史/知识失败归因于未执行的 V4/V7，也不从分母删除。来源：[evaluation/INTENT_P31_REPORT.md](../evaluation/INTENT_P31_REPORT.md)。

### 已见 test 回归（P3 后修复版），不作为未见成绩

| 模式 | 正确 | 危险错误 | 执行失败/回退/预算跳过 | 来源报告 |
| --- | --- | --- | --- | --- |
| hybrid，单次已见回归 | 85/100（85.0%） | 7/100 | 0 / 0 / 0 | [evaluation/INTENT_P31_REPORT.md](../evaluation/INTENT_P31_REPORT.md) |

这次回归只查看自动评分的整体数字，没有据 test 失败再修代码，也没有更新 P3 正式成绩。上述已见数字只用于记录修复后状态，不能补充未见证据或补判 P3 的准入条件。来源：[evaluation/INTENT_P31_REPORT.md](../evaluation/INTENT_P31_REPORT.md)。

## 为什么保持默认 rule：G5 与 G1A02

P3 的 G5 要求既有 Agent 能力不退步，但 C 中基础集和 generalization 均出现报告任务退步，因此不能只凭 A 的准确率提升或 B 的任务改善切换默认模式。正式判定及数字来源：[evaluation/INTENT_P3_REPORT.md](../evaluation/INTENT_P3_REPORT.md)。P3.1 解决部分日期/锚点问题后仍未满足自己的验收；项目保持 `rule`，`hybrid` 只作为可选开关，P3/P3.1 到此收尾。来源：[evaluation/INTENT_P31_REPORT.md](../evaluation/INTENT_P31_REPORT.md)。

G1A02 首轮不是上述日期或锚点问题：实际记录已有滤网寿命 **剩余 45 天**，Agent 初始草稿也含该值，但意图模型原始 JSON 只提议毛发清理字段。校验冲突为空，最终报告因此漏项。这是模型上游的语义漏提取，没有发生 V4 拒绝或 V7 位移；按修正范围单列说明，不补字段、不改提示词。原因及原始结果哈希来源：[evaluation/INTENT_P31_REPORT.md](../evaluation/INTENT_P31_REPORT.md)；运行前诊断记录：[evaluation/INTENT_DEV_LOG.md](../evaluation/INTENT_DEV_LOG.md)。

## 局限与下一步：把意图解析前移到工具规划

实验只覆盖同一演示知识域与 CSV、固定模型身份，样本由助手参与编制、作者批准；没有独立外部专家评分，也没有跨域、生产流量或统计显著性证明。所谓未见，是未用于实现和 dev 调优，不是编题者从未接触题目。重复组件测量不能替代端到端重复实验。局限来源：[evaluation/INTENT_P3_REPORT.md](../evaluation/INTENT_P3_REPORT.md)、[evaluation/INTENT_P31_REPORT.md](../evaluation/INTENT_P31_REPORT.md)。

确定性校验可以发现目录、日历算术、原文依据、限定或否定冲突，却不能保证模型提出了全部字段、正确判定了月份角色，或工具规划覆盖所有子任务。保守检查既有保护，也有误伤；新回归中其他模型步骤仍会波动。

B 的失败主要受工具规划约束：IA001/IA002/IA006/IA007 的后续轮只查基准，没有本轮目标记录；IA010 首轮没查比较基准；IA005/IA012 没调用必需的知识检索；IA004 的后续轮缺少该轮必需查表。出口的意图解析无法补上这些调用，权限检查也不会允许拿别的月份顶替。逐轮失败与依据来源：[evaluation/INTENT_P3_REPORT.md](../evaluation/INTENT_P3_REPORT.md)、[evaluation/INTENT_P3_B.md](../evaluation/INTENT_P3_B.md)。

下一步应把意图解析前移到工具规划之前：先明确目标月、比较基准、字段与知识子问，供规划器安排查表和检索；执行时继续由会话身份、工具策略与 Runtime 限定权限和预算；查到记录后再验证动态目录和数值，最后检查所有子目标是否交付。这是后续设计方向，本次没有实现、没有继续迭代，也没有用已见回归替代新的未见验证。

## 主动开启 hybrid

仓库配置 `config/intent.yml` 保持 `mode: rule`。在启动页面或 API 前设置进程环境变量即可使用可选模式：

```powershell
$env:AGENT_INTENT_MODE = 'hybrid'
.\.venv\Scripts\python.exe -B scripts/manage.py serve
# 使用 API 时，用同一环境变量启动 scripts/manage.py api。
```

Linux shell 使用 `export AGENT_INTENT_MODE=hybrid` 后启动服务。已有进程需要重启以接收新环境；删除环境覆盖并重启后恢复仓库默认。`llm_only` 用于消融，不建议作为用户服务的模式。配置行为依据：[agent/intent/llm_parser.py](../agent/intent/llm_parser.py)。
