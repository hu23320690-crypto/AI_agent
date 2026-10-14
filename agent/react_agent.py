import argparse
import json
import re
import sys
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import date
from uuid import uuid4
from pathlib import Path
from threading import Lock, RLock
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from model.factory import chat_model
from utils.model_output import final_answer
from rag.security import KnowledgeAccessError
from rag.rag_service import EvidenceCheck
from rag.answer_policy import requires_conditional_guarantee, conditional_guarantee_reply
from utils.report_render import render_lookup, record_fields
from agent.intent import resolve_turn_intent
from agent.toolset import load_toolset
from utils.record_evidence import record_evidence_reply
from utils.logger_hander import logger
from agent.runtime import RunContext, RunBusy, load_limits, default_runtime, runtime_call
from agent.context_budget import load_context_policy
from agent.context_memory import TurnMemoryPlan
from agent.tools.agent_tools import (
    rag_summerize, get_weather, get_user_location, get_user_id,
    get_current_month, fetch_external_data, fill_context_for_report,
)
from agent.tools.middleware import monitor_tool, monitor_model, log_before_model, report_prompt_switch, manage_context


def _knowledge_requested(query):
    # Definition questions need no maintenance-specific topic word. Check
    # separate clauses so an explicit "do not explain" does not authorize a
    # model's unsolicited RAG call, or suppress another positive subquestion.
    clauses = []
    for part in re.finditer(r'([^，,。；;！？?\n]+)([，,。；;！？?\n]?)', query):
        pieces = re.split(r'但是|不过|但|改为|改成|而是', part[1])
        clauses.extend((text, index == len(pieces) - 1 and part[2] in ('?', '？'))
                       for index, text in enumerate(pieces))
    for clause, is_question in clauses:
        if re.search(r'(?:不要|不必|无需|不用|不需要|别|禁止|不)\s*'
                     r'(?:再|额外|另外)?\s*'
                     r'(?:说明|解释|介绍|阐明|讲解|回答|分析|查询|检索|定义|给出|输出|补充|提供)', clause):
            continue
        explanation = re.search(r'说明|解释|介绍|阐明|讲解|如何|怎么|怎样|多久|判断|证明|确认|'
                                r'(?:是|为)什么|什么(?:是|叫)|代表什么|表示什么|意味着什么|'
                                r'什么意思|请.*定义', clause)
        # A requested field may itself be called "replacement cycle" or
        # "maintenance condition". Its name alone is not a knowledge task.
        if re.search(r'(?:只|仅)(?:列(?:出)?|显示|输出|展示|给出)', clause) and not explanation:
            continue
        definition = (re.search(r'含义|定义|概念|原理|意思|什么(?:是|叫)|代表什么|表示什么|意味着什么', clause)
                      and (explanation or is_question))
        procedural = (re.search(r'维护|保养|维修|故障|清洗|清理|清洁|更换|安装|资料|说明书|门槛', clause)
                      and re.search(r'说明|解释|如何|怎么|怎样|多久|是否|能否|判断|步骤|要求|周期|条件', clause))
        if definition or procedural:
            return True
    return False


