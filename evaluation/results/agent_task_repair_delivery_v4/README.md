# Agent任务修复回归

冻结40题：28知识、6资料不足、6Agent，计划45次真实用户提问。两个长历史各64对合成历史不计真实交互。

40/40执行、40/40复核。知识严格23/28、不足5/6、Agent全轮6/6。6案共11次真实Agent提问，工具选择6/6。

本目录为已见题修复回归，不是独立新题验证。主助手逐项复核，非盲评，尚无独立真人/领域专家审核；未通过项全部保留。

- results.jsonl：原始请求、响应、来源输入、工具输出与trace。rag_answers保存程序路径实际资料输入，不冒充LLM输入。
- reviews.jsonl：内容/忠实度/任务评分，绑定对应原始结果SHA256。
- summary.json / audit.md：汇总与逐题阅读入口。
- manifest.json / snapshot：代码、题集、资料、模型及配置身份。分块与检索未改变；外部单案例墙钟上限300秒（修复前240秒），本轮全部实际案例小于240秒。共享Runtime预算仍按生产配置执行。
- snapshot/config/tokenizers：按冻结descriptor的SHA256另补存原tokenizer缓存，未修改模型、缓存或业务代码。
- seal.json：完整离线SHA256归档清单；不是签名或答案正确证明。

修复前结果位于holdout_v2_current。评测与评分标准分别见evaluation/README.md、SEMANTIC_REVIEW_V2.md，修复实现见docs/AGENT_TASK_REPAIR.md。
