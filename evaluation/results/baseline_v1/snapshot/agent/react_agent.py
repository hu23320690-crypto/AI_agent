import argparse
import sys
from pathlib import Path
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware
from langchain_core.messages import AIMessage, HumanMessage
from model.factory import chat_model
from utils.model_output import final_answer
from utils.report_render import render_lookup
from agent.tools.agent_tools import (
    rag_summerize, get_weather, get_user_location, get_user_id,
    get_current_month, fetch_external_data, fill_context_for_report,
)
from agent.tools.middleware import monitor_tool, log_before_model, report_prompt_switch

class ReactAgent:
    def __init__(self, user_id: str = "", city: str = "", *, model=None):
        self.user_id = user_id.strip()
        self.city = city.strip()
        self.messages = []
        self.agent = create_agent(
            context_schema=dict,
            model=model if model is not None else chat_model,
            tools=[rag_summerize, get_weather, get_user_id, get_current_month,
                   get_user_location, fill_context_for_report, fetch_external_data],
            middleware=[monitor_tool, log_before_model, report_prompt_switch,
                        ModelCallLimitMiddleware(run_limit=8, exit_behavior="error")],
        )

    def clear_history(self):
        self.messages = []

    def execute_stream(self, query: str):
        """Yield the final answer, retaining the existing API (not token streaming).

        Each instance owns its history. Commit only completed turns so a model
        failure cannot leave dangling tool calls in the next conversation turn.
        """
        if not query.strip():
            raise ValueError("请输入问题。")
        context = {"user_id": self.user_id, "city": self.city,
                   "report": False, "report_data": None,
                   "lookup_result": None, "tool_errors": {}}
        result = self.agent.invoke(
            {"messages": [*self.messages, HumanMessage(content=query)]},
            config={"recursion_limit": 100},
            context=context,
        )
        final = result["messages"][-1]
        if not isinstance(final, AIMessage) or final.tool_calls:
            raise RuntimeError("模型没有生成完整回答，请重试。")
        if context["lookup_result"] is not None:
            text = render_lookup(context["lookup_result"])
        elif context["tool_errors"]:
            details = "；".join(dict.fromkeys(context["tool_errors"].values()))
            text = "本次查询未完成，无法提供可靠的查询结论。" + details
        else:
            text = final_answer(final.text)
        result["messages"][-1] = final.model_copy(update={"content": text})
        self.messages = result["messages"]
        yield text

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="扫地机器人客服")
    parser.add_argument("query", nargs="*", default=[])
    parser.add_argument("--user-id", default="")
    parser.add_argument("--city", default="")
    args = parser.parse_args()
    agent = ReactAgent(user_id=args.user_id, city=args.city)
    for chunk in agent.execute_stream(" ".join(args.query) or "扫地机器人应该如何保养？"):
        print(chunk, flush=True)
