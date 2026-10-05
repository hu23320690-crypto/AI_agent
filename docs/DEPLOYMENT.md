# 本机 API、Docker 与 Linux 运行

本页描述截至 2026-10-05 的服务部署配置。FastAPI 把现有 Agent 封装成 HTTP 服务；Ollama 推理与 Chroma 索引仍由本项目的 Runtime、来源校验和上下文预算约束。Streamlit 界面仍可用于交互演示。接口与错误码见 [API.md](API.md)。

GitHub Actions 会在 Windows/Linux 的 Python 3.12 上安装锁定依赖、运行 `pytest` 和离线 `doctor`，并在 Linux 构建镜像、启动 API 做 HTTP 存活检查。工作流的绿色结果才代表对应提交在该环境通过；容器烟测不下载模型、不验证真实回答质量。真实模型验收与历次评测参见 [CONTEXT_MANAGEMENT_VERIFICATION.md](CONTEXT_MANAGEMENT_VERIFICATION.md) 和 [evaluation/README.md](../evaluation/README.md)。

## 本机启动

在项目根目录准备 Python 3.12、固定依赖与两个 Ollama 模型。Windows PowerShell：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m pip check
ollama pull qwen3:4b
ollama pull qwen3-embedding:4b
.\.venv\Scripts\python.exe -B -m model.token_count export
.\.venv\Scripts\python.exe -B scripts/manage.py doctor
.\.venv\Scripts\python.exe -B scripts/manage.py index
$env:API_KEY = (& .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(32))")
.\.venv\Scripts\python.exe -m uvicorn api.app:app --host 127.0.0.1 --port 8000 --workers 1
```

`API_KEY` 是调用该演示服务的共享 Bearer 密钥，仓库没有默认密钥。保存自己的密钥后，在另一个终端用它访问受保护接口。通过环境变量传递密钥；本机直接运行 Uvicorn 不会自动读取 `.env`，需要自行设置环境变量或显式使用 `--env-file .env`。密钥不等于用户登录系统，CSV 中的 `user_id` 是演示记录标识。

访问 `http://127.0.0.1:8000/docs` 查看 OpenAPI，并使用 Authorize 输入自己的密钥。`GET /healthz` 无须认证，只表示 API 进程存活；`GET /readyz` 需要认证，检查模型、有效来源索引和 tokenizer 身份。缺模型、未初始化索引或缓存不匹配时，readiness 返回 503。API 启动不会自动拉模型、运行生成或建立索引。

服务默认并发上限 2、会话上限 100、空闲会话 TTL 1800 秒、每请求等待上限 125 秒。对应环境变量见 [.env.example](../.env.example)。推理的总预算仍由 `config/runtime.yml` 管理；HTTP 超时或取消会阻止迟到结果提交，会释放资源的具体时机取决于同步推理是否实际结束，不能把取消描述为强制终止 Ollama。

## Docker Compose 首次运行

