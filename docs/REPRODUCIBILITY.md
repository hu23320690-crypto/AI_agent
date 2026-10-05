# 环境复现与排查

本页为截至 2026-10-05 的运行说明。阶段安装/交付记录是对应历史版本的验证，见 [DELIVERY_VERIFICATION.md](DELIVERY_VERIFICATION.md)；最新上下文功能验收见 [CONTEXT_MANAGEMENT_VERIFICATION.md](CONTEXT_MANAGEMENT_VERIFICATION.md)。

## 固定环境与模型

已验证 Windows 11 x64、CPython 3.12.2。当前 `requirements.txt` 声明 15 项直接依赖，`requirements-lock.txt` 固定 121 项依赖及传递依赖，不含 pip 本身。历史交付时的 12 项、Runtime 时的 14 项分别属于当时版本；tokenizers 已在锁文件中，现已直接声明。

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

相同标签不保证以后下载内容相同。`doctor` 显示本机实际 digest，并核验聊天模型与 tokenizer 模板身份。默认服务地址为 `http://127.0.0.1:11434`；设置 `OLLAMA_HOST` 时，应指向自己的服务。本地 tokenizer 导出与身份验证只支持本机 host。

当前 `context.yml` 窗口 8192、输出预留 4096、安全余量 256，输入预算 3840 估计单位；推理也占生成额度，提供方标记截断的输出不提交。整轮 Runtime 默认 120 秒，模型单次等待默认 90 秒，HTTP 配置超时为 120 秒；评测案例外部进程上限另行设置。有限重试共享整轮预算，不是每次重新获得 120 秒。

索引当前集合为 `agent_chunks_qwen3_governed_v1`，chunk_size=200、overlap=20；混合 Top-5、每路 20 候选、RRF 常数 60，增加来源准入、每源配额和查询覆盖排序。旧 `agent_chunks_qwen3_v1` 是历史集合。

## 验证顺序

~~~powershell
.\.venv\Scripts\python.exe -B scripts/manage.py doctor --offline
.\.venv\Scripts\python.exe -B scripts/manage.py doctor
.\.venv\Scripts\python.exe -B scripts/manage.py test
.\.venv\Scripts\python.exe -B scripts/manage.py index
.\.venv\Scripts\python.exe -B scripts/manage.py serve
~~~

离线 doctor 检查依赖、配置、资料和缓存，不访问 Ollama。在线 doctor 另核验模型与模板；它不测试答案准确率。`test` 替换模型推理，验证程序行为。

源码首次运行会生成应用向量库；索引包含源路径与版本信息，不应依赖从其他目录拷贝的旧向量库。仓库保留约 2 MB 的 tokenizer 缓存，因为这是离线计数资源。

模型或模板不匹配时，明确确认本机版本后重新导出：

~~~powershell
.\.venv\Scripts\python.exe -B -m model.token_count export
.\.venv\Scripts\python.exe -B -m model.token_count verify
.\.venv\Scripts\python.exe -B scripts/manage.py doctor
~~~

导出只读查询 Ollama 元数据并写本地缓存，不下载模型、不生成回答。变更后重启应用；这会改变当前实验输入身份，旧 run 应保留，新评测使用新目录。身份未验证时采用保守字节回退，可能提前拒绝本可容纳的输入。

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
| 恢复旧评测被拒绝 | 保留旧 manifest 和记录，当前代码用新的 --run；不删除校验信息绕过保护 |

## 复测与归档

~~~powershell
.\.venv\Scripts\python.exe -B -m evaluation.run --run evaluation/results/my_current_experiment --stage all
.\.venv\Scripts\python.exe -B -m evaluation.report --run evaluation/results/my_current_experiment
.\.venv\Scripts\python.exe -B -m evaluation.export --run evaluation/results/my_current_experiment
~~~

report 汇总已有 reviews，不会自动获得语义分数。按固定题目对照实际证据复核，超时、错误和未知样本保留。其他故障、安全、长历史命令及执行快照区别见 [评测入口](../evaluation/README.md)。

GitHub 保留历史评测 snapshot、原始提交结果和精选 artifacts；普通运行日志及 worker 临时文件排除，历史验收所需的回归日志作为精选证据保留。打包命令见主 README，ZIP 内 `DELIVERY_MANIFEST.json` 提供逐文件 SHA256。旧实验和失败不能覆写成新成绩。

