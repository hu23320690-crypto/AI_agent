# 扫地机器人智能客服：RAG + Agent

中文客服项目，通过 Streamlit 和 FastAPI REST 服务提供产品知识问答、连续追问和按用户/月度查询的使用报告。实现混合检索、工具调用、共享执行预算、超时与取消、重试与熔断、来源治理、故障与安全评测，以及长对话的上下文预算和结构化摘要。HTTP 层用 asyncio 管理会话与请求，将同步 Agent 调用交给有上限的线程执行；提供 Docker Compose 和 Linux 运行说明。

技术栈：Python 3.12、FastAPI / Uvicorn、asyncio、Streamlit、LangChain / LangGraph、Ollama、Chroma、字符 BM25、RRF、pytest、Docker Compose、Git / GitHub Actions。

## 当前完成情况

文档整理截至 **2026-10-07**。本轮评测于 2026-10-06 开始，2026-10-07 完成记录与辅助语义复核：当前版本重跑原 60 个案例与旧 12 道保留题，另将推理前冻结的新 40 题用于历史混合检索版与当前版同题对照。新题知识严格通过为 **24/28 → 21/28**，资料不足两版 **6/6**，Agent 全轮任务两版 **0/6**；当前版有 2 个生成截断案例，保持未知并留在原计划分母。方法、失败和逐题证据见 [本轮评测](docs/EVALUATION_V2.md)，题集见 [holdout_v2](evaluation/holdout_v2/README.md)。