Windows 使用支持 Linux containers 的 Docker Desktop；Linux 安装 Docker Engine 和 Compose 插件，例如 [Docker 的 Ubuntu 安装说明](https://docs.docker.com/engine/install/ubuntu/)。先确认：

```sh
docker version
docker compose version
```

项目镜像基于 `python:3.12-slim-bookworm`，该 minor 标签会随镜像更新，构建输出记录实际镜像；Ollama 镜像固定为 `ollama/ollama:0.35.1`。Python 软件包来自 `requirements-lock.txt`，不将模型权重、旧向量库、虚拟环境或评测快照复制到镜像。容器中的应用使用 UID/GID `10001:10001`；内部 Ollama 服务不映射宿主端口，API 默认只绑定宿主的 `127.0.0.1:8000`。

在项目根目录复制 `.env.example` 到 `.env`，生成自己的随机 `API_KEY` 并写入 `.env`。PowerShell 用 `Copy-Item .env.example .env`，Linux 用 `cp .env.example .env`。在 Linux 设置 `chmod 600 .env`。生成密钥的命令：

```sh
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

然后按顺序执行，任一步失败先检查日志，成功后才进行下一步：

```sh
docker compose config --quiet
docker compose build api
docker compose up --detach ollama
docker compose --profile setup run --rm models
docker compose --profile setup run --rm bootstrap
docker compose up --detach api
docker compose ps
```

`models` 是一次性任务，通过内部 Ollama API 拉取聊天与 Embedding 模型；`bootstrap` 在应用镜像中导出当前模型 tokenizer、检查环境并增量建立知识索引。Ollama 模型下载和索引 Embedding 需要时间与磁盘空间。默认 Compose 使用 CPU，具体响应速度取决于主机；需要 GPU 时按 [Ollama Docker 文档](https://docs.ollama.com/docker)配置对应设备和驱动，再重新验证时限。

Compose 用 [healthcheck 与 depends_on 条件](https://docs.docker.com/reference/compose-file/services/#depends_on)等待 Ollama 服务存活。模型是否已拉取、索引是否完成仍由初始化任务和 `/readyz` 检查，存活检查不会代替这些步骤。`setup` 服务使用 [Compose profiles](https://docs.docker.com/compose/how-tos/profiles/)，日常启动 API 不会自动执行模型下载和入库。

容器显式设置 `OLLAMA_HOST=http://ollama:11434`。管理员允许 tokenizer 导出/校验读取相同的 `TOKENIZER_ALLOWED_ORIGIN`；该选项只应指向自己控制的 Ollama 服务，客户端请求不能改变它。镜像中的 `data` 与 `prompts` 是当前提交的输入，`config_state` named volume 初次创建时从镜像复制配置，随后持久保存 tokenizer manifest/cache 和知识审批清单。API 与 bootstrap 共用这份配置，避免缓存只写入一次性容器后丢失。

验证存活与就绪，Linux 示例从私有 `.env` 读取密钥；不要复制示例密钥：

```sh
curl --fail http://127.0.0.1:8000/healthz
set -a
. ./.env
set +a
curl --fail --header "Authorization: Bearer $API_KEY" http://127.0.0.1:8000/readyz
```

也可通过浏览器的 `/docs` 页面执行。此时应再选一个 RAG 问题和一个记录报告问题做实际 HTTP 验证：健康检查不会验证工具调用和答案语义。现有模型验证数据仍属于文档中记录的历史实验，不因添加 HTTP 外壳就获得新的准确率。

## Linux 日常操作与更新

```sh
docker compose logs --tail 100 api
docker compose logs --tail 100 ollama
docker compose restart api
docker compose stop api
docker compose up --detach api
```

Compose 配置 `restart: unless-stopped`。API 容器的健康状态由无认证的 `/healthz` 检查；运维确认推理可用时另查受保护的 `/readyz`。容器退出可由 restart policy 恢复；只标记 unhealthy 不会自动重启进程。服务收到停止信号后最多等待 130 秒，Compose 给出 135 秒停止宽限，供运行中的请求清理。

更新代码前先备份状态，记录 `git rev-parse HEAD`，随后使用 `git pull --ff-only`、`docker compose build api` 和 `docker compose up --detach api`。Git 冲突需先解决，不能覆盖本机审核中的资料。升级锁依赖、Ollama 镜像或模型标签后，重新运行测试、doctor、bootstrap 和真实请求。

**已有 `config_state` 不会被新镜像的配置自动覆盖。** 更改 `context.yml`、Runtime 配置或审批清单时，先审查差异，停止 API，再将明确审核的文件复制到容器卷内。以下仅示范把单个已经审核过的配置同步到卷；把文件名换成实际改动的文件，不要批量覆盖审批记录：

```sh
docker compose stop api
docker compose --profile setup run --rm --no-deps --volume "${PWD}/config/context.yml:/tmp/reviewed-context.yml:ro" --entrypoint python bootstrap -c "import shutil; shutil.copyfile('/tmp/reviewed-context.yml', '/app/config/context.yml')"
docker compose --profile setup run --rm bootstrap
docker compose up --detach api
```

临时 bootstrap 容器仍以 UID 10001 写入，只将明确审核的宿主文件以只读方式挂到临时路径，不覆盖整个配置目录。修改知识文件时镜像里的数据和卷内清单必须同时匹配：在新镜像中运行 `python -B scripts/manage.py knowledge scan`、按 SHA256 审核 `approve`，最后 `sync`。不要通过直接改 Chroma 数据库绕过审批；新内容未获批准时被隔离是预期行为。来源治理详细命令见 [README](../README.md)。

## 卷备份与恢复

持久卷包括 Ollama 模型、Chroma 索引、配置审批/tokenizer 和日志。`docker compose down` 保留 named volumes；`down --volumes` 会删除状态。默认项目名 `ai-agent`，卷名分别为 `ai-agent_ollama_models`、`ai-agent_chroma_data`、`ai-agent_config_state`、`ai-agent_agent_logs`；如果用 `--project-name` 启动，按实际卷名操作。

在 Linux 停止 API 和 Ollama 后做一致备份，示例使用已构建的应用镜像，只备份核心配置与索引：

```sh
docker compose stop api ollama
mkdir -p backups
docker run --rm --user 0:0 --entrypoint tar --volume ai-agent_config_state:/state:ro --volume "$PWD/backups:/backup" ai-agent:local -czf /backup/config-state.tgz -C /state .
docker run --rm --user 0:0 --entrypoint tar --volume ai-agent_chroma_data:/state:ro --volume "$PWD/backups:/backup" ai-agent:local -czf /backup/chroma-data.tgz -C /state .
docker compose up --detach ollama api
```

恢复时停止 API，校验备份来源和版本，使用同类临时容器将归档解压到对应卷，保留 UID/GID 10001 的应用文件归属，再运行 doctor、来源检查和 readiness。模型权重可重新拉取或另备份 `ollama_models`；更换模型 digest 后应重新导出 tokenizer 并同步索引，不应直接相信旧缓存。备份可能包含审批记录或日志，作为本机运维资料保存，不提交公开仓库。

## 当前部署边界

只支持 **一个 Uvicorn worker / 一个 API 实例**：会话、排队、并发额度与熔断状态在进程内，服务重启丢失对话；多 worker 或多副本会造成会话查找与预算不一致。需要横向扩展时应先引入共享会话/任务存储并重新设计取消与锁。

当前交付范围是本机和 Linux 容器运行配置、pytest 与 CI。它没有多租户身份系统、HTTPS 反向代理、共享会话数据库或云平台上线保证。默认共享密钥只适合受控演示；对外发布前需结合实际服务器完成认证、HTTPS、访问限制与监控设计。未运行的容器或未成功的 CI 不能在简历上写成已经通过 Linux 部署验收。
