"""Bounded tool-free planning. JSON proposals confer no execution authority."""
import json
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from agent.context_budget import ContextBudgetExceeded, enforce_request, sanitize_messages
from agent.runtime import dependency_call, dependency_key
from model.factory import budgeted_chat_model
from service_desk import plan_core
from utils.model_output import ensure_complete_response

ROOT = Path(__file__).resolve().parents[1]


def _object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('duplicate JSON key')
        value[key] = item
    return value


def parse_plan(message):
    """Reject truncation, tool calls, duplicate keys and nonfinite JSON as P1."""
    if (not isinstance(message, AIMessage) or not isinstance(message.content, str)
            or message.tool_calls or message.invalid_tool_calls
            or message.additional_kwargs.get('tool_calls')):
        raise ValueError('planner must return tool-free JSON')
    ensure_complete_response(message)
    def invalid(value):
        raise ValueError('nonfinite JSON')
    value = json.loads(message.content, object_pairs_hook=_object, parse_constant=invalid)
    if not isinstance(value, dict):
        raise ValueError('plan must be an object')
    return value


def planner_messages(query, history, cards, context, feedback, *, model, policy, run, schema):
    """Trim older public turns, then card summaries, keeping the query intact."""
    turns = []
    for index, message in enumerate(history[:-1]):
        if (isinstance(message, HumanMessage) and message.name not in ('action_event', 'conversation_memory')
                and isinstance(history[index + 1], AIMessage)):
            turns.append({'user': str(message.content)[-512:],
                          'answer': str(history[index + 1].content)[-512:]})
    data = {'query': query, 'history': turns[-2:], 'pending_cards': [dict(c) for c in cards],
            'business_date': context['business_date'], 'feedback': feedback}
    prompt = (ROOT / 'prompts/service_planner.txt').read_text(encoding='utf-8')
    while True:
        messages = sanitize_messages([SystemMessage(content=prompt),
                                      HumanMessage(content=json.dumps(data, ensure_ascii=False))])
        try:
            enforce_request(messages, response_format=schema, policy=policy, model=model,
                            run=run, label='agent.planner')
            return messages
        except ContextBudgetExceeded:
            if data['history']:
                data['history'].pop(0)
            elif any('summary' in c for c in data['pending_cards']):
                for card in data['pending_cards']:
                    card.pop('summary', None)
            elif '[示例开始]' in prompt and '[示例结束]' in prompt:
                # Examples teach syntax but confer no authority. Keep all rules,
                # user evidence and repair feedback when the request is tight.
                before, example = prompt.split('[示例开始]', 1)
                _, after = example.split('[示例结束]', 1)
                prompt = before + after
            else:
                raise


def request_plan(query, history, cards, context, feedback, *, model, policy):
    run = context['run_context']
    run.check_budget('model')
    schema = plan_core.plan_json_schema()
    selected = budgeted_chat_model(model, policy)
    if isinstance(selected, ChatOllama):
        selected = selected.model_copy(update={'format': schema, 'reasoning': False, 'temperature': 0})
    messages = planner_messages(query, history, cards, context, feedback, model=selected,
                                policy=policy, run=run, schema=schema)
    trace = context.get('turn_trace')
    config = {'callbacks': [trace]} if trace is not None else {}
    run.validate_commit_checks()
    with run.lock:
        run.counts['planner_calls'] += 1
    # A planner attempt is single shot; re-planning has one explicit owner.
    response = dependency_call('model', 'agent.planner', lambda: selected.invoke(messages, config=config),
                               dependency=dependency_key(selected, 'chat'), run=run)
    run.check_size(json.dumps({'content': response.content, 'tool_calls': response.tool_calls},
                              ensure_ascii=False), run.limits.max_output_chars, '模型输出')
    run.validate_commit_checks()
    return parse_plan(response)
