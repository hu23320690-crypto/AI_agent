# current_main_regression_v2 评测汇总

评分人：Codex 助手按题目与证据逐项复核，尚未经用户或领域专家复核。

这不是行业基准；文档内容的真实性与厂商适用性不在本轮验证范围。

## 完成情况

计划 60 个案例；执行 60；复核 60。

## 自动指标

{
  "statuses": {
    "ok": 60,
    "error": 0,
    "timeout": 0,
    "truncated": 0,
    "running": 0,
    "not_run": 0
  },
  "execution_outcomes": {
    "ok": 60,
    "error": 0,
    "timeout": 0,
    "truncated": 0,
    "running": 0,
    "unknown": 0,
    "not_run": 0
  },
  "retrieval": {
    "evaluated": 40,
    "planned": 40,
    "hit_counts": {
      "1": 26,
      "3": 33,
      "5": 38
    },
    "all_required_hit_counts": {
      "1": 26,
      "3": 33,
      "5": 38
    },
    "all_required_metrics_observed": 40,
    "policy_hit_counts": {
      "1": 26,
      "3": 33,
      "5": 38
    },
    "mrr_at_5": 0.755,
    "mrr_definition": "Legacy MRR measures the first rank with any annotated anchor; it does not require all cross-passage evidence."
  },
  "knowledge_answers": {
    "planned": 40,
    "completed": 40,
    "reviewed": 40,
    "errors": 0,
    "execution_complete": 40,
    "not_run": 0,
    "unknown": 0,
    "full_correct": 33,
    "partial": 7,
    "incorrect": 0,
    "grounded": 40,
    "strict_pass": 33,
    "strict_fail": 7,
    "strict_pass_fraction_planned": 0.825,
    "actual_input_evidence": {
      "observed": 40,
      "any_hit": 38,
      "all_required_hit": 38,
      "policy_hit": 38
    }
  },
  "unanswerable_answers": {
    "planned": 8,
    "completed": 8,
    "reviewed": 8,
    "errors": 0,
    "execution_complete": 8,
    "not_run": 0,
    "unknown": 0,
    "full_correct": 8,
    "partial": 0,
    "incorrect": 0,
    "grounded": 8,
    "strict_pass": 8,
    "strict_fail": 0,
    "strict_pass_fraction_planned": 1.0,
    "actual_input_evidence": {
      "observed": 0,
      "any_hit": 0,
      "all_required_hit": 0,
      "policy_hit": 0
    }
  },
  "agent": {
    "planned": 12,
    "completed": 12,
    "reviewed": 12,
    "task_pass": 10,
    "task_fail": 2,
    "unknown": 0,
    "tool_selection_pass": 12,
    "planned_real_turns": 14,
    "synthetic_seeded_turns": 0,
    "observed_model_requests": 27
  },
  "latency": {
    "retrieval": {
      "count": 48,
      "median_seconds": 0.3329658500000505,
      "p95_seconds": 0.45238979999999174
    },
    "rag_generation": {
      "count": 48,
      "median_seconds": 30.920034349999924,
      "p95_seconds": 47.39857219999999
    },
    "agent_turn": {
      "count": 14,
      "median_seconds": 14.057306899999958,
      "p95_seconds": 73.80999030000021
    },
    "case_wall_all_statuses": {
      "count": 60,
      "median_seconds": 33.07585460000007,
      "p95_seconds": 52.28539950000004
    }
  },
  "model_usage": {
    "observed_requests": 75,
    "requests_by_status": {
      "ok": 75,
      "error": 0,
      "running": 0
    },
    "usage_records": 75,
    "input_tokens": 131105,
    "output_tokens": 127744,
    "request_input_message_counts": {
      "count": 75,
      "median_messages": 2,
      "p95_messages": 6
    },
    "note": "Includes actual summary/planner/RAG model calls. Synthetic seed history is input only, not model-generated interactions. Missing provider usage remains unmeasured."
  }
}

## 需改进案例

- K02：执行完成。回答正确说明重建图前清理反光物和移动障碍物，并保留镜面、抛光地砖例子；这些内容与实际输入的地图错乱问答一致。但题面要求重建图前应处理的事项，遗漏实际输入与冻结参考均明确要求的删除旧地图，前置处理不完整，故为部分正确。

