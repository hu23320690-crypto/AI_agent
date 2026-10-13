# LLM Intent P3 正式评测报告

日期：2026-10-13（Australia/Sydney）。按作者批准的 A/B/C 批次运行，唯一运行时版本为 `c105253026453bb203aab1186d68aae0bb10acd3`。默认模式仍为 `rule`；实现、提示词、模型采样、工具与预算均未修改；未 push。

**准入结论：** 未满足全部G1–G6；G5未通过。 本阶段遵照作者指令不切换默认模式。

## 运行与评分合同

已核对计划顶部修订记录、第5节/5.6节、第6节、两份r1 SCORING及其generalization引用、INTENT_EVAL与INTENT_DEV_LOG。引用[评分合同补充说明01](../docs/plans/SCORING_AMENDMENT_01.md)；test/Agent冻结gold不变。原SCORING里的待审核措辞为历史状态，冻结manifest及本次作者批准已确认准入。

运行前及每次运行后将所有运行时文件（含evaluation运行器/评分代码）逐字节与Git冻结blob核对，共71文件；无不一致。每个manifest的`p3_runtime_byte_sha256`保存完整SHA256，`p3_runtime_version`保存c105253。源CSV、知识资料、tokenizer缓存、依赖、模式及模型身份另由原运行器记录。生成的Chroma索引与Python缓存不是版本化运行时源代码。

`doctor`通过152检查；qwen3:4b digest=`359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`。首个doctor因沙箱网络权限失败，获本机网络权限后通过；无正式推理已在失败检查时启动。离线检查首次遇到沙箱Temp写权限问题，原日志保留；使用授权工作区临时目录后原669测试通过。

全部推理串行、每次新目录；A使用独立`--repeat 1`目录，预登记的r001/r002/r003身份写入manifest（原始记录内部编号保持r001，不重写结果）。意图解析模型temperature=0、reasoning=False、JSON Schema、num_predict上限384，未显式设seed，沿用冻结工厂；Agent规划与RAG模型保持各自原配置。所有失败/超时/未执行/未复核留在原分母，未重跑或挑选最佳题。完成评分与导出后用原seal脚本封存并verify。

B/C评审包在输出后去掉模式标签及成本事件、打乱完整任务样本；只向评审暴露题目、答案、工具、实际知识输入及哈希。全部逐轮评分含理由，先保存评分并锁定其SHA256，再读取揭盲键。盲评是Codex助手辅助标签隐藏复核；不是独立真人或领域专家盲评。

## A：组件test（主要证据）

| 模式 | 各次完全正确/100 | 均值/最差准确率 | 各次危险错误 | 最大危险错误 |
|---|---|---:|---|---:|
| rule | 16 | 16.0%/16.0% | 13 | 13 |
| llm_only | 79/79/79 | 79.0%/79.0% | 15/15/15 | 15 |
| hybrid | 80/80/80 | 80.0%/80.0% | 10/10/10 | 10 |

完整分槽位、错误分级、回退率、冲突码、p50/p95（全部及成功状态）、逐题拦截与校验致错见[A结果表](INTENT_P3_A.md)及`evaluation/results/intent_p3_A_analysis/`。每次100题，共700条。

三模式整体回退率均0%，执行失败和预算跳过均0；rule额外意图调用0，llm_only/hybrid各次100。hybrid各次p95为1.7592/1.6826/1.6967秒，所有状态与成功状态相同。

每轮均有8题从llm_only危险变为hybrid无危险：IT021/024/025/027/028/030（qualifier_dropped）、IT047（relative_month_recomputed）、IT057（month_unsupported）。其中IT027/057仍未完全正确。同一hybrid原始提议的零模型调用确定性复算确认校验归因，而非只凭两组模型输出差异。

每轮均有5题因校验从原本正确变错：IT041（qualifier_dropped）、IT044/049（relative_month_recomputed）、IT072（qualifier_dropped、negated_field_selected、negated_month_selected、fields_rule_fallback）、IT076（negated_field_selected、negated_month_selected、fields_rule_fallback）。三轮分别保留，共24条危险拦截记录、15条校验致错记录；不挑选单题。

