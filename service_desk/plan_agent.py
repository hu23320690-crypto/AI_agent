"""Plan → validate → execute → verify → respond in one RunContext."""
from copy import deepcopy
import json
from types import SimpleNamespace
from typing import TypedDict
from uuid import uuid4

from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.graph import StateGraph, START, END
from pydantic import ValidationError

from agent.runtime import RuntimeControlError
from agent.tools.middleware import monitored_tool_call
from agent.tools.policy import ToolPolicyDenied
from service_desk import plan_core
from service_desk.access import connection_for
from service_desk.actions import list_actions
from service_desk.planner import request_plan
from utils.model_output import IncompleteModelOutput

WRITE_GOALS = {'book': 'propose_service_visit', 'order': 'propose_order', 'change': 'propose_change'}
EVIDENCE_TOOLS = {
    'diagnose': {'lookup_error_code'}, 'warranty': {'check_warranty'}, 'knowledge': {'rag_summarize'},
    'report': {'fetch_external_data'}, 'usage': {'get_daily_usage'}, 'slots': {'find_service_slots'},
    'consumables': {'find_consumables'}, 'status': {'get_my_orders_and_tickets'},
}
HANDLED = {'proposed', 'condition_false', 'condition_unknown', 'precheck_failed', 'slot_unavailable'}


class GraphState(TypedDict, total=False):
    proposal: dict | None
    validation: dict
    route: str
    result: tuple


def pending_cards(context):
    """Use only owned, unexpired pending cards, with archived arguments."""
    active = {c['action_id']: c for c in list_actions(context) if c['status'] == 'pending'}
    with connection_for(context) as connection:
        return [dict(active[row['action_id']], args=json.loads(row['args_json'])) for row in connection.execute(
            "SELECT action_id,args_json FROM pending_actions WHERE session_id=? AND user_id=? AND status='pending'",
            (context['session_id'], context['user_id'])) if row['action_id'] in active]


