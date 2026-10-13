# P3 B：Agent test

按冻结合同逐轮评内容0/1/2和忠实度；任务通过另要求全轮完整、内容2、忠实度真。标签及 Runtime 成本信息隐藏，样本按运行前登记种子打乱。评分完成并锁定 SHA256 后才使用揭盲键。每条评分绑定原始 result_sha256。此为 Codex 助手辅助盲评，不是独立专家审核。

| 数据集/模式 | 全轮通过 | 内容0/1/2 | 忠实轮数 | 报告轮/解析观测 | 解析p50/p95秒 | 额外意图调用 | 预算跳过 |
|---|---:|---:|---:|---:|---:|---:|---:|
| intent_agent_v1_r1/rule | 1/12 | 8/6/10 | 21/24 | 24/23 | 0.0000/0.0310 | 0 | 0 |
| intent_agent_v1_r1/hybrid | 4/12 | 4/4/16 | 23/24 | 24/23 | 1.6880/4.6250 | 23 | 0 |

| 数据集 | 进步 | 退步 | 共同通过 | 共同失败 | 未知 | 配对新增解析p95秒/观测轮 |
|---|---:|---:|---:|---:|---:|---:|
| intent_agent_v1_r1 | 3 | 0 | 1 | 8 | 0 | 4.609/23 |

## 逐轮评分和成本

表内内容分/忠实度按真实轮次顺序。逐轮完整理由、工具选择、意图冲突、预算跳过及 result_sha256 保留于各运行目录的 `reviews.jsonl` 和 `p3_turn_metrics.jsonl`。尚未执行或截断的轮次也有评分，不从任务分母删除。

| 数据集/模式/任务 | 逐轮 内容分/忠实度 | 全轮通过 |
|---|---|---|
| intent_agent_v1_r1/rule/IA001 | T1=0/假; T2=0/真 | False |
| intent_agent_v1_r1/rule/IA002 | T1=2/真; T2=0/真 | False |
| intent_agent_v1_r1/rule/IA003 | T1=2/真; T2=0/真 | False |
| intent_agent_v1_r1/rule/IA004 | T1=2/真; T2=2/假 | False |
| intent_agent_v1_r1/rule/IA005 | T1=1/真; T2=0/真 | False |
| intent_agent_v1_r1/rule/IA006 | T1=1/假; T2=0/真 | False |
| intent_agent_v1_r1/rule/IA007 | T1=2/真; T2=0/真 | False |
| intent_agent_v1_r1/rule/IA008 | T1=2/真; T2=2/真 | True |
| intent_agent_v1_r1/rule/IA009 | T1=2/真; T2=0/真 | False |
| intent_agent_v1_r1/rule/IA010 | T1=1/真; T2=1/真 | False |
| intent_agent_v1_r1/rule/IA011 | T1=2/真; T2=1/真 | False |
| intent_agent_v1_r1/rule/IA012 | T1=2/真; T2=1/真 | False |
| intent_agent_v1_r1/hybrid/IA001 | T1=2/真; T2=0/真 | False |
| intent_agent_v1_r1/hybrid/IA002 | T1=2/真; T2=0/真 | False |
| intent_agent_v1_r1/hybrid/IA003 | T1=2/真; T2=2/真 | True |
| intent_agent_v1_r1/hybrid/IA004 | T1=2/真; T2=2/假 | False |
| intent_agent_v1_r1/hybrid/IA005 | T1=1/真; T2=1/真 | False |
| intent_agent_v1_r1/hybrid/IA006 | T1=2/真; T2=0/真 | False |
| intent_agent_v1_r1/hybrid/IA007 | T1=2/真; T2=0/真 | False |
| intent_agent_v1_r1/hybrid/IA008 | T1=2/真; T2=2/真 | True |
| intent_agent_v1_r1/hybrid/IA009 | T1=2/真; T2=2/真 | True |
| intent_agent_v1_r1/hybrid/IA010 | T1=1/真; T2=2/真 | False |
| intent_agent_v1_r1/hybrid/IA011 | T1=2/真; T2=2/真 | True |
| intent_agent_v1_r1/hybrid/IA012 | T1=2/真; T2=1/真 | False |

证据目录：
- intent_agent_v1_r1/rule: `evaluation\results\intent_agent_v1_r1_test_p3_rule`（已封存）。
- intent_agent_v1_r1/hybrid: `evaluation\results\intent_agent_v1_r1_test_p3_hybrid`（已封存）。
