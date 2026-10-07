# generalization_repair_v2 评测汇总

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
    "full_correct": 24,
    "partial": 4,
    "incorrect": 0,
    "grounded": 19,
    "strict_pass": 17,
    "strict_fail": 11,
    "strict_pass_fraction_planned": 0.6071428571428571,
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
    "grounded": 5,
    "strict_pass": 5,
    "strict_fail": 1,
    "strict_pass_fraction_planned": 0.8333333333333334,
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
      "median_seconds": 0.3296735500007344,
      "p95_seconds": 0.46707359999709297
    },
    "rag_generation": {
      "count": 34,
      "median_seconds": 2.659785549996741,
      "p95_seconds": 4.176642600003106
    },
    "agent_turn": {
      "count": 11,
      "median_seconds": 20.987947699999495,
      "p95_seconds": 50.021825299998454
    },
    "case_wall_all_statuses": {
      "count": 40,
      "median_seconds": 7.649956050001492,
      "p95_seconds": 66.10105150000163
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
    "input_tokens": 88890,
    "output_tokens": 17894,
    "request_input_message_counts": {
      "count": 55,
      "median_messages": 2,
      "p95_messages": 9
    },
    "note": "Includes actual summary/planner/RAG model calls. Synthetic seed history is input only, not model-generated interactions. Missing provider usage remains unmeasured."
  }
}

## 需改进案例

- G1K01：普通家用3000Pa、地毯4000Pa下限及可调吸力适配不同地面完整正确。新增“及污渍程度”与避免污渍差异导致效果不佳的吸力调节适用关系，未由本轮实际输入证明：选购2条只支持不同地面适配，42条按顽固污渍调高档说的是出水量，不能移作吸力能力说明。内容完整，但扩展条件关联缺依据。

- G1K09：外壳ABS耐磨、拖布支架不锈钢防锈、密封圈食品级硅胶三个材质和题面所求两用途均正确。但额外解释食品级硅胶可避免化学腐蚀及保证清洁卫生，实际输入选购21条只给该材质名，其余模型输入也没有该材料用途/因果；新增具体功效无依据。 根代理已独立核对完整实际输入证据并确认该判定；未据失败修改代码、金标或重跑。

- G1K11：10cm处停拖、只扫及抬升替代功能均答出，禁拖区扩展亦由本轮输入支持。关键配置却被写成应将缓冲区设为离地毯10cm的区域，原文要求把地毯边缘设为缓冲区、10cm是机器人停拖的距离；不能从动作阈值推出APP区域边界参数，因此配置答法不准确且依据不忠实。原冻结gold对其他有效替代办法有标注歧义仍保留，但本答案已明确含抬升，该歧义不构成本次扣分原因。 根代理已独立核对完整实际输入证据并确认该判定；未据失败修改代码、金标或重跑。

- G1K12：部分机型支持、中档出水、专用瓷砖清洁液、多次拖扫所求条件完整，支持时配合按使用该功能理解，不因未逐字说开启扣分。但把多次拖扫具体化为3-5次，两处新增确定次数均没有实际输入依据；本轮只有多次及可设置次数，没有3-5的建议。 根代理已独立核对完整实际输入证据并确认该判定；未据失败修改代码、金标或重跑。

- G1K15：干软布/无尘布轻擦、禁止湿布和酒精、移到通风干燥处均已交付，内容覆盖冻结必答点。忠实度不通过：model_requests[0].rag_contexts 的5份实际资料含扫拖问答61及维护13—16，却没有故障179的‘移至干燥环境使用’；回答将阳台通风安排推广为受潮传感器的恢复环境，缺少本次具体来源依据。镜面家具、低矮家具的每周传感器维护本身有实际资料，但不能替代缺失的受潮恢复条目。

- G1K16：检查并清理底部防跌落传感器、排除灰尘遮挡、平整地面校准和测试、损坏联系售后更换均正确，但遗漏题面所求恢复步骤中的‘重启设备’。两份锚完整进入模型，属生成遗漏，不能以笼统校准等价为重启。已输出具体事实均有据。

- G1K17：答出尘盒是否安装到位和感应传感器是否有灰尘两项检查，但将检查项作为‘检查和处理’的全部回答，遗漏重新安装并扣紧尘盒、擦拭感应传感器两个对应处理步骤。故障27完整进入模型，属有证据情况下的步骤遗漏；现有检查事实有据。

- G1K18：禁区边界调整、保存后重新识图、关闭‘禁区临时取消’完整正确。额外要求‘需确保机器人支持地毯增压功能’却将相邻地毯增压条目的条件错误应用到禁区恢复；‘避免因地图不完整导致禁区识别错误’也是把分区清扫条目推广为该故障因果。相邻原文出现这些词不等于为禁区提供该条件，因此忠实度不通过。

- G1K24：水泵堵塞并疏通、线路松动检查、水泵故障联系售后更换三分支覆盖冻结必答点。忠实度不通过：额外给出‘紧固线路’，实际故障155只有‘检查线路’，其他实际资料为拖布电机安装/线路售后排查或清洁仓滤网，不提供自行紧固此水泵线路的方法。不能将推测修复动作视为原文依据。

- G1K27：低温保护、机身结冰检查，室温静置30分钟及解冻后充电开机正确，但另一子问将充电最低温度错误答成10℃，冻结维护19要求≥5℃。实际模型资料只有故障173而无维护19，且编造‘低温保护机制要求电池温度≥10℃才能安全充电’的依据。主要启动恢复子问正确，充电温度子问错误，内容为部分正确；忠实度不通过。

- G1K28：特殊字符、机器人中文WiFi支持、改为英文或数字、重新连接四个必答点完整。额外断言‘部分老旧路由器不兼容中文WiFi’并要求检查路由器的中文SSID支持，实际资料只谈机器人的名称兼容，没有路由器年代与兼容性事实。重启路由器/机器人和重输密码本身在实际故障3中有据，不能用它为前一具体无据断言背书。

- G1N06：完整拒答具体设备的Home Assistant完全离线支持和实体ID/服务名/端口，手机离线定时工作的限定受本次扫拖88输入支持。但又断言其集成‘需设备厂商提供特定协议和API’；实际5块输入没有Home Assistant集成条件，也不能据通用智能联动证明厂商提供接口是必要条件。核心拒答内容2，新增必要条件无本次依据。

- G1A05：首轮真实回忆完整保留具体清洁仓刷、三个动作及按章节分频率要求；第二轮虽仍称同一目标，却把水箱柠檬酸浸泡和主刷胶条检查迁移到清洁仓刷，并错误称无固定更换周期，未交付耗材专项每月清水冲洗/3-6个月更换及分章节频率。完整执行与摘要保留不等于维护任务通过。

- G1A06：首轮检查电池/配件与空转1-2分钟的流程完整，第二轮正确拒绝因空转假设免除充电和地图处理，并给充电30分钟、删旧图重建，但遗漏激活电池、校准电量显示及扫拖/避障/回充目的，且编造通常5-10分钟建图时长。全部实际轮次执行完整，第二轮仍不通过。