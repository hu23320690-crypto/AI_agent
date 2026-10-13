# LLM Intent P3.1 修正与已见题回归报告

日期：2026-10-13（Australia/Sydney）。修正运行版本 `95a1d476992a1999cadd75aea15c9e656a43262f`。P3 正式成绩、报告和封存全部保留；G5 仍未通过，默认保持 rule，未 push。
**预定验收：未满足。** 逐项判定见下表。已见 test 数字仅描述修复后回归，不用于此轮验收，也不能更新 P3 的未见成绩。

## 修正范围

仅 agent/intent/validate.py 与配套 resolve.py 空字段处理变化。V4 比较视图先去掉绝对、相对、裸月及中文月份，再去掉尾部“的报告/的记录/使用记录/数据”等泛词。只有这些日期/泛词的未知项被删除并记录 non_metric_unknown_dropped；其造成的模型空列表范围限制一并撤销，显式用户“只列”仍优先。真实部件、区域、模式限定保留，非空未知名称继续保留原始锚定原词。
查询一致性只在有效 previous_target、当前实际查询月和声明锚点均存在时生效：声明 current_lookup/today 加原有偏移不等于查询月，而 previous_target 加相同偏移恰好等于查询月，改用后者并记录 anchor_lookup_consistency。没有上一目标、两种计算都不匹配、声明 none/previous_target、已匹配、原有 null+unresolved、否定相对表达等保留原行为。未扩大偏移语法；比较基准的计算不变。
提示词、配置、rule 解析、其他校验、模型与预算、SCORING 和 gold 均未改。62 个虚构正反例覆盖这些边界及 rule 等价性、llm_only 不应用本修正。完整 pytest：1077 passed、291 subtests passed、3 项 Windows 符号链接权限跳过；doctor --offline 149 检查、在线 152 检查通过。qwen3:4b digest 为 359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7。

## G1A02 首轮遗漏原因（本轮不修）

原话：“请查我2025年5月，只列宠物毛发清理率和滤网剩余寿命。”已查记录含宠物毛发清理91%和滤网寿命剩余45天，Agent 的初始报告草稿也含两项。但意图模型原始 JSON 只提出宠物毛发清理，target=2025-05、anchor=none；校验冲突为空。最终只交付91%。这是结构化模型的语义漏提取，不属于日期被当限定词/未知字段，也不是锚点重算。本轮没有补字段启发式或提示词修改。
先于实现写入 INTENT_DEV_LOG.md；P3 证据 evaluation/results/intent_p3_seen_generalization_v1_hybrid/results.jsonl，G1A02 call_index=2，result_sha256=ca6e44689ec626069b7ea43053f999450036513bf19251b4b397dd28b7c8d658。

## dev：P2.1 与 P3.1 同题对照

| 模式 | P2.1 正确/40 | P3.1 正确/40 | 危险错误 前→后 | P3.1 p50/p95秒 | 回退/预算跳过/执行失败 |
|---|---:|---:|---:|---:|---|
| rule | 10 (25.0%) | 10 (25.0%) | 8→8 | 0.0011/0.0019 | 0/0/0 |
| llm_only | 31 (77.5%) | 31 (77.5%) | 1→1 | 1.2043/1.3858 | 0/0/0 |
| hybrid | 32 (80.0%) | 33 (82.5%) | 1→1 | 1.2011/1.3875 | 0/0/0 |

dev 的各槽位、全部错误分级、冲突与成本保存在各 summary.json；完整原始结果与确定性评分全部封存。与P2.1逐题比较，三模式原始提议均无变化，rule及llm_only的40条预测也完全相同；hybrid仅ID028从错误转正确，冲突为field_not_in_catalog、non_metric_unknown_dropped、fields_rule_fallback，删除日期假字段后回到已有安全字段选择。对照证据：evaluation/results/intent_p31_analysis/dev_paired_comparison.json。这次净增1题可以归因于校验变化，但单次结果并非统计显著性证明。

## C：已见题 Agent 回归，原 SCORING 盲评

| 数据集 | P3 rule/hybrid 全轮通过 | P3.1 rule/hybrid 全轮通过 | 进步/退步/共同通过/共同失败/未知 | hybrid 相对 P3 新全轮失败 |
|---|---|---|---|---|
| base | 12/12，10/12 | 12/12，12/12 | 0/0/12/0/0 | 无 |
| generalization_v1 | 5/6，3/6 | 5/6，4/6 | 0/1/4/1/0 | 无 |
| holdout_v2 | 6/6，6/6 | 6/6，6/6 | 0/0/6/0/0 | 无 |

| 数据集/模式 | 内容0/1/2：P3→P3.1 | 忠实轮数：P3→P3.1 | P3.1解析p50/p95秒 | 额外意图调用/预算跳过 |
|---|---|---:|---:|---|
| base/rule | 0/0/14→0/0/14 | 14/14→14/14 | 0.0000/0.0160 | 0/0 |
| base/hybrid | 3/0/11→0/0/14 | 14/14→14/14 | 1.3280/1.9530 | 6/0 |
| generalization_v1/rule | 0/1/10→0/1/10 | 10/11→10/11 | 0.0000/0.0000 | 0/0 |
| generalization_v1/hybrid | 1/2/8→2/1/8 | 10/11→9/11 | 1.5000/2.4840 | 6/0 |
| holdout_v2/rule | 0/0/11→0/0/11 | 11/11→11/11 | 0.0000/0.0160 | 0/0 |
| holdout_v2/hybrid | 0/0/11→0/0/11 | 11/11→11/11 | 1.5780/2.2970 | 4/0 |

