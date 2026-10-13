# intent_v1_r1 · P0修订第二步草稿

dev第一步4题已获作者复核；本版仅完成组件第二步，dev40/test100分母不变，等待作者复核后才能冻结。

- STEP2_REVIEW.md：4道替换题完整上下文/gold、4条note与IT085等价规则。
- step2_checks.json：全部静态核对、CSV动态目录、4000对相似度及双视图top3、逐字节保护证据与限制。
- STEP2_STATIC_CHECKS.md / step2_static_checks.json：静态结果；STEP2_SIMILARITY.md / step2_similarity_report.json：相似度视图。
- DEV_CHANGES_REVIEW.md / SIMILARITY.md / step1_checks.json：保留第一步历史原样。

替换IT052/053/054/067；4题均有current查询，月份未知由题面造成。IT067确定目标2025-04，基准null，compare=true。IT013/047/085/088只补充说明；IT085额外预列unknown_aliases=["每日耗水量"]，gold不改，已知字段仍精确匹配。

任务开始时已存在第二步草稿，按要求在f14b964原样提交后再完成本版。CSV全部10用户均在dev出现，采用全新用户+字段组合、dev零提及字段及新句式。其余96题的题面、上下文、gold与字段全序逐字节一致；获授权note/alias改动单列，整行一致数相对执行基线95、相对第一步原test92。

原intent_v1、intent_agent_v1及intent_agent_v1_r1不动；未处理第三步。未运行解析器或模型，未生成freeze_manifest，不批准P1。
