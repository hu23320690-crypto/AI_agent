# generalization_repair_holdout_v2 评测汇总

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
      "1": 20,
      "3": 27,
      "5": 28
    },
    "all_required_hit_counts": {
      "1": 17,
      "3": 25,
      "5": 27
    },
    "all_required_metrics_observed": 28,
    "policy_hit_counts": {
      "1": 17,
      "3": 25,
      "5": 27
    },
    "mrr_at_5": 0.8345238095238096,
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
    "full_correct": 25,
    "partial": 3,
    "incorrect": 0,
    "grounded": 21,
    "strict_pass": 18,
    "strict_fail": 10,
    "strict_pass_fraction_planned": 0.6428571428571429,
    "actual_input_evidence": {
      "observed": 28,
      "any_hit": 26,
      "all_required_hit": 25,
      "policy_hit": 25
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
    "task_pass": 5,
    "task_fail": 1,
    "unknown": 0,
    "tool_selection_pass": 6,
    "planned_real_turns": 11,
    "synthetic_seeded_turns": 128,
    "observed_model_requests": 25
  },
  "latency": {
    "retrieval": {
      "count": 34,
      "median_seconds": 0.33233124999605934,
      "p95_seconds": 0.4395330000043032
    },
    "rag_generation": {
      "count": 34,
      "median_seconds": 2.797681250001915,
      "p95_seconds": 4.206863999999769
    },
    "agent_turn": {
      "count": 11,
      "median_seconds": 18.25489329999982,
      "p95_seconds": 34.278325100000075
    },
    "case_wall_all_statuses": {
      "count": 40,
      "median_seconds": 7.668314099999407,
      "p95_seconds": 52.18635809999978
    }
  },
  "model_usage": {
    "observed_requests": 56,
    "requests_by_status": {
      "ok": 56,
      "error": 0,
      "running": 0
    },
    "usage_records": 56,
    "input_tokens": 102397,
    "output_tokens": 13609,
    "request_input_message_counts": {
      "count": 56,
      "median_messages": 2.0,
      "p95_messages": 9
    },
    "note": "Includes actual summary/planner/RAG model calls. Synthetic seed history is input only, not model-generated interactions. Missing provider usage remains unmeasured."
  }
}

## 需改进案例

- V2K05：不能混用、规格功能不同、拖地系统专门过滤污水与混用损坏设备的核心正确。但新增拖地滤网耐水抗污、结构更细密拦截泥沙，以及混用导致堵塞/清洁效率下降，实际模型输入没有这些结构材质和后果关系。HEPA过滤0.3μm和海绵滤网有PDF依据，不因这些有据扩展扣分；未支持扩展仍使忠实度失败。 根代理已独立核对最终回答、实际资料及原口径说明并确认本判定。

- V2K06：说明薄地毯可能无法识别、需确认开启地毯增压，但遗漏先确认机型支持该功能的必要限制。驱动轮打滑、杂物、防滑贴额外检查有本轮故障35条及扫地14条支持，答案标明跨地毯故障检测来源，故内容不完整而忠实度通过。 根代理已独立核对最终回答、实际资料及原口径说明并确认本判定。

- V2K07：手机离线可执行已设置任务、机器人连接WiFi和任务设置前提完整正确；水箱充足/尘盒空的扩展在本轮长出差扫拖73条有依据。但额外假设依赖手机的实时参数、APP动态吸力/水量断网后可能无法更新这一具体行为，不在本轮任何实际输入中，不能从手机离线定时执行条目推导。 根代理已独立核对最终回答、实际资料及原口径说明并确认本判定。

- V2K13：不同机型差异、不能保证所有机型、需查看对应机型官方参数均正确。本次也明确举例部分机型门槛≤2cm；主结论仍采用PDF多数1.5-2cm/高端2.5cm，≤2cm仅作为部分机型举例，没有把TXT一般≤2cm作为所求常见上限，按冻结金标记1分。实际输入同时支持PDF数值与TXT一般≤2cm，忠实度通过。题面只说扫地问答、未指明TXT/PDF，广义正确与固定gold口径有争议，单独保留原有来源别名歧义；本次已补核对实际机型，不因该项遗漏扣分，不据输出回改金标。 根代理已独立核对最终回答、实际资料及原口径说明并确认本判定。

- V2K15：浮球防污水回流、易拆洗便于清除残留避免异味两个所求点答齐。额外把浮球作用扩大为保证水位稳定及防过高溢出，实际指南23仅支持防回流；指南132的防溢出属于水位显示和及时倾倒，不支持浮球的该作用。拆洗防堵塞、延长设备整体使用寿命也无本次依据，故忠实度不通过。

- V2K17：仅支持机型、APP绘制路径、重点区域精准扫拖三个必答点完整，未泛化成全部机型。但把APP‘自定义清扫—先扫后拖’及吸力/出水量设置称为自定义路线的具体设置方法，将不同功能的问答2错套到问答87，虽两条均实际入模仍缺该路线方法的依据，忠实度不通过。

- V2K21：存放断开充电座、不长期插电、每1—2个月补电至80%—90%三个必答点完整。额外断言‘月度补电周期与电池类型相关’并引用维护资料，但实际输入无电池类型决定补电周期的条件；‘长期存放需密封’也把仅配件密封袋规则泛化。拆卸电池存放前50%—70%条目确在本次输入，但不为上述新关系背书。

- V2K24：水位异常的清水刻度、污水已满、水位传感器清理、加水倒污水后重启完整正确。但清理机器人前的通用安全子问未答全程断电，改答安装拖布前干净无硬化、避免二次污染；后者事实本身来自实际维护9且保留‘安装拖布前’条件，因此属于有据但答非所问的安全子问，内容部分正确，忠实度仍真。断电锚本次未进入模型。

- V2K26：所问网络和供电要求已完整回答：升级前连接WiFi、升级中保持开机与网络连接、不可关机断电。题面已假定APP开始升级，未请求具体点击入口，不因未复述‘立即升级’而扣内容分。忠实度不通过：追加‘否则可能导致设备损坏’，实际升级条目只写不可断电，另一固件升级失败条目仅给恢复办法，没有断电导致硬件损坏的具体机制或后果依据。

- V2K28：每层单独建图、专属扫拖参数、搬运前清理底部相关部位和传感器并校准、手动搬到二楼后启动均交付，未假定自动跨层。但额外要求地图必须标注楼层分界线、APP设置水压/拖布类型及手动确认参数加载，实际多楼层条目没有这些设置、属性或检查条件。将轮组列作传感器、要求APP切换二楼地图也超出本次所给多楼层说明（另一资料反而写传感器自动识别楼层）。具体扩展缺依据，忠实度不通过。

- V2N04：核心拒答没有编造1004特定日期的单次起止时间或逐分钟噪音，实际通用入模资料确无此明细；但末句“需要查看项目演示CSV文件才能获取相关数据”错误暗示CSV可提供所求明细，而冻结CSV仅为月度汇总，无法反推，故内容2但新增事实忠实度不通过。

- V2A06：首轮实际历史摘要保留1004/2025-09与两字段并正确回顾；次轮也成功实查正确用户月份，猫砂8次/月正确，但最终把“两个字段”的“两个”黏进自动回充成功率字段名，输出“自动回充成功率两个：未提供”，遗漏工具明确给出的88%并产生与请求字段证据相冲突的缺值反馈。因此工具选择通过不能算全轮语义通过。