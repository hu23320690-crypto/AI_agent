# 演示指南

本页整理于2026-10-05，安装和tokenizer身份检查见[主README](../README.md)。先执行`doctor`、`index`、`serve`，打开http://127.0.0.1:8501，侧栏用户设1001。本机知识轮次可能需要一分钟，首次模型加载更慢；下面是核对点，不是预录答案。

## 约5—8分钟的展示顺序

1. **介绍任务**：本地知识客服与CSV使用记录，不是实时设备平台。
2. **报告**：“请生成我2025年8月的使用报告。”核对1001、2025-08、覆盖率83%、日均43㎡、主刷50天、HEPA30%。说明数据由程序渲染，模型不自由编造数值。
3. **月份追问**：“那2025年9月呢？”核对覆盖率84%、日均44㎡、主刷45天、HEPA25%，说明重新查了当月数据。
4. **知识追问**：清空对话，问“主刷上缠了长头发，应该怎么清理？”，再问“清理刚才那个部件前需要断开电源吗？”。应给出剪断毛发、勿强拉及清理前断电。展示指代和资料检索。
5. **无记录**：“请生成我2099年1月的使用报告。”应明确查不到，不用已有月份代替。天气未接入时同样不能编造实时数值。
6. **实验取舍**：打开`evaluation/results/optimized_v1/comparison.md`，说明200/400/600字分块实验、混合检索与Top-K变化，展示改善题，也展示4道步骤遗漏的退步题。

## 命令演示

```powershell
.\.venv\Scripts\python.exe -B scripts/manage.py demo
```

运行A01问候、A02报告、A04无记录、A09天气、A11知识两轮、A12工具异常，共6例7次提问。A10月份追问在完整60例评测中有独立记录。

- 输出目录为`artifacts/demo_时间/`。`demo.md`是当次实际答案，`results.jsonl`保存工具、参数和耗时。
- 各案例独立会话，A11两轮共享历史。
- A12只注入工具连接异常，不关闭Ollama。
- 指定`--output artifacts/目录`可断点续跑相同版本。已有失败也会跳过，重测请换新目录。
- 退出码0只代表全部案例正常执行，不等于语义质量全过；人工检查事实和完整性。
- `manage.py pytest`运行完整离线回归与 API 测试，`test`保留原 unittest 入口；均不能与真实模型评测混用。

## HTTP 服务展示

按 [API 文档](API.md)生成自己的密钥，运行 `manage.py api`，在 `/docs` 创建用户 1001 的会话并提交报告问题。展示 request_id / run_id、独立会话、healthz 与 readyz 的区别，以及取消和容量错误。同步 Agent 在受限线程中执行，HTTP 控制使用 asyncio；取消不代表强杀远端模型。

