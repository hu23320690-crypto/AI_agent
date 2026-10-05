# Runtime 第二步：有限重试与依赖熔断

实现位置：`agent/runtime/resilience.py`。验收见 [RUNTIME_STAGE2_VERIFICATION.md](RUNTIME_STAGE2_VERIFICATION.md)。

## 接入位置和范围

外层 Agent 生成、RAG 内部生成，以及同步 embedding 批请求都通过 `dependency_call`。每次真实尝试都通过第一步的 `runtime_call`，所以重试也占用同一轮调用预算及并发名额。

整个工具、检索链和 Agent 图不自动重跑。现有 CSV/天气/会话工具仍走原来的单次工具入口；未来外部工具只有在最底层依赖请求处接入适配器，并明确 `retry_safe=True` 才启用重试。这个参数只能由开发者的代码指定；它不实现幂等键或事务补偿。未显式声明可安全重试的操作默认只尝试一次。

通过 ContextVar 拒绝嵌套依赖重试入口，避免工具层和模型层各自重试导致次数相乘。当前固定版本 Ollama SDK 的请求路径未配置自动重试；以后更换 SDK/调用 `.with_retry()` 时需重新检查，不能假设能拦截外部库内部所有重试。

范围为同步用户入口。没有 RunContext 的离线索引管理和底层 chain 评测仍执行一次，不会悄悄增加重试；异步接口不在本阶段保证范围内。

## 默认策略

配置 `config/resilience.yml`，修改后重启应用：

| 配置 | 默认 | 含义 |
| --- | --- | --- |
| max_attempts | 2 | 包含第一次；最多额外重试 1 次，配置上限 5 |
| base_delay_seconds | 0.5 | 指数退避初始上限 |
| max_delay_seconds | 2 | 本地退避上限；从 0 到上限随机取等待时间 |
| minimum_samples | 3 | 滚动窗口内最小有效样本数 |
| failure_threshold | 3 | 同一窗口内失败数，必须同时满足最小样本数 |
| window_seconds | 60 | 滚动窗口长度 |
| recovery_seconds | 15 | 熔断等待后允许恢复探测 |

统计粒度是依赖的真实尝试，重试也算一个样本，不是用户问题数。当前是绝对失败数阈值，尚无自适应阈值或生产流量校准。成功返回是一次正常样本；参数/权限/取消等中性结果不进入故障窗口。

同一逻辑请求的所有尝试和退避共用固定截止时间 `min(整轮 deadline, 首次调用时间 + 该类调用上限)`，不会每重试一次就重新获得完整90秒。预算不足时直接停止；退避期间支持取消。

httpx HTTPStatusError 若保留 Retry-After，支持秒数及HTTP日期，并等待至少该时间；如果剩余时间不足，直接结束，不提前重试。当前 Ollama SDK 的 ResponseError 不保留响应头，此时只能使用本地退避，不能声称已经遵循丢失的 Retry-After。

## 错误分类

| 情况 | 自动重试 | 计入依赖故障 |
| --- | --- | --- |
| 已返回的连接失败、读写网络异常、连接/读写超时 | 仅 retry_safe 请求，在预算内重试 | 是 |
| HTTP 408、429、500、502、503、504 | 同上 | 是 |
| 401、403、404、422、参数错误、代码异常 | 否 | 否 |
| 正常返回查无记录 | 否 | 否，作为正常样本 |
| 本地线程/连接池排队超时 | 否 | 否 |
| 执行层已派发请求的单次等待超时 | 否，底层线程可能还在运行 | 是，且只记一次 |
| 整轮截止时间、父工具超时、主动取消、预算耗尽 | 否 | 不据此断言子依赖故障 |

等待超时与底层 HTTP 客户端已经抛出的 ReadTimeout 含义不同。前者保留第一步的终止整轮行为，不制造重叠重试；后者发生时本地请求函数已经退出，可在安全声明下有限重试。两者都不保证远端已经停止计算，模型推理可能带来重复计算成本。

## 熔断状态和并发

```text
CLOSED --窗口内失败数及样本数达到阈值--> OPEN
OPEN --冷却结束，下次请求到来--> HALF_OPEN
HALF_OPEN --单个探测成功--> CLOSED
HALF_OPEN --探测发生依赖故障--> OPEN（重新冷却）
```

HALF_OPEN 同时只放行一个请求，不启动定时探测线程，也不关闭或重启 Ollama。探测自身不自动重试。取消/参数错误只释放探测名额，保持 HALF_OPEN，不假称服务已经恢复。

默认 ExecutionRuntime 为进程共享单例，所以不同 Agent 会话共享断路器。依赖键按调用通道、端点和模型标识区分：同一模型的外层 Agent 与 RAG 共享 chat 断路器，embedding 单独维护。端点（可能含凭据）只用于散列，不以原文写入 trace。

锁控制状态转换与探测许可；许可带有状态代次，过期请求的迟到成功/失败不能改写已经变化的断路器。取得许可后若排队期间其他请求触发熔断，会在实际操作前再次校验许可。重启清空状态；多进程不共享熔断状态，不是分布式高可用实现。

## 降级与轨迹

熔断返回 CircuitOpen；可重试依赖故障耗尽尝试后返回 DependencyUnavailable。两者都是 RuntimeControlError，穿过工具错误处理直接停止整轮，页面显示依赖不可用，并保留此前成功历史。不会让外层模型基于失败结果生成“有知识库依据”的答案。

控制异常立即发布到共享 RunContext，其他并行工具的等待方和根调用者会停止等待；底层尚未退出的线程继续保留其并发名额。这样不依赖 LangChain 图先等待所有并行分支结束才能把失败反馈给用户。

trace 增加 dependency_failed、retry_scheduled、circuit_transition、circuit_rejected，包含依赖散列键、尝试次数、等待时间与状态；不写原始异常内容、凭据、问题或文档。沿用第一步调用者结束时快照的边界。

## 验证与复现

```powershell
.\.venv\Scripts\python.exe -B scripts/manage.py doctor
.\.venv\Scripts\python.exe -B scripts/manage.py test
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_resilience.py -v
```

故障验证使用假时钟、受控阻塞操作、真实 LangChain 图和 httpx.MockTransport；后者经过真实 ChatOllama/Ollama SDK 的 HTTP 503 错误转换后恢复为流式响应。不会关闭用户 Ollama 服务或修改知识库来制造故障。

第三步的 RAG 来源管理、撤销、工具权限和第四步投毒攻击评测尚未实现。第二步不提供投毒防护，也不增加事实准确率保证。
