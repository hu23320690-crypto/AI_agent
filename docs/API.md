# Agent REST API

FastAPI 服务复用已有 ReactAgent、Runtime、来源治理和上下文管理。启动与容器初始化见 [部署说明](DEPLOYMENT.md)。本页接口对应 `api/app.py`，交互文档为 `/docs`，接口定义为 `/openapi.json`。

## 认证与接口

启动必须设置至少 32 个 ASCII 字符的随机 `API_KEY`。受保护接口带 `Authorization: Bearer <自己的密钥>`。密钥不写入 Git；`.env.example` 只列变量名。当前是受控演示共享密钥，`user_id` 用于选择合成 CSV 记录，不构成多租户登录认证。

| 方法 | 路径 | 请求 / 响应 |
| --- | --- | --- |
| GET | `/healthz` | 无认证；200 表示 HTTP 进程存活 |
| GET | `/readyz` | 需认证；模型、tokenizer 身份和有效来源索引满足时 200，否则 503 |
| POST | `/v1/sessions` | `{"user_id":"1001","city":"上海"}`；201 返回随机 `session_id` |
| POST | `/v1/sessions/{session_id}/messages` | `{"query":"请生成我2025年8月的使用报告。"}`；返回完整回答及运行元数据 |
| GET | `/v1/sessions/{session_id}/actions` | service 模式；返回本会话卡片列表，包含所有状态 |
| POST | `/v1/sessions/{session_id}/actions/{action_id}/confirm` | service 模式；无请求体或 `{}`，返回状态和代码渲染结果 |
| POST | `/v1/sessions/{session_id}/actions/{action_id}/reject` | service 模式；无请求体或 `{}`，拒绝 pending 动作 |
| POST | `/v1/sessions/{session_id}/cancel` | 取消运行中的本轮；返回 `{"cancelled":true}`，无运行则 false |
| DELETE | `/v1/sessions/{session_id}` | 取消本轮并删除会话；成功 204 |

会话创建后身份固定，消息请求只允许 `query`，拒绝额外字段和内部 Runtime 参数。问题最多 8000 字符，实际请求体最多 32768 字节，包括没有 Content-Length 的分块传输。默认最多 100 个会话，空闲 1800 秒过期；每个会话独立 Agent 和成功历史。同一会话不能同时执行两个问题。

### 售后服务确认卡片

使用 `AGENT_TOOLSET=service` 启动，并先运行 `python -B scripts/manage.py service-db init`。不会自动创建业务数据库。会话 ID、用户 ID、数据库路径均由服务端绑定；确认/拒绝请求体不接受任何字段（包括身份、数据库路径或动作参数）。聊天中说“确认”仍不会执行。

service 模式的 messages 成功响应额外包含 `actions`：该轮结束时本会话尚处于 pending 的卡片列表，没有卡片时为 `[]`。legacy 响应保持原结构。GET actions 返回 S2-A 的完整卡片列表，惰性标记过期动作；卡片包含 action_id、tool、summary、created_at、expires_at、args_sha256、status。

确认/拒绝返回示例：`{"action_id":"动作 UUID","status":"executed","message":"已创建订单 O-SVC-…，处理中。", ...}`。executed、rejected、expired、superseded、failed 均为 200，包含结果文本；重复确认返回首次存档结果。不存在、其他会话/用户的动作以及 S2-A 校验拒绝统一为 404 action_not_found，响应体完全相同：`{"error":{"code":"action_not_found","message":"动作不存在或不属于当前会话。"}}`，追踪 ID 仅在 X-Request-ID 响应头。会话正在执行问题或卡片请求时为 409 session_busy；legacy 模式为 409 service_disabled。三个接口均需 Bearer 鉴权，未鉴权为 401；额外请求体字段为 422 invalid_request。

卡片决定不经过模型，使用原有有界工作线程及准入控制。业务操作和写回历史持有 Agent 的状态锁，决定期间持有本次操作的 run.lock，避免取消穿过业务提交/历史追加边界。同一动作的历史只写一次，裁剪后仍不会重写。消息为 HumanMessage(name='action_event', content='[卡片操作] 确认/拒绝 <action_id>') 和 AIMessage(content=代码渲染结果) 的完整一对；卡片操作不参与 RAG 用户原话、意图历史或摘要用户引用。数据库与历史分别位于 SQLite 和进程内存，重启会丢失会话及内存历史，数据库决定仍保留。

成功回答示例结构（用时、计数由实际请求生成）：

```json
{
  "session_id": "随机会话 ID",
  "answer": "完整回答",
  "run_id": "本轮运行 ID",
  "status": "succeeded",
  "seconds": 1.2,
  "counts": {"run": 1, "model": 2, "tool": 1}
}
```

## 本机调用

在设置了自己密钥的 PowerShell 终端启动：

```powershell
$env:API_KEY = (& .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(32))")
.\.venv\Scripts\python.exe -B scripts/manage.py api
```

