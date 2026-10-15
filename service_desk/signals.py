"""Shared, deterministic recognition of explicit user requirements."""
import re


def recognize(query):
    # Reuse the legacy predicate without changing it or its callers. Broader
    # explicit requests below are service-only and honor negative clauses.
    from agent.react_agent import _knowledge_requested
    knowledge = _knowledge_requested(query)
    for clause in re.split(r'[，,。；;！？?\n]|但是|不过|但|而是', query):
        if re.search(r'(?:不要|不必|无需|不用|不需要|别|禁止|不)\s*(?:再|额外|另外)?\s*(?:说明|解释|介绍|查询|检索|给出|输出|补充|提供)', clause):
            continue
        if re.search(r'(?:说明|步骤|注意事项|处理方法|政策解释|解释.*政策)', clause):
            knowledge = True
    conditions = []
    for clause in re.split(r'[。；;！？?\n]', query):
        if re.search(r'(?:如果|若|只有)[^。；;！？?]*?(?:还)?(?<!不)在保|(?<!不)在保\s*(?:才|的话|就)', clause):
            # Whole-machine is the default only when battery is not specified.
            component = 'battery' if re.search(r'电池[^，,。；;]{0,12}在保', clause) else 'whole_machine'
            conditions.append({'type': 'warranty_in_force', 'component': component})
        for match in re.finditer(r'(不高于|不超过|低于|高于|不低于)\s*(\d+(?:\.\d+)?)\s*(%|％|天)([^。；;！？?]*?(?:才|就))', clause):
            conditions.append({'type': 'record_threshold', 'op': {
                '不高于': '<=', '不超过': '<=', '低于': '<', '高于': '>', '不低于': '>='}[match[1]],
                'value': float(match[2]), 'unit': '%' if match[3] == '％' else match[3],
                'evidence': match.group(), 'subject': re.split(r'[，,]', clause[:match.start()])[-1]})
    # Deduplicate identical warranty clauses; never infer conditions from data.
    unique = []
    for condition in conditions:
        if condition not in unique:
            unique.append(condition)
    return {'conditions': unique, 'knowledge_requested': bool(knowledge)}


def prompt_hints(signals):
    lines = []
    for condition in signals['conditions']:
        if condition['type'] == 'warranty_in_force':
            description = ('电池' if condition['component'] == 'battery' else '整机') + '在保'
        else:
            description = condition['evidence']
        lines.append(f'本轮用户附带条件：{description}。提议前必须先核对，条件不成立就不要提议。')
    if signals['knowledge_requested']:
        lines.append('本轮用户要求说明：必须调用 rag_summarize。')
    return '\n'.join(lines)


def validate_signals(plan, signals):
    errors = []
    for step in plan['steps']:
        if step['tool'] not in ('propose_service_visit', 'propose_order', 'propose_change'):
            continue
        actual = step.get('condition') or {}
        for wanted in signals['conditions']:
            keys = ('type', 'component') if wanted['type'] == 'warranty_in_force' else ('type', 'op', 'value', 'unit')
            matches = all(actual.get(key) == wanted[key] for key in keys)
            if matches and wanted['type'] == 'record_threshold':
                hint = actual.get('field_hint', '').strip().casefold()
                matches = bool(hint and hint in wanted['subject'].casefold())
            if not matches:
                errors.append({'code': 'P9', 'step_id': step['id'], 'detail': f'写步骤缺少用户明确条件：{wanted}'})
    if signals['knowledge_requested'] and (
            not any(g['type'] == 'knowledge' for g in plan['goals'])
            or not any(s['tool'] == 'rag_summarize' for s in plan['steps'])):
        errors.append({'code': 'P10', 'step_id': None, 'detail': '用户要求说明：必须有 knowledge 目标及 rag_summarize 步骤'})
    return errors
