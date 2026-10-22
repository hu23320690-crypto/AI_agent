# qwen3:4b 与 gemma4:12b 同机同代码对照

日期：2026-10-22。分支 `eval/gemma4-12b-comparison`。只替换聊天模型，检索、提示、配置、预算和代码对两个模型完全相同。评分结果与结论见 [对照报告](../../docs/MODEL_COMPARISON_GEMMA4.md)。

## 运行环境

| 项目 | 值 |
| --- | --- |
| 硬件 | Intel Core Ultra 9 290HX Plus、32 GB DDR5-5600、RTX 5070 Laptop 12 GB |
| 软件 | Windows 11 10.0.26300、Ollama 0.40.8、Python 3.12.10，依赖按 requirements-lock.txt |
| 聊天模型 | qwen3:4b `359d7dd4…`（与历史 S5/G5 运行 digest 相同）；gemma4:12b `6114515d…`（Q4_K_M，11.9B） |
| 嵌入模型 | qwen3-embedding:4b `df5bd2e3…`（与历史运行相同），索引 326 块 |
| 共同参数 | num_ctx 8192、reasoning true、temperature 0、context.yml/runtime.yml 原值、intent_mode rule、legacy + react |

## 为公平所做的唯一代码改动：gemma4 离线 token 计数

上下文预算原先只对 qwen3:4b 精确计数，其他模型退回 UTF-8 字节计数。同一批 201,375 字节的项目文本，qwen3 为 54,079 token，gemma4 为 57,735 token；字节计数会把预算估高约 3.5 倍，导致 gemma4 的请求大量被误判超限。

因此在 `model/token_count.py` 中加入按模型固定的计数器（`PINNED_MODELS`），从本机 Ollama 的 GGUF 元数据离线重建 gemma4 BPE，并像 Qwen 一样固定 model digest 与模板 hash。Qwen 的缓存文件、清单和计数方法保持不变。

| 检查 | 结果 |
| --- | --- |
| [gemma4 计数 vs Ollama prompt_eval_count](tokenizer_check_gemma4_12b.json) | 79/79 完全一致，57,735 = 57,735 |
| [qwen3 计数 vs Ollama prompt_eval_count](tokenizer_check_qwen3_4b.json) | 79/79 完全一致，54,079 = 54,079 |
| pytest | 2188 passed、3 skipped（Windows 符号链接权限，与历史相同） |
| 在线 doctor | 两个模型均 ok |

剩余差异：同样 8192 窗口下，gemma4 每段文本平均多用约 7% token，可容纳的上下文略少。这是模型分词器的真实差异，未做补偿。

## 运行

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_model_comparison.ps1
```

默认依次用 qwen3:4b、gemma4:12b 跑 generalization_v1 与 holdout_v2（各 40 题：28 知识、6 资料不足、6 Agent），每个组合写入新目录 `evaluation/results/model_cmp_<日期>_<题集>_<模型>`，并生成 report/export。中断后用同一 `-Tag` 重跑即可续跑。脚本只改 `config/rag.yml` 的 chat_model_name，结束时恢复原文件。

2026-10-22 的 3 题冒烟（V2K01、V2N01、V2A02）两模型均 3/3 执行完成；gemma4 的 34 次请求全部使用 `local_gemma4_bpe` 计数且 0 次预算超限。冒烟目录在临时文件夹，不计成绩。

## 对照基准与解读限制

- 当前代码上已有的 qwen3:4b 成绩只有 G5 Agent 子集（legacy + react）：base 11/12、generalization_v1 5/6、holdout_v2 6/6，见 [S5 报告](../../docs/SERVICE_AGENT_S5_REPORT.md)。两套 40 题的知识题最近一次结果来自更早的代码，因此本次在同机重跑 qwen3:4b 作为基准。
- `evaluation.report` 不自动评分。两模型的答案都要按各题集 SCORING.md 另做语义复核（reviews.jsonl），复核时应隐藏模型标签。
- 两个题集都已用于此前的修复，属于已见题回归，不能当作未见泛化成绩。
- 12 GB 显存放不下 gemma4（约 9.2 GB）与嵌入模型同时常驻，Agent 轮次中可能出现模型换入换出；时延对比对 gemma4 偏不利，以答案质量为主。
- 每个组合只运行一次，不声明统计显著性；超时、报错和截断保留在计划分母中，按未通过计。
