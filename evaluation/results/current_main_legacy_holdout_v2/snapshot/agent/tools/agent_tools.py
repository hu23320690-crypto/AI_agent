import json
from datetime import date
from functools import lru_cache
from langchain.tools import ToolRuntime, tool
from utils.records import load_records, normalize_month

@lru_cache(maxsize=1)
def get_rag_service():
    # Reports and greetings do not need a running embedding service.
    from rag.rag_service import RagSummarizeService
    return RagSummarizeService()

@tool("rag_summarize", description="检索机器人知识库并回答产品、故障、保养问题。")
def rag_summerize(query: str) -> str:
    return get_rag_service().rag_summarize(query)

@tool(description="查询天气可用性。当前未接入实时天气，不能返回实时温度或湿度。")
def get_weather(city: str) -> str:
    return f"尚未接入实时天气服务，无法查询{city}的天气。请用户提供天气或湿度信息。"

@tool(description="获取用户在页面或启动参数中明确设置的城市，未设置时返回缺失说明。")
def get_user_location(runtime: ToolRuntime[dict]) -> str:
    return runtime.context.get("city") or "用户尚未设置城市，请询问用户。"

@tool(description="获取当前会话明确设置的演示用户 ID，未设置时返回缺失说明。")
def get_user_id(runtime: ToolRuntime[dict]) -> str:
    return runtime.context.get("user_id") or "尚未设置用户 ID，请先在页面设置演示用户 ID。"

@tool(description="获取系统当前月份，返回 YYYY-MM；历史报告应使用用户指定月份。")
def get_current_month() -> str:
    return date.today().strftime("%Y-%m")

@tool(description="按当前会话用户 ID 和月份查询本地演示使用记录，返回 ok 或 not_found 状态及数据。")
def fetch_external_data(user_id: str, month: str, runtime: ToolRuntime[dict]) -> str:
    context = runtime.context
    context["report"] = False
    context["report_data"] = None
    context["lookup_result"] = None
    selected_user = context.get("user_id")
    if not selected_user:
        raise ValueError("请先在页面设置演示用户 ID。")
    if user_id.strip() != selected_user:
        raise ValueError("查询用户与当前会话不一致，请先切换页面中的演示用户 ID。")
    month = normalize_month(month)
    record = load_records().get((selected_user, month))
    if record is None:
        result = {
            "status": "not_found", "user_id": selected_user, "month": month,
            "message": "该用户在指定月份没有使用记录，不能生成该月使用情况结论。",
        }
        context["lookup_result"] = result
        return json.dumps(result, ensure_ascii=False)
    result = {"status": "ok", "user_id": selected_user, "month": month, "data": record}
    context["report_data"] = result
    context["lookup_result"] = result
    # The transition must not depend on the LLM remembering a second tool call.
    context["report"] = True
    return json.dumps(result, ensure_ascii=False)

@tool(description="在本轮成功查询到使用记录后启用报告模式；没有数据时不能启用。")
def fill_context_for_report(runtime: ToolRuntime[dict]) -> str:
    if not runtime.context.get("report_data"):
        raise ValueError("本轮尚未查询到有效记录，不能生成报告。")
    runtime.context["report"] = True
    return "报告资料已准备完成，请根据查询到的记录生成报告。"
