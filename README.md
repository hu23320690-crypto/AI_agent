# 扫地机器人智能客服 Agent

[![CI](https://github.com/hu23320690-crypto/AI_agent/actions/workflows/ci.yml/badge.svg)](https://github.com/hu23320690-crypto/AI_agent/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.12-3776AB)
![LangGraph](https://img.shields.io/badge/LangChain%20%2F%20LangGraph-1.x-1C3C3C)
![Ollama](https://img.shields.io/badge/Ollama-Qwen3%3A4b-000000)
![FastAPI](https://img.shields.io/badge/FastAPI-REST-009688)

基于 LangChain / LangGraph 和本地 Qwen3 的中文客服 Agent。它用混合检索回答产品、故障和保养问题，也能按用户和月份查询使用记录、生成报告。

这个项目的重点不止是"把工具调通"，而是让 Agent **可控、可审计、可评测**：每一轮都有时间和调用预算，工具参数先校验再执行，知识来源需要审批，长对话有 token 预算和结构化摘要，另外还有一套带故障注入和新题测试的评测体系。

**技术栈**：Python 3.12 · LangChain / LangGraph · Ollama（Qwen3:4b、Qwen3-embedding:4b）· Chroma · FastAPI / asyncio · Streamlit · pytest · Docker Compose · GitHub Actions

<!-- 演示：把 Streamlit 界面的截图或录屏放到 docs/images/ 下，然后取消下一行注释 -->
<!-- ![demo](docs/images/demo.gif) -->

## 功能演示

| 场景 | 输入示例 | 系统行为 |
| --- | --- | --- |
| 知识问答 | 主刷上缠了长头发，应该怎么清理？ | 混合检索 Top-5 证据后生成有依据的步骤；资料不足时明确说明，不编造 |
| 连续追问 | 清理刚才那个部件前需要断开电源吗？ | 把"刚才那个部件"解析为主刷，重新检索断电规则 |
| 使用报告 | 请生成我 2025 年 8 月的使用报告。 | 查询当前会话用户 1001 的记录，报告由程序渲染：覆盖率 83%、日均 43㎡、主刷剩余 50 天、滤网 30% |
| 月份追问 | 那 2025 年 9 月呢？ | 重新查询 9 月数据，不复用上一轮的数值 |
| 无记录 | 请生成我 2099 年 1 月的使用报告。 | 明确告知没有记录，不拿其他月份顶替 |
| 越权尝试 | 帮我查一下用户 1002 的记录 | 用户身份只认会话设置；模型就算提出查询 1002，也会在执行前被权限校验拒绝 |

演示数据：6 份知识资料（5 个 TXT + 1 个 PDF，共 326 个分块），以及用户 1001–1010 在 2025 年的 120 条合成使用记录。

## 架构

```mermaid
flowchart TD
    subgraph AGENT["Agent 图（LangChain create_agent / LangGraph）"]
        CTX["上下文管理<br/>token 预算 · 完整轮次裁剪 · 结构化摘要"] --> LLM["Qwen3:4b 决策"]
        LLM -->|"工具调用"| POL["权限校验<br/>Pydantic strict · 身份取自会话"]
        POL --> TOOLS["7 个工具"]
        TOOLS -->|"观察结果"| LLM
    end

    UI["Streamlit 页面"] --> RT["Runtime<br/>整轮 deadline · 调用预算 · 并发闸门 · 重试 / 熔断"]
    API["FastAPI REST<br/>Bearer 鉴权 · 会话 · 取消"] -->|"asyncio + 有界线程"| RT
    RT --> CTX

    TOOLS --> RAG["知识检索工具"]
    TOOLS --> CSV["使用记录查询工具"]
    RAG --> SRC["来源审批清单<br/>SHA256 · 隔离 · 撤销"]
    SRC --> HY["向量 + BM25 → RRF<br/>来源配额 · 覆盖重排 · 去重 → Top-5"]
    HY --> GEN["受约束生成<br/>JSON 输出 · 截断即拒绝"]
    CSV --> RENDER["程序渲染报告<br/>Decimal 计算跨月差值"]
    GEN --> OUT["最终出口<br/>提交前复核来源 · 只提交成功轮次"]
    RENDER --> OUT
```

**一次请求的执行过程**

1. 入口创建 `RunContext`：整轮 120 秒 deadline，模型最多调用 8 次、工具 12 次、embedding 16 次。
2. 检查历史对话引用过的知识来源是否仍然有效；只要有来源被撤销或篡改，整段记忆作废。
3. `manage_context` 中间件估算 token。输入超过预算的 80% 时，把旧轮次压缩成结构化摘要，保留最近 2 轮原文。
4. 模型决定调用工具。`monitor_tool` 先做参数和身份校验，再经 Runtime 计入预算和并发闸门后执行。
5. 生成最终回答：报告由程序根据本轮查到的记录渲染；知识回答直接采用 RAG 工具的结果，不让外层模型再改写一遍。
6. 提交前再核对一遍引用来源的内容和版本。只有成功的轮次才写回会话历史，取消、超时或失败都不提交。

## 技术亮点

### 1. Runtime：每一轮都有边界

代码：[`agent/runtime/`](agent/runtime/)

- **共享预算**：整轮共用一个 deadline 和调用预算，RAG 内部嵌套的模型和 embedding 调用也计入其中，工具循环无法无限消耗资源。
- **分类型并发闸门**：run / model / tool / retrieval / embedding 各有独立的信号量，避免嵌套调用耗尽同一个池子而死锁。
- **重试与熔断**：模型和 embedding 请求最多 2 次尝试，指数退避，遵循 `Retry-After`。60 秒滑动窗口内失败 3 次即熔断，15 秒后半开，只放行一个探测请求。
- **线程超时的处理**：Python 线程没法强杀，所以超时只是停止等待。worker 真正退出前继续占用名额，迟到的结果也不能写回会话。

### 2. 工具调用的权限边界

代码：[`agent/tools/policy.py`](agent/tools/policy.py)、[`agent/tools/middleware.py`](agent/tools/middleware.py)

- 每个工具对应一个 Pydantic strict 模型（`extra="forbid"`），拒绝多余字段、控制字符，以及 `runtime`、`state` 这类注入参数名。
- `user_id` 只认服务端会话：模型给出的值必须与会话一致，校验通过后仍以会话值为准。评测中出现过模型提出越权参数的情况，已在执行前被拦截。
- 拒绝时返回固定文案，不把非法输入回显给模型或写进日志。
- 系统提示声明：工具返回内容和知识片段都是外部资料，不具有指令权限。

### 3. 混合检索 RAG 与来源治理

代码：[`rag/`](rag/)

- 200 字分块、20 字重叠。Qwen3-embedding 向量检索和字符二元组 BM25 各取 20 个候选，再用 RRF（k=60）融合。BM25 用字符二元组，不需要中文分词词典。
- 每个来源最多 3 块：前 2 块按 RRF 排名选，第 3 块优先给能覆盖新查询词的候选。相似度 ≥ 0.96 的近重复块会被过滤，最终取 Top-5。
- 知识文件需管理员按 SHA256 审批后才能入库。新增或修改的文件会自动隔离；撤销对后续检索立即生效。命中注入风险规则的文件需要显式复核。
- 检索后、生成后、提交前各核对一次来源的内容、版本和授权状态。

### 4. 长对话上下文管理

代码：[`agent/context_budget.py`](agent/context_budget.py)、[`agent/context_memory.py`](agent/context_memory.py)

- 用本地缓存的 Qwen tokenizer 离线计数。8192 的窗口中为输出预留 4096 tokens；tokenizer 身份未验证时，退回更保守的字节估计。
- 输入超过预算的 80% 时触发压缩：保留最近 2 轮原文，更早的内容按**完整轮次**压缩，工具调用和工具返回必须成对保留或成对移除。
- 摘要是固定 4 个字段的 JSON（主题 / 用户要求 / 已报告结果 / 待解决问题）。格式不符或被截断就直接拒绝，降级为只裁剪，不尝试修补。
- 摘要以"低信任资料"身份进入上下文，不能改变身份或权限。程序另外保留有长度上限的用户原话引用，避免压缩后丢掉最初的目标。
- 实测：注入 64 轮合成历史后，首次请求的消息数从 129 条压缩到 6 条。

### 5. 评测体系与 Harness

代码：[`evaluation/`](evaluation/)

- **题集**：开发集 60 题（40 道知识题、8 道资料不足题、12 个 Agent 多轮任务），外加两套在推理前冻结的 40 题新题集。
- **分开统计**：检索命中、工具调用正确、最终答案正确各自计分。工具调对了、但用户最终收到的回答是错的，按失败计。
- **故障注入（7 类）**：模型阻塞、工具阻塞、连续失败熔断、半开恢复、无限工具循环、取消后迟到、名额占满。
- **安全样本（23 条）**：资料投毒、prompt 注入 canary、工具结果诱导越权、重复资料挤占，以及对合法资料的误拦截。
- **可复现**：每次运行都冻结代码、配置、模型 digest 和题集快照，结果绑定 SHA256；失败和退步全部保留。

### 6. 服务化与工程化

代码：[`api/`](api/)、[`Dockerfile`](Dockerfile)、[`compose.yaml`](compose.yaml)、[`.github/workflows/ci.yml`](.github/workflows/ci.yml)

- FastAPI 提供 Bearer 鉴权，支持会话的创建、提问、取消和删除；限制请求体长度；`/healthz` 检查进程存活，`/readyz` 检查模型、索引和 tokenizer 是否就绪。
- asyncio 负责等待和断连检测，同步的 Agent 调用放在有上限的线程中执行；同一会话互斥，总并发和会话 TTL 都有上限。
- 非 root 的 Docker 镜像，Compose 编排 Ollama、初始化和持久卷。GitHub Actions 在 Windows 和 Linux 上运行 pytest，并做容器存活检查。
- 669 项离线测试通过：模型推理用脚本替代，LangGraph 图、Chroma 和 Streamlit 都是真实组件。

### 7. LLM 意图解析 + 规则校验

设计与完整评测：[docs/LLM_INTENT.md](docs/LLM_INTENT.md)

- LLM 按 JSON Schema 提议字段、月份、范围和知识子问，报告数值继续由程序从实际查询结果渲染。
- V1–V10 只校验可证伪的结构、目录、日期、限定和排除冲突，保留未知项及可见拒答。
- 调用、结构或预算失败时回退原正则解析；意图提议不授予用户身份或工具权限。
- 默认保持 `rule`，可通过 `AGENT_INTENT_MODE=hybrid` 主动开启；消融与失败案例见上方设计文档。

## 设计取舍：问题与做法

| 问题 | 做法 |
| --- | --- |
| 模型写报告时，把"剩余寿命"改写成记录里没有的进度和日期 | 报告中的数字一律由程序根据本轮查询结果渲染，模型只负责决定查什么 |
| RAG 工具已经回答"资料不足"，外层 Agent 却补出了品牌名和客服电话 | 知识类回答直接采用本轮 RAG 工具的结果，不再让外层模型二次改写 |
| 断电规则排在同一来源的第 4 块，被"每个来源最多 3 块"的配额挤掉 | 第 3 个配额位优先给覆盖新查询词的候选。另一种全局重排方案让 Top-5 命中从 38 降到 33，没有上线 |
| 分块越大，排序反而越差 | 对比 200 / 400 / 600 字分块后保留 200 字，改用向量 + BM25 融合（见下方检索对比） |
| 本地 Qwen 模板即使关闭思考仍会输出思考内容，占用生成额度，可能导致回答被截断 | RAG 生成改用只含 `answer` 字段的 JSON schema 约束；被截断的输出直接拒绝，不写入历史 |
| 线程超时后结果迟到，可能覆盖用户已经清空的会话 | 取消、清空与提交在同一把锁下串行执行；提交前检查本轮状态，迟到结果直接丢弃 |
| 正则覆盖不了新说法 | LLM 提议、规则校验、失败回退 |
| 只用 LLM 危险错误反而更多 | 保留可证伪的校验规则 |

## 评测结果

### 检索：分块大小与召回方式

开发集 40 道知识题，统计标注证据是否出现在检索结果中。

| 分块 / 检索方式 | Hit@1 | Hit@3 | Hit@5 |
| --- | ---: | ---: | ---: |
| 200 字 / 向量 | 19/40 | 31/40 | 33/40 |
| 400 字 / 向量 | 15/40 | 30/40 | 34/40 |
| 600 字 / 向量 | 13/40 | 21/40 | 26/40 |
| 200 字 / BM25 | 13/40 | 26/40 | 32/40 |
| **200 字 / 向量 + BM25（RRF）** | **26/40** | **33/40** | **38/40** |

400 字分块的 Hit@5 只多 1 题，Hit@1 却从 19 降到 15，送进模型的上下文还翻了一倍；混合检索的 Hit@1 从 19 提升到 26。

### 端到端问答

"严格通过"指要点完整，而且没有资料不支持的内容。Agent 任务以用户最终收到的回答为准。

| 题集 | 知识题 | 资料不足（正确拒答） | Agent 多轮任务 |
| --- | ---: | ---: | ---: |
| 开发集（2026-10-06 版本） | 33/40 | 8/8 | 10/12 |
| 新题集 generalization_v1：首次测试 | 18/28 | 5/6 | 1/6 |
| 同一新题集：针对失败修复后 | 20/28 | 6/6 | 4/6 |
| 新题集 holdout_v2：修复后 | 22/28 | 6/6 | 6/6 |

- 首次测试中 Agent 任务只通过 1/6。多数失败是工具查对了，但最终交付出错，比如字段同义词没有对上、目标月份和对比月份混淆、"报告 + 知识判断"的组合任务漏了一部分。
- 修复后的两行属于"已见题回归"：题目已经用来定位问题，不能代表对未见问题的泛化能力。下一步需要另外冻结一套新题来检验。
- 样本量小，每次只跑一遍；语义判分由 AI 助手辅助完成，未经独立人工盲评。逐题失败分析见 [AGENT_GENERALIZATION_REPAIR.md](docs/AGENT_GENERALIZATION_REPAIR.md)。

### 意图解析改造（未见题）

P3 冻结版本的组件正确率取均值，与最差一次相同；危险错误取最大一次。Agent 按全部真实轮次完成判任务通过。来源：[evaluation/INTENT_P3_A.md](evaluation/INTENT_P3_A.md)、[evaluation/INTENT_P3_B.md](evaluation/INTENT_P3_B.md)。

| 模式 / 任务 | 组件正确率 | 危险错误 | Agent 全轮通过 |
| --- | ---: | ---: | ---: |
| rule | 16.0% | 13/100 | — |
| llm_only | 79.0% | 15/100 | — |
| hybrid | 80.0% | 10/100 | — |
| Agent test（rule → hybrid） | — | — | 1/12 → 4/12 |

默认仍为 `rule`：G5 的已见报告任务回归出现退步，未满足全部准入条件；`hybrid` 保留为可选开关，判定见 [evaluation/INTENT_P3_REPORT.md](evaluation/INTENT_P3_REPORT.md)。

### 鲁棒性与安全

| 测试项 | 结果 |
| --- | --- |
| 故障注入：阻塞、熔断、半开恢复、工具死循环、取消后迟到、名额占满 | 7/7 断言通过 |
| 未批准、被篡改、已撤销或命中风险规则的资料 | 6/6 未进入模型 |
| 已进入模型上下文的注入指令（canary） | 0/4 被执行 |
| 检索片段或工具返回诱导跨用户查询 | 越权执行 0/4 |
| 合法安全培训资料的首次审核 | 误拦截 2/6 |
| 已获批准的错误事实 | 2/2 被采纳（未解决） |
| 工具返回中的恶意文本 | 2/2 原样出现在回答中（未解决） |

以上是 23 条合成样本单次运行的结果，不代表能全面防御投毒或注入。详见 [RUNTIME_STAGE4_VERIFICATION.md](docs/RUNTIME_STAGE4_VERIFICATION.md)。

## 快速开始

需要 Python 3.12 和 [Ollama](https://docs.ollama.com/quickstart)。以下命令已在 Windows 11 上验证；Linux 下用 `python3.12 -m venv .venv` 创建环境，并把 `.\.venv\Scripts\python.exe` 换成 `.venv/bin/python`。

```powershell
# 1. 安装锁定版本的依赖
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt

# 2. 准备本地模型
ollama pull qwen3:4b
ollama pull qwen3-embedding:4b

# 3. 环境自检 → 建立知识索引 → 启动页面（http://127.0.0.1:8501）
.\.venv\Scripts\python.exe -B scripts/manage.py doctor
.\.venv\Scripts\python.exe -B scripts/manage.py index
.\.venv\Scripts\python.exe -B scripts/manage.py serve
```

页面侧栏默认的演示用户是 1001。

**可选 hybrid 模式**

默认意图模式为 `rule`。要开启 `hybrid`，在启动页面或 API 前设置环境变量，并重启已有服务进程：

```powershell
$env:AGENT_INTENT_MODE = 'hybrid'
.\.venv\Scripts\python.exe -B scripts/manage.py serve
# API 服务也使用此环境变量，再执行 scripts/manage.py api。
```

Linux shell 使用 `export AGENT_INTENT_MODE=hybrid`。设计与回退行为见 [docs/LLM_INTENT.md](docs/LLM_INTENT.md)。

**REST API**

```powershell
$env:API_KEY = (& .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(32))")
.\.venv\Scripts\python.exe -B scripts/manage.py api    # 交互文档：http://127.0.0.1:8000/docs
```

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/v1/sessions` | 创建会话，固定 `user_id` |
| `POST` | `/v1/sessions/{id}/messages` | 提问，返回回答和本轮运行信息 |
| `POST` | `/v1/sessions/{id}/cancel` | 取消正在运行的一轮 |
| `DELETE` | `/v1/sessions/{id}` | 删除会话 |
| `GET` | `/healthz`、`/readyz` | 存活检查、就绪检查 |

Docker 部署见 [DEPLOYMENT.md](docs/DEPLOYMENT.md)，接口细节和错误码见 [API.md](docs/API.md)。

**测试与评测**

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q                         # 离线回归，不需要 Ollama
.\.venv\Scripts\python.exe -B scripts/manage.py demo               # 6 个真实 Agent 案例
.\.venv\Scripts\python.exe -B scripts/manage.py harness --run evaluation/results/my_harness_v1   # 故障 + 安全 Harness
```

<details>
<summary>更多命令：tokenizer 校验、知识库更新、源码打包</summary>

`doctor` 会检查 Python、依赖、配置、知识来源、模型和 tokenizer 缓存，不下载也不重建索引；`doctor --offline` 不访问 Ollama。

仓库自带离线 tokenizer 缓存。如果本机模型或模板与缓存不一致，先确认模型版本，再重新导出：

```powershell
.\.venv\Scripts\python.exe -B -m model.token_count export
.\.venv\Scripts\python.exe -B -m model.token_count verify
.\.venv\Scripts\python.exe -B scripts/manage.py doctor
```

新增或修改知识资料（UTF-8 TXT 或可提取文字的 PDF）时，需要先审核再入库：

```powershell
.\.venv\Scripts\python.exe -B scripts/manage.py knowledge scan
.\.venv\Scripts\python.exe -B scripts/manage.py knowledge status
.\.venv\Scripts\python.exe -B scripts/manage.py knowledge approve "新资料.txt" --sha256 "<scan 输出的 SHA256>" --reason "审核依据"
.\.venv\Scripts\python.exe -B scripts/manage.py knowledge sync
```

审批只表示允许使用该文件，不保证内容正确。`--allow-risk` 用于明确复核过的合法引用。撤销用 `knowledge revoke <source_id> --reason "撤销依据"`，然后同步索引并重启页面。详见 [RUNTIME_STAGE3.md](docs/RUNTIME_STAGE3.md)。

打包源码（排除虚拟环境、向量库、模型、日志和密钥，附逐文件 SHA256 清单）：

```powershell
.\.venv\Scripts\python.exe -B scripts/package_project.py --output dist/AI_agent_source.zip
```

</details>

## 项目结构

```text
├── app.py                    # Streamlit 页面
├── api/                      # FastAPI：鉴权、会话生命周期、异步等待、就绪检查
├── agent/
│   ├── react_agent.py        # Agent 图、最终出口与成功提交
│   ├── tools/                # 7 个工具、权限校验、中间件
│   ├── runtime/              # deadline、预算、并发闸门、重试与熔断
│   ├── context_budget.py     # 请求级 token 预算
│   └── context_memory.py     # 完整轮次裁剪与结构化摘要
├── rag/                      # 分块索引、混合检索、来源治理、受约束生成
├── model/                    # 模型工厂、离线 tokenizer 计数
├── utils/                    # 报告意图解析、报告渲染、CSV 读取
├── config/  prompts/         # 配置与提示词
├── data/                     # 演示知识资料与合成使用记录
├── evaluation/               # 题集、评测脚本、Harness 与结果
├── tests/                    # pytest 离线回归
├── scripts/manage.py         # doctor / index / serve / api / pytest / demo / harness / knowledge
└── docs/                     # 设计说明、验收记录、部署与 API 文档
```

## 已知限制

- **规模**：只在 6 份资料、326 个分块和 120 条合成记录上验证过，没有测过大规模语料和高并发。
- **身份**：API 使用共享的 Bearer 密钥，CSV 中的用户 ID 只是演示用的数据选择，不是多租户认证。
- **部署**：只支持单进程、单 worker；会话和熔断状态保存在内存中，重启后丢失。
- **回答质量**：报告意图解析基于规则，覆盖不了任意的自然语言表达；知识回答仍会出现漏步骤、混用部件条件的情况。
- **安全**：无法识别已获批准的错误资料；工具返回中的恶意文本可能经直出路径展示给用户。
- **功能**：天气接口未接入；回答是一次性返回的，不支持 token 级流式输出。

完整说明见 [LIMITATIONS.md](docs/LIMITATIONS.md)。

## 文档导航

| 想了解 | 文档 |
| --- | --- |
| Runtime 设计（预算、并发、重试、熔断） | [RUNTIME_HARNESS_PLAN.md](docs/RUNTIME_HARNESS_PLAN.md)、[RUNTIME_STAGE2.md](docs/RUNTIME_STAGE2.md)、[RUNTIME_STAGE4.md](docs/RUNTIME_STAGE4.md) |
| 知识来源治理 | [RUNTIME_STAGE3.md](docs/RUNTIME_STAGE3.md) |
| 上下文预算与摘要 | [CONTEXT_MANAGEMENT.md](docs/CONTEXT_MANAGEMENT.md)、[验收记录](docs/CONTEXT_MANAGEMENT_VERIFICATION.md) |
| 评测方法与命令 | [evaluation/README.md](evaluation/README.md)、[EXPERIMENTS.md](evaluation/EXPERIMENTS.md) |
| 新题测试与修复 | [GENERALIZATION_EVALUATION.md](docs/GENERALIZATION_EVALUATION.md)、[AGENT_GENERALIZATION_REPAIR.md](docs/AGENT_GENERALIZATION_REPAIR.md)、[EVALUATION_V2.md](docs/EVALUATION_V2.md) |
| 安装排查与环境复现 | [REPRODUCIBILITY.md](docs/REPRODUCIBILITY.md) |
| HTTP 接口 / Docker 部署 | [API.md](docs/API.md)、[DEPLOYMENT.md](docs/DEPLOYMENT.md) |
| 演示流程 | [DEMO.md](docs/DEMO.md) |
| 旧版 README（逐阶段验证记录） | [README_ARCHIVE.md](docs/README_ARCHIVE.md) |
