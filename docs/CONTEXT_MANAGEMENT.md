# 上下文管理（更新于 2026-10-07）

按照请求预算、完整轮次裁剪、旧轮摘要、失败降级的顺序实现。沿用已有LangChain图和Runtime，当前轮工具链保持完整；只有成功轮次才一起提交原文、摘要和来源检查。运行验收及已知限制见 [验收记录](CONTEXT_MANAGEMENT_VERIFICATION.md)。

## 1. 每次请求的预算

`agent/context_budget.py` 计入系统提示、可见消息、工具schema、调用参数/结果和response format。主Agent预算检查在动态报告提示之后执行；RAG独立检查最终资料prompt。发送视图明确去掉Ollama会重放的隐藏思考，但不删可见答案或工具调用配对。

默认窗口8192、输出预留4096、安全余量256，输入准入上限3840。模型实际num_ctx较小时取较小窗口；无法容纳预留时明确拒绝。Ollama实际num_predict受输出预留限制，已有更小正数上限保留。主Agent使用context.yml的reasoning_enabled=true；RAG独立使用rag_reasoning_enabled=false，并以只有answer字段的JSON schema约束生成，解析后向用户返回普通文本。2026-10-07复验仍发现本机Qwen模板即使收到reasoning=false也会生成思考，所以不以开关值作为成功关闭思考的证据。受约束的答案格式避免依赖这个模板开关，格式预算一并计入准入；无效结构和截断仍拒绝。摘要单独使用固定JSON格式、reasoning=false、生成上限512，失败则降级。

`model/token_count.py`从已安装qwen3:4b的GGUF元数据重建离线Qwen2 BPE计数器，缓存位于config/tokenizers，受控manifest固定模型digest、模板及tokenizer SHA。模型构造时只读验证本地Ollama模型和模板，成功才给模型写入计数器digest pin。未知模型、非本地host、未验证pin或缓存校验失败时回退UTF-8字节计数。每次准入不联网、不生成、不下载；tokenizers已在原锁文件中，现在列为直接依赖。

文本tokenizer计数外仍加消息、工具和请求封装余量，并保留安全余量；这里没有逐字复现服务端的所有chat/tool模板，不能声称任意请求的精确总token数或绝对硬界。Ollama标签、模板或模型变更后必须重新导出并重启；运行中远端模型变化仍是限制。保守字节回退可能使原本可运行的问题提前拒绝，doctor会报告本地缓存/模型不匹配。

RAG仍召回Top5；最终prompt超过准入上限时，按排名移除末尾完整证据块，不截半段操作步骤。如果单个证据块或当前问题本身仍不能容纳，零模型派发并明确报错。`rag_context_admitted`记录召回和实际选用数量及chunk IDs；旧Top5指标不自动成为预算后效果。

## 2. 按完整轮次裁剪

`TurnMemoryPlan`保留graph原始历史边界，仅替换每次实际发送视图；因此本轮RAG工具结果仍按原始边界提取，旧回答不会被误当本轮答案。历史Human消息划分轮次，AI的并行工具调用与全部ToolMessage返回必须完整配对；legacy非Human前缀整体保留或整体删除。

最近2轮是保留偏好。当近期轮次加当前请求无法容纳时，额外旧轮也进入摘要候选；一个很大的历史轮也可压缩。系统规则、当前用户输入和当前未完成工具链不裁剪，当前链超限直接终止。每次工具结果加入后都会重算预算。

## 3. 低信任结构化摘要

首次请求超过输入预算80%时，按时间顺序将旧的完整轮次分块，前一块的摘要作为下一块的previous_memory。最多尝试3次，预留至少2次主模型调用；摘要模型输出只允许topic、user_requests、reported_results、open_questions四个字段，严格验证类型、长度、重复字段与工具调用。不会先删掉最早目标再摘要。单个完整轮次本身超过摘要输入预算时不拆开，明确记录跳过。

在可选摘要前，程序另存task_references原文引用：首个目标最多512个UTF-8字节、最近两个实质请求各最多256字节。它们不能由摘要模型生成；重复进度记录不会替代目标，当前问题优先。引用超长会带省略号，并非无限或无损记忆。摘要失败时不保存失败模型输出，只保留这些有界原文引用及此前有效摘要。

