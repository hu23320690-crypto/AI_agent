# P3.1 C：已见题回归

按冻结合同逐轮评内容0/1/2和忠实度；任务通过另要求全轮完整、内容2、忠实度真。标签及 Runtime 成本信息隐藏，样本按运行前登记种子打乱。评分完成并锁定 SHA256 后才使用揭盲键。每条评分绑定原始 result_sha256。此为 Codex 助手辅助盲评，不是独立专家审核。

| 数据集/模式 | 全轮通过 | 内容0/1/2 | 忠实轮数 | 报告轮/解析观测 | 解析p50/p95秒 | 额外意图调用 | 预算跳过 |
|---|---:|---:|---:|---:|---:|---:|---:|
| base/rule | 12/12 | 0/0/14 | 14/14 | 9/6 | 0.0000/0.0160 | 0 | 0 |
| base/hybrid | 12/12 | 0/0/14 | 14/14 | 9/6 | 1.3280/1.9530 | 6 | 0 |
| generalization_v1/rule | 5/6 | 0/1/10 | 10/11 | 6/6 | 0.0000/0.0000 | 0 | 0 |
| generalization_v1/hybrid | 4/6 | 2/1/8 | 9/11 | 6/6 | 1.5000/2.4840 | 6 | 0 |
| holdout_v2/rule | 6/6 | 0/0/11 | 11/11 | 4/4 | 0.0000/0.0160 | 0 | 0 |
| holdout_v2/hybrid | 6/6 | 0/0/11 | 11/11 | 4/4 | 1.5780/2.2970 | 4 | 0 |

| 数据集 | 进步 | 退步 | 共同通过 | 共同失败 | 未知 | 配对新增解析p95秒/观测轮 |
|---|---:|---:|---:|---:|---:|---:|
| base | 0 | 0 | 12 | 0 | 0 | 1.937/6 |
| generalization_v1 | 0 | 1 | 4 | 1 | 0 | 2.484/6 |
| holdout_v2 | 0 | 0 | 6 | 0 | 0 | 2.297/4 |

## 逐轮评分和成本

表内内容分/忠实度按真实轮次顺序。逐轮完整理由、工具选择、意图冲突、预算跳过及 result_sha256 保留于各运行目录的 `reviews.jsonl` 和 `p31_turn_metrics.jsonl`。尚未执行或截断的轮次也有评分，不从任务分母删除。

| 数据集/模式/任务 | 逐轮 内容分/忠实度 | 全轮通过 |
|---|---|---|
| base/rule/A01 | T1=2/真 | True |
| base/rule/A02 | T1=2/真 | True |
| base/rule/A03 | T1=2/真 | True |
| base/rule/A04 | T1=2/真 | True |
| base/rule/A05 | T1=2/真 | True |
| base/rule/A06 | T1=2/真 | True |
| base/rule/A07 | T1=2/真 | True |
| base/rule/A08 | T1=2/真 | True |
| base/rule/A09 | T1=2/真 | True |
| base/rule/A10 | T1=2/真; T2=2/真 | True |
| base/rule/A11 | T1=2/真; T2=2/真 | True |
| base/rule/A12 | T1=2/真 | True |
| base/hybrid/A01 | T1=2/真 | True |
| base/hybrid/A02 | T1=2/真 | True |
| base/hybrid/A03 | T1=2/真 | True |
| base/hybrid/A04 | T1=2/真 | True |
| base/hybrid/A05 | T1=2/真 | True |
| base/hybrid/A06 | T1=2/真 | True |
| base/hybrid/A07 | T1=2/真 | True |
| base/hybrid/A08 | T1=2/真 | True |
| base/hybrid/A09 | T1=2/真 | True |
| base/hybrid/A10 | T1=2/真; T2=2/真 | True |
| base/hybrid/A11 | T1=2/真; T2=2/真 | True |
| base/hybrid/A12 | T1=2/真 | True |
| generalization_v1/rule/G1A01 | T1=2/真 | True |
| generalization_v1/rule/G1A02 | T1=2/真; T2=2/真 | True |
| generalization_v1/rule/G1A03 | T1=2/真; T2=2/真 | True |
| generalization_v1/rule/G1A04 | T1=2/真; T2=2/真 | True |
| generalization_v1/rule/G1A05 | T1=2/真; T2=1/假 | False |
| generalization_v1/rule/G1A06 | T1=2/真; T2=2/真 | True |
| generalization_v1/hybrid/G1A01 | T1=2/真 | True |
| generalization_v1/hybrid/G1A02 | T1=1/真; T2=2/真 | False |
| generalization_v1/hybrid/G1A03 | T1=2/真; T2=2/真 | True |
| generalization_v1/hybrid/G1A04 | T1=2/真; T2=2/真 | True |
| generalization_v1/hybrid/G1A05 | T1=0/假; T2=0/假 | False |
| generalization_v1/hybrid/G1A06 | T1=2/真; T2=2/真 | True |
| holdout_v2/rule/V2A01 | T1=2/真 | True |
| holdout_v2/rule/V2A02 | T1=2/真; T2=2/真 | True |
| holdout_v2/rule/V2A03 | T1=2/真; T2=2/真 | True |
| holdout_v2/rule/V2A04 | T1=2/真; T2=2/真 | True |
| holdout_v2/rule/V2A05 | T1=2/真; T2=2/真 | True |
| holdout_v2/rule/V2A06 | T1=2/真; T2=2/真 | True |
| holdout_v2/hybrid/V2A01 | T1=2/真 | True |
| holdout_v2/hybrid/V2A02 | T1=2/真; T2=2/真 | True |
| holdout_v2/hybrid/V2A03 | T1=2/真; T2=2/真 | True |
| holdout_v2/hybrid/V2A04 | T1=2/真; T2=2/真 | True |
| holdout_v2/hybrid/V2A05 | T1=2/真; T2=2/真 | True |
| holdout_v2/hybrid/V2A06 | T1=2/真; T2=2/真 | True |

证据目录：
- base/rule: `evaluation\results\intent_p31_seen_base_rule`（已封存）。
- base/hybrid: `evaluation\results\intent_p31_seen_base_hybrid`（已封存）。
- generalization_v1/rule: `evaluation\results\intent_p31_seen_generalization_v1_rule`（已封存）。
- generalization_v1/hybrid: `evaluation\results\intent_p31_seen_generalization_v1_hybrid`（已封存）。
- holdout_v2/rule: `evaluation\results\intent_p31_seen_holdout_v2_rule`（已封存）。
- holdout_v2/hybrid: `evaluation\results\intent_p31_seen_holdout_v2_hybrid`（已封存）。

知识与资料不足非Agent题在运行前依据代码路径证明决定不重跑：`evaluation/results/intent_p3_preflight/non_report_path_proof.json 与 evaluation/results/intent_p31_preflight/runtime_byte_identity.json` ；P3.1 仅改报告意图校验。本节只用于检查退步，不能作为未见泛化证据。