class PlanTurn:
    def __init__(self, agent, query, history, run, memory, context, lookup_records, report_intent):
        self.agent, self.query, self.history, self.run = agent, query, history, run
        self.memory, self.context = memory, context
        self.lookup_records, self.report_intent = lookup_records, report_intent
        self.card_context_denied = False
        try:
            self.cards = pending_cards(context)
        except ToolPolicyDenied:
            # Card metadata is optional context. A missing/invalid identity must
            # not crash greetings or clarification before model/tool handling.
            self.cards = []
            self.card_context_denied = True
        self.goals, self.steps, self.results, self.states = [], {}, {}, {}
        self.current = None
        self.ask = None
        self.feedback = {}
        self.validation_retried = False
        self.verify_retried = False
        self.repair = False
        self.missing = []
        self.graph = self._graph()

    def _graph(self):
        graph = StateGraph(GraphState)
        for name in ('plan', 'validate', 'execute', 'verify', 'respond', 'fallback'):
            graph.add_node(name, getattr(self, name))
        graph.add_edge(START, 'plan')
        graph.add_edge('plan', 'validate')
        graph.add_conditional_edges('validate', lambda s: s['route'],
                                    {'plan': 'plan', 'execute': 'execute', 'fallback': 'fallback', 'respond': 'respond'})
        graph.add_conditional_edges('execute', lambda s: s['route'], {'verify': 'verify', 'respond': 'respond'})
        graph.add_conditional_edges('verify', lambda s: s['route'], {'plan': 'plan', 'respond': 'respond'})
        graph.add_edge('respond', END)
        graph.add_edge('fallback', END)
        return graph.compile()

    def invoke(self):
        if self.card_context_denied:
            self.run.note('plan_card_context_denied')
            return self.fallback({})['result']
        return self.graph.invoke({}, config={'recursion_limit': 40})['result']

    def plan(self, state):
        self.run.check()
        try:
            proposal = request_plan(self.query, self.history, self.cards, self.context, self.feedback,
                                    model=self.agent.selected_model, policy=self.agent.context_policy)
        except IncompleteModelOutput:
            return {'proposal': None}
        except RuntimeControlError:
            raise
        except (ValueError, TypeError, RecursionError):
            return {'proposal': None}
        return {'proposal': proposal}

    def _validation_context(self, completed=()):
        # Completed evidence is virtual for validation; it consumes no new calls.
        return {'user_text': self.query, 'history_user_texts': self.context['rag_user_history'],
                'business_date': self.context['business_date'], 'pending_cards': self.cards,
                'remaining_model_calls': self.run.remaining_calls('model') + sum(s['tool'] == 'rag_summarize' for s in completed),
                'remaining_tool_calls': self.run.remaining_calls('tool') + len(completed)}

    def validate(self, state):
        proposal = state['proposal']
        candidate, corrections = plan_core.normalize_plan(proposal, self._validation_context())
        for correction in corrections:
            with self.run.lock:
                self.run.counts["plan_normalizations"] += 1
            self.run.note("plan_normalization", **correction)
        completed = []
        extra_errors = []
        if self.repair and isinstance(candidate, dict):
            try:
                plan_core.Plan.model_validate(candidate)
            except ValidationError:
                candidate = None
        if self.repair and isinstance(candidate, dict):
            completed = [s for key, s in self.steps.items() if self.states[key]['status'] in {'done', *HANDLED}]
            if candidate.get('goals') != self.missing:
                extra_errors.append({'code': 'P5', 'detail': 'repair must preserve only missing goals'})
            missing_ids = {g['id'] for g in self.missing}
            if any(set(s.get('covers', [])) - missing_ids for s in candidate.get('steps', [])):
                extra_errors.append({'code': 'P5', 'detail': 'repair cannot add work for handled goals'})
            completed_ids = {s['id'] for s in completed}
            if any(s.get('id') in completed_ids for s in candidate.get('steps', []) if isinstance(s, dict)):
                extra_errors.append({'code': 'P4', 'detail': 'repair cannot replace completed steps'})
            candidate['goals'] = self.goals
            candidate['steps'] = [*completed, *candidate.get('steps', [])]
        if candidate is None:
            checked = {'ok': False, 'plan': None, 'errors': [{'code': 'P1', 'detail': 'invalid or truncated JSON'}]}
        else:
            checked = plan_core.validate_plan(candidate, self._validation_context(completed))
        if extra_errors:
            checked['ok'] = False
            checked['errors'].extend(extra_errors)
        self.run.note('plan_validation', ok=checked['ok'], codes=[e['code'] for e in checked['errors']])
        if checked['ok']:
            self.current = checked['plan']
            if not self.goals:
                self.goals = self.current['goals']
            self.ask = self.current.get('ask_user')
            return {'validation': checked, 'route': 'execute'}
        self.feedback['validation_errors'] = [
            {'code': e['code'], 'step_id': e.get('step_id'), 'detail': e['detail'][:300]}
            for e in checked['errors'][:8]]
        if not self.validation_retried and self.run.counts['planner_calls'] < 3:
            self.validation_retried = True
            self._replan('validation')
            return {'validation': checked, 'route': 'plan'}
        return {'validation': checked, 'route': 'fallback'}

    def _replan(self, reason):
        with self.run.lock:
            self.run.counts['replans'] += 1
        self.run.note('plan_replan', reason=reason)

    def _skip(self, step, status, reason, **details):
        self.states[step['id']] = {'status': status, 'reason': reason, **details}
        with self.run.lock:
            self.run.counts['skipped_steps'] += 1
        self.run.note('plan_step_skipped', step_id=step['id'], status=status, reason=reason)

    def _call(self, step, arguments):
        tool = self.agent.service_tools[step['tool']]
        runtime = SimpleNamespace(context=self.context)
        call = {'name': step['tool'], 'args': arguments, 'id': 'plan-' + uuid4().hex, 'type': 'tool_call'}
        request = ToolCallRequest(tool_call=call, tool=tool, state={}, runtime=runtime)
        def handler(req):
            content = req.tool.func(runtime=runtime, **req.tool_call['args'])
            return ToolMessage(content=content, name=call['name'], tool_call_id=call['id'])
        message = monitored_tool_call(request, handler)
        self.context.setdefault('plan_tool_messages', []).extend([
            AIMessage(content='', tool_calls=[call]), message])
        result = self.context['service_results'][-1]
        self.results[step['id']] = result
        payload = result['payload']
        status = 'error' if message.status == 'error' or payload.get('status') in ('blocked', 'denied', 'error') else 'done'
        if step['tool'] in plan_core.WRITE_TOOLS and payload.get('status') == 'pending':
            status = 'proposed'
        self.states[step['id']] = {'status': status}

    def execute(self, state):
        queue = list(self.current['steps'])
        while queue:
            self.run.check()
            # Validated DAGs may list independent dependencies later in the array.
            step = next(s for s in queue if all(d in self.states for d in s.get('depends_on', [])))
            queue.remove(step)
            key = step['id']
            if key in self.states and self.states[key]['status'] in {'done', *HANDLED}:
                continue
            self.steps[key] = step
            if any(self.states[d]['status'] != 'done' for d in step.get('depends_on', [])):
                self._skip(step, 'missing', 'dependency_unavailable')
                continue
            resolved = plan_core.resolve_args(step, self.results, {'business_date': self.context['business_date'],
                                                                   'pending_cards': self.cards})
            if resolved['status'] != 'ok':
                status = 'slot_unavailable' if resolved.get('detail') == 'slot_unavailable' else 'missing'
                self._skip(step, status, resolved['detail'])
                if resolved['status'] == 'ambiguous':
                    kind = {'device_id': 'which_device', 'slot_id': 'which_slot', 'new_slot_id': 'which_slot'}.get(resolved['param'])
                    self.ask = {'type': kind or 'other', 'text': '请明确要处理的对象。'}
                continue
            arguments = resolved['args']
            if self.repair and step['tool'] not in plan_core.WRITE_TOOLS:
                reused = next((r for k, r in self.results.items() if self.states[k]['status'] == 'done'
                               and r['tool'] == step['tool'] and r['args'] == arguments), None)
                if reused is not None:
                    self.results[key] = reused
                    self.states[key] = {'status': 'done'}
                    self.run.note('plan_step_reused', step_id=key)
                    continue
            if step['tool'] in plan_core.WRITE_TOOLS:
                condition = step.get('condition')
                if condition:
                    value, detail = plan_core.evaluate_condition(condition, self.results)
                    if value != 'true':
                        rendered_condition = dict(condition)
                        if condition['type'] == 'record_threshold':
                            rendered_condition['month'] = self.results[condition['from_step']]['payload'].get('month', '')
                        self._skip(step, 'condition_' + value, detail, condition=rendered_condition)
                        continue
                failure = plan_core.precheck(step['tool'], arguments, self.results)
                if failure:
                    self._skip(step, 'slot_unavailable' if failure['reason_code'] == 'slot_unavailable' else 'precheck_failed', failure['message'])
                    continue
            self._call(step, arguments)
        return {'route': 'respond' if self.ask else 'verify'}

    def _outcome(self, goal):
        candidates = [(s, self.states[key]) for key, s in self.steps.items() if goal['id'] in s.get('covers', [])]
        write_tool = WRITE_GOALS.get(goal['type'])
        if write_tool:
            evidence = [value for step, value in candidates if step['tool'] == write_tool and value['status'] in HANDLED]
        else:
            evidence = [value for step, value in candidates if step['tool'] in EVIDENCE_TOOLS[goal['type']] and value['status'] == 'done']
        value = evidence[-1] if evidence else {'status': 'missing'}
        return {'goal_type': goal['type'], 'goal_text': goal['text'],
                'action': {'book': 'visit', 'order': 'order', 'change': 'change'}.get(goal['type']), **value}

    def verify(self, state):
        self.missing = [g for g in self.goals if self._outcome(g)['status'] == 'missing']
        self.run.note('plan_verify', missing_goals=[g['id'] for g in self.missing])
        if self.missing and not self.ask and not self.verify_retried and self.run.counts['planner_calls'] < 3:
            self.verify_retried = self.repair = True
            self.feedback = {'missing_goals': self.missing,
                             'completed_steps': [s for key, s in self.steps.items() if self.states[key]['status'] in {'done', *HANDLED}],
                             'completed_results': {key: r for key, r in self.results.items()
                                                   if self.states[key]['status'] in {'done', 'proposed'}}}
            self._replan('verify')
            return {'route': 'plan'}
        return {'route': 'respond'}

    def respond(self, state):
        result = {'messages': [*self.history, HumanMessage(content=self.query), AIMessage(content='计划处理结果。')]}
        return {'result': self.agent._finish_turn(self.query, self.history, self.run, self.memory, self.context,
                    result, self.lookup_records, self.report_intent, mode='plan', ask=self.ask,
                    outcomes=[self._outcome(g) for g in self.goals])}

    def fallback(self, state):
        with self.run.lock:
            self.run.counts['plan_fallback'] = 1
        self.run.note('plan_fallback')
        return {'result': self.agent._invoke_react(self.query, self.history, self.run, self.memory,
                                                  self.context, self.lookup_records, self.report_intent)}
