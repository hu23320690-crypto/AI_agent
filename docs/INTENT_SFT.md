# 意图解析：用可验证合成数据做 SFT

> 一句话：把"qwen3:4b + 1859 token 长提示词"的结构化意图抽取，换成"小模型 + 55 token 短提示词 + LoRA 微调"。训练数据全部由程序合成，每条标签都经过线上同一套校验管线复核。在从未打开过的 test 上，与原方案对比准确率、危险错误和延迟。

[预注册计划](plans/INTENT_SFT_PLAN.md) · [开发日志](INTENT_SFT_DEV_LOG.md) · 代码 [`training/intent_sft/`](../training/intent_sft/)

## 1. 任务

用户的报告请求（如"2025 年三月只列滤网还剩几天和覆盖比例，顺便问下 HEPA 能水洗吗？"）要被解析成 `IntentProposal` JSON，包括字段映射与未知字段、范围、目标月与锚点、比较基准、排除项、知识子问。之后由 V1–V10 校验与规则合并。评分按冻结的九槽合同，**全部槽位都正确才算对**，并把错误分为危险 / 范围错误 / 安全失败 / 其他四级。

难点在于：同义改写与限定词（"墙角覆盖率"不是"覆盖率"）、相对月份的锚点（上一轮目标 / 本轮查询月 / 今天 / 未知事件）、比较中目标与基准的角色、否定与更正、多轮指代。

## 2. 方法

### 2.1 结构先行的合成数据

```
采样结构化意图 ──► 模板渲染成中文原话 ──► 标签 = 结构本身（不来自任何模型）
        │                                   │
        └──── 真实 resolve 管线（hybrid + llm_only）复核：九槽必须与金标准一致，
              原文锚定检查：每个 mention / 月份 / 知识子问都必须逐字出现在原文里
```

- 9 个题型，对应 SCORING 合同的各类现象；8000 条，构造阶段跳过率约 4%。
- 25% 使用**虚构目录**（"星辉率""晶片寿命"等）和 2030 年代的月份，迫使模型读取输入里的 `field_catalog`，而不是背下 37 个演示字段。
- 字段改写词表：gemma4:12b 为每个字段提出 12 个候选，**人工逐条筛选**。凡是可能指向另一字段的（例如泛泛的"滤网"说法）、带限定词的、与 dev 雷同的，一律删除。
- 训练样本的模型输入由线上同一个函数 `build_messages()` 生成，并在 resolve 实际调用时捕获参数，保证训练和线上**逐字节同构**。

### 2.2 训练与部署

- Qwen3-0.6B / 1.7B / 4B，LLaMA-Factory LoRA（r16，all-linear，1 epoch，有效 batch 16）；4B 用 4bit QLoRA。
- 短提示词（4 行，不含规则和示例）。规则由数据"学进权重"，系统提示词从 1859 token 降到 55 token。
- 合并 → GGUF q8_0 → Ollama，接入方式是 `config/intent.yml` 中的 `model_name` / `prompt` / `schema_constrained` 三个开关，默认值保持原行为。

## 3. 结果

> 在封存 test 上，SFT 1.7B 的 hybrid 完全正确率为 **93%**，同日 qwen3:4b 长提示词基线为 83%；危险错误 **9 → 3**，解析 p95 **1.21 s → 0.81 s**。0.6B 为 90%，p95 0.46 s，**是唯一同时满足 S1–S3 的配置**。

### 3.1 test 主结果

test 共 100 题。每个配置在 llm_only 和 hybrid 两种模式下各重复 3 次，2026-10-31 同机、同代码一次跑完，共 10 组，都是登记批次。

| 配置 | 解码 | llm_only 完全正确 | hybrid 完全正确 | 最大危险错误 llm_only / hybrid | hybrid p50 / p95（s） |
| --- | --- | ---: | ---: | ---: | --- |
| qwen3:4b + 长提示词（同日基线） | schema | 78.0% | 83.0% | 16 / 9 | 1.040 / 1.210 |
| SFT 0.6B | 无约束 | 89.0% | 90.0% | 10 / 7 | **0.355 / 0.459** |
| SFT 1.7B | 无约束 | **94.0%** | **93.0%** | **5 / 3** | 0.643 / 0.811 |
| SFT 4B（QLoRA） | 无约束 | 93.0% | **93.0%** | **5 / 3** | 1.298 / 1.550 |
| SFT 1.7B（消融） | schema | 75.7%（最差 75.0%） | 78.0% | 14 / 8 | 0.902 / 1.042 |
| *P3 正式成绩（参照）* | *schema* | *79%* | *80%* | *15 / 10* | *—* |

- 除 1.7B + schema 的 llm_only 外，每组 3 次重复的完全正确数都相同（温度为 0）。因此重复只能反映系统层面的非确定性，不能当作抽样误差。
- 10 组都没有执行失败，没有回退，也没有被预算跳过。
- 同日基线的 hybrid 比 P3 正式成绩高 3 个点（83% 对 80%）。无论和哪一个比，结论方向都一样。
- 系统提示词从 1859 token 降到 55 token（Qwen3 分词器计数）。用户侧 JSON 两种方案相同。
- 原始数据：`evaluation/results/intent_sft_final_test_*`。表中数字由 `training/intent_sft/report.py` 从各组的 `summary.json` 汇总，未读取逐题结果。

### 3.2 预设判定（[计划第 8 节](plans/INTENT_SFT_PLAN.md#8-预设判定报告时逐项写是否)）