| 槽位 | rule | llm_only 均值/最差 | hybrid 均值/最差 |
|---|---:|---:|---:|
| compare | 92.0% | 100.0%/100.0% | 100.0%/100.0% |
| comparison_month | 86.0% | 97.0%/97.0% | 97.0%/97.0% |
| fields | 60.0% | 88.0%/88.0% | 92.0%/92.0% |
| knowledge_requested | 95.0% | 100.0%/100.0% | 100.0%/100.0% |
| requested_field_order | 48.0% | 86.0%/86.0% | 89.0%/89.0% |
| scope | 91.0% | 99.0%/99.0% | 99.0%/99.0% |
| target_month | 72.0% | 95.0%/95.0% | 92.0%/92.0% |
| unknown_fields | 65.0% | 87.0%/87.0% | 90.0%/90.0% |
| unresolved_month | 94.0% | 96.0%/96.0% | 96.0%/96.0% |

## B：Agent test

| 模式 | 全轮通过/12 | 内容0/1/2（24轮） | 忠实轮/24 |
|---|---:|---:|---:|
| rule | 1/12 | 8/6/10 | 21/24 |
| hybrid | 4/12 | 4/4/16 | 23/24 |

同题对照：进步3，退步0，共同通过1，共同失败8，未知0。逐轮评分、完整理由、工具选择和每个报告轮成本见[B结果表](INTENT_P3_B.md)与各运行reviews.jsonl/p3_turn_metrics.jsonl。

B的共同失败说明出口意图解析的边界：IA001/IA002/IA006/IA007第二轮只查基准，没有本轮目标记录；IA010首轮未查基准；IA005/IA012没有执行必需知识检索。正确选意图不能补授查询或自行触发工具调用，原权限守卫保留了拒绝代用记录的边界。IA004第二轮虽数值正确，两组都缺本轮必需fetch，不能判严格通过。

## C：已见题回归

先完成并保存[代码路径证明](results/intent_p3_preflight/non_report_path_proof.json)：除报告分支及必要导入外ReactAgent AST一致；既有agent/rag模型工厂路径AST一致；既有Runtime AST一致（只新增只读预算查询）；utils/rag、安全、工具、已有提示配置逐字节未变。原main测试文件未改动。证明成立，因此知识与资料不足非Agent题不重跑；这是正式推理前决定的简化。

| 数据集 | rule全轮通过 | hybrid全轮通过 | 进步/退步/共同通过/共同失败/未知 |
|---|---:|---:|---|
| base | 12/12 | 10/12 | 0/2/10/0/0 |
| generalization_v1 | 5/6 | 3/6 | 0/2/3/1/0 |
| holdout_v2 | 6/6 | 6/6 | 0/0/6/0/0 |

C的4个退步任务是原开发集A03、A10和generalization的G1A02、G1A03。A03/A10把日期当未知字段而未交付已查到的记录；G1A02首轮遗漏滤网寿命；G1A03在工具正确查询2026-01后将目标重算成2026-02。既有资料路径不变不能抵消报告路径的这些退步。

逐轮内容、忠实度和解析成本见[C结果表](INTENT_P3_C.md)。三个完整冻结输入均保留；seal中的cases.jsonl只是运行前选定Agent阶段的显式计划，并用input_dataset_sha256绑定原输入。已见题只能检查退步，不算未见效果证据。

## G1–G6逐项判定

| 标准 | 通过 | 数字与理由 | 证据 |
|---|---|---|---|
| G1 | 是 | 原有测试669 passed、291 subtests passed、3项符号链接权限跳过；main测试文件均未改动。 | `evaluation/results/intent_p3_preflight/offline_tests_workspace_temp.txt` |
| G2 | 是 | hybrid最差80.0%，rule 16.0%，增加64.0个百分点（要求≥10）。 | `evaluation/results/intent_p3_A_analysis/summary.json` |
| G3 | 是 | hybrid最大危险错误10/100，rule 13/100。 | `evaluation/results/intent_p3_A_analysis/summary.json` |
| G4 | 是 | rule 1/12，hybrid 4/12；进步3，退步0，未知0。 | `evaluation/results/intent_agent_v1_r1_test_p3_blind/paired_summary.json` |
| G5 | 否 | 知识/资料不足既有代码路径改动0，运行前决定不重跑，以代码路径等价证明作为本次准入依据；未声称实测新推理成绩变化为0。Agent base: rule 12/12，hybrid 10/12；generalization_v1: rule 5/6，hybrid 3/6；holdout_v2: rule 6/6，hybrid 6/6。 | `evaluation/results/intent_p3_preflight/non_report_path_proof.json；evaluation/results/intent_p3_C_analysis/summary.json` |
| G6 | 是 | 各批次配对新增解析延迟p95最大4.6090秒（≤10）；hybrid预算跳过合计0/343，任一批次最大跳过率0.0%（≤5%）。 | `evaluation/results/intent_p3_gate_metrics.json；各Agent运行p3_turn_metrics.jsonl` |