class ReactAgent:
    def __init__(self, user_id: str = "", city: str = "", *, model=None, limits=None, executor=None,
                 context_policy=None, summary_model=None, session_id=None, service_db_path=None):
        self.user_id = user_id.strip()
        self.city = city.strip()
        self.toolset = load_toolset()
        self.session_id = str(uuid4()) if session_id is None else session_id
        if not isinstance(self.session_id, str) or not self.session_id.strip():
            raise ValueError("session_id must be a nonempty string")
        self.service_state = None
        if self.toolset == "service":
            from service_desk.access import session_context
            self.service_state = session_context(self.user_id, self.session_id, service_db_path)
        self.messages = []
        self._recorded_action_events = set()
        self._history_checks = []
        self._lookup_records = []
        self._report_intent = None
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
        tools = [rag_summerize, get_weather, get_user_id, get_current_month,
                 get_user_location, fill_context_for_report, fetch_external_data]
        if self.toolset == "service":
            from service_desk.tools import build_service_tools
            tools = build_service_tools()
        self.agent = create_agent(
            context_schema=dict,
            model=selected_model,
            tools=tools,
            middleware=[monitor_tool, log_before_model, report_prompt_switch, manage_context, monitor_model],
        )

    def clear_history(self):
        with self._state_lock:
            self.cancel_current()
            self.messages = []
            self._recorded_action_events.clear()
            self._history_checks = []
            self._lookup_records = []
            self._report_intent = None
            self.summary = None

    def cancel_current(self):
        """May be called from another thread; does not kill remote inference."""
        with self._state_lock:
            if self._active_run is not None:
                self._active_run.cancel()
                return True
            return False

    def record_action_event(self, result):
        """Append one complete code-rendered card turn; return False on replay."""
        with self._state_lock:
            if self.toolset != 'service':
                raise ValueError('service_disabled')
            if self._active_run is not None:
                raise RunBusy('当前会话已有任务运行，请等待或取消后重试。')
            if (not isinstance(result, dict) or result.get('status') not in
                    {'executed', 'rejected', 'expired', 'superseded', 'failed'}
                    or not isinstance(result.get('action_id'), str) or not result['action_id']
                    or not isinstance(result.get('message'), str) or not result['message']):
                raise ValueError('invalid_action_result')
            action_id = result['action_id']
            if action_id in self._recorded_action_events:
                return False
            operation = result.get('operation', 'reject' if result['status'] == 'rejected' else 'confirm')
            if operation not in ('confirm', 'reject'):
                raise ValueError('invalid_action_operation')
            label = '确认' if operation == 'confirm' else '拒绝'
            self.messages.extend([
                HumanMessage(content=f'[卡片操作] {label} {action_id}', name='action_event'),
                AIMessage(content=result['message']),
            ])
            # Retain replay protection even after complete-turn history trimming.
            self._recorded_action_events.add(action_id)
            return True

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
        with self._state_lock:
            if not self._turn_lock.acquire(blocking=False):
                raise RunBusy("当前会话已有任务运行，请等待或取消后重试。")
            run = run_context if run_context is not None else RunContext(self.limits, self.executor)
            self._active_run = run
        try:
            with self._state_lock:
                run.check()
                history = list(self.messages)
                history_checks = tuple(self._history_checks)
                summary = self.summary
                lookup_records = deepcopy(self._lookup_records)
                report_intent = self._report_intent
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
                    self._lookup_records = []
                    self._report_intent = None
                    history, history_checks = [], ()
                    summary = None
                    lookup_records = []
                    report_intent = None
                run.note('history_sources_invalidated')
            for check in history_checks:
                run.add_commit_check(check)
            plan = TurnMemoryPlan(history, summary, policy=self.context_policy,
                                  summary_model=self.summary_model, run=run,
                                  report_reference=asdict(report_intent) if report_intent is not None else None)
            messages, text, new_lookups, new_intent = runtime_call(
                'run', 'agent.turn', lambda: self._execute_turn(
                    query, history, run, plan, lookup_records=lookup_records,
                    report_intent=report_intent), run=run)
            # Cancellation/clear and commit are serialized; old turns cannot
            # overwrite a cleared conversation, even if a worker returns late.
            def commit():
                self.messages = plan.committed_messages(messages)
                self.summary = plan.summary
                self._history_checks = list(run.get_commit_checks())
                # Records come from successful authorized tool callbacks, not
                # from assistant text or model-generated conversation memory.
                records = {(item['user_id'], item['month']): item for item in lookup_records}
                for item in new_lookups:
                    key = (item['user_id'], item['month'])
                    records.pop(key, None)
                    records[key] = item
                self._lookup_records = deepcopy(list(records.values())[-24:])
                self._report_intent = new_intent
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

    def _execute_turn(self, query, history, run, plan=None, *, lookup_records=(), report_intent=None):
        service_state = getattr(self, "service_state", None)
        context = {"user_id": self.user_id, "city": self.city,
                   "user_query": query,
                   "rag_user_history": [m.content for m in history
                                        if isinstance(m, HumanMessage) and isinstance(m.content, str)
                                        and m.name not in ('conversation_memory', 'action_event')],
                   "report": False, "report_data": None,
                   "lookup_result": None, "lookup_results": [], "tool_errors": {}, "run_context": run,
                   "context_policy": self.context_policy, "memory_plan": plan}
        if service_state is not None:
            context.update(service_state)
        result = self.agent.invoke(
            {"messages": [*history, HumanMessage(content=query)]},
            config={"recursion_limit": 100, "max_concurrency": self.limits.tool_concurrency},
            context=context,
        )
        final = result["messages"][-1]
        if not isinstance(final, AIMessage) or final.tool_calls:
            raise RuntimeError("模型没有生成完整回答，请重试。")
        # Successful tool observations belong to this turn. Never treat the
        # final planner's report prose or a previous assistant answer as data.
        def observation_text(message):
            if service_state is not None:
                from service_desk.prompt import rag_answer
                return final_answer(rag_answer(message.content))
            return final_answer(message.content)
        observations = list(dict.fromkeys(observation_text(m) for m in
                            result["messages"][len(history) + 1:]
                            if isinstance(m, ToolMessage) and m.name == "rag_summarize"
                            and m.status == "success" and isinstance(m.content, str)))
        if context.get("policy_denied"):
            text = "本次查询未完成，工具调用未通过安全检查，请检查当前会话设置和输入后重试。"
        elif context["lookup_result"] is not None:
            previous_queries = [m.content for m in history
                                if isinstance(m, HumanMessage) and isinstance(m.content, str)
                                and m.name not in ('conversation_memory', 'action_event')]
            if plan is not None and plan.summary is not None:
                # A reference may have just been copied from this same graph
                # prefix. Replay it only when no original turn is available.
                previous_queries = [*(reference for reference in plan.summary.get('task_references', ())
                                      if reference not in previous_queries), *previous_queries]
            lookups = [*lookup_records, *context['lookup_results']]
            known_fields = tuple(dict.fromkeys(
                field for item in lookups if item['status'] == 'ok'
                and item['user_id'] == self.user_id for field in record_fields(item['data'])))
            # Once a report has completed, its resolved absolute month and
            # field selectors survive compression without replaying relative
            # queries ("next month") twice. This confers no lookup authority.
            intent_reference = report_intent
            if service_state is not None:
                from service_desk.prompt import report_reference
                intent_reference = report_reference(query, report_intent, service_state["business_date"])
            turn_intent = resolve_turn_intent(
                query, history_queries=previous_queries if report_intent is None else (),
                llm_history_queries=previous_queries,
                known_fields=known_fields, fallback_month=context['lookup_result']['month'],
                previous_intent=intent_reference,
                today=(date.fromisoformat(service_state["business_date"])
                       if service_state is not None else date.today()), run=run)
            report_intent = turn_intent.intent
            if (report_intent.target_month is None and not report_intent.invalid_month
                    and not report_intent.unresolved_month):
                report_intent = replace(report_intent, target_month=context['lookup_result']['month'])
            if (turn_intent.final_scope == 'full_report'
                    and turn_intent.final_excluded_fields):
                # Exclusions turn a full report into the remaining metrics.
                # The session catalog may contain other months' metrics; only
                # this turn's authorized target record supplies this list.
                target_record = next((item for item in reversed(context['lookup_results'])
                                      if item.get('status') == 'ok'
                                      and item.get('month') == report_intent.target_month
                                      and item.get('user_id') == self.user_id), None)
                if target_record is not None:
                    target_fields = record_fields(target_record['data'])
                    excluded = set(turn_intent.final_excluded_fields)
                    fields = tuple(field for field in report_intent.fields
                                   if field in target_fields and field not in excluded)
                    report_intent = replace(report_intent, fields=fields,
                                            limited=report_intent.limited or not fields)
            text = render_lookup(context["lookup_result"], query=query,
                                 lookup_results=lookups, intent=report_intent,
                                 current_results=context['lookup_results'])
            # Field selection controls the numeric report, not separate user
            # questions about knowledge or what these measurements establish.
            # Preserve successful RAG subtask answers, and answer a requested
            # evidence boundary from verified records/source text, never from
            # an arbitrary planner diagnosis or a similar field name.
            knowledge_requested = turn_intent.knowledge_requested
            if knowledge_requested:
                if observations:
                    text += "\n\n" + "\n\n".join(observations)
                elif 'rag_summarize' in context['tool_errors']:
                    text += "\n\n本轮知识查询未完成，无法可靠回答相应知识子问。"
            current_record = next((item for item in reversed(context['lookup_results'])
                                   if item.get('month') == report_intent.target_month
                                   and item.get('user_id') == self.user_id), None)
            source_documents = [check.document for check in run.get_commit_checks()
                                if isinstance(check, EvidenceCheck)]
            boundary = record_evidence_reply(query, current_record,
                                             source_documents=source_documents)
            if boundary:
                text += "\n\n" + boundary
                run.note('agent_record_evidence_boundary_answered')
        elif context["tool_errors"]:
            details = "；".join(dict.fromkeys(context["tool_errors"].values()))
            text = "本次查询未完成，无法提供可靠的查询结论。" + details
        else:
            # The RAG tool already generates a grounded answer. A second LLM
            # paraphrase can invent facts after an explicit "not enough data".
            # Inspect this turn only; never replay a previous turn's knowledge.
            if requires_conditional_guarantee(query):
                # This policy also applies when the planner chooses not to
                # repeat retrieval. Only captured, revalidated RAG evidence
                # may supply quotes; model memory is never evidence authority.
                evidence = [check.document for check in run.get_commit_checks()
                            if isinstance(check, EvidenceCheck)]
                text = conditional_guarantee_reply(query, evidence)
                run.note('agent_conditional_guarantee_declined')
            elif observations:
                text = "\n\n".join(observations)
            else:
                text = final_answer(final.text)
        result["messages"][-1] = final.model_copy(update={"content": text})
        return result["messages"], text, ([] if context.get('policy_denied') else context['lookup_results']), report_intent

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="扫地机器人客服")
    parser.add_argument("query", nargs="*", default=[])
    parser.add_argument("--user-id", default="")
    parser.add_argument("--city", default="")
    args = parser.parse_args()
    agent = ReactAgent(user_id=args.user_id, city=args.city)
    for chunk in agent.execute_stream(" ".join(args.query) or "扫地机器人应该如何保养？"):
        print(chunk, flush=True)