容器展示以 [部署说明](DEPLOYMENT.md)与 [GitHub Checks](https://github.com/hu23320690-crypto/AI_agent/pull/1/checks)为证据：Linux 镜像构建、非 root 启动与健康检查，明确容器 CI 没有运行模型。实际 HTTP 问答输出见 [本轮记录](../artifacts/api_engineering_v1/live_smoke.json)；连续追问本次拒答，保留为语义未通过，不能展示成成功案例。

## 面试中值得展开的内容

报告曾把剩余寿命改写成记录没有的进度和日期，因此采用查询状态驱动、结构化渲染。知识工具曾明确拒答，Agent却补出品牌电话，因此增加本轮工具结果直出。检索方面，较大分块未必命中更多，词法和向量融合才在历史开发题集上取得更好结果。

代码与评测是AI辅助协作成果。应能独立解释入口、配置、评分口径，复现失败和运行测试，再将掌握的部分作为项目经验讲述。

## Runtime与上下文展示

运行控制可展示[第四步验收](RUNTIME_STAGE4_VERIFICATION.md)中的7类故障，解释共享预算、重试、熔断、取消和迟到不得提交。长对话展示[上下文验收](CONTEXT_MANAGEMENT_VERIFICATION.md)：64轮为合成历史，随后真实执行摘要与两次提问，首请求消息129降至6。摘要有损；长历史v4断电追问因本次证据未召回而拒答，不能计为任务成功。

最终配置安全评测23条均记录、22条完成、C01截断未知；错误事实采纳2/2与工具文本污染2/2仍是失败。主README检索和问答指标属于历史实验。


## S7 售后服务真实界面演示

![service + react 的真实界面](images/service_demo.gif)

本节录制于 2026-10-16，代码基于 main `c89a00b`，没有修改应用、提示或配置。GIF 是真实截图的节选，等待时间已压缩，左侧为编辑说明，右侧为原界面等比例保留的截图区域；只统一裁去顶部工具栏与底部空白，没有替换回答或卡片文字。业务对象和用户均为合成演示数据。

使用 `AGENT_TOOLSET=service`、`AGENT_MODE=react`，侧栏会话用户设为 **1006**。输入 dev **SV-D02** 的问题（不是 test 或注入题）：

> 我的旗舰机提示E11，已经移离楼梯。我想查一下处理方法和保障情况，1月15日16点到18点能安排检查吗？

核对流程：提交问题 → 回答中的设备、E11、保修和可约时段事实块 → 聊天主区域的“待确认”卡片 → 点击“确认” → 返回工单/预约编号，卡片状态为“已执行”。确认与拒绝是页面触发的代码操作，不由模型代点。这里确认只影响隔离的合成数据库。

本次回答的知识资料部分为“知识库中没有可用参考资料，无法据此回答”；开头“已生成预约”也不够准确，实际状态仍为待确认。GIF 保留这两处问题。它展示两段式交互机制，不能当作完整任务质量通过，S5 成绩仍以 [正式报告](SERVICE_AGENT_S5_REPORT.md) 为准。

### 本次启动命令

为保护原工作区数据库，录制在仓库外的临时目录运行同一提交的原样源码；复制已有索引，重新初始化独立种子库。实际工作目录位于聊天工作区的 `work/s7/demo_checkout`；下面用临时目录变量表达同一组命令，避免要求复现者使用本机路径。先在仓库根目录打开 PowerShell，完成 [README 的依赖、模型和索引准备](../README.md#快速开始)。

```powershell
$sourceRoot = (Get-Location).Path
$python = Join-Path $sourceRoot '.venv/Scripts/python.exe'
$mediaRoot = Join-Path ([IO.Path]::GetTempPath()) ('agent-s7-' + [guid]::NewGuid().ToString('N'))
$demoRoot = Join-Path $mediaRoot 'demo_checkout'
New-Item -ItemType Directory -Path $demoRoot -Force | Out-Null
git archive --format=zip --output="$mediaRoot/demo_source.zip" c89a00b app.py agent rag utils model config prompts service_desk service_kb data scripts
Expand-Archive -LiteralPath "$mediaRoot/demo_source.zip" -DestinationPath $demoRoot
Copy-Item -LiteralPath "$sourceRoot/rag/chroma_db" -Destination "$demoRoot/rag/chroma_db" -Recurse
Push-Location $demoRoot
& $python -B -c "from service_desk.db import init_db; init_db('service_data/service.db')"
$env:AGENT_TOOLSET = 'service'
$env:AGENT_MODE = 'react'
$env:PYTHONUTF8 = '1'
& $python -B -m streamlit run app.py --server.address=127.0.0.1 --server.port=8507 --server.headless=true --browser.gatherUsageStats=false
# Ctrl+C 停止后：Pop-Location
```

打开 `http://127.0.0.1:8507`，展开侧栏设置用户，收起侧栏再输入问题。先检查卡片内容再点确认；卡片到期后不要继续确认。数据库、截图原帧和日志只留本地，不提交，也不覆盖原数据库。相同问题的模型文字可能不同，业务日期来自固定合成种子，并不表示当前真实预约日期。

### 截图与 GIF 合成

本次使用 Codex 浏览器控制的 `getScreenshot()` 获取原生 389×669 截图，未调整应用布局或浏览器视口。在各状态下保存截图，例如 `await mediaFs.writeFile(frameDir + '/05-pending.jpg', await demoTab.getScreenshot())`；复现者也可在浏览器中按以下状态截图，以同名文件保存在临时 `frames/` 目录。所有帧检查为无本机路径、用户名、令牌或密钥。

| 原帧文件 | 捕捉时机 |
| --- | --- |
| 02-question.jpg | 已输入问题、尚未发送 |
| 07-facts.jpg | 回答完成，滚动至问题与回答开头 |
| 09-facts-body.jpg | 滚动至设备、错误码、保修和时段事实块 |
| 05-pending.jpg | 确认前，卡片及确认/拒绝按钮完整可见 |
| 06-executed.jpg | 点击确认后，工单/预约编号与已执行状态 |

只在仓库外创建媒体虚拟环境；本次使用 Pillow 12.3.0，不改 requirements：

```powershell
& $python -m venv "$mediaRoot/media_env"
& "$mediaRoot/media_env/Scripts/python.exe" -m pip install Pillow==12.3.0
# 将下方代码保存为临时目录中的 compose_gif.py；frames/ 与该文件同级
& "$mediaRoot/media_env/Scripts/python.exe" -B "$mediaRoot/compose_gif.py"
```

下面是实际合成逻辑，输出路径改为临时目录；将检查后的 service_demo.gif 复制到 `docs/images/` 即可。字体使用 Windows 自带微软雅黑。

```python
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import json

scratch=Path(__file__).parent
font_path=r'C:\Windows\Fonts\msyh.ttc'
def font(n): return ImageFont.truetype(font_path,n)
stages=[
 ('02-question.jpg','01 / 提交请求',['dev · SV-D02 / user 1006','旗舰机提示 E11，已移离楼梯。','查询处理方法和保障情况，','请求 1 月 15 日 16–18 点检查。'],'service + react · 独立合成数据库',3500),
 ('07-facts.jpg','02 / 返回事实',['设备、错误码与保修信息','由本轮工具结果汇总。','开头“已生成预约”不够准确；','实际仍需确认卡片。'],'真实回答保留措辞问题',4500),
 ('09-facts-body.jpg','03 / 核对事实块',['设备 D-1006-01 / SV-400','E11：跌落感应异常','整机在保；不承诺免费。','列出 1 月 15 日可约时段。'],'本次资料不可用提示原样保留',6500),
 ('05-pending.jpg','04 / 待确认卡片',['卡片显示在聊天主区域。','核对设备、时段、费用说明。','点击“确认”后，','由确定性代码提交。'],'模型只生成提议',4500),
 ('06-executed.jpg','05 / 已执行',['页面返回工单和预约编号。','卡片状态更新为“已执行”。','本次操作只写入','隔离的合成演示数据库。'],'确认 → 事务 / 幂等 / 审计',5000),
]
frames=[]
for i,(file,title,lines,foot,duration) in enumerate(stages):
 im=Image.new('RGB',(1100,720),'#edf2f5'); d=ImageDraw.Draw(im)
 d.rectangle((0,0,1100,7),fill='#087f83')
 d.text((44,42),'售后服务 Agent',font=font(34),fill='#142d42')
 d.text((46,95),'真实 Streamlit 界面 · 合成演示数据',font=font(18),fill='#557083')
 d.rounded_rectangle((44,160,606,223),14,fill='#dcebed')
 d.text((62,174),title,font=font(27),fill='#086b72')
 for j,line in enumerate(lines): d.text((48,269+j*52),line,font=font(24),fill='#233f53')
 d.text((48,530),foot,font=font(20),fill='#086b72')
 d.text((48,583),'节选截图；等待时间已压缩。',font=font(17),fill='#607889')
 d.text((48,615),'默认组合仍为 legacy + react。',font=font(17),fill='#607889')
 for j in range(5): d.rounded_rectangle((48+j*105,670,140+j*105,677),3,fill='#087f83' if j<=i else '#c9d7df')
 # Same crop on every real screenshot: browser toolbar and empty lower margin only.
 shot=Image.open(scratch/'frames'/file).convert('RGB').crop((0,56,389,626))
 d.rounded_rectangle((641,69,1062,687),18,fill='#14202d')
 im.paste(shot,(657,94))
 frames.append(im.quantize(colors=192))
out=scratch/'service_demo.gif'
frames[0].save(out,save_all=True,append_images=frames[1:],duration=[s[-1] for s in stages],loop=0,optimize=True,disposal=2)
print(json.dumps({'gif_bytes':out.stat().st_size,'frames':len(frames),'size':[1100,720],'duration_ms':sum(s[-1] for s in stages)}))
```

成品为 **595075 字节、5 帧、1100×720、24 秒循环**，小于 5 MB。原帧与合成环境不进入仓库。

## S7 plan 轨迹来源

![原始 dev 轨迹摘录](images/plan_trace.svg)

- 原始记录：`evaluation/results/service_s3e_r4_plan/raw/SV-D02.json`，第一个用户轮，`user_id=1006`，`mode=plan`。这是已有 S3-E dev 运行，本阶段没有为画图重跑正式评测。
- 原文件 SHA256：`556e3990c8762eeefec9e93fb3e303196a969260a351009560c793e1dac3b27e`。原记录留在本地，不提交 `evaluation/results` 文件。
- 图为该文件的人工排版摘录，包含 `turns[0].model_outputs` 的两份计划、`runtime.events` 的校验/验证事件、`tool_calls`、`proposals` 和 `answer`；下表保留关键字段供对照。图内时间为该轮相对秒数，均来自原记录。

| 原始位置 | 摘录 |
| --- | --- |
| model_outputs[0] | goals 为 diagnose / warranty / book；步骤为 list_my_devices、lookup_error_code、check_warranty、find_service_slots、propose_service_visit，未含知识步骤 |
| runtime.events | 7.344 秒：plan_validation，ok=false，codes=[P10]；同刻 plan_replan，reason=validation |
| model_outputs[1] | 增加 knowledge 目标及 rag_summarize，六步执行顺序见图；其余目标为 diagnose / book |
| runtime.events | 17.609 秒：plan_validation，ok=true，codes=[] |
| tool_calls[0–2] | 设备 D-1006-01 / SV-400；E11 跌落感应异常、requires_visit=true、self_fixable=false；整机保修到 2027-10-02，业务日期 2026-01-12 |
| tool_calls[3] | rag_summarize 查询 E11错误的处理方法，返回远离台阶、清洁外部感应窗口、不遮挡、不在高处试验、需服务人员检查 |
| tool_calls[4] | find_service_slots，from_date=2026-01-15，返回六个时段；目标时段 S-east-20260115-3 |
| tool_calls[5] | propose_service_visit，device_id=D-1006-01、error_code=E11、slot_id=S-east-20260115-3；description=我的旗舰机提示E11,已经移离楼梯 |
| proposals | action_id=358601db-f13d-4ab5-a466-dc5fb9aa3336，status=pending；args_sha256=bb8fa8be58a48ea5da7b232728c48a0513674bf872af2f2247be5e5b74c9c374 |
| runtime.events | 31.781 秒：plan_verify，missing_goals=[]；runtime.plan_fallback=false |
| answer | “已为你准备预约的确认卡片。”以及“请在确认卡片上确认，确认前不会提交。” |

P10 的实际校验含义见 [`service_desk/signals.py`](../service_desk/signals.py)：用户要求说明时，必须有 knowledge 目标及 rag_summarize 步骤。`missing_goals=[]` 是结构覆盖检查，不能代替内容与忠实度评审。该 plan 轨迹止于待确认；GIF 则是本阶段另一次 service + react 交互，不能混成同一轮记录。
