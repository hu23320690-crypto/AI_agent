# generalization_repair_v3 评测汇总

评分人：Codex 助手按题目与证据逐项复核，尚未经用户或领域专家复核。

这不是行业基准；文档内容的真实性与厂商适用性不在本轮验证范围。

## 完成情况

计划 40 个案例；执行 40；复核 40。

## 自动指标

{
  "statuses": {
    "ok": 40,
    "error": 0,
    "timeout": 0,
    "truncated": 0,
    "running": 0,
    "not_run": 0
  },
  "execution_outcomes": {
    "ok": 40,
    "error": 0,
    "timeout": 0,
    "truncated": 0,
    "running": 0,
    "unknown": 0,
    "not_run": 0
  },
  "retrieval": {
    "evaluated": 28,
    "planned": 28,
    "hit_counts": {
      "1": 21,
      "3": 27,
      "5": 28
    },
    "all_required_hit_counts": {
      "1": 18,
      "3": 26,
      "5": 27
    },
    "all_required_metrics_observed": 28,
    "policy_hit_counts": {
      "1": 18,
      "3": 26,
      "5": 27
    },
    "mrr_at_5": 0.8601190476190477,
    "mrr_definition": "Legacy MRR measures the first rank with any annotated anchor; it does not require all cross-passage evidence."
  },
  "knowledge_answers": {
    "planned": 28,
    "completed": 28,
    "reviewed": 28,
    "errors": 0,
    "execution_complete": 28,
    "not_run": 0,
    "unknown": 0,
    "full_correct": 21,
    "partial": 7,
    "incorrect": 0,
    "grounded": 24,
    "strict_pass": 20,
    "strict_fail": 8,
    "strict_pass_fraction_planned": 0.7142857142857143,
    "actual_input_evidence": {
      "observed": 28,
      "any_hit": 25,
      "all_required_hit": 23,
      "policy_hit": 23
    }
  },
  "unanswerable_answers": {
    "planned": 6,
    "completed": 6,
    "reviewed": 6,
    "errors": 0,
    "execution_complete": 6,
    "not_run": 0,
    "unknown": 0,
    "full_correct": 6,
    "partial": 0,
    "incorrect": 0,
    "grounded": 6,
    "strict_pass": 6,
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
    "planned": 6,
    "completed": 6,
    "reviewed": 6,
    "task_pass": 4,
    "task_fail": 2,
    "unknown": 0,
    "tool_selection_pass": 6,
    "planned_real_turns": 11,
    "synthetic_seeded_turns": 64,
    "observed_model_requests": 25
  },
  "latency": {
    "retrieval": {
      "count": 34,
      "median_seconds": 0.3490808999999899,
      "p95_seconds": 0.49687649999987116
    },
    "rag_generation": {
      "count": 34,
      "median_seconds": 2.5363634000000275,
      "p95_seconds": 3.8121642999999494
    },
    "agent_turn": {
      "count": 11,
      "median_seconds": 19.439746600000035,
      "p95_seconds": 41.46438430000012
    },
    "case_wall_all_statuses": {
      "count": 40,
      "median_seconds": 7.549024300000042,
      "p95_seconds": 60.67685499999993
    }
  },
  "model_usage": {
    "observed_requests": 55,
    "requests_by_status": {
      "ok": 55,
      "error": 0,
      "running": 0
    },
    "usage_records": 55,
    "input_tokens": 88714,
    "output_tokens": 16487,
    "request_input_message_counts": {
      "count": 55,
      "median_messages": 2,
      "p95_messages": 9
    },
    "note": "Includes actual summary/planner/RAG model calls. Synthetic seed history is input only, not model-generated interactions. Missing provider usage remains unmeasured."
  }
}

## 需改进案例

- G1K01：普通家用≥3000Pa、地毯≥4000Pa及吸力可调适配不同地面三个所求要点完整。额外称调节可避免吸力过强导致地面损伤：本次实际模型资料仅有不同地面适配、瓷砖强吸力、出水量不同档位等，没有吸力过强损伤地面这一因果。不能把出水量场景适配或一般常识当该新增吸力风险的输入依据。

