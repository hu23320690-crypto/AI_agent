# intent_agent_v1_r1 第三步作者复核清单

仅列两个替换任务和IA008追加note。未冻结、未运行意图解析器或模型。

## IA002

**替换说明**：r1 替换题，原题见 intent_agent_v1。目标2025-01有两项记录，要求保持目标并与上个月2024-12比较，但前一年基准无记录。区别于G1A03移到下一年导致目标无记录，以及G1A02/V2A02两期有记录的比较；用户1003和两字段组合未在其余10例使用，题面不复用旧句式。两轮各有当前报告查询；第二轮expect=record仅描述目标存在，comparison_checks为空是因为基准缺失，不得生成差值。

### 第1轮

**完整题面**：为我整理2025年一月这份记录，毛发清理放前面，地毯增压使用放后面，就这两栏。

```json
{
  "query": "为我整理2025年一月这份记录，毛发清理放前面，地毯增压使用放后面，就这两栏。",
  "reference_answer": "报告用户为受信会话用户1003，目标月份2025-01，不得替换用户或月份。 毛发清理为92%。 地毯增压使用为15次/月。 只列毛发清理、地毯增压使用，保持该顺序，不追加其他报告字段。 本轮不比较、不请求知识说明，不追加诊断。",
  "required_points": [
    "报告用户为受信会话用户1003，目标月份2025-01，不得替换用户或月份。",
    "毛发清理为92%。",
    "地毯增压使用为15次/月。",
    "只列毛发清理、地毯增压使用，保持该顺序，不追加其他报告字段。",
    "本轮不比较、不请求知识说明，不追加诊断。"
  ],
  "evidence": [
    {
      "source": "data/external/records.csv",
      "line_start": 4,
      "line_end": 4,
      "quote": "\"1003\",\"90㎡ | 1狗 | 短毛地毯\",\"毛发清理:92%\\n地毯增压使用:15次/月\",\"胶刷更换:剩余25天\\n尘盒容量:每日清理\",\"毛发处理效率前15%\",\"2025-01\""
    }
  ],
  "evidence_policy": "all",
  "required_tools": [
    "fetch_external_data"
  ],
  "allowed_tools": [
    "get_user_id",
    "get_current_month",
    "fetch_external_data",
    "fill_context_for_report"
  ],
  "expect": "record",
  "user_id": "1003",
  "month": "2025-01",
  "gold_intent": {
    "fields": [
      "毛发清理",
      "地毯增压使用"
    ],
    "unknown_fields": [],
    "limited": true,
    "full_report": false,
    "target_month": "2025-01",
    "compare": false,
    "comparison_month": null,
    "knowledge_requested": false,
    "unresolved_month": false
  },
  "record_checks": [
    {
      "user_id": "1003",
      "month": "2025-01",
      "field": "毛发清理",
      "value": "92%",
      "csv_line": 4
    },
    {
      "user_id": "1003",
      "month": "2025-01",
      "field": "地毯增压使用",
      "value": "15次/月",
      "csv_line": 4
    }
  ],
  "comparison_checks": []
}
```

### 第2轮

**完整题面**：一月仍作目标，沿用这两栏，和上个月比；请按实际有无记录说明比较结果。