延迟使用nearest-rank。A为同题selector墙钟增量，B/C为trace实测意图解析增量；完整Agent模型/检索耗时会受规划波动影响，未将其声称为解析器的因果增量。没有实际进入解析的报告轮单列缺测，不虚构零值。

## 典型成功与失败（各3个）

以下固定引用hybrid r001原始输出作示例，均保留在100题主分母；示例不替代全部失败清单。

### 成功：同义字段和顺序：IT001

原文：把2025年1月主刷还能撑几天放在前面，再列平均每天清扫的面积，报告就这两项。

最终意图：

```json
{
  "fields": [
    "主刷寿命",
    "日均清扫"
  ],
  "target_month": "2025-01",
  "comparison_month": null,
  "compare": false,
  "limited": true,
  "invalid_month": false,
  "unresolved_month": false,
  "scope": "only_listed",
  "knowledge_requested": false,
  "excluded_fields": []
}
```

将“主刷还能撑几天”和“平均每天清扫的面积”映射为目录字段，顺序、范围和月份均正确。

冲突码：`无`。原始证据：`evaluation/results/intent_v1_r1_test_p3_hybrid_r001/results.jsonl`，result_sha256=`1e70efc397f2c670b256041f2d51bb6c979ef80759b25dba7b512b8f24156d28`。

### 成功：区域限定保护：IT021

原文：2025年2月只列厨房覆盖率这一栏。

最终意图：

```json
{
  "fields": [
    "厨房覆盖率"
  ],
  "target_month": "2025-02",
  "comparison_month": null,
  "compare": false,
  "limited": true,
  "invalid_month": false,
  "unresolved_month": false,
  "scope": "only_listed",
  "knowledge_requested": false,
  "excluded_fields": []
}
```

V4拒绝将“厨房覆盖率”映射为通用“覆盖率”，保留未知原指标，未选择目录里的近似字段。

冲突码：`qualifier_dropped`。原始证据：`evaluation/results/intent_v1_r1_test_p3_hybrid_r001/results.jsonl`，result_sha256=`da46ff796b97b105ca13aa72e68f5eb0136422fcbc562703ce69c5e38d09420a`。

### 成功：明确查询锚点的月份算术：IT047

原文：以刚查到的这份记录为起点，前一个月只列尘盒清理。

最终意图：

```json
{
  "fields": [
    "尘盒清理"
  ],
  "target_month": "2025-07",
  "comparison_month": null,
  "compare": false,
  "limited": true,
  "invalid_month": false,
  "unresolved_month": false,
  "scope": "only_listed",
  "knowledge_requested": false,
  "excluded_fields": []
}
```

以当前查询2025-08为明确起点，代码重算前一个月为2025-07；组件选择正确不授予该未查询月的数字输出权限。

冲突码：`relative_month_recomputed`。原始证据：`evaluation/results/intent_v1_r1_test_p3_hybrid_r001/results.jsonl`，result_sha256=`5155150b7d91748895c13dbfe9a252910a76972402c388c443a5e4e6fcec3ba4`。

### 失败：日期被误当字段限定词：IT041

原文：只取 2025 年十一月的玩具避障率，我不需要其它项。

最终意图：

```json
{
  "fields": [
    "2025 年十一月的玩具避障率"
  ],
  "target_month": "2025-11",
  "comparison_month": null,
  "compare": false,
  "limited": true,
  "invalid_month": false,
  "unresolved_month": false,
  "scope": "only_listed",
  "knowledge_requested": false,
  "excluded_fields": []
}
```

