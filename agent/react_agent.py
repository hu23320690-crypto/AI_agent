import argparse
import json
import sys
from pathlib import Path
from threading import Lock, RLock
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from model.factory import chat_model
from utils.model_output import final_answer
from rag.security import KnowledgeAccessError
from utils.report_render import render_lookup
from utils.logger_hander import logger
from agent.runtime import RunContext, RunBusy, load_limits, default_runtime, runtime_call
from agent.context_budget import load_context_policy
from agent.context_memory import TurnMemoryPlan
from agent.tools.agent_tools import (
    rag_summerize, get_weather, get_user_location, get_user_id,
    get_current_month, fetch_external_data, fill_context_for_report,
)
from agent.tools.middleware import monitor_tool, monitor_model, log_before_model, report_prompt_switch, manage_context

class ReactAgent:
    def __init__(self, user_id: str = "", city: str = "", *, model=None, limits=None, executor=None,
                 context_policy=None, summary_model=None):
        self.user_id = user_id.strip()
        self.city = city.strip()
        self.messages = []
        self._history_checks = []
        self.summary = None
        self.context_policy = context_policy or load_context_policy()
        selected_model = model if model is not None else chat_model
        self.summary_model = summary_model if summary_model is not None else selected_model
        self.limits = limits or load_limits()
        self.executor = executor or default_runtime()
        self.last_run = None
        self._active_run = None
        self._turn_lock = Lock()
        self._state_lock = RLock()
        self.agent = create_agent(
            context_schema=dict,
            model=selected_model,
            tools=[rag_summerize, get_weather, get_user_id, get_current_month,
                   get_user_location, fill_context_for_report, fetch_external_data],
            middleware=[monitor_tool, log_before_model, report_prompt_switch, manage_context, monitor_model],
        )

    def clear_history(self):
        with self._state_lock:
            self.cancel_current()
            self.messages = []
            self._history_checks = []
            self.summary = None

    def cancel_current(self):
        """May be called from another thread; does not kill remote inference."""
        with self._state_lock:
            if self._active_run is not None:
                self._active_run.cancel()
                return True
            return False

    def execute_stream(self, query: str, *, run_context: RunContext | None = None):
        """Yield the final answer, retaining the existing API (not token streaming).

        Each instance owns its history. Commit only completed turns so a model
        failure cannot leave dangling tool calls in the next conversation turn.
        A trusted caller may create the run before scheduling this generator,
        preserving cancellation and deadlines while its worker is queued.
        """
        if run_context is not None:
            if not isinstance(run_context, RunContext):
                raise TypeError("run_context must be a RunContext")
            if run_context.limits != self.limits or run_context.executor is not self.executor:
                raise ValueError("run_context must use this agent's limits and executor")
        if not query.strip():
            raise ValueError("请输入问题。")
        if not self._turn_lock.acquire(blocking=False):
            raise RunBusy("当前会话已有任务运行，请等待或取消后重试。")
        run = run_context if run_context is not None else RunContext(self.limits, self.executor)
        try:
            with self._state_lock:
                self._active_run = run
                run.check()
                history = list(self.messages)
                history_checks = tuple(self._history_checks)
                summary = self.summary
            run.check_size(query, self.limits.max_query_chars, '输入')
            def validate_history():
                for check in history_checks:
                    run.check()
                    check()
                    run.check()
            try:
                if history_checks:
                    runtime_call('retrieval', 'agent.history_validation', validate_history, run=run)
            except KnowledgeAccessError:
                # Discard model memory as a whole; do not replay revoked evidence
                # or unsupported answers from it in a later turn.
                with self._state_lock:
                    run.check()
                    self.messages, self._history_checks = [], []
                    self.summary = None
                    history, history_checks = [], ()
                    summary = None
                run.note('history_sources_invalidated')
            for check in history_checks:
                run.add_commit_check(check)
            plan = TurnMemoryPlan(history, summary, policy=self.context_policy,
                                  summary_model=self.summary_model, run=run)
            messages, text = runtime_call(
                'run', 'agent.turn', lambda: self._execute_turn(query, history, run, plan), run=run)
            # Cancellation/clear and commit are serialized; old turns cannot
            # overwrite a cleared conversation, even if a worker returns late.
            def commit():
                self.messages = plan.committed_messages(messages)
                self.summary = plan.summary
                self._history_checks = list(run.get_commit_checks())
            run.check_size(text, self.limits.max_output_chars, '回答')
            run.complete(commit=commit, commit_lock=self._state_lock)
        except BaseException as exc:
            run.fail(exc)
            raise
        finally:
            with self._state_lock:
                self.last_run = run.snapshot()
                snapshot = self.last_run
                self._active_run = None
            self._turn_lock.release()
            logger.info('[runtime] %s', json.dumps(snapshot, ensure_ascii=False))
        yield text

    def _execute_turn(self, query, history, run, plan=None):
        context = {"user_id": self.user_id, "city": self.city,
                   "report": False, "report_data": None,
                   "lookup_result": None, "tool_errors": {}, "run_context": run,
                   "context_policy": self.context_policy, "memory_plan": plan}
        result = self.agent.invoke(
            {"messages": [*history, HumanMessage(content=query)]},
            config={"recursion_limit": 100, "max_concurrency": self.limits.tool_concurrency},
            context=context,
        )
        final = result["messages"][-1]
        if not isinstance(final, AIMessage) or final.tool_calls:
            raise RuntimeError("模型没有生成完整回答，请重试。")
        if context.get("policy_denied"):
            text = "本次查询未完成，工具调用未通过安全检查，请检查当前会话设置和输入后重试。"
        elif context["lookup_result"] is not None:
            text = render_lookup(context["lookup_result"])
        elif context["tool_errors"]:
            details = "；".join(dict.fromkeys(context["tool_errors"].values()))
            text = "本次查询未完成，无法提供可靠的查询结论。" + details
        else:
            # The RAG tool already generates a grounded answer. A second LLM
            # paraphrase can invent facts after an explicit "not enough data".
            # Inspect this turn only; never replay a previous turn's knowledge.
            observations = [final_answer(m.content) for m in
                            result["messages"][len(history) + 1:]
                            if isinstance(m, ToolMessage) and m.name == "rag_summarize"
                            and m.status == "success" and isinstance(m.content, str)]
            observations = list(dict.fromkeys(observations))
            if observations:
                text = "\n\n".join(observations)
            else:
                text = final_answer(final.text)
        result["messages"][-1] = final.model_copy(update={"content": text})
        return result["messages"], text

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="扫地机器人客服")
    parser.add_argument("query", nargs="*", default=[])
    parser.add_argument("--user-id", default="")
    parser.add_argument("--city", default="")
    args = parser.parse_args()
    agent = ReactAgent(user_id=args.user_id, city=args.city)
    for chunk in agent.execute_stream(" ".join(args.query) or "扫地机器人应该如何保养？"):
        print(chunk, flush=True)