```json
{
  "query": "一月仍作目标，沿用这两栏，和上个月比；请按实际有无记录说明比较结果。",
  "reference_answer": "保持受信用户1003，目标仍为2025-01；上个月是比较基准2024-12，不将目标移到2024-12。 交付目标2025-01的毛发清理92%、地毯增压使用15次/月，保持该顺序且不追加字段。 明确用户1003在基准月2024-12无记录，因此无法计算这两项的差值。 不把缺失基准当零，不估算差值，也不改用2025-01或其他月份作为基准。 本轮目标值须来自本轮有效授权查询；基准无记录须经正确用户和月份查询核实。",
  "required_points": [
    "保持受信用户1003，目标仍为2025-01；上个月是比较基准2024-12，不将目标移到2024-12。",
    "交付目标2025-01的毛发清理92%、地毯增压使用15次/月，保持该顺序且不追加字段。",
    "明确用户1003在基准月2024-12无记录，因此无法计算这两项的差值。",
    "不把缺失基准当零，不估算差值，也不改用2025-01或其他月份作为基准。",
    "本轮目标值须来自本轮有效授权查询；基准无记录须经正确用户和月份查询核实。"
  ],
  "evidence": [
    {
      "source": "data/external/records.csv",
      "line_start": 4,
      "line_end": 4,
      "quote": "\"1003\",\"90㎡ | 1狗 | 短毛地毯\",\"毛发清理:92%\\n地毯增压使用:15次/月\",\"胶刷更换:剩余25天\\n尘盒容量:每日清理\",\"毛发处理效率前15%\",\"2025-01\""
    }
  ],
  "evidence_policy": "all",
  "required_tools": [
    "fetch_external_data"
  ],
  "allowed_tools": [
    "get_user_id",
    "get_current_month",
    "fetch_external_data",
    "fill_context_for_report"
  ],
  "expect": "record",
  "user_id": "1003",
  "month": "2025-01",
  "gold_intent": {
    "fields": [
      "毛发清理",
      "地毯增压使用"
    ],
    "unknown_fields": [],
    "limited": true,
    "full_report": false,
    "target_month": "2025-01",
    "compare": true,
    "comparison_month": "2024-12",
    "knowledge_requested": false,
    "unresolved_month": false
  },
  "record_checks": [
    {
      "user_id": "1003",
      "month": "2025-01",
      "field": "毛发清理",
      "value": "92%",
      "csv_line": 4
    },
    {
      "user_id": "1003",
      "month": "2025-01",
      "field": "地毯增压使用",
      "value": "15次/月",
      "csv_line": 4
    }
  ],
  "comparison_checks": [],
  "absence_basis": {
    "source": "data/external/records.csv",
    "scope": "全表用户1003、比较基准月份2024-12",
    "inspection": "静态检查CSV主键(1003,2024-12)不存在；2025-01目标记录存在。基准缺失不代表数值为零。"
  }
}
```

## IA005

**替换说明**：r1 替换题，原题见 intent_agent_v1。HEPA剩余比例与资料建议更换周期不能推出个体剩余时间；区别于G1A04电池衰减与续航门槛判断、V2A04/V2A05滤网部件区分及清洗更换条件。两轮换月但不比较，不复用旧题面句式。第2轮资料不足判断主要由record_evidence和RAG完成，分析时不得把该轮变化直接归因于意图改造。

### 第1轮

**完整题面**：把2025年二月报告缩到HEPA滤网一栏，保留记录里的剩余比例；再从《维护保养》的HEPA条目摘出更换周期。

```json
{
  "query": "把2025年二月报告缩到HEPA滤网一栏，保留记录里的剩余比例；再从《维护保养》的HEPA条目摘出更换周期。",
  "reference_answer": "报告用户为受信会话用户1001，目标月份2025-02，不得替换用户或月份。 仅列HEPA滤网，记录为剩余35%，不追加其他报告字段。 依据《维护保养》第129行HEPA条目说明3–6个月更换新滤网。 3–6个月是资料中的更换周期，不是这只滤网还能使用的时间；不据剩余比例诊断实际设备。",
  "required_points": [
    "报告用户为受信会话用户1001，目标月份2025-02，不得替换用户或月份。",
    "仅列HEPA滤网，记录为剩余35%，不追加其他报告字段。",
    "依据《维护保养》第129行HEPA条目说明3–6个月更换新滤网。",
    "3–6个月是资料中的更换周期，不是这只滤网还能使用的时间；不据剩余比例诊断实际设备。"
  ],
  "evidence": [
    {
      "source": "data/external/records.csv",
      "line_start": 12,
      "line_end": 12,
      "quote": "\"1001\",\"65㎡公寓 | 单身 | 木地板\",\"覆盖率:86%\\n日均清扫:46㎡\\n漏扫区域:沙发底部（高度不足）\",\"主刷寿命:剩余55天\\nHEPA滤网:剩余35%\",\"优于68%同面积用户（清洁频率更高）\",\"2025-02\""
    },
    {
      "source": "data/维护保养.txt",
      "line_start": 129,
      "line_end": 129,
      "quote": "1. HEPA滤网：每周用软毛刷轻刷表面灰尘，每1-2个月用清水冲洗（不可揉搓），阴凉处晾干，3-6个月更换新滤网。"
    }
  ],
  "evidence_policy": "all",
  "required_tools": [
    "fetch_external_data",
    "rag_summarize"
  ],
  "allowed_tools": [
    "get_user_id",
    "get_current_month",
    "fetch_external_data",
    "fill_context_for_report",
    "rag_summarize"
  ],
  "expect": "record",
  "user_id": "1001",
  "month": "2025-02",
  "gold_intent": {
    "fields": [
      "HEPA滤网"
    ],
    "unknown_fields": [],
    "limited": true,
    "full_report": false,
    "target_month": "2025-02",
    "compare": false,
    "comparison_month": null,
    "knowledge_requested": true,
    "unresolved_month": false
  },
  "record_checks": [
    {
      "user_id": "1001",
      "month": "2025-02",
      "field": "HEPA滤网",
      "value": "剩余35%",
      "csv_line": 12
    }
  ],
  "comparison_checks": []
}
```

