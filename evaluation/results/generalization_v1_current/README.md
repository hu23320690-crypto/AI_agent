# generalization_v1_current 首次运行归档

这是推理前冻结的新40案例在修复版本上的一次串行运行。知识严格通过 18/28、资料不足 5/6、Agent全轮 1/6；40/40已执行并复核，未知 0。本轮不调参、不改业务、不选择最佳重跑；题集今后若用于修复需改称已见回归集。

完整方法、结果和失败见 [新题报告](../../../docs/GENERALIZATION_EVALUATION.md)。[cases.jsonl](cases.jsonl)、[manifest.json](manifest.json)、[results.jsonl](results.jsonl)、[reviews.jsonl](reviews.jsonl)、[summary.md](summary.md)、[audit.md](audit.md) 保留原始证据，`snapshot/` 保存受测业务、评测器、来源、冻结题集身份、评分规则及构造审计。

runner 未自动复制的 tokenizer gzip 缓存已按冻结 descriptor SHA核验后补入快照，评分文本和构造审计亦按冻结manifest核验。运行后的报告补全不会修改原始输出或业务。完成后用 [seal脚本](../../../scripts/seal_evaluation_run.py) 首次生成 [seal.json](seal.json)，之后仅校验，不能覆盖；它不是防篡改签名。workers/logs保留本机并由仓库忽略。

Codex助手团队复核，非独立真人专家审核；只有同域演示小样本的一次测量，没有旧版同题对照，不能据此宣称跨域或生产能力。
