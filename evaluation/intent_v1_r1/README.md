# intent_v1_r1 · P0修订第二步草稿

已完成第一步4道dev改写，以及第二步4道test替换/4条note。仍为dev40/test100，原intent_v1和intent_agent_v1完整保留。Agent修订目录未修改，第三步待明确指令。

- [第二步8项复核清单](STEP2_REVIEW.md)：仅列IT052/053/054/067新题与IT013/047/085/088新增note。
- [组件静态核对](STEP2_STATIC_CHECKS.md)及[机器记录](step2_static_checks.json)。
- [第二步dev/test相似度](STEP2_SIMILARITY.md)及[全部4000配对](step2_similarity_report.json)。
- [第一步dev改动清单](DEV_CHANGES_REVIEW.md)与[第一步相似度历史](SIMILARITY.md)保持原样。

SCORING.md继承原合同，未改变未知字段接受集合或判分。4替换题都具有current查询，月份无法确定来自题面事件日期缺失或否定无替代；不是缺查询的V8防御场景。IT067保留确定目标，只令未知基准null。

当前为待作者复核草稿，未冻结、未批准P1、未运行任何模型/意图解析器，不存在评测成绩。作者确认后才按审核流程冻结；词面相似度不是语义独立证明。