- K08：执行完成。用剪刀剪断缠绕毛发、切勿强行拉扯均有实际输入维护条目支持，清理方法主体正确。但题面明确问如何取下来清理，回答未说明拆卸两端卡扣并取下主刷，也未说明用毛刷清理滚刷仓内杂物；实际输入已提供这些完整步骤，回答流程不完整，故为部分正确。

- K12：执行完成。回答正确指出APP分区设置中为客厅、卧室分别配置吸力和出水量，两个指定区域与两类参数均保留，且实际输入直接支持。题面未说明已有完整分区地图，配置不同房间参数需要先完成建图并对地图分区命名；冻结参考和实际输入明确给出这一前提与步骤，回答全部省略，仅给出后半段参数设置，故为部分正确。参考中的清洁次数并非本题所问，不因未复述清洁次数另扣分。

- K13：执行完成。回答列出水箱盖、密封圈、出水管，均为实际输入加水后漏水问答所列的检查部位，没有编造部件。按冻结参考将加水后漏水的检查范围解释为包括水位与刻度线时，回答遗漏刻度线/是否加水过满的检查，故主评分为部分正确。题面只问检查位置，无需机械要求复述拧紧、破损、堵塞等检查细节或完整处理流程；位置范围的合理另一解释见歧义字段。

- K27：执行完成。APP版本和待机状态检查正确，实际输入一般APP无法控制条目支持；退出APP重新进入和切换手动模式也确实出现在实际输入的手动遥控无反应条目中，故具体事实有据。主评分按题面一般APP连接后无法控制的问题判，回答未检查网络是否正常，也未覆盖机器人重启/重新绑定的一般处理，并将手动遥控子场景的操作直接混入而未说明适用条件，排查范围不完整，故为部分正确。题面已显示连接成功，仍不能断言网络工作完全正常。

- K32：执行完成。回答中的电量不足、清扫完成自动回充设置、设备故障均逐项受实际输入‘突然停止清扫，自动回充’故障条目支持，故不属于无据编造。但题面只说清扫中经常停下，并未确认自动回充；按冻结参考的频繁暂停范围，只有电量检查明确对应，未给出尘盒满溢和传感器遮挡两类具体检查，泛称设备故障不能替代它们。实际输入未包含该冻结频繁暂停条目，回答将相关但带自动回充条件的另一故障范围代入，故主评分为部分正确。

- K37：执行完成。回答未给出冻结参考要求的集尘袋至少2.5L，故关键容量问题未回答；对额外设计则给出实际输入支持的无纺布材质和更换时防灰尘溢出的撕拉设计，部分选购建议正确。实际输入确实未检索到2.5L数值及该参考的密封设计条目，回答未指定数值的说明对本次提供资料成立，无纺布容量大及撕拉设计均有实际输入条目支持，故忠实度为真。撕拉更换防溢灰是有据的相关替代设计，但仍不能替代缺失的最低容量答案；知识题有据而不完整不算严格通过。

- A04：唯一真实轮次完整完成，无截断。用户明确要求2099年1月；实际fetch_external_data参数为会话用户1001、月份2099-01，真实返回not_found，最终答复正确说明该用户该月无记录、无法生成报告，未换用户或月份、未生成使用/耗材结论；核心查询与安全反馈完成，工具选择符合允许路径。严格任务通过判否：最终追加的“内置演示记录覆盖2025年”未出现在本次实际模型输入或工具返回中；真实返回仅含status/user_id/month/message，没有months、records或覆盖范围，不能用其他CSV记录或程序常量替代实际输入证据。模型原始生成曾写“2026年至今”，与最终返回文本不同，保留此差异但以实际最终交付文本评分。

- A05：唯一真实轮次完整完成，无截断。实际system日期为2026-10-06，“本月”正确解析为2026-10；fetch_external_data实际查询会话用户1001、月份2026-10，真实返回not_found。最终答复明确该用户该月无记录、无法生成该月报告，未擅自改查2025年有数据的月份，未编造设备数据；核心查询与安全反馈完成，工具选择符合允许路径。严格任务通过判否：最终追加的“内置演示记录覆盖2025年”不受本轮实际输入或工具返回支持；真实返回仅含status/user_id/month/message，没有months、records或覆盖范围。模型原始生成没有此覆盖范围句，以实际最终交付文本评分。