### 第2轮

**完整题面**：换看2025年十一月，仍只抄HEPA滤网的剩余比例。这个比例能折算成“还能用几个月”吗？请说明资料是否给出了换算依据。

```json
{
  "query": "换看2025年十一月，仍只抄HEPA滤网的剩余比例。这个比例能折算成“还能用几个月”吗？请说明资料是否给出了换算依据。",
  "reference_answer": "报告用户为受信会话用户1001，目标月份换为2025-11，必须本轮查询新月份记录。 仅列HEPA滤网，记录为剩余15%，不追加其他报告字段，也不自行比较两个月。 不能将剩余15%换算成还能使用几个月或几天；CSV和第129行没有提供这种换算依据。 3–6个月更换周期不等于个体滤网总寿命或剩余寿命，不能将15%乘以3或6个月，也不能据此给出剩余月数或天数。 说明现有资料不足以确定剩余使用时间，不诊断该设备是否现在需要更换或还能安全使用多久。",
  "required_points": [
    "报告用户为受信会话用户1001，目标月份换为2025-11，必须本轮查询新月份记录。",
    "仅列HEPA滤网，记录为剩余15%，不追加其他报告字段，也不自行比较两个月。",
    "不能将剩余15%换算成还能使用几个月或几天；CSV和第129行没有提供这种换算依据。",
    "3–6个月更换周期不等于个体滤网总寿命或剩余寿命，不能将15%乘以3或6个月，也不能据此给出剩余月数或天数。",
    "说明现有资料不足以确定剩余使用时间，不诊断该设备是否现在需要更换或还能安全使用多久。"
  ],
  "evidence": [
    {
      "source": "data/external/records.csv",
      "line_start": 102,
      "line_end": 102,
      "quote": "\"1001\",\"65㎡公寓 | 单身 | 木地板\",\"覆盖率:88%\\n日均清扫:48㎡\\n无漏扫区域（沙发底部垫高）\",\"主刷寿命:剩余35天\\nHEPA滤网:剩余15%\",\"优于75%同面积用户（清洁无死角）\",\"2025-11\""
    },
    {
      "source": "data/维护保养.txt",
      "line_start": 129,
      "line_end": 129,
      "quote": "1. HEPA滤网：每周用软毛刷轻刷表面灰尘，每1-2个月用清水冲洗（不可揉搓），阴凉处晾干，3-6个月更换新滤网。"
    }
  ],
  "evidence_policy": "all",
  "required_tools": [
    "fetch_external_data"
  ],
  "allowed_tools": [
    "get_user_id",
    "get_current_month",
    "fetch_external_data",
    "fill_context_for_report",
    "rag_summarize"
  ],
  "expect": "record",
  "user_id": "1001",
  "month": "2025-11",
  "gold_intent": {
    "fields": [
      "HEPA滤网"
    ],
    "unknown_fields": [],
    "limited": true,
    "full_report": false,
    "target_month": "2025-11",
    "compare": false,
    "comparison_month": null,
    "knowledge_requested": true,
    "unresolved_month": false
  },
  "record_checks": [
    {
      "user_id": "1001",
      "month": "2025-11",
      "field": "HEPA滤网",
      "value": "剩余15%",
      "csv_line": 102
    }
  ],
  "comparison_checks": [],
  "knowledge_evidence_policy": "prior_verified_evidence_allowed",
  "note": "本轮知识子问可复用第一轮仍有效、已经验证的第129行HEPA更换周期；必须本轮查2025-11记录。允许重新RAG，不要求重复检索；百分比不能推导剩余月数/天数或设备诊断。"
}
```

## IA008追加note

P0 审核补充：两轮请求的2026-01和2026-04均无该用户记录，会话已授权字段目录为空，所以gold_intent把“覆盖率”记为unknown_fields，而非已知字段。Agent评分以最终交付是否正确说明相应用户/月无记录、无挪月或补值为准；辅助意图分类不代替交付评分。本轮仅补充note，不改gold或其他标注。

## 核对

12例/24轮；49条记录、8个差值、52次证据引用、3个缺失键静态核对通过。完整CSV值/行号、百分点及方向、原文引用、1000对相似度与各组双视图top3见step3_checks.json。

9例整行与原版逐字节一致；IA008只有note变化；组件r1全部文件与45d65f0一致；原冻结目录和业务文件不动。
