# 扫地机器人智能客服：RAG + Agent

本地中文客服项目，提供产品知识问答、连续追问和按用户/月度查询的使用报告。实现混合检索、工具调用、共享执行预算、超时与取消、重试与熔断、来源治理、故障与安全评测，以及长对话的上下文预算和结构化摘要。

技术栈：Python 3.12、Streamlit、LangChain / LangGraph、Ollama、Chroma、字符 BM25、RRF。

## 当前完成情况

文档整理截至 **2026-10-05**。最新功能验收记录为 **2026-10-01**；历史实验保留原始版本、输出和失败记录。

2026-10-05 发布前已在独立源码副本再次运行回归：259 项运行、258 通过、1 项权限跳过，离线 doctor 142 项通过；文档链接与待上传文件检查见[发布检查记录](artifacts/github_publication_v1/checks.json)。本次没有重新测量全部真实模型问答。

| 能力 | 当前实现 |
| --- | --- |
| RAG | 200 字分块、20 字重叠；向量与 BM25 各取 20 候选，RRF 融合；来源配额、查询词覆盖重排、近重复过滤，检索 Top-5 |
| Agent | 7 个工具，多轮历史与指代追问；按会话用户和月份查询 CSV，由程序渲染事实报告 |
| Runtime | 整轮共享 deadline 与模型/工具/embedding 调用预算；有限并发、取消、有限重试和进程内熔断 |
| 来源治理 | 新增/变化资料隔离、文件摘要审核、撤销与同步；检索、生成后和提交前复核来源 |
| 上下文管理 | 消息及工具结构预算、完整轮次裁剪、低信任结构化摘要、失败降级、截断输出拒绝提交 |
| Harness | 冻结输入与 worker 执行；7 类故障、23 条安全/正常样本；原始输出与语义复核分别保存 |

2026-10-01 回归运行 **259 项：258 通过、1 项 Windows 符号链接权限跳过**。长历史验收注入 64 轮合成已完成历史，再实际生成摘要和执行两次提问；首请求消息从 129 条降至 6 条。这不是 64 次真实模型对话，摘要不能保证零信息损失。

最终配置的真实安全评测记录了 23 条，22 条执行完成、1 条生成截断未完成。获准错误事实仍被采纳，恶意工具结果仍可能污染最终输出。完整结果见[上下文验收](docs/CONTEXT_MANAGEMENT_VERIFICATION.md)，边界见[已知限制](docs/LIMITATIONS.md)。

## 新环境安装

已验证：Windows 11、64 位 CPython **3.12.2**。代码使用 Python 3.12 语法，在项目目录打开 PowerShell：

~~~powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m pip check
~~~

不需要激活环境。没有 `py` 时，用已安装的 Python 3.12 可执行文件替代。`requirements.txt` 声明 **15 项直接依赖**，`requirements-lock.txt` 固定 **121 项依赖及传递依赖**，验证范围为 Windows / Python 3.12。

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

导出只查询本机元数据，不生成回答或下载模型。身份未验证时使用保守字节回退；计数加请求封装余量仍是预算估计，并非精确服务端总 token 数。详见[环境复现](docs/REPRODUCIBILITY.md)。

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
.\.venv\Scripts\python.exe -B scripts/manage.py demo
~~~

`test` 使用真实 LangChain 图、Chroma 和 Streamlit 测试入口，替换模型推理。`demo` 运行 6 个真实 Agent 案例、7 次提问，通常需要数分钟，输出在 `artifacts/demo_时间/`。工具故障注入不会关闭 Ollama。命令成功只代表执行完成，答案仍需核对。

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
| `app.py` | 页面、用户输入、会话与错误反馈 |
| `agent/react_agent.py`、`agent/tools/` | Agent 图、7 个工具、状态与最终输出 |
| `agent/runtime/` | deadline、预算、并发、重试、熔断与执行校验 |
| `agent/context_budget.py`、`agent/context_memory.py` | 请求预算、轮次裁剪、摘要与失败降级 |
| `model/token_count.py` | 本地 tokenizer 导出/验证及离线计数 |
| `rag/vector_store.py`、`rag/hybrid.py`、`rag/relevance.py` | 分块、增量索引、混合召回、查询覆盖排序 |
| `rag/rag_service.py`、`rag/security.py` | 资料隔离、来源治理、证据预算与复核 |
| `utils/records.py`、`utils/report_render.py` | CSV、月份规范化与事实渲染 |
| `evaluation/`、`tests/` | 固定题集、实验与 Harness、回归 |
| `scripts/`、`config/`、`prompts/`、`docs/` | 管理入口、配置、提示词与说明 |

知识结果在外层 Agent 图完成后被选为最终输出，减少外层添写；RAG 子模型仍可能答错。`execute_stream` 返回完成后的答案，当前没有 token 级流式生成。

## 效果记录与口径

下表为**历史检索优化实验**，不是当前版本重新测出的整体准确率：

| 指标 | 基线 | 改进后 |
| --- | --- | --- |
| 默认标注证据命中（K 从 3 改为 5） | 31/40 | 38/40 |
| 同为 Top-5（向量 → 混合） | 33/40 | 38/40 |
| 知识回答严格通过 | 30/40 | 33/40 |
| Agent 任务完成 | 11/12 | 12/12 |
| 资料不足拒答 | 8/8 | 8/8 |

另 12 道未参与选型的保留题在该轮通过，4 道操作题退步保留。语义评分由助手对照题目、资料和实际输出复核，未经过独立专家审核；小规模单次实验不代表生产效果。Runtime 第四步正式检索复核仍为 38/40；上下文管理后未重跑全部 40 题答案，送入模型的证据数量还受预算影响。

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
| 展示项目 | [演示指南](docs/DEMO.md) |
| 方法、命令与结果 | [评测 README](evaluation/README.md) |
| Runtime 设计 | [分步计划](docs/RUNTIME_HARNESS_PLAN.md)、[第四步说明](docs/RUNTIME_STAGE4.md) |
| 上下文预算与摘要 | [上下文管理](docs/CONTEXT_MANAGEMENT.md) |
| 当前边界 | [已知限制](docs/LIMITATIONS.md) |

阶段验收和评测 snapshot 是对应版本的历史证据，保留当时计数与输出。当前使用方法以本页和评测入口为准。知识资料未核实厂商适用性；CSV 为合成数据；天气、OCR、会话持久化、生产认证和大规模并发尚未实现。