原始mention携带日期，V4把日期当作字段限定，误将可答的“玩具避障率”降为未知，造成safe_fail。

冲突码：`qualifier_dropped`。原始证据：`evaluation/results/intent_v1_r1_test_p3_hybrid_r001/results.jsonl`，result_sha256=`38d6f5a2055e8dfbe8e9d265f02bb1c1c704192302bbd60bc5b2d75644955b88`。

### 失败：错误锚点声明被重算放大：IT044

原文：翻到下个月，仍然只列避障成功率。

历史用户原话：["只列 2025 年七月的避障成功率。"]

最终意图：

```json
{
  "fields": [
    "避障成功率"
  ],
  "target_month": "2025-09",
  "comparison_month": null,
  "compare": false,
  "limited": true,
  "invalid_month": false,
  "unresolved_month": false,
  "scope": "only_listed",
  "knowledge_requested": false,
  "excluded_fields": []
}
```

gold应由上轮2025-07得到2025-08；模型的锚点声明使V7重算为2025-09，产生错误但合法的目标月。校验不保证语义锚点判断正确。

冲突码：`relative_month_recomputed`。原始证据：`evaluation/results/intent_v1_r1_test_p3_hybrid_r001/results.jsonl`，result_sha256=`ee0a8664203c692b8f8104b66922557a0b6760075b58ac579c1227182345c292`。

### 失败：撤回月份和字段误选未拦住：IT075

原文：我不比较 2025 年四月了，2025 年五月只列主刷寿命。

最终意图：

```json
{
  "fields": [
    "覆盖率"
  ],
  "target_month": "2025-04",
  "comparison_month": null,
  "compare": false,
  "limited": true,
  "invalid_month": false,
  "unresolved_month": false,
  "scope": "only_listed",
  "knowledge_requested": false,
  "excluded_fields": []
}
```

应选择2025-05主刷寿命，最终选择2025-04覆盖率；无冲突码。月份有据和目录成员检查不足以证明当前肯定意图角色。

冲突码：`无`。原始证据：`evaluation/results/intent_v1_r1_test_p3_hybrid_r001/results.jsonl`，result_sha256=`33ea51153528c92e26c9a2ed949cec346e377c68b0b896e481ad4134b3cb722f`。

## 局限性

只有同一演示CSV/知识域、一个4B模型digest；组件100题、Agent12任务，不构成跨域或生产可靠性证明。冻结题由助手团队参与编制，作者批准gold；“未见”只指未用于实现、dev调优或结果筛选。三次组件重复反映这一固定配置的稳定性；Agent每模式只有一次，任务差异仍可能包含模型规划、检索和多轮历史波动。

确定性校验只能证伪目录、锚定、日期证据、算术和否定等事实，不能保证完整理解角色、顺序或遗漏。实际修正和保守校验造成的退步均如实列出。相对月份锚点合同修订不修改test gold。代码路径证明支持本次不重跑非Agent知识/资料不足题的范围决定，不是对新一轮随机生成分数的实测。

资料是项目演示材料，其真实厂商适用性未经本实验验证。盲评隐藏了模式标签，仍可能从输出形式或调用特征推测模式；评分者也参与过项目工作，不能声称独立外部盲评。

封存是SHA256清单与结构校验，不是防篡改签名。所有评分为助手依据真实证据复核，尚非独立领域专家审核。

最终审计：15个运行封存均verify通过，772条原始记录/772条评分绑定完整；其中组件700条，Agent72次任务运行/120个真实轮次。71个运行时文件与c105253逐字节一致，全部输入gold与d61a06a相同。审计证据：`evaluation/results/intent_p3_final_audit.json`。

## 提交与路径

仓库报告路径：`C:\Users\胡\Documents\Codex\2026-09-17\new-chat\AI_agent_publication\evaluation\INTENT_P3_REPORT.md`。A/B分别独立提交；C和最终报告在本报告所在提交中完成。

- 6e601b642e4ab731b9880c5e8a15aa918bec18c6 eval(intent): P3 A sealed component test and validation attribution
- 5f493575171b2abc36a4e04fdf7ad26fbbc99bd1 eval(intent): P3 B blinded Agent test and paired results
