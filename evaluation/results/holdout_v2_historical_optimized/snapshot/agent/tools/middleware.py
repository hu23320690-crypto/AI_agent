import json
from datetime import date
from typing import Callable
from langchain.agents import AgentState
from langchain.agents.middleware import ModelRequest, wrap_tool_call, before_model, dynamic_prompt
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import ToolMessage
from langgraph.runtime import Runtime
from langgraph.types import Command
from utils.logger_hander import logger
from utils.prompt_loader import load_report_prompts, load_system_prompts

@wrap_tool_call
def monitor_tool(request: ToolCallRequest,
                 handler: Callable[[ToolCallRequest], ToolMessage | Command]) -> ToolMessage | Command:
    name = request.tool_call["name"]
    errors = request.runtime.context.setdefault("tool_errors", {})
    logger.info("[tool monitor]执行工具:%s 参数:%s", name, request.tool_call["args"])
    try:
        result = handler(request)
        if isinstance(result, ToolMessage) and result.status == "error":
            logger.warning("[tool monitor]工具返回错误:%s", result.content)
            errors[name] = "工具参数有误或相关服务暂不可用，请检查输入后重试。"
        else:
            errors.pop(name, None)
            logger.info("[tool monitor]工具%s调用成功", name)
        return result
    except Exception as exc:
        logger.exception("工具%s调用失败", name)
        detail = str(exc) if isinstance(exc, ValueError) else "服务暂时不可用，请稍后重试。"
        errors[name] = detail
        return ToolMessage(
            content=f"工具执行失败：{detail} 不得据此编造结果，不要重复调用相同参数。",
            name=name, tool_call_id=request.tool_call["id"], status="error",
        )

@before_model
def log_before_model(state: AgentState, runtime: Runtime):
    logger.info("[log_before_model]即将调用模型，带有%d条消息", len(state.get("messages", [])))

@dynamic_prompt
def report_prompt_switch(request: ModelRequest) -> str:
    context = request.runtime.context or {}
    prompt = load_report_prompts() if context.get("report") else load_system_prompts()
    session = {"当前日期": date.today().isoformat(),
               "演示用户ID": context.get("user_id") or "未设置",
               "用户设置的城市": context.get("city") or "未设置"}
    prompt += "\n当前会话信息：" + json.dumps(session, ensure_ascii=False)
    if context.get("report") and context.get("report_data"):
        prompt += "\n本轮已查询的报告资料：" + json.dumps(context["report_data"], ensure_ascii=False)
    return prompt