默认访问 `http://127.0.0.1:8000`，`api --port 8001` 更换端口。另一个终端需要设置同一个密钥；不要把密钥发到日志或公开仓库。调用示例：

```powershell
$headers = @{ Authorization = "Bearer $env:API_KEY" }
$base = 'http://127.0.0.1:8000'
Invoke-RestMethod "$base/healthz"
Invoke-RestMethod "$base/readyz" -Headers $headers
$session = Invoke-RestMethod "$base/v1/sessions" -Method Post -Headers $headers -ContentType 'application/json' -Body '{"user_id":"1001","city":"上海"}'
$body = @{ query = '请生成我2025年8月的使用报告。' } | ConvertTo-Json
Invoke-RestMethod "$base/v1/sessions/$($session.session_id)/messages" -Method Post -Headers $headers -ContentType 'application/json; charset=utf-8' -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
Invoke-RestMethod "$base/v1/sessions/$($session.session_id)" -Method Delete -Headers $headers
```

Linux 中在终端设置 `API_KEY` 后，创建会话和查看状态：

```sh
curl --fail http://127.0.0.1:8000/healthz
curl --fail --header "Authorization: Bearer $API_KEY" http://127.0.0.1:8000/readyz
curl --fail --header "Authorization: Bearer $API_KEY" --header 'Content-Type: application/json' --data '{"user_id":"1001","city":"上海"}' http://127.0.0.1:8000/v1/sessions
```

从返回 JSON 获取 session_id，再调用 messages、cancel 或 DELETE。取消需要另一条 HTTP 请求；在等待 messages 的同一终端输入取消命令不会自动建立并行连接。

## asyncio 与执行控制

HTTP 接口、依赖 HTTP 探测、请求等待、断连监听、TTL 清理和服务关闭使用 `asyncio`。现有 LangChain Agent 与工具是同步实现，放入专用 `ThreadPoolExecutor`，默认最多 2 个并行任务，不阻塞事件循环。这里没有将整个模型链改写为原生异步推理。

准入与登记在事件循环中连续完成，容量满直接 429，不创建无限队列。外部 RunContext 在提交线程前建立，包含线程启动等待时间；Agent 复用相同 deadline、执行器和调用预算。HTTP 默认等待 125 秒，Runtime 默认总预算 120 秒，取消/断连/HTTP 超时都会标记同一 RunContext，阻止迟到回答和历史提交。

停止 HTTP 等待不会强杀远端 Ollama。实际同步线程结束前保留 API 并发名额；底层 Runtime 对尚未结束的依赖任务另有并发门禁。关闭先停止准入、标记取消并有限等待，不承诺任意阻塞代码都能被强制终止。进程内状态要求 **1 worker、1 实例**；重启丢失会话，当前没有共享数据库与分布式取消。

readiness 合并同时到来的检查，缓存 5 秒；等待超过 3 秒返回 `check_pending`，不为同一检查重复创建线程。它只读检查依赖，不生成答案、拉模型或自动建索引。liveness 不代表答案正确，readiness 也不代表业务质量评测通过。

## 错误与观测

| HTTP 状态 | 常见 error.code | 含义 |
| --- | --- | --- |
| 401 | unauthorized | 缺少或错误的共享密钥 |
| 404 | session_not_found / action_not_found | 会话不存在/过期，或动作无法由本会话处理 |
| 409 | session_busy / run_cancelled / service_disabled | 同会话正在执行、本轮取消，或未启用 service |
| 413 | body_too_large | 实际请求体超限 |
| 422 | invalid_request / context_budget_exceeded / call_budget_exceeded | 参数或上下文/调用预算不满足 |
| 429 | service_busy / session_capacity | 执行或会话容量已满，含 Retry-After |
| 499 | client_disconnected | 内部断连结果；连接已断开，客户端通常收不到响应 |
| 502 | incomplete_model_output | 模型生成截断，拒绝提交 |
| 503 | dependency_unavailable / knowledge_unavailable | 依赖熔断、不可用或来源失效 |
| 504 | request_timeout / deadline_exceeded / dependency_timeout | HTTP、整轮或依赖等待超时 |
| 500 | internal_error | 未预期错误；响应不暴露异常栈和请求输入 |

错误响应包含 `error.code`、安全提示和 `request_id`（action_not_found 仅返回固定 error 对象）；响应头带 `X-Request-ID`。API 日志记录路由模板、状态、耗时及 run_id/调用计数，不记录密钥或完整请求体。已有 Agent 调试日志可能包含问题、工具结果等业务内容，应按运行环境控制访问和保留周期。

离线验证使用 `python -B scripts/manage.py pytest`，HTTPX ASGITransport 加真实工作线程，模型替身覆盖认证、输入约束、会话隔离、容量、取消、超时、断连和关闭。真实模型与真实 HTTP 验收另行记录，见 [工程化检查](../artifacts/api_engineering_v1/checks.json)。这些有限测试不能证明生产高并发性能或所有注入均已防护。
