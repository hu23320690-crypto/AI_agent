# optimized_v1 评测汇总

评分人：Codex 助手按题目与证据逐项复核，尚未经用户或领域专家复核。

这不是行业基准；文档内容的真实性与厂商适用性不在本轮验证范围。

## 完成情况

计划 60 个案例；执行 60；复核 60。

## 自动指标

{
  "statuses": {
    "ok": 60,
    "error": 0,
    "timeout": 0
  },
  "retrieval": {
    "evaluated": 40,
    "planned": 40,
    "hit_counts": {
      "1": 26,
      "3": 33,
      "5": 38
    },
    "mrr_at_5": 0.75375
  },
  "knowledge_answers": {
    "planned": 40,
    "completed": 40,
    "reviewed": 40,
    "errors": 0,
    "full_correct": 33,
    "partial": 7,
    "incorrect": 0,
    "grounded": 40,
    "strict_pass": 33
  },
  "unanswerable_answers": {
    "planned": 8,
    "completed": 8,
    "reviewed": 8,
    "errors": 0,
    "full_correct": 8,
    "partial": 0,
    "incorrect": 0,
    "grounded": 8,
    "strict_pass": 8
  },
  "agent": {
    "planned": 12,
    "completed": 12,
    "reviewed": 12,
    "task_pass": 12,
    "tool_selection_pass": 12
  },
  "latency": {
    "retrieval": {
      "count": 48,
      "median_seconds": 0.22030220000010559,
      "p95_seconds": 0.2880382999996982
    },
    "rag_generation": {
      "count": 48,
      "median_seconds": 26.798917600000095,
      "p95_seconds": 50.748759000000064
    },
    "agent_turn": {
      "count": 14,
      "median_seconds": 13.16785899999968,
      "p95_seconds": 60.77391459999944
    }
  }
}

## 需改进案例

- K01：按冻结关键点保守计分：回答拆包装和充电，缺少首次使用的建图安排。题目“启动前”与标注建图步骤存在边界歧义，本轮保留题目和尺度，后续版本应澄清。

- K02：正确处理反光物和移动障碍物，但缺少重建前删除旧地图这一标注步骤。

- K05：磨损与沿边模式正确，传感器清理也有检索依据；遗漏边刷能否正常旋转的标注检查点。

- K08：剪断毛发且勿强拉正确，但没有回答怎么拆下主刷及清理刷仓。

- K13：水箱盖、密封圈、出水管正确，但与基线一样没有提到加水刻度限制。

- K32：仍只正确覆盖电量，混入停扫回充情境，漏掉尘盒与传感器，和基线同样部分正确。

- K37：仍未回答至少2.5L；无纺布和撕拉设计是实际资料支持的部分选购建议，因此部分正确。没有再把尘盒500/600ml冒充集尘袋容量。