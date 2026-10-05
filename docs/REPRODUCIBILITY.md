# 环境复现与排查

本页为截至 2026-10-05 的运行说明，包括新加入的 FastAPI、pytest 和容器入口。阶段安装/交付记录是对应历史版本的验证，见 [DELIVERY_VERIFICATION.md](DELIVERY_VERIFICATION.md)；上下文功能验收见 [CONTEXT_MANAGEMENT_VERIFICATION.md](CONTEXT_MANAGEMENT_VERIFICATION.md)。API 调用见 [API.md](API.md)，Docker/Linux 操作见 [DEPLOYMENT.md](DEPLOYMENT.md)。

## 固定环境与模型

已有历史环境验证为 Windows 11 x64、CPython 3.12.2。当前 `requirements.txt` 声明 17 项运行时直接依赖，`requirements-lock.txt` 固定 125 项依赖及传递依赖，含开发用 pytest 及其依赖，不含 pip 本身。`requirements-dev.txt` 引用该锁。历史交付时的 12 项、Runtime 时的 14 项、上下文版本的 15 项直接依赖和 121 项锁定依赖分别属于当时版本。

2026-10-05 API 接入前的源码发布检查运行了 259 项回归（258 通过、1 项权限跳过），离线 doctor 142 项通过，原始证据见 [发布检查](../artifacts/github_publication_v1/checks.json)。这些数字不能作为新 API 或 Linux 验收结果。CI 第三次运行已通过 Windows/Linux 各 321 项回归和 Linux 镜像构建、非 root HTTP 启动检查；后续提交的最新状态查看 [PR Checks](https://github.com/hu23320690-crypto/AI_agent/pull/1/checks)。本机尚未安装 Docker；CI 容器烟测没有拉取模型，不代表容器内真实问答通过。

本轮本机 pytest 320 项通过、1 项权限跳过，188 项 unittest 子断言通过；离线 doctor 146 项通过，pip check 无依赖冲突。新增 API 测试 39 项全通过，证据见[工程化检查](../artifacts/api_engineering_v1/checks.json)。真实 HTTP 检查单独记录，不以健康接口通过代替模型回答质量验证。

~~~powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m pip check
~~~

不需要激活环境。模型由 Ollama 管理，不在仓库或源码包中；按主 [README](../README.md) 准备模型。历史实验 digest：

| 模型 | SHA256 digest |
| --- | --- |
| qwen3:4b | 359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7 |
| qwen3-embedding:4b | df5bd2e3c74cd8d069d21dc038f1b359fcdc9458fce1c99bd43c9eb1518ff907 |

相同标签不保证以后下载内容相同。`doctor` 显示实际 digest，并核验聊天模型与 tokenizer 模板身份。默认服务地址为 `http://127.0.0.1:11434`；设置 `OLLAMA_HOST` 时，应指向自己控制的服务。tokenizer 导出与身份验证默认只允许 loopback host；容器内可由管理员额外指定一个完整、精确的 `TOKENIZER_ALLOWED_ORIGIN`（本项目 Compose 为 `http://ollama:11434`），只允许匹配该 origin 的目标。该选项不会允许任意远程 host，也不能由请求参数或知识内容改变。

当前 `context.yml` 窗口 8192、输出预留 4096、安全余量 256，输入预算 3840 估计单位；推理也占生成额度，提供方标记截断的输出不提交。整轮 Runtime 默认 120 秒，模型单次等待默认 90 秒，Ollama 客户端 HTTP 超时配置为 120 秒；FastAPI 的请求等待默认 125 秒，由 `API_REQUEST_TIMEOUT_SECONDS` 控制。评测案例外部进程上限另行设置。有限重试共享整轮预算，不是每次重新获得 120 秒。

索引当前集合为 `agent_chunks_qwen3_governed_v1`，chunk_size=200、overlap=20；混合 Top-5、每路 20 候选、RRF 常数 60，增加来源准入、每源配额和查询覆盖排序。旧 `agent_chunks_qwen3_v1` 是历史集合。

## 验证顺序

~~~powershell
.\.venv\Scripts\python.exe -B scripts/manage.py doctor --offline
.\.venv\Scripts\python.exe -B scripts/manage.py doctor
.\.venv\Scripts\python.exe -B scripts/manage.py pytest
.\.venv\Scripts\python.exe -B scripts/manage.py index
.\.venv\Scripts\python.exe -B scripts/manage.py serve
~~~

离线 doctor 检查依赖、配置、资料和缓存，不访问 Ollama。在线 doctor 另核验模型与模板；它不测试答案准确率。`pytest` 运行原有单元测试与新增 API 回归，替换模型推理，验证程序行为；`test` 保留 unittest 入口。API 模块通过注入的假 Agent 验证异步 HTTP 行为，不能由此推导实际回答准确率。

源码首次运行会生成应用向量库；索引包含源路径与版本信息，不应依赖从其他目录拷贝的旧向量库。仓库保留约 2 MB 的 tokenizer 缓存，因为这是离线计数资源。

模型或模板不匹配时，明确确认本机版本后重新导出：

~~~powershell
.\.venv\Scripts\python.exe -B -m model.token_count export
.\.venv\Scripts\python.exe -B -m model.token_count verify
.\.venv\Scripts\python.exe -B scripts/manage.py doctor
~~~

导出只读查询 Ollama 元数据并写本地缓存，不下载模型、不生成回答。变更后重启应用；这会改变当前实验输入身份，旧 run 应保留，新评测使用新目录。身份未验证时采用保守字节回退，可能提前拒绝本可容纳的输入。

## API 与容器复现

~~~powershell
$env:API_KEY = (& .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(32))")
.\.venv\Scripts\python.exe -B scripts/manage.py api
~~~

打开 `http://127.0.0.1:8000/docs`，使用自己生成的 Bearer 密钥。`/healthz` 是无认证存活检查，`/readyz` 需要认证并检查模型、tokenizer 和当前授权/版本匹配的索引。API 启动不自动入库或生成；未准备依赖时可以存活，但不能就绪。直接 Uvicorn 运行时必须使用 `--workers 1`，管理脚本和 Docker 默认均为单 worker。

asyncio 负责 HTTP 等待、断连检测及会话生命周期；同步 Agent 调用在有上限的线程池执行。总运行数默认 2，同会话同时运行返回冲突，任务槽不会因 HTTP 超时而提前归还。会话最多 100 个，空闲 TTL 1800 秒；会话、并发额度和熔断都在进程内，不能用多 worker 或多副本直接扩展。

容器复现使用项目 `Dockerfile` 和 `compose.yaml`，先配置未提交的 `.env`，再按 [部署说明](DEPLOYMENT.md)运行模型下载与 bootstrap。API 与 bootstrap 共用配置卷，使 tokenizer manifest/cache 和知识审批状态一致，Chroma 与 Ollama 模型也各自持久化。数据和提示词来自镜像；升级镜像不自动覆盖已有配置卷，需审查并迁移配置。Linux CI 仅做无模型的 API 存活与未就绪检查，真实模型运行仍需独立验收。

## 常见故障

| 现象 | 处理 |
| --- | --- |
| SyntaxError 或 Python 版本失败 | 使用 Python 3.12，并确认调用项目虚拟环境解释器 |
| 依赖缺失或版本不一致 | 使用该解释器安装 lock，再执行 pip check |
| Ollama 连接失败 | 确认服务运行及 OLLAMA_HOST；避免重复启动占用端口 |
| 模型不存在 | pull 对应模型，再运行 doctor |
| tokenizer 身份不匹配 | 确认本机模型/模板，再 export、verify、doctor 并重启 |
| 新资料未生效 | knowledge scan 后按内容与 SHA256 审核，再 knowledge sync；未获准资料保持隔离 |
| 删除或撤销资料后旧索引仍占空间 | 后续检索已排除失效来源；knowledge sync 物理清理 |
| 首问很慢或请求超时 | 查看 trace 与日志，确认没有同时运行其他模型评测；同步等待停止不保证远端推理立即停止 |
| 对话超预算或生成截断 | 查看 context.yml 与预算 trace；当前工具链不截断，失败轮不提交。不能以增大配置替代实际资源核验 |
| 本月无记录 | 合成 CSV 只覆盖 2025 年，使用明确月份如 2025-08 |
| 页面端口占用 | serve --port 8502，访问对应端口 |
| API 启动时报 API_KEY 错误 | 设置不少于 32 个 ASCII 字符的随机密钥；不使用示例密钥。直接运行不会隐式加载 .env |
| API 返回 401 | 请求加 Authorization: Bearer 自己的密钥；readiness 也需认证 |
| API 存活但 readiness 503 | 核对模型、tokenizer 身份与授权来源索引，完成 export / doctor / index；容器中执行 bootstrap |
| API 返回 409 / 429 | 409 常见于同会话已有运行；429 表示运行或会话容量已满。停止等待不保证后台同步任务已经退出 |
| 容器重启后配置或会话表现不同 | 配置与索引来自 named volume，升级需显式迁移；对话会话未持久化，重启后需重新创建 |
| 恢复旧评测被拒绝 | 保留旧 manifest 和记录，当前代码用新的 --run；不删除校验信息绕过保护 |

## 复测与归档

~~~powershell
.\.venv\Scripts\python.exe -B -m evaluation.run --run evaluation/results/my_current_experiment --stage all
.\.venv\Scripts\python.exe -B -m evaluation.report --run evaluation/results/my_current_experiment
.\.venv\Scripts\python.exe -B -m evaluation.export --run evaluation/results/my_current_experiment
~~~

report 汇总已有 reviews，不会自动获得语义分数。按固定题目对照实际证据复核，超时、错误和未知样本保留。其他故障、安全、长历史命令及执行快照区别见 [评测入口](../evaluation/README.md)。

GitHub 保留历史评测 snapshot、原始提交结果和精选 artifacts；普通运行日志及 worker 临时文件排除，历史验收所需的回归日志作为精选证据保留。打包命令见主 README，ZIP 内 `DELIVERY_MANIFEST.json` 提供逐文件 SHA256。旧实验和失败不能覆写成新成绩。