全轮任务要求全部真实轮次内容2、忠实度真并交付完成；工具要求单独核查。标签/成本事件隐藏，完整任务按事先确定种子打乱；逐轮理由、result_sha256 与全轮判断在 blind_scores.jsonl 中，评分 SHA256 先锁定再揭盲。此为助手辅助标签隐藏评分，不是独立专家复核。详见 [C逐轮评分表](INTENT_P31_C.md)。
实际修正证据：A03、A10的三个hybrid报告轮均触发non_metric_unknown_dropped，完整交付已查记录；G1A03 T2触发anchor_lookup_consistency，目标保持实际查询的2026-01并交付not_found。G1A02仍是原始提议漏滤网字段，两个报告轮均无冲突。G1A05的新长历史/知识失败两轮意图解析调用均为0，不能归因于本轮V4/V7校验改动；该失败照样保留在Agent分母。原始提议、答案、冲突事件和SHA256见evaluation/results/intent_p31_analysis/C_fix_evidence.json。

相对P3逐轮退步（即使全轮任务原本已失败也保留）：

- generalization_v1/hybrid/G1A05 T1：内容2→0，忠实度True→False，工具要求True→False。应回忆已明确的清洁仓清洁刷目标和三条约束，却额外调用不允许的RAG并说初选不明，转述主刷/边刷、宠物与木地板资料，未回答回忆任务；把通用拖布含水率附到木地板条件、否认已写明的目标，核心不能由有效历史/资料支持。 result_sha256=9a2a80e6bf1e9ac52135b21eab7a74d27866c9e0eb8821fa3df2b72d1968e088。
- generalization_v1/hybrid/G1A05 T2：内容1→0，忠实度False→False，工具要求True→False。未执行要求的新RAG查询，虽标题写清洁仓刷，主体却拿宠物尘盒/滚刷、主刷/边刷寿命替代该部件，缺少每周去毛发、每月冲洗、3-6个月及磨损立即换等请求事实，反而继续说目标不明；跨对象归用不忠实。 result_sha256=9a2a80e6bf1e9ac52135b21eab7a74d27866c9e0eb8821fa3df2b72d1968e088。

## 已见 test 回归（P3 后修复版），不作为未见成绩

实现先独立提交并完成 dev/C；最后仅运行一次 hybrid，自动按冻结评分合同计算汇总。未打开/展示/分析 test 题面、逐题原始提议或失败内容；未据该结果修改代码、提示词、gold 或重跑。

正确 85/100（85.0%）；危险错误 7，wrong_scope 1，safe_fail 4，other_error 3；执行失败 0，回退 0，预算跳过 0。p50/p95=1.2740/1.4391秒，额外模型调用100。
结果目录：`evaluation/results/已见 test 回归（P3 后修复版），不作为未见成绩_p31_hybrid`。目录名、manifest 和 P31_LABEL.txt 均保留上述已见标签。

| 槽位 | 已见 test 回归准确率 |
|---|---:|
| compare | 100.0% |
| comparison_month | 97.0% |
| fields | 95.0% |
| knowledge_requested | 100.0% |
| requested_field_order | 92.0% |
| scope | 99.0% |
| target_month | 96.0% |
| unknown_fields | 92.0% |
| unresolved_month | 96.0% |

## 预定验收判定

| 条件 | 数字/证据 | 是否满足 |
|---|---|---|
| dev hybrid 正确率 ≥ P2.1 | 33/40 ≥ 32/40；dev hybrid summary.json | 是 |
| dev hybrid 危险错误 ≤ P2.1 | 1/40 ≤ 1/40；全部分母保留 | 是 |
| C base hybrid ≥ rule 且无新退步 | 12 ≥ 12；同题退步0，相对P3 hybrid新失败0 | 是 |
| C generalization_v1 hybrid ≥ rule 且无新退步 | 4 < 5；同题退步1，相对P3 hybrid新失败0 | 否 |
| C holdout_v2 hybrid ≥ rule 且无新退步 | 6 ≥ 6；同题退步0，相对P3 hybrid新失败0 | 是 |

“无新退步”同时核查本轮同题 rule→hybrid 和 P3 hybrid→P3.1 hybrid 全轮通过转失败；未知不默认通过。组件 test 不参与验收。

## 封存、版本与限制

共10个新运行（dev3、C6、已见test1），全部串行、新目录、一次、不挑选、不重跑，均经原seal脚本封存并verify。每个manifest包含71文件完整SHA256及实现提交；原始结果和每轮评分哈希绑定保留。审计：evaluation/results/intent_p31_final_audit.json；完整汇总及控制脚本：evaluation/results/intent_p31_analysis/。P3归档和评分未改。
已见题来自同一演示资料域。意图解析温度固定为0但未显式配置seed；Agent规划、摘要及RAG保持各自原配置，单次生成仍可波动。跨阶段前后差异不能全部归因于这两条校验规则；G1A02上游漏字段、知识资料取用或维护对象混淆等未修。test 已见回归不能补充未见证据或补判P3 G5。
实现提交：`95a1d476992a1999cadd75aea15c9e656a43262f`。验证结果和本报告在后续单独提交中归档。默认保持rule；未push。
仓库报告：`C:\Users\胡\Documents\Codex\2026-09-17\new-chat\AI_agent_publication\evaluation\INTENT_P31_REPORT.md`。