**本轮本机离线验证**为 pytest 367 项通过、3 项 Windows 符号链接权限跳过、270 个子断言通过，耗时 42.49 秒；离线 doctor 146 项通过，`pip check` 无依赖冲突。证据见[本轮检查](artifacts/evaluation_v2/checks.json)、[pytest 输出](artifacts/evaluation_v2/pytest.log)和[离线 doctor](artifacts/evaluation_v2/doctor_offline.json)。对应提交的 Windows/Linux 与 Docker 结果见 [Actions](https://github.com/hu23320690-crypto/AI_agent/actions) / PR 检查，本机验证不替代 CI。

**2026-10-05 的 API 工程化检查**继续保留为历史验证：本机 320 项通过、1 项 Windows 权限跳过，188 项 unittest 子断言通过，新增 API 39 项通过；离线 doctor 146 项通过，`pip check` 无依赖冲突。Windows/Linux 各 321 项测试和非 root 镜像启动见 [历史 CI 第三次运行](https://github.com/hu23320690-crypto/AI_agent/actions/runs/37268280297)，容器检查不含模型下载或真实推理。证据见[工程化检查](artifacts/api_engineering_v1/checks.json)、[pytest 输出](artifacts/api_engineering_v1/pytest.log)与[CI 记录](artifacts/api_engineering_v1/ci_history.json)，这些计数不作为本轮结果。

历史 [HTTP 验收](artifacts/api_engineering_v1/live_smoke.json)中三次模型请求均执行完成，报告与主刷清理符合预期，断电追问语义未通过。HTTP 200、工具执行完成和答案正确分别判断；旧失败与阶段记录继续保留。

| 能力 | 当前实现 |
| --- | --- |
| HTTP 服务 | Bearer 密钥、会话创建/提问/取消/删除、参数与请求体校验、请求 ID、healthz / readyz、OpenAPI |
| 异步执行 | asyncio 等待与断连检测；有上限的同步任务执行、会话互斥、总并发和 TTL；超时后保留额度直至真实任务退出 |
| 运行与交付 | 单 worker API、非 root Docker 镜像、Compose 初始化与持久卷、Linux 运维说明、Windows/Linux pytest 和容器 CI 工作流 |
| RAG | 200 字分块、20 字重叠；向量与 BM25 各取 20 候选，RRF 融合；来源配额、查询词覆盖重排、近重复过滤，检索 Top-5 |
| Agent | 7 个工具，多轮历史与指代追问；按会话用户和月份查询 CSV，由程序渲染事实报告 |
| Runtime | 整轮共享 deadline 与模型/工具/embedding 调用预算；有限并发、取消、有限重试和进程内熔断 |
| 来源治理 | 新增/变化资料隔离、文件摘要审核、撤销与同步；检索、生成后和提交前复核来源 |
| 上下文管理 | 消息及工具结构预算、完整轮次裁剪、低信任结构化摘要、失败降级、截断输出拒绝提交 |
| Harness | 冻结输入与 worker 执行；7 类故障、23 条安全/正常样本；原始输出与语义复核分别保存 |

2026-10-01 的长历史、受控回归与安全验收保留在[上下文验收](docs/CONTEXT_MANAGEMENT_VERIFICATION.md)。合成历史不计真实模型交互；来源批准也不保证事实正确。当前边界见[已知限制](docs/LIMITATIONS.md)。

## 新环境安装

已验证：Windows 11、64 位 CPython **3.12.2**。代码使用 Python 3.12 语法，在项目目录打开 PowerShell：

~~~powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m pip check
~~~

不需要激活环境。没有 `py` 时，用已安装的 Python 3.12 可执行文件替代。`requirements.txt` 声明 **17 项运行时直接依赖**，`requirements-lock.txt` 固定 **125 项依赖及传递依赖**，含开发测试用 pytest。`requirements-dev.txt` 引用同一份锁；Windows/Linux 安装与回归结果应核对对应提交的 [Actions](https://github.com/hu23320690-crypto/AI_agent/actions) / PR 检查。

安装并启动 [Ollama](https://docs.ollama.com/quickstart)，准备模型：

~~~powershell
ollama pull qwen3:4b
ollama pull qwen3-embedding:4b
ollama list
~~~

服务未运行时，可在独立终端执行 `ollama serve`。下载需要网络；默认推理使用本机 Ollama。模型由 Ollama 管理，不在仓库中。模型标签可能更新，历史实验以记录的 digest 为准。

## 检查、初始化与启动

~~~powershell
.\.venv\Scripts\python.exe -B scripts/manage.py doctor
.\.venv\Scripts\python.exe -B scripts/manage.py index
.\.venv\Scripts\python.exe -B scripts/manage.py serve
~~~

打开 **http://127.0.0.1:8501**，Ctrl+C 结束。端口占用可用 `serve --port 8502`。

- `doctor` 检查 Python、依赖、配置、知识来源、模型和 tokenizer 缓存身份；不下载、不重建索引。失败返回退出码 1；成功不代表答案质量通过。
- `doctor --offline` 不访问 Ollama，仍校验本地 tokenizer 缓存。
- `index` 同步允许来源，内置 6 份演示资料（5 个 TXT、1 个 PDF） 对应 326 个分块。删除/撤销立即被后续检索排除，同步时物理清理。仓库不带应用向量库，首次运行需要入库。

仓库附带离线 tokenizer 缓存及身份清单。若本机同名聊天模型或模板与缓存不匹配，确认模型版本后显式导出、检查，再重启应用：

~~~powershell
.\.venv\Scripts\python.exe -B -m model.token_count export
.\.venv\Scripts\python.exe -B -m model.token_count verify
.\.venv\Scripts\python.exe -B scripts/manage.py doctor
~~~

导出默认只查询 loopback Ollama 元数据，不生成回答或下载模型。容器内由管理员显式设置 `TOKENIZER_ALLOWED_ORIGIN=http://ollama:11434`，仅允许匹配该完整 origin 的服务进行校验/导出；该配置不接受客户端输入。身份未验证时使用保守字节回退；计数加请求封装余量仍是预算估计，并非精确服务端总 token 数。详见[环境复现](docs/REPRODUCIBILITY.md)。

## REST API 与容器运行

在已安装依赖的项目目录生成本次服务密钥并启动 API：

~~~powershell
$env:API_KEY = (& .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(32))")
.\.venv\Scripts\python.exe -B scripts/manage.py api
~~~

默认访问 `http://127.0.0.1:8000/docs`，用 Authorize 输入自己的密钥。`GET /healthz` 检查进程存活；受保护的 `GET /readyz` 检查 Ollama 模型、有效来源索引和 tokenizer 身份。首次准备模型、缓存及索引仍按上文执行；API 启动不会自动拉模型、生成或入库。端口可用 `api --port 8001` 调整。

REST 入口提供 `POST /v1/sessions`、会话提问与取消，以及 `DELETE /v1/sessions/{session_id}`。API 默认最多 2 个运行任务、100 个会话、1800 秒空闲 TTL，HTTP 等待上限 125 秒；同步任务超时后仍占名额直到实际退出。密钥是演示服务的共享访问门槛，CSV 用户 ID 不代表登录身份。只支持 **一个 worker / 一个 API 实例**，重启后会话丢失。

Docker 首次运行需配置私有 `.env`，依次启动 Ollama、执行模型下载和 bootstrap，最后启动 API。镜像用非 root 用户，模型、配置审批/tokenizer 与索引分别保存在持久卷，宿主默认仅绑定回环地址。接口格式、错误码与调用示例见 [API 文档](docs/API.md)；完整 Compose 命令、Linux 更新、日志和备份见 [部署说明](docs/DEPLOYMENT.md)。

## 演示与测试

侧栏默认演示用户 1001；CSV 包含 1001—1010 在 2025 年各月的 120 条合成记录。ID 是数据选择，未实现生产登录认证。

| 场景 | 输入示例 | 核对点 |
| --- | --- | --- |
| 知识问答 | 主刷上缠了长头发，应该怎么清理？ | 有依据的清理步骤 |
| 连续追问 | 清理刚才那个部件前需要断开电源吗？ | 定位主刷，检查是否召回断电依据 |
| 使用报告 | 请生成我2025年8月的使用报告。 | 1001、2025-08、覆盖率83%、日均43㎡ |
| 无记录 | 请生成我2099年1月的使用报告。 | 明确无记录 |
| 天气 | 悉尼此刻的准确温度和湿度是多少？ | 接口未接入，应说明无法提供实时值 |

~~~powershell
.\.venv\Scripts\python.exe -B scripts/manage.py test
.\.venv\Scripts\python.exe -B scripts/manage.py pytest
.\.venv\Scripts\python.exe -B scripts/manage.py demo
~~~

`test` 保留 unittest 入口；`pytest` 是包含 API 测试的完整离线回归入口，也可直接执行 `python -B -m pytest -q`。测试使用真实 LangChain 图、Chroma 和 Streamlit 测试入口并替换模型推理；API 测试检查 HTTP、并发、取消和失败边界，不需要生成真实答案。GitHub Actions 为 Windows/Linux 配置了同一回归与离线 doctor，另在 Linux 构建镜像并做 HTTP 存活烟测；结果需查看对应提交的工作流。

`demo` 运行 6 个真实 Agent 案例、7 次提问，通常需要数分钟，输出在 `artifacts/demo_时间/`。工具故障注入不会关闭 Ollama。命令成功只代表执行完成，答案仍需核对。

新评测始终使用新目录，已有结果受版本保护：

~~~powershell
.\.venv\Scripts\python.exe -B scripts/manage.py harness --run evaluation/results/my_runtime_harness_v1
.\.venv\Scripts\python.exe -B scripts/manage.py harness --suite security --real-model --run evaluation/results/my_security_v1
.\.venv\Scripts\python.exe -B -m evaluation.context_recheck --run evaluation/results/my_context_v1
~~~

完整方法见[评测入口](evaluation/README.md)，展示顺序见[演示指南](docs/DEMO.md)。

## 架构与代码入口

~~~mermaid
flowchart TD
    UI[Streamlit 会话] --> Runtime[共享 deadline / 调用预算 / 并发]
    HTTP[FastAPI REST / Bearer / 会话] --> Async[asyncio 等待 / 有上限线程 / 断连取消]
    Async --> Runtime
    Runtime --> Agent[Agent 图 / 工具执行前校验]
    Agent <--> Memory[请求预算 / 完整轮次 / 低信任摘要]
    Agent --> RAG[知识工具]
    RAG --> Sources[允许来源与版本校验]
    Sources --> Search[向量 + BM25 / RRF / 覆盖重排]
    Search --> Budget[Top-5 证据 / RAG 输入预算]
    Budget --> LLM[本地 Qwen 回答 / 来源复核]
    LLM --> Output[本轮知识结果直出 / 提交复核]
    Agent --> CSV[指定用户和月份查询 CSV]
    CSV --> Report[程序渲染报告]
    Runtime --> Resilience[有限重试 / 进程内熔断 / 取消]
~~~

| 位置 | 职责 |
| --- | --- |
| `api/` | HTTP 边界、会话生命周期、异步等待、执行额度和就绪检查 |
| `app.py` | 页面、用户输入、会话与错误反馈 |
| `agent/react_agent.py`、`agent/tools/` | Agent 图、7 个工具、状态与最终输出 |
| `agent/runtime/` | deadline、预算、并发、重试、熔断与执行校验 |
| `agent/context_budget.py`、`agent/context_memory.py` | 请求预算、轮次裁剪、摘要与失败降级 |
| `model/token_count.py` | 本地 tokenizer 导出/验证及离线计数 |
| `rag/vector_store.py`、`rag/hybrid.py`、`rag/relevance.py` | 分块、增量索引、混合召回、查询覆盖排序 |
| `rag/rag_service.py`、`rag/security.py` | 资料隔离、来源治理、证据预算与复核 |
| `utils/records.py`、`utils/report_render.py` | CSV、月份规范化与事实渲染 |
| `evaluation/`、`tests/` | 固定题集、实验与 Harness、回归 |
| `Dockerfile`、`compose.yaml`、`.github/workflows/ci.yml` | Linux 镜像、初始化与持久卷、跨平台测试和容器烟测 |
| `scripts/`、`config/`、`prompts/`、`docs/` | 管理入口、配置、提示词与说明 |

知识结果在外层 Agent 图完成后被选为最终输出，减少外层添写；RAG 子模型仍可能答错。`execute_stream` 返回完成后的答案，当前没有 token 级流式生成。

## 效果记录与口径

本轮原 60 个案例均完整执行与复核：知识严格通过 **33/40**（7 题部分正确），模型实际输入中的标注证据覆盖 **38/40**，资料不足 **8/8**，Agent 严格任务 **10/12**；工具名称路径 **12/12**，Agent 共 14 次真实提问。A04／A05 的无记录查询功能正确（`functional=true`），程序在最终输出额外附加的 2025 年覆盖范围未包含于本次实际工具结果，因此严格实际证据口径未通过。A08 的模型越权参数被控制器成功拦截；工具名称路径合规不等于参数合规。旧 12 题本轮全部通过（8 道知识、4 道资料不足），H06 的题面只问功能名称，参考答案包含扩展解释，歧义及评分理由另存。详情见[本轮评测](docs/EVALUATION_V2.md)。

新 40 题的两版记录、评分及[逐题对照](evaluation/results/holdout_v2_comparison/comparison.json)已保存，以下均使用原计划分母：

| 新题指标 | 历史混合检索版 | 当前版 |
| --- | --- | --- |
| 知识严格通过 | 24/28（4 题部分正确） | 21/28（6 题部分正确、1 题截断未知） |
| 资料不足严格通过 | 6/6 | 6/6 |
| Agent 全轮任务通过 | 0/6（6 例失败） | 0/6（5 例失败、1 例截断未知） |
| Agent 工具名称路径 | 4/6 | 4/6 |
| 检索 Top-5 任一标注锚 / 全部必需锚 | 28/28 / 27/28 | 28/28 / 27/28 |
| 案例记录 / 执行完成 | 40/40 / 40/40 | 40/40 / 38/40 |

知识题中 21 题共同通过，2 题退步，4 题共同失败，1 题未知，没有进步题；Agent 为 5 例共同失败和 1 例未知。V2A01 的三个指定数值正确，但程序报告追加了“只列”范围之外的字段；V2A02 正确查到两个相邻月份，却未交付请求的差值；V2A04 漏掉晾干提醒。当前长历史 V2A05/V2A06 的摘要丢失部件、月份、字段或限制，后续没有完成原目标；历史版也出现未检索便拒答或未查表便断言无记录。当前 V2K22 和 V2A03 的截断不计正确拒答。这些反例保留为后续改进依据，本轮未按新题结果修改业务实现。

两版使用相同新题、资料和模型 digest，保留各自业务配置；检索、提示、来源治理、请求预算和历史管理共同变化，结果不支持全面提升或单一算法因果改善。复核隐藏版本标签并打乱排列，由 Codex 助手检查冻结要求与实际输入；提示和行为仍可能透露实现特征，属于辅助语义复核，未经独立真人专家审核。

下表保留**历史检索优化实验**的当时口径：

| 指标 | 基线 | 改进后 |
| --- | --- | --- |
| 默认标注证据命中（K 从 3 改为 5） | 31/40 | 38/40 |
| 同为 Top-5（向量 → 混合） | 33/40 | 38/40 |
| 知识回答严格通过 | 30/40 | 33/40 |
| Agent 任务完成 | 11/12 | 12/12 |
| 资料不足拒答 | 8/8 | 8/8 |

历史优化轮的 12 道保留题通过，4 道操作题退步保留。历史 33/40 与本轮 33/40 来自不同版本和运行；整体版本有多项功能共同变化，不能据此归因于单一改动。2026-10-01 的上下文验收当时只做有限复验，本轮已重新执行原题。助手语义复核未经独立专家审核或真人盲评；小规模单次实验不代表生产效果。

- [历史改进报告](evaluation/results/optimized_v1/comparison.md)及[逐题记录](evaluation/results/optimized_v1/audit.md)
- [保留题记录](evaluation/results/holdout_optimized_v1/audit.md)
- [Runtime / Harness 第四步验收](docs/RUNTIME_STAGE4_VERIFICATION.md)
- [上下文管理验收](docs/CONTEXT_MANAGEMENT_VERIFICATION.md)

## 更新知识与打包

新增/修改 UTF-8 TXT 或可提取文字的 PDF 后，先扫描并核对资料内容、版本与摘要。管理员命令不提供给 Agent：

~~~powershell
.\.venv\Scripts\python.exe -B scripts/manage.py knowledge scan
.\.venv\Scripts\python.exe -B scripts/manage.py knowledge status
.\.venv\Scripts\python.exe -B scripts/manage.py knowledge approve "新资料.txt" --sha256 "<扫描输出的SHA256>" --reason "审核依据"
.\.venv\Scripts\python.exe -B scripts/manage.py knowledge sync
~~~

审批表示允许使用该文件，不保证事实正确。`--allow-risk` 用于明确复核过的合法引用。撤销使用 `knowledge revoke <source_id> --reason "撤销依据"`，然后同步索引并重启页面。详见[来源管理](docs/RUNTIME_STAGE3.md)。

~~~powershell
.\.venv\Scripts\python.exe -B scripts/package_project.py --output dist/AI_agent_source.zip
~~~

源码包与仓库包含源码、配置、演示资料、测试、文档和精选证据；排除虚拟环境、应用向量库、模型、普通日志、IDE 文件及密钥。约 2 MB 的 tokenizer 缓存是离线计数资源，需要保留。源码包提供逐文件 SHA256 清单，已有 ZIP 不静默覆盖。

## 文档导航

| 阅读目的 | 文档 |
| --- | --- |
| 安装和排查 | [环境复现](docs/REPRODUCIBILITY.md) |
| HTTP 调用、接口和错误码 | [API 文档](docs/API.md) |
| Docker / Linux 运行与运维 | [部署说明](docs/DEPLOYMENT.md) |
| 展示项目 | [演示指南](docs/DEMO.md) |
| 方法、命令与结果 | [评测 README](evaluation/README.md) |
| 本轮原题回归与新题同题对照 | [EVALUATION_V2](docs/EVALUATION_V2.md)、[新 40 题](evaluation/holdout_v2/README.md) |
| 准备隔离的历史业务版本 | [prepare CLI](scripts/prepare_evaluation_variant.py)、[同题版本对照](evaluation/README.md#同题版本对照) |
| 完成评测后的离线归档校验 | [seal CLI](scripts/seal_evaluation_run.py)、[归档说明](evaluation/README.md#证据快照与恢复约定) |
| Runtime 设计 | [分步计划](docs/RUNTIME_HARNESS_PLAN.md)、[第四步说明](docs/RUNTIME_STAGE4.md) |
| 上下文预算与摘要 | [上下文管理](docs/CONTEXT_MANAGEMENT.md) |
| 当前边界 | [已知限制](docs/LIMITATIONS.md) |

阶段验收和评测 snapshot 是对应版本的历史证据，保留当时计数与输出。seal 是离线归档校验，不是防篡改签名，也不替代恢复推理时的实时身份保护。知识资料未核实厂商适用性；CSV 为合成数据；天气、OCR、会话持久化、生产认证和大规模并发尚未实现。

