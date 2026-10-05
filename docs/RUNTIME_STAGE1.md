# Runtime 第一步：统一执行控制

状态：第一步已实现。以下保留第一步验收时的能力边界；当前重试与熔断扩展见 [第二步说明](RUNTIME_STAGE2.md)，来源审批、投毒防护仍属于后续阶段，详见 [实施计划](RUNTIME_HARNESS_PLAN.md)。

## 运行路径

```text
ReactAgent.execute_stream
  └─ RunContext：同一 run_id / deadline / 计数 / 终态
      └─ ExecutionRuntime.run
          ├─ monitor_model → model 名额与调用预算
          └─ monitor_tool → tool 名额与调用预算
              └─ RagSummarizeService
                  ├─ retrieval → embedding 名额与单独计数
                  └─ invoke_rag_model → 同一 model 名额与调用预算
```

保留 LangChain 图、原有 7 个工具和同步 execute_stream 接口。execute_stream 仍输出完整最终回答，没有变成 token 流。

## 配置

`config/runtime.yml` 是执行预算配置，修改后重启应用生效。默认：

| 项目 | 默认值 | 定义 |
| --- | --- | --- |
| 整轮时限 | 120 秒 | 从执行入口起算，包括排队和嵌套步骤，monotonic 时钟 |
| 单次模型等待 | 90 秒 | 同时受整轮剩余时间限制 |
| 单次工具等待 | 110 秒 | 包含工具内检索、模型等待 |
| 检索 / embedding 等待 | 100 / 90 秒 | 首次自动入库也消耗整轮预算 |
| 模型次数 | 8 | 外层 Agent 和 RAG 回答合计，不再只是外层图次数 |
| 工具次数 | 12 | 每轮所有工具调用合计 |
| embedding 次数 | 16 | 每次 embedding 批请求计一次，独立于生成模型预算 |
| 输入 / 输出 / 工具参数长度 | 8000 / 16000 / 4000 字符 | 输出在返回执行边界时检查，不能限制服务端已生成 token 数 |
| 进程并发 | run=2、model=2、tool=4、retrieval=2、embedding=2 | 各类独立门控，避免嵌套调用在同一线程池互相等待 |

计数在获得名额、启动工作前预占，所以是尝试预算上界，不应作为精确计费统计。排队超时未启动的操作不消耗调用次数。

`config/rag.yml` 的 request_timeout=120 仍是底层 I/O 超时；它与执行层的等待时限含义不同。本阶段不新增自动重试，不改变模型生成参数。

## 取消、会话与超时

`agent.cancel_current()` 可由其他线程调用，取消当前轮并保留此前成功历史；`agent.clear_history()` 取消当前轮并清空历史。每个实例只允许一轮调用，重入返回 RunBusy。

前端在切换身份或清空会话时调用 clear_history，并展示 RuntimeControlError 的具体提示。没有新增“生成时点击即可强制停止 Ollama”的按钮；Streamlit 同步脚本的即时交互受其重运行机制限制。取消 API 的并发行为由离线测试验证。

只有执行仍有效且完整结束时，才原子提交新历史。模型/工具的迟到结果、预算超限、截止时间耗尽和取消均不能提交会话。控制异常穿过工具错误处理，终止整轮，不作为普通观察值送回模型继续循环。

## 为什么后台任务没有直接被杀掉

现有库和工具是同步接口，本实现使用有限并发的 daemon 线程隔离等待。调用者可在截止时间或取消后返回；后台阻塞函数可能仍继续运行。它占用的名额直到函数实际退出后才归还。

- 不保证停止远端推理，也不保证本机同步函数即时退出。
- I/O 超时不等于远端总推理时限；持续收到数据的远端请求可能持续更长时间。
- 若依赖永久挂起，名额可能一直被占用，后续请求会排队超时；强制恢复需独立进程隔离或重启应用。
- 这不是 OS 安全沙箱。未来涉及外部写操作需额外做幂等和补偿，丢弃返回值不能撤销写操作。
- 首次入库可能超出交互预算，建议先执行 `scripts/manage.py index`；超时不回滚已经完成的索引批次，下一次初始化会按已有机制重试未完整入库的文件。
- 控制针对同步 Agent / rag_summarize 路径。直接访问底层 chain、异步 aembed_*、批量索引管理等低层接口不自动建立 RunContext；不要把它们当作受控用户入口。
- 并发名额是进程内限制；多进程部署不共享限额，不是分布式限流。

## 轨迹

Agent 最近一轮摘要在 `agent.last_run`，也写入现有日志的 `[runtime]` 行。包含 run_id、状态、耗时、预算计数、调用事件与错误类型；不写完整问题、模型回答、工具参数和文档原文。

摘要表示调用者返回时的状态，不会追写后台线程的后续事件；succeeded 表示执行完成，不代表答案正确。既有异常日志与评测原始回答仍沿用原有用途，不能将新 trace 的脱敏约定误认为全项目日志已完成安全审计。

## 验证命令

```powershell
.\.venv\Scripts\python.exe -B scripts/manage.py test
.\.venv\Scripts\python.exe -B scripts/manage.py doctor
# 单独运行新增控制测试（不需要 Ollama）
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_runtime.py -v
# 小规模真实 Agent 验证；每次代码变化使用新的结果目录
.\.venv\Scripts\python.exe -B -m evaluation.run --stage agent --run artifacts/runtime_stage1_smoke --ids A01 A02
.\.venv\Scripts\python.exe -B -m evaluation.run --stage agent --run artifacts/runtime_stage1_knowledge_smoke --ids A11
```

原有业务测试 36 项。新增测试覆盖：共享模型预算及回调传递、工具预算、阻塞超时、取消/清空、迟到结果、输入输出长度、工具参数长度、trace 数据最小化、超时后名额保留与恢复、共享截止时间、embedding 单次计数、非法配置，以及页面错误反馈。

实际验收记录见 [RUNTIME_STAGE1_VERIFICATION.md](RUNTIME_STAGE1_VERIFICATION.md)。旧 60 例评测、holdout 和第四阶段交付结果保留原始版本，本次不宣称回答准确率提升。