trace分别记录summary_seen_turns（实际送入已返回模型调用的轮次）、summarized_turns（有效摘要覆盖）、summary_input_omitted_turns（未见轮次）、lost_turns（没有有效摘要保留的轮次）。部分摘要和中止原因单独记录；原文引用不会冒充整轮已经摘要或事实已验证。

摘要作为带低信任标记的Human资料消息发送，不插入系统消息，不授予身份或权限，不取代程序的当前用户/月度报告状态。reported_results仅代表历史报告过的内容，不保证事实真实。摘要仍可能遗漏条件或接受错误事实，本功能不承诺解决投毒。

成功的报告另外提交程序解析的选择条件（月份、字段、比较基准）与最多24份已授权工具记录；不从模型回答或摘要恢复数值。模型请求以低信任Human引用接收上一次已完成报告的绝对选择条件，避免重复重放“下一月”。此引用最多1024个UTF-8字节；预算不足时移除并记录context_report_reference_removed，程序状态保留，当前问题不被可选引用阻塞。会话清空或历史来源失效时同时清除报告状态；失败、取消和提交前撤销不提交本轮查表结果。

来源校验回调继续随会话保留。每个RAG参考捕获原文和完整metadata摘要、绑定store身份，重复证据检查可安全归并；普通应用回调不按名称去重。来源依赖总量上限2048；资料篡改/删除/撤销时原文和摘要整体失效，不能用摘要恢复。保留检查可能比裁剪后严格，旧源撤销仍可能清空整个会话。

## 4. 降级与提交

RAG检索另外接收最多1024字节的低信任用户原文引用，只在对象省略或指代时补充。明确的新对象优先；进度记录不替代目标，模型回答、工具数值与身份字段不写入引用。原始当前问题在生成请求中完整出现一次；可选补充超输入预算时先移除，再按正常规则裁剪完整证据块。

报告当前目标月份必须来自本轮查表，缓存仅用于历史比较基准。查错月份时明确指出本轮未查到指定月份，不用旧记录掩盖错误。

`optional_model_call`只用于无工具摘要，每块单次尝试、共享模型调用预算、容量和进程内熔断；每次局部等待最多10秒，全部摘要合计最多使用剩余时间的三分之一且不超过20秒。局部摘要等待超时可裁剪降级，迟到worker继续占容量直到真实退出，不重叠重试。剩余模型名额不超过2个时跳过摘要，保留主模型机会。

非法摘要、普通生成错误、可选局部超时或依赖熔断时，在确认父run仍有效后降级为完整轮次裁剪；总deadline、取消、调用次数耗尽及来源失效仍终止，绝不恢复已失败run。必要时移除摘要以满足预算，trace记录遗漏轮次和摘要移除。摘要不能容纳也不会豁免主请求的预算。

原文、摘要、来源依赖在`run.complete`内一起提交；清空或身份切换同时取消当前轮并清摘要。局部模型等待超时不保证停止远端请求，生成上限也不代表远端可被强制终止。

模型返回done_reason=length或finish_reason=length/max_tokens时，主Agent在工具派发前拒绝，RAG在返回工具结果前拒绝；本轮历史与摘要不提交。合法JSON但标记截断的摘要也视为摘要失败，不当作完整记忆。该检查依赖提供方如实给出终止元数据，不是通用的答案质量评分器。

## 配置与复验

修改`config/context.yml`后重启Streamlit进程；同时确保`config/rag.yml`的num_ctx符合本机资源。summary_enabled=false可仅使用预算和完整轮次裁剪。

```powershell
.\.venv\Scripts\python.exe -B scripts/manage.py doctor --offline
.\.venv\Scripts\python.exe -B scripts/manage.py doctor
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -B -m evaluation.context_recheck --run evaluation/results/my_context_run
.\.venv\Scripts\python.exe -B -m evaluation.normal_recheck --run evaluation/results/my_context_normal
```

更换本地同名模型或模板后，显式重新导出缓存，再运行doctor并重启应用：

```powershell
.\.venv\Scripts\python.exe -B -m model.token_count export
.\.venv\Scripts\python.exe -B -m model.token_count verify
```

当前真实长历史案例由64轮合成已完成历史起步，随后实际运行摘要和两次真实提问；不把合成历史计为64次真实模型对话。早期v1-v3使用24轮；其中v3改用BPE后未触发摘要，不能作为真实压缩验收。结果保存实际模型输入、输出、num_ctx/num_predict、运行trace及输入快照；语义复核独立保存。既有结果目录不可覆盖，复验需新目录。
