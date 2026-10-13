# intent_v1 · P0冻结候选

固定字节与SHA256，等待项目作者审核。gold_review_status=pending_author_review，evaluation_eligible=false。不要进入P1或运行模型；本次没有任何评测成绩。

组件140条：dev40 + test100。类别test配额20/10/8/16/14/12/8/8/4；dev用最大余数法分配为8/4/3/6/6/5/3/3/2。

- [评分合同](SCORING.md)：先验固定语义、分母、错误分类及正式运行次数。
- [完整金标准审核清单](TEST_GOLD_REVIEW.md)：本次交付作者审核；不是开发示例。包含IT001–IT100全部题面、上下文与九槽gold及字段全序。
- [dataset_manifest.json](dataset_manifest.json)：题集、原始资料、编制合同、基线实现身份及文件SHA256。
- [construction_audit.json](construction_audit.json)：纯静态核对，无模型或基线解析调用。
- [freeze_manifest.json](freeze_manifest.json)：含dataset_manifest在内的文件清单，SHA256非签名，逻辑封存不是文件ACL。

P1/P2只读取dev.jsonl；不能打开cases.jsonl、test.jsonl或本审核清单。cases.jsonl保留计划要求的完整140行；两个split副本逐字一致。 作者审核后记录独立批准凭据才可进入下一阶段；不原位改写本次候选和金标。如果作者发现歧义/错误，另建修订版，保留本版和原分母。P3每次运行另建结果目录并按计划封存，不能把本题集manifest冒充推理结果的seal。

P0按作者请求编题和静态审核；封存后测试内容不用于实现、few-shot、单元测试或提示调参。助手参与编题，不是外部专家盲评；与dev共享演示资料和任务类别，不证明跨域泛化。
