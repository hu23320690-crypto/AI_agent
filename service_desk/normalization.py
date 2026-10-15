"""Conservative syntax repairs; all resulting plans still require validation."""
from copy import deepcopy
import re


def normalize_plan(plan, ctx):
    from service_desk import plan_core as core
    candidate, changes = deepcopy(plan), []
    if not isinstance(candidate, dict) or not isinstance(candidate.get('steps'), list):
        return candidate, changes
    pool = [ctx.get('user_text', ''), *ctx.get('history_user_texts', [])]
    pool = [s for s in pool if isinstance(s, str)]
    numeral = r'[0-9零一二两三四五六七八九十]+'
    patterns = {
        'date': rf'大后天|后天|明天|今天|\d{{4}}[-/]\d{{1,2}}[-/]\d{{1,2}}|(?:\d{{4}}年)?{numeral}月{numeral}[日号]',
        'month': rf'上个月|上月|下个月|下月|这个月|本月|当月|\d{{4}}[-/]\d{{1,2}}|(?:\d{{4}}年)?{numeral}月',
        'time': rf'(?:上午|下午|晚上|中午|凌晨|早上|夜里)?\s*{numeral}(?:[:：]\d{{2}}|点)',
        'number': numeral + r'(?:个|件|天|次)?',
        'code': r'(?<![A-Za-z0-9])E\d{2}(?!\d)',
    }

    def repair_evidence(source, kind, path):
        if not isinstance(source, dict) or set(source) != {'value', 'evidence'}:
            return
        evidence = source['evidence']
        if not isinstance(evidence, str) or (evidence and any(evidence in s for s in pool)):
            return
        value = source['value']
        if kind == 'id':
            if not isinstance(value, str) or not value:
                return
            pattern = r'(?<![A-Za-z0-9_-])' + re.escape(value) + r'(?![A-Za-z0-9_-])'
        else:
            pattern = patterns[kind]
        matches = []
        for text in pool:
            for match in re.finditer(pattern, text):
                fragment = match.group().strip()
                if kind == 'date':
                    parsed = core.parse_date(fragment, ctx.get('business_date'))
                elif kind == 'month':
                    parsed = core.parse_month(fragment, ctx.get('business_date'))
                elif kind == 'time':
                    parsed = core.parse_time(fragment)
                elif kind == 'number':
                    parsed = core.parse_number(fragment)
                else:
                    parsed = fragment
                if parsed == value:
                    matches.append(fragment)
        if len(matches) == 1:
            source['evidence'] = matches[0]
            changes.append({'type': 'evidence', 'path': path, 'before': evidence, 'after': matches[0]})

    def enum(container, name, allowed, path):
        raw = container.get(name)
        value = raw.get('value') if isinstance(raw, dict) and set(raw) == {'value', 'evidence'} else raw
        if isinstance(value, str) and value in allowed:
            container[name] = {'enum': value}
            changes.append({'type': 'enum', 'path': path, 'before': raw, 'after': {'enum': value}})

    earlier = []
    for step in candidate['steps']:
        if not isinstance(step, dict):
            continue
        sid = step.get('id')
        args = step.get('args')
        if not isinstance(args, dict):
            earlier.append(step)
            continue

        def reference(source, tool, path):
            if not isinstance(source, dict) or not tool or not isinstance(step.get('depends_on', []), list):
                return
            ref = source.get('from_step')
            if any(s.get('id') == ref and s.get('tool') == tool for s in candidate['steps'] if isinstance(s, dict)):
                return
            matches = [s for s in earlier if s.get('tool') == tool and isinstance(s.get('id'), str)]
            if len(matches) == 1:
                source['from_step'] = matches[0]['id']
                deps = step.setdefault('depends_on', [])
                if source['from_step'] not in deps:
                    deps.append(source['from_step'])
                changes.append({'type': 'reference', 'path': path, 'before': ref, 'after': source['from_step']})

        spec = core.TOOLS.get(step.get('tool'), {}).get('params', {})
        for name in list(args):
            path = f'{sid}.args.{name}'
            allowed = spec.get(name, {}).get('enum')
            if allowed:
                enum(args, name, allowed, path)
            source = args[name]
            if not isinstance(source, dict):
                continue
            pick = source.get('pick')
            reference(source, core.PICK_TOOL.get(pick), path)
            if pick == 'slot_at':
                repair_evidence(source.get('date'), 'date', path + '.date')
                repair_evidence(source.get('start'), 'time', path + '.start')
            elif pick == 'record':
                enum(source, 'kind', ['order', 'appointment'], path + '.kind')
                enum(source, 'status', ['processing', 'scheduled'], path + '.status')
                repair_evidence(source.get('id'), 'id', path + '.id')
            elif pick == 'consumable_kind':
                enum(source, 'kind', core.TOOLS['find_consumables']['params']['kind']['enum'], path + '.kind')
            kind = ('id' if name in core.ID_PARAMS else 'number' if name in core.NUMBER_PARAMS
                    else 'code' if name in ('code', 'error_code') else core.VALUE_PARSERS.get(name))
            if kind:
                repair_evidence(source, kind, path)
        condition = step.get('condition')
        if isinstance(condition, dict):
            reference(condition, core.CONDITION_TOOL.get(condition.get('type')), f'{sid}.condition')
        earlier.append(step)
    return candidate, changes