- G1K11：10cm处停止拖地、仅扫地已正确，缓冲区情境保留，但未明确把地毯边缘设为缓冲区；“设置为10cm处停止拖地”是行动阈值描述，不据此断言其编造了10cm宽的区域边界。替代方案选择了同次输入另一条目的禁拖区，并说明其自动抬升或跳过拖地，不能说完全未出现抬升；但未给冻结金标所要求的独立开启拖布抬升这一替代功能。按原固定关键点记部分，禁拖区内容有据不判幻觉；保留题面宽泛“哪种替代功能”与冻结指定答案的边界。

- G1K12：第一段给出了仅部分机型支持、中档出水、专用瓷砖清洁液、多次拖扫，主体正确，但未明确开启高频振动且后段产生矛盾及错误条件关联：将缺水恢复用的断点续拖/分区分批说成瓷砖缝污渍处理方法，还称资料未明确上述安排细节，否认实际输入已明示的措施。不能因这些词分别存在于资料就认为其适用关系受支持。

- G1K14：滋滋声滤网堵塞、咔咔声滚刷/边刷缠杂物、嗡嗡声电机故障三种多为线索及不能直接确诊的限定均正确。但题目明确问资料处理方向，答案只给进一步排查和处理，未交付针对性清理或联系售后这一关键措施，按固定要求记部分。非确诊判断是对“多为”的准确归纳，无新增诊断保证。

- G1K15：干软布/无尘布轻擦、禁用湿布和酒精回答正确；遗漏题目要求的受潮后移至干燥环境使用。实际模型输入含扫拖问答61和维护保养13—16，答案新增通风、镜面家具和低矮家具的传感器清理均有本次输入支持；故障179的干燥环境恢复片段未进入本次输入，不能以知识库另处存在为已回答。

- G1K17：仅回答尘盒安装到位和感应传感器灰尘两处检查，未交付重新安装扣紧及擦拭传感器的处理动作。故障27原句完整进入实际模型输入，故属于有据但漏步骤；现有回答无新增无据事实。

- G1K21：回答通道清理和机器人/集尘座连接，但遗漏集尘仓关闭这一明确所求条件。新增“回充传感器可能影响集尘系统连接”无本次依据：输入问答10仅涉及不自动回充，不能支持其对集尘连接的影响。集尘电机、重启和满溢检查虽有其他本次输入支持，仍不能弥补该漏点及无据因果。

- G1K27：低温保护/结冰检查、室温30分钟、解冻后充电开机四项正确；充电门槛回答“高于5℃”，与冻结参考“不低于5℃（≥5℃）”边界不同。并且本次实际模型输入/生产服务资料只有故障173—174，未含维护19的冬季充电最低温度；不能以低于5℃不能开机的事实反推冬季充电门槛。

- G1A05：64对合成历史后首轮完整回顾基站清洁仓清洁刷、排除底部清洁刷、动作分离、分章节频率与不足不猜；但第二轮实际RAG只入模3块，缺耗材专项清洁刷条目。最终虽每日去毛发正确，却把污水仓冲洗、水箱柠檬酸浸泡和主刷打滑更换列给清洁刷，缺每周去毛发、每月清水洗、3–6个月与分章节频次，且以主刷胶条磨损支撑清洁刷，内容部分正确但对象关联忠实度失败。

- G1A06：两轮所求核心流程内容完整；第一轮却将扫拖98的搬家后磕碰检查并入“按长期存放维护资料”要求。本次模型确见该答句，但chunk切掉其“搬家后重新使用”标题，源问适用场景不同，不能无条件作为长期存放条目要求，故首轮新增适用关联不忠实。次轮充电30分钟、激活及显示校准、删旧图重建和扫拖/避障/回充校准完整且有实际维护17–19输入支持，没有假设变已测或虚构建图时长。