| 判定 | 0.6B | 1.7B | 4B |
| --- | --- | --- | --- |
| S1：hybrid 最差完全正确 ≥ 80% | 是（90%） | 是（93%） | 是（93%） |
| S2：最大危险错误 ≤ 10 | 是（7） | 是（3） | 是（3） |
| S3：p95 ≤ 同日基线的 50%（≤ 0.605 s） | **是**（0.459 s，38%） | **否**（0.811 s，67%） | **否**（1.550 s，128%） |
| S4：规模曲线 | 见 3.3 | | |

计划要求 S1–S3 由**同一个**模型满足，0.6B 做到了。准确率最高的 1.7B 达到了 S1 和 S2，但 p95 只降到基线的 67%，没有达到 S3 的 50% 门槛。

### 3.3 观察

- **规模曲线**：从 0.6B 到 1.7B，准确率 +3 点，危险错误 7 → 3。从 1.7B 到 4B，准确率不再提升，延迟翻倍（4B 导出为 q8_0，见第 5 节）。在这个任务上，1.7B 是准确率与成本的折中点；如果更看重延迟，0.6B 只差 3 个点。
- **规则学进了权重**：hybrid 下，基线每 100 题平均触发 31 次校验冲突（3 次合计 93 次，最多的是 `qualifier_dropped` 21 次、`mention_unanchored_kept` 12 次、`negated_field_selected` 12 次）。三个 SFT 模型每 100 题都只触发 4 次。也就是说，原来靠 V2–V10 事后纠正的规则，SFT 模型在生成时就已经遵守了。
- **校验层仍然有用**：从 llm_only 到 hybrid，SFT 的危险错误仍在下降（1.7B 5 → 3，0.6B 10 → 7）。所以应保留 hybrid，不能只用模型输出。
- **约束解码消融**：1.7B 开启 JSON Schema 约束后，hybrid 从 93% 降到 78%（-15 点），p50 反而从 0.64 s 涨到 0.90 s。`field_not_in_catalog` 冲突从 0 次增加到 81 次（每次运行 27 次），说明约束语法改变了切分，模型输出了目录外的字段名。dev 上是 -10 点，方向一致。
- **dev 与 test 差距不大**：1.7B 在 dev 上 95%、test 上 93%；4B 为 97.5% 和 93%；0.6B 为 87.5% 和 90%。合成数据学到的能力迁移到了由别人编写、本实验从未打开过的 test 上。

> 登记批次第一次启动时，批处理在调用评测之前就挂起了，没有产生任何结果。之后以相同配置重新启动，过程见[计划修订 2](plans/INTENT_SFT_PLAN.md#修订-22026-10-31test-无任何结果产生)。

## 4. 排查出的三个坑

| 现象 | 根因 | 处理 |
| --- | --- | --- |
| dev 上目标月与基准月被调换 | 生成器伪相关：比较类样本的 `current_lookup_month` 总等于目标月 | 两个查询月随机排序；其他题型也有 20% 额外查询了别的月份 |
| 换了一版数据，同尺寸模型延迟反而 +70% | Ollama 官方 Qwen3 模板给助手回合插入空思考块，训练格式里没有；`think:false` 还会再改写提示（+4 token） | 写与训练格式逐字一致的模板，专用模型不发送 `think`；用分词器计数核对（143 = 143） |
| 开着 JSON Schema 约束解码时，微调模型准确率下降约 10 个点 | 约束语法会改变分词切分，模型被迫偏离训练时的 token 序列 | 微调模型关闭约束；V1 严格解析与规则回退不变；test 中保留"开约束"一组作消融对照 |

## 5. 局限

- 单一领域、单份演示 CSV；test 只有 100 题，每个配置只有一个批次（3 次重复）。
- 生成器作者读过 dev 的题型和部分题面；dev 用于选择解码方式，dev 数字偏乐观。test 由先前的助手团队编写，本实验期间从未打开。
- 4B 的延迟对比不公平：SFT 导出为 q8_0，qwen3:4b 官方为 Q4_K_M。
- 合成数据的语义正确性依赖模板构造；resolve 复核能抓出与原文、校验规则不一致的标签，但抓不出"标签和金标准一起错"。

## 6. 复现

```powershell
# 1. 生成数据（应用环境）
.\.venv\Scripts\python.exe -B -m training.intent_sft.generate --count 8000 --seed 20261031 --out <work>/intent_sft/data_r2
# 2. 训练 + 合并 + GGUF + Ollama（训练环境：LLaMA-Factory + llama.cpp）
<train-python> -B -m training.intent_sft.train --work <work> --size 1.7B --data intent_sft/data_r2 --tag r2
# 3. 评测（dev；test 需 --p3-approved）
.\.venv\Scripts\python.exe -B -m training.intent_sft.evaluate --model intent-sft-1.7b-r2 --split dev --no-schema
# 4. 汇总（只读各组 summary.json）
.\.venv\Scripts\python.exe -B -m training.intent_sft.report (Get-ChildItem evaluation/results -Directory -Filter 'intent_sft_final_test_*').FullName --slots
```

在应用中启用 SFT 解析器。默认仍是 `rule` 模式和共享的 qwen3:4b，以下环境变量只对当前终端生效：

```powershell
$env:AGENT_INTENT_MODE = 'hybrid'
$env:AGENT_INTENT_MODEL = 'intent-sft-1.7b-r2'
$env:AGENT_INTENT_PROMPT = 'prompts/intent_parser_sft.txt'
$env:AGENT_INTENT_SCHEMA = '0'
```
