"""Structure-first synthetic data for intent SFT, verified by the real resolver.

Each sample starts as an IntentProposal-shaped label plus the SCORING nine-slot
gold; the user text is rendered from that structure, so no label comes from a
model. A sample is kept only when agent.intent.resolve, fed the label as the
model proposal, reproduces the gold in both hybrid and llm_only modes. The
exported model input is the exact request parse_turn_intent would have sent.

    python -B -m training.intent_sft.generate --count 6000 --seed 20261030 --out <dir>
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import random
from unittest.mock import patch

from training.intent_sft.lexicon import (
    FICTIONAL_PREFIXES, FICTIONAL_SUFFIXES, FIELD_PARAPHRASES, KNOWLEDGE_ABOUT_FIELD,
    KNOWLEDGE_DECLINES, KNOWLEDGE_LEADS, KNOWLEDGE_QUESTIONS, QUALIFIERS, UNKNOWN_METRICS,
)

ROOT = Path(__file__).resolve().parents[2]
SFT_PROMPT = 'prompts/intent_parser_sft.txt'
CN_MONTH = [None, '一', '二', '三', '四', '五', '六', '七', '八', '九', '十', '十一', '十二']
CN_DIGIT = '〇一二三四五六七八九'
COUNT_WORDS = {2: ['2', '两'], 3: ['3', '三'], 4: ['4', '四'], 5: ['5', '五'], 6: ['6', '六']}
ORDINALS = {1: ['第一项', '第1项', '最前面那项'], 2: ['第二项', '第2项'], 3: ['第三项', '第3项']}
DEFAULT_TODAY = date(2026, 10, 13)
# A deliberately anchorless relative phrase is a correct V8 safe failure.
ALLOWED_CONFLICTS = frozenset({'no_anchor'})
WEIGHTS = {
    'field_rephrase': 16, 'qualifier_distractor': 9, 'unknown_field': 9, 'month_resolution': 16,
    'comparison_roles': 14, 'negation_correction': 12, 'report_scope': 8, 'report_knowledge': 8,
    'multi_turn_reference': 10,
}


def shift(month, offset):
    from utils.report_intent import shift_month
    return shift_month(month, offset)


class Draft:
    """A sample under construction: context, label slots and rendered text."""

    def __init__(self, category, catalog, fallback, today=DEFAULT_TODAY, *, history=(),
                 previous=None, fictional=False):
        self.category, self.catalog, self.fallback, self.today = category, list(catalog), fallback, today
        self.history, self.previous, self.fictional = list(history), previous, fictional
        self.items, self.scope = [], 'only_listed'
        self.target, self.target_mention, self.anchor = None, '', 'none'
        self.compare, self.baseline, self.baseline_mention = False, None, ''
        self.excluded, self.knowledge, self.unresolved, self.query = [], '', False, ''

    def label(self):
        return {'task_type': 'report_with_knowledge' if self.knowledge else 'report',
                'fields': [{'mention': mention, 'field': field} for mention, field in self.items],
                'scope': self.scope, 'target_month': self.target,
                'target_mention': self.target_mention, 'target_anchor': self.anchor,
                'compare': self.compare, 'baseline_month': self.baseline,
                'baseline_mention': self.baseline_mention, 'excluded_fields': list(self.excluded),
                'knowledge_question': self.knowledge, 'unresolved': self.unresolved}

    def gold(self):
        """The contract's meaning of the label, written independently of resolve."""
        full = self.scope == 'full_report'
        limited = not full and (self.scope == 'only_listed' or bool(self.items))
        order = list(dict.fromkeys(field if field is not None else mention
                                   for mention, field in self.items)) if limited else []
        catalog = set(self.catalog)
        return {'fields': [name for name in order if name in catalog],
                'unknown_fields': [name for name in order if name not in catalog],
                'limited': limited, 'full_report': full, 'target_month': self.target,
                'compare': self.compare,
                'comparison_month': self.baseline if self.compare else None,
                'knowledge_requested': bool(self.knowledge), 'unresolved_month': self.unresolved,
                'requested_field_order': order}


class World:
    def __init__(self, rng):
        from utils.records import load_records
        from utils.report_render import record_fields
        self.rng = rng
        self.fields = {key: list(record_fields(value)) for key, value in load_records().items()}
        self.keys = sorted(key for key, value in self.fields.items() if len(value) >= 3)
        self.all_fields = sorted({name for names in self.fields.values() for name in names})

    def catalog(self, user, months):
        names = []
        for month in months:
            names.extend(self.fields.get((user, month), ()))
        return list(dict.fromkeys(names))

    def pick(self, months_needed=1, *, span=None):
        """A user with records; optionally a second data month span apart."""
        rng = self.rng
        user, month = rng.choice(self.keys)
        if span is None:
            return user, month
        other = shift(month, span)
        return (user, month, other) if (user, other) in self.fields else None


def fictional_catalog(rng):
    names = set()
    while len(names) < rng.randint(3, 6):
        names.add(rng.choice(FICTIONAL_PREFIXES) + rng.choice(FICTIONAL_SUFFIXES))
    return list(names)


def fictional_month(rng):
    return f'{rng.randint(2030, 2039)}-{rng.randint(1, 12):02d}'


def random_today(rng, month=None):
    """Usually the dev/test day; otherwise any day after the report month."""
    if (month is None or month < '2026-09') and rng.random() < .7:
        return DEFAULT_TODAY
    start = date(int(month[:4]), int(month[5:]), 28) if month else date(2026, 1, 1)
    return start + timedelta(days=rng.randrange(7, 400))


def absolute(month, rng):
    year, number = int(month[:4]), int(month[5:])
    forms = [f'{year}-{number:02d}', f'{year}年{number}月', f'{year}年{CN_MONTH[number]}月',
             f'{year}/{number:02d}', ''.join(CN_DIGIT[int(c)] for c in str(year)) + f'年{CN_MONTH[number]}月']
    return rng.choices(forms, weights=[4, 3, 3, 1, 1])[0]


def bare(month, rng):
    number = int(month[5:])
    return rng.choice([f'{number}月', f'{CN_MONTH[number]}月'])


def relative(offset, rng):
    if offset == 1:
        return rng.choice(['下个月', '下一个月', '后一个月', '下一月'])
    if offset == -1:
        return rng.choice(['上个月', '上一个月', '前一个月'])
    if offset == 2:
        return '下下个月'
    if offset == -2:
        return rng.choice(['上上个月', rng.choice(COUNT_WORDS[2]) + '个月前'])
    word = rng.choice(COUNT_WORDS[abs(offset)])
    return f'{word}个月后' if offset > 0 else rng.choice([f'{word}个月前', f'{word}个月之前'])


def surface(field, rng, fictional):
    if fictional or field not in FIELD_PARAPHRASES or rng.random() < .5:
        return field
    return rng.choice(FIELD_PARAPHRASES[field])


def join(mentions, rng):
    if len(mentions) == 1:
        return mentions[0]
    if len(mentions) == 2:
        return mentions[0] + rng.choice(['和', '、', '以及', '，还有']) + mentions[1]
    return '、'.join(mentions[:-1]) + rng.choice(['和', '、', '以及']) + mentions[-1]


def count_word(n, rng):
    return rng.choice({1: ['一'], 2: ['两', '2'], 3: ['三', '3'], 4: ['四', '4']}.get(n, [str(n)]))


def unknown_metric(rng, catalog, world):
    absent = [name for name in (world.all_fields if world else ()) if name not in catalog]
    pool = [name for name in UNKNOWN_METRICS if name not in catalog]
    return rng.choice(absent if absent and rng.random() < .35 else pool)


def base(category, rng, world, *, fictional=None, decorrelate=True):
    """A report month with records; returns (draft, month).

    With decorrelate, a fifth of samples also looked up another month, so the
    last lookup (current_lookup_month) is not always the requested target.
    """
    fictional = rng.random() < .25 if fictional is None else fictional
    other = shift_choice(rng) if decorrelate and rng.random() < .2 else None
    if fictional:
        month = fictional_month(rng)
        fallback = shift(month, other) if other else month
        draft = Draft(category, fictional_catalog(rng), fallback, random_today(rng, month),
                      fictional=True)
        return draft, month
    user, month = world.pick()
    lookups = [month]
    if other:
        lookups = [month, shift(month, other)] if rng.random() < .5 else [shift(month, other), month]
    draft = Draft(category, world.catalog(user, lookups), lookups[-1], random_today(rng, month))
    draft.user = user
    return draft, month


def shift_choice(rng):
    return rng.choice([-3, -2, -1, 1, 2])


def choose(rng, catalog, low=1, high=3):
    k = min(len(catalog), rng.randint(low, high))
    return rng.sample(catalog, k)


def listed(draft, rng, fields):
    draft.items = [(surface(field, rng, draft.fictional), field) for field in fields]
    return join([mention for mention, _ in draft.items], rng)


ONLY_TEMPLATES = [
    '{T}只列{F}。', '{T}仅要{F}。', '查{T}，只看{F}。', '{T}的记录里只需要{F}。',
    '麻烦调出{T}的{F}，其他先不看。', '帮我看看{T}的{F}，只报这些。', '请列出{T}的{F}。',
    '{T}：{F}，按这个顺序列出来。', '{T}给我{F}就行。', '{T}只返回{F}。',
    '{T}那份记录，摘出{F}。', '想了解{T}的{F}，仅显示这些。',
]


def b_field_rephrase(rng, world):
    draft, month = base('field_rephrase', rng, world)
    fields = choose(rng, draft.catalog, 1, 4)
    draft.target, draft.target_mention = month, absolute(month, rng)
    if len(fields) <= 2 and rng.random() < .3:
        draft.items = [(surface(field, rng, draft.fictional), field) for field in fields]
        mentions = [mention for mention, _ in draft.items]
        if len(mentions) == 1:
            template = rng.choice(['{T}{A}是多少？就问这一个。', '{T}的{A}怎么样？只看这个。'])
        else:
            template = rng.choice(['{T}的{A}多少，{B}又是多少？', '{T}{A}怎么样？还有{B}呢？'])
        draft.query = template.format(T=draft.target_mention, A=mentions[0], B=mentions[-1])
        return draft
    text = listed(draft, rng, fields)
    draft.query = rng.choice(ONLY_TEMPLATES).format(T=draft.target_mention, F=text)
    return draft


def b_qualifier(rng, world):
    draft, month = base('qualifier_distractor', rng, world)
    candidates = [(q + name, name) for q in QUALIFIERS for name in draft.catalog
                  if q + name not in draft.catalog]
    if not candidates:
        return None
    qualified, plain = rng.choice(candidates)
    items = [(qualified, None)]
    if rng.random() < .6:
        items.insert(rng.randint(0, 1), (plain, plain))
    others = [name for name in draft.catalog if name != plain]
    if others and rng.random() < .4:
        extra = rng.choice(others)
        items.append((surface(extra, rng, draft.fictional), extra))
    draft.items = items
    draft.target, draft.target_mention = month, absolute(month, rng)
    draft.query = rng.choice(ONLY_TEMPLATES).format(
        T=draft.target_mention, F=join([mention for mention, _ in items], rng))
    return draft


def b_unknown(rng, world):
    draft, month = base('unknown_field', rng, world)
    fields = choose(rng, draft.catalog, 0 if rng.random() < .2 else 1, 2)
    items = [(surface(field, rng, draft.fictional), field) for field in fields]
    for _ in range(rng.choice([1, 1, 2])):
        name = unknown_metric(rng, draft.catalog, None if draft.fictional else world)
        if all(name != mention for mention, _ in items):
            items.insert(rng.randint(0, len(items)), (name, None))
    draft.items = items
    draft.target, draft.target_mention = month, absolute(month, rng)
    draft.query = rng.choice(ONLY_TEMPLATES).format(
        T=draft.target_mention, F=join([mention for mention, _ in items], rng))
    return draft


def previous_turn(rng, world, month, fields, fictional, catalog):
    """A rendered earlier user request and its saved absolute intent."""
    from utils.report_intent import ReportIntent
    mentions = [surface(field, rng, fictional) for field in fields]
    text = rng.choice([
        '{T}请把{F}依次列成{n}行。', '{T}只列{F}。', '查{T}，只看{F}。', '{T}先记{F}。',
    ]).format(T=absolute(month, rng), F=join(mentions, rng), n=count_word(len(fields), rng))
    previous = ReportIntent(fields=tuple(fields), target_month=month, limited=True)
    return text, previous, mentions


def b_month(rng, world):
    variant = rng.choice(['absolute', 'previous', 'previous', 'bare', 'lookup', 'today',
                          'event', 'ambiguous'])
    fictional = rng.random() < .25
    if variant == 'absolute':
        draft = b_field_rephrase(rng, world)
        draft.category = 'month_resolution'
        return draft
    if variant in ('previous', 'bare'):
        if fictional:
            catalog, before = fictional_catalog(rng), fictional_month(rng)
            offset = rng.choice([-2, -1, 1, 1, 2, 3, -3])
            month = shift(before, offset) if variant == 'previous' else (
                f'{before[:4]}-{rng.randint(1, 12):02d}')
        else:
            user, before = world.pick()
            offset = rng.choice([-2, -1, 1, 1, 2, 3, -3])
            month = shift(before, offset) if variant == 'previous' else (
                f'{before[:4]}-{rng.randint(1, 12):02d}')
            if month == before or (user, month) not in world.fields:
                return None
            catalog = world.catalog(user, [before, month])
        if month == before:
            return None
        prior = choose(rng, catalog, 1, 3)
        text, previous, _ = previous_turn(rng, world, before, prior, fictional, catalog)
        draft = Draft('month_resolution', catalog, month, random_today(rng, max(month, before)),
                      history=[text] if rng.random() < .7 else [], previous=previous,
                      fictional=fictional)
        fields = choose(rng, catalog, 1, 2)
        names = listed(draft, rng, fields)
        draft.target = month
        if variant == 'previous':
            draft.target_mention, draft.anchor = relative(offset, rng), 'previous_target'
            template = rng.choice(['往后挪到{R}，{F}照旧。', '{R}只看{F}。', '再看{R}的{F}。',
                                   '接着看{R}，只列{F}。'])
            draft.query = template.format(R=draft.target_mention, F=names)
        else:
            written = bare(month, rng)
            draft.target_mention = written
            prefix = rng.choice(['同年', '', '再看'])
            draft.query = rng.choice(['{P}{M}只列{F}。', '那{P}{M}呢？只要{F}。']).format(
                P=prefix, M=written, F=names)
        return draft
    if variant in ('lookup', 'today', 'event', 'ambiguous'):
        draft, lookup = base('month_resolution', rng, world, fictional=fictional,
                             decorrelate=variant in ('event', 'ambiguous'))
        fields = choose(rng, draft.catalog, 1, 2)
        names = listed(draft, rng, fields)
        if variant == 'lookup':
            offset = rng.choice([-1, -1, 1, -2, 2, -3])
            draft.target, draft.anchor = shift(lookup, offset), 'current_lookup'
            draft.target_mention = relative(offset, rng)
            lead = rng.choice(['以刚查到的这份为起点，', '从刚才查到的那份记录算起，', '以这次查到的月份为准，'])
            draft.query = f'{lead}{draft.target_mention}只列{names}。'
        elif variant == 'today':
            offset = rng.choice([-1, -1, -1, 1, -2])
            draft.today = date(int(shift(lookup, -offset)[:4]), int(shift(lookup, -offset)[5:]),
                               rng.randint(1, 28))
            draft.target, draft.anchor = lookup, 'today'
            draft.target_mention = relative(offset, rng)
            draft.query = rng.choice(['{R}只列{F}。', '请生成我{R}的报告，只要{F}。',
                                      '{R}的{F}给我看一下，只看这些。']).format(
                R=draft.target_mention, F=names)
        elif variant == 'event':
            offset = rng.choice([-1, 1, 1])
            draft.target_mention = relative(offset, rng)
            event = rng.choice(['我搬家那个月', '我买机器那个月', '第一次换刷那个月', '上次报修那个月'])
            draft.unresolved = True
            draft.query = rng.choice(['从{E}算起的{R}，只列{F}。', '{E}的{R}，只看{F}。']).format(
                E=event, R=draft.target_mention, F=names)
        else:
            n = rng.choice([2, 3])
            draft.unresolved = True
            draft.query = rng.choice(['前{N}个月的{F}，只列这些。', '把前{N}个月的{F}列出来。']).format(
                N=rng.choice(COUNT_WORDS[n]), F=names)
        return draft
    return None


def b_compare(rng, world):
    variant = rng.choice(['basis', 'basis', 'plain', 'roles', 'mom', 'ago', 'directional',
                          'negated', 'previous', 'correction', 'full'])
    fictional = rng.random() < .25
    if variant in ('mom', 'ago', 'directional'):
        span = -1 if variant == 'mom' else -rng.choice([2, 3, 4])
    else:
        span = rng.choice([-6, -4, -3, -2, -1, 1, 2, 3])
    # The agent looks both months up in either order; the last one is the
    # current lookup, so it must not reveal which month is the target.
    if fictional:
        catalog, target = fictional_catalog(rng), fictional_month(rng)
        baseline = shift(target, span)
        months = [target, baseline] if rng.random() < .5 else [baseline, target]
    else:
        picked = world.pick(span=span)
        if picked is None:
            return None
        user, target, baseline = picked
        months = [target, baseline] if rng.random() < .5 else [baseline, target]
        catalog = world.catalog(user, months)
    draft = Draft('comparison_roles', catalog, months[-1], random_today(rng, max(target, baseline)),
                  fictional=fictional)
    fields = choose(rng, catalog, 1, 2)
    names = listed(draft, rng, fields)
    draft.target, draft.compare, draft.baseline = target, True, baseline
    same_year = target[:4] == baseline[:4]
    if variant == 'basis':
        draft.baseline_mention = absolute(baseline, rng)
        draft.target_mention = bare(target, rng) if same_year and rng.random() < .5 else absolute(target, rng)
        draft.query = rng.choice([
            '拿{B}当参照，{T}的{F}涨了还是跌了？只看{F}。',
            '{B}为基期，{T}的{F}变化多少？只看这个。',
        ]).format(B=draft.baseline_mention, T=draft.target_mention, F=names)
    elif variant == 'plain':
        draft.target_mention, draft.baseline_mention = absolute(target, rng), absolute(baseline, rng)
        draft.query = rng.choice(['{T}的{F}和{B}比一下。', '{T}只列{F}，并与{B}对比。',
                                  '对比{B}，{T}的{F}有什么变化？']).format(
            T=draft.target_mention, B=draft.baseline_mention, F=names)
    elif variant == 'roles':
        draft.target_mention, draft.baseline_mention = absolute(target, rng), absolute(baseline, rng)
        draft.query = rng.choice(['{F}做个对比：{T}是本期，{B}是参照。',
                                  '只看{F}，基期{B}，本期{T}。']).format(
            T=draft.target_mention, B=draft.baseline_mention, F=names)
    elif variant == 'mom':
        draft.target_mention, draft.baseline_mention = absolute(target, rng), '环比'
        draft.query = rng.choice(['{T}的{F}环比怎么样？', '{T}只列{F}，看环比。']).format(
            T=draft.target_mention, F=names)
    elif variant == 'ago':
        word = rng.choice(COUNT_WORDS[-span])
        draft.target_mention, draft.baseline_mention = absolute(target, rng), f'{word}个月前'
        draft.query = rng.choice(['{T}的{F}跟{A}比怎么样？只看这一项。', '{T}只列{F}，和{A}相比。']).format(
            T=draft.target_mention, A=draft.baseline_mention, F=names)
    elif variant == 'directional':
        word = rng.choice(COUNT_WORDS[-span])
        draft.target_mention, draft.baseline_mention = absolute(target, rng), f'往前{word}个月'
        draft.query = '{T}的{F}，和{A}对比一下。'.format(
            T=draft.target_mention, A=draft.baseline_mention, F=names)
    elif variant == 'negated':
        draft.compare, draft.baseline = False, None
        draft.target_mention = absolute(target, rng)
        draft.query = rng.choice(['{T}的{F}单独列出，无需对比。', '{T}只列{F}，不用和别的月份比。']).format(
            T=draft.target_mention, F=names)
    elif variant == 'previous':
        from utils.report_intent import ReportIntent
        draft.previous = ReportIntent(fields=tuple(fields), target_month=baseline, limited=True)
        draft.target_mention = absolute(target, rng)
        if rng.random() < .5:
            draft.baseline_mention = bare(baseline, rng) if same_year else absolute(baseline, rng)
            template = '{B}那份当基准，现在看{T}的{F}变化。'
        else:
            draft.baseline_mention = '上次那个月'
            template = '上次那个月作为对照，{T}的{F}差了多少？'
        draft.query = template.format(B=draft.baseline_mention, T=draft.target_mention, F=names)
    elif variant == 'correction':
        wrong = shift(baseline, rng.choice([-2, -1, 1]))
        if wrong == target:
            return None
        draft.target_mention = absolute(target, rng)
        draft.baseline_mention = absolute(baseline, rng)
        draft.query = rng.choice(['{T}的{F}做对比，基期不是{W}而是{B}。',
                                  '对比{T}的{F}：参照月换掉{W}，改为{B}。']).format(
            T=draft.target_mention, F=names, W=absolute(wrong, rng), B=draft.baseline_mention)
    else:
        draft.items, draft.scope = [], 'full_report'
        draft.target_mention, draft.baseline_mention = absolute(target, rng), absolute(baseline, rng)
        draft.query = rng.choice(['{T}完整报告，和{B}对比。', '把{T}的全部记录跟{B}比较一下。']).format(
            T=draft.target_mention, B=draft.baseline_mention)
    return draft


def b_negation(rng, world):
    variant = rng.choice(['month_switch', 'month_retract', 'month_change', 'drop_only',
                          'drop_only', 'drop_full', 'field_fix'])
    draft, month = base('negation_correction', rng, world)
    draft.target, draft.target_mention = month, absolute(month, rng)
    if variant.startswith('month'):
        other = shift(month, rng.choice([-3, -2, -1, 1, 2]))
        lookups = [month, other] if rng.random() < .5 else [other, month]
        draft.fallback = lookups[-1]
        if not draft.fictional:
            draft.catalog = world.catalog(draft.user, lookups)
        written = absolute(other, rng)
        names = listed(draft, rng, choose(rng, draft.catalog, 1, 2))
        draft.query = {
            'month_switch': '不是{O}，而是{T}，只列{F}。',
            'month_retract': '{O}那份先不要了，改看{T}的{F}。',
            'month_change': '本来想看{O}，改为{T}，只列{F}。',
        }[variant].format(O=written, T=draft.target_mention, F=names)
        return draft
    if len(draft.catalog) < 2:
        return None
    dropped = rng.choice(draft.catalog)
    rest = [name for name in draft.catalog if name != dropped]
    draft.excluded = [dropped]
    if variant == 'drop_full':
        draft.scope = 'full_report'
        draft.query = rng.choice(['{T}完整报告，去掉{X}。', '{T}的全部字段都要，但拿掉{X}。',
                                  '{T}所有指标都列出，{X}除外。']).format(T=draft.target_mention, X=dropped)
        return draft
    if variant == 'drop_only':
        names = listed(draft, rng, rng.sample(rest, min(len(rest), rng.randint(1, 2))))
        draft.query = rng.choice(['{T}去掉{X}，只留{F}。',
                                  '{T}不要{X}了，只要{F}。']).format(T=draft.target_mention, X=dropped, F=names)
        return draft
    wrong, right = dropped, rng.choice(rest)
    draft.excluded = []
    draft.items = [(right, right)]
    draft.query = '{T}只列{W}。不对，不是{W}，而是{R}。'.format(T=draft.target_mention, W=wrong, R=right)
    return draft


def b_scope(rng, world):
    variant = rng.choice(['unspecified', 'full', 'full', 'limited_to_full', 'full_to_limited'])
    draft, month = base('report_scope', rng, world)
    draft.target, draft.target_mention = month, absolute(month, rng)
    if variant == 'unspecified':
        draft.scope = 'unspecified'
        draft.query = rng.choice(['看看{T}的报告。', '{T}的使用记录给我看一下。', '查一下{T}的记录。']).format(
            T=draft.target_mention)
    elif variant == 'full':
        draft.scope = 'full_report'
        draft.query = rng.choice(['{T}完整报告。', '把{T}的全部记录都列出来。', '{T}所有指标都要。',
                                  '给我{T}的完整报告。']).format(T=draft.target_mention)
    elif variant == 'limited_to_full':
        from utils.report_intent import ReportIntent
        prior = choose(rng, draft.catalog, 1, 2)
        draft.previous = ReportIntent(fields=tuple(prior), target_month=month, limited=True)
        draft.scope = 'full_report'
        draft.query = '上次只看了{P}，这回{T}要完整报告。'.format(
            P=join(prior, rng), T=draft.target_mention)
    else:
        from utils.report_intent import ReportIntent
        draft.previous = ReportIntent(target_month=shift(month, -1))
        names = listed(draft, rng, choose(rng, draft.catalog, 1, 2))
        draft.query = '上回给的是全量报告，{T}这次只要{F}。'.format(T=draft.target_mention, F=names)
    return draft


def b_knowledge(rng, world):
    variant = rng.choice(['ask', 'ask', 'ask_question', 'about_field', 'about_field', 'decline',
                          'full_ask'])
    draft, month = base('report_knowledge', rng, world)
    draft.target, draft.target_mention = month, absolute(month, rng)
    question = rng.choice(KNOWLEDGE_QUESTIONS)
    if variant == 'full_ask':
        draft.scope, draft.knowledge = 'full_report', question
        draft.query = f'{draft.target_mention}完整报告，{rng.choice(KNOWLEDGE_LEADS)}{question}'
        return draft
    fields = choose(rng, draft.catalog, 1, 2)
    names = listed(draft, rng, fields)
    if variant == 'decline':
        draft.query = '{T}只要{F}的数值，{D}。'.format(T=draft.target_mention, F=names,
                                                     D=rng.choice(KNOWLEDGE_DECLINES))
        return draft
    if variant == 'about_field':
        mention = draft.items[0][0]
        draft.knowledge = rng.choice(KNOWLEDGE_ABOUT_FIELD).format(f=mention)
        draft.query = f'{draft.target_mention}只列{names}，{draft.knowledge}'
        return draft
    draft.knowledge = question
    if variant == 'ask_question' and len(fields) == 1:
        draft.query = f'{draft.target_mention}的{names}是多少？{rng.choice(KNOWLEDGE_LEADS)}{question}'
    else:
        draft.query = f'{draft.target_mention}只列{names}；{rng.choice(KNOWLEDGE_LEADS)}{question}'
    return draft


def b_multi_turn(rng, world):
    variant = rng.choice(['ordinal', 'ordinal', 'repeat', 'next', 'absolute'])
    fictional = rng.random() < .25
    if fictional:
        catalog, before = fictional_catalog(rng), fictional_month(rng)
        current = shift(before, 1)
    else:
        picked = world.pick(span=1)
        if picked is None:
            return None
        user, before, current = picked
        catalog = world.catalog(user, [before, current])
    prior = choose(rng, catalog, 2, 3)
    if len(prior) < 2:
        return None
    text, previous, mentions = previous_turn(rng, world, before, prior, fictional, catalog)
    draft = Draft('multi_turn_reference', catalog, current, random_today(rng, current),
                  history=[text], previous=previous, fictional=fictional)
    draft.target = before
    if variant == 'ordinal':
        position = rng.randint(1, len(prior))
        if position == len(prior) and rng.random() < .5:
            word = rng.choice(['排在末尾的那项', '最后一项'])
        else:
            word = rng.choice(ORDINALS[position])
        draft.items = [(mentions[position - 1], prior[position - 1])]
        draft.query = rng.choice([
            '刚才那{n}项里只保留{W}，月份还用上一轮的。',
            '上一轮那{n}个指标里只要{W}，月份不变。',
        ]).format(n=count_word(len(prior), rng), W=word)
    elif variant == 'repeat':
        draft.items = list(zip(mentions, prior))
        draft.query = rng.choice(['把刚才那{n}项按原顺序再给我一次，月份不变。',
                                  '还是上一轮那{n}项，同一个月份，再列一次。']).format(
            n=count_word(len(prior), rng))
    elif variant == 'next':
        draft.items = list(zip(mentions, prior))
        draft.target, draft.anchor = current, 'previous_target'
        draft.target_mention = relative(1, rng)
        draft.query = rng.choice(['换到{R}，字段不变。', '同样这几项，看{R}。']).format(R=draft.target_mention)
    else:
        target = current
        draft.items = list(zip(mentions, prior))
        draft.target, draft.target_mention = target, absolute(target, rng)
        draft.query = rng.choice(['同样的字段，看{T}。', '还是这{n}项，换成{T}。']).format(
            T=draft.target_mention, n=count_word(len(prior), rng))
    return draft


BUILDERS = {
    'field_rephrase': b_field_rephrase, 'qualifier_distractor': b_qualifier,
    'unknown_field': b_unknown, 'month_resolution': b_month, 'comparison_roles': b_compare,
    'negation_correction': b_negation, 'report_scope': b_scope, 'report_knowledge': b_knowledge,
    'multi_turn_reference': b_multi_turn,
}


def verify(draft):
    """Run the real resolver on the label; return captured inputs or a reason."""
    from agent.intent import resolve
    from agent.intent.schema import IntentProposal
    from agent.runtime import RunContext
    from evaluation.intent_eval import adapt_result, score_case
    proposal = IntentProposal.model_validate(draft.label())
    # Semantic slots cannot be checked by resolve when label and gold agree;
    # at least every copied span must exist in the text it claims to copy.
    texts = (draft.query, *draft.history)
    spans = [mention for mention, _ in draft.items]
    if any(not any(span in text for text in texts) for span in spans):
        return None, 'span:mention'
    for span in (draft.target_mention, draft.baseline_mention, draft.knowledge):
        if span and span not in draft.query:
            return None, 'span:query'
    captured = {}

    def scripted(query, **kwargs):
        captured.update(query=query, **{key: value for key, value in kwargs.items()
                                        if key not in ('run', 'cfg')})
        return proposal

    gold = draft.gold()
    with patch.object(resolve, 'parse_turn_intent', scripted):
        for mode in ('hybrid', 'llm_only'):
            result = resolve.resolve_turn_intent(
                draft.query, history_queries=tuple(draft.history), previous_intent=draft.previous,
                known_fields=tuple(draft.catalog), fallback_month=draft.fallback, today=draft.today,
                mode=mode, run=RunContext())
            if result.trace.get('fallback_reason'):
                return None, f"{mode}:fallback:{result.trace['fallback_reason']}"
            conflicts = set(result.trace.get('conflicts', ())) - ALLOWED_CONFLICTS
            if mode == 'hybrid' and conflicts:
                return None, 'hybrid:conflict:' + ','.join(sorted(conflicts))
            score = score_case(adapt_result(result, tuple(draft.catalog)), gold)
            if not score['pass']:
                return None, f'{mode}:gold_mismatch'
    return captured, None


def to_example(draft, captured):
    from agent.intent.llm_parser import build_messages
    messages = build_messages(captured['query'], history_queries=captured['history_queries'],
                              previous_intent=captured['previous_intent'],
                              known_fields=captured['known_fields'], today=captured['today'],
                              fallback_month=captured['fallback_month'], prompt=SFT_PROMPT)
    answer = json.dumps(draft.label(), ensure_ascii=False, separators=(',', ':'))
    return {'category': draft.category, 'fictional': draft.fictional,
            'system': messages[0].content,
            'messages': [{'role': 'user', 'content': messages[1].content},
                         {'role': 'assistant', 'content': answer}],
            'gold': draft.gold()}


def generate(count, seed):
    rng = random.Random(seed)
    world = World(rng)
    names, weights = list(WEIGHTS), list(WEIGHTS.values())
    kept, seen, rejected = [], set(), Counter()
    attempts = 0
    while len(kept) < count and attempts < count * 20:
        attempts += 1
        category = rng.choices(names, weights=weights)[0]
        draft = BUILDERS[category](rng, world)
        if draft is None:
            rejected['builder_skip'] += 1
            continue
        key = (draft.query, tuple(draft.history), tuple(draft.catalog), draft.fallback)
        if key in seen:
            rejected['duplicate'] += 1
            continue
        seen.add(key)
        captured, reason = verify(draft)
        if captured is None:
            rejected[f'{draft.category}:{reason}'] += 1
            continue
        kept.append(to_example(draft, captured))
    return kept, rejected, attempts


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--count', type=int, default=6000)
    parser.add_argument('--seed', type=int, default=20261030)
    parser.add_argument('--val-fraction', type=float, default=.05)
    parser.add_argument('--out', required=True)
    args = parser.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    examples, rejected, attempts = generate(args.count, args.seed)
    random.Random(args.seed + 1).shuffle(examples)
    cut = int(len(examples) * args.val_fraction)
    splits = {'val': examples[:cut], 'train': examples[cut:]}
    digests = {}
    for name, rows in splits.items():
        data = json.dumps(rows, ensure_ascii=False, indent=1).encode('utf-8')
        (out / f'{name}.json').write_bytes(data)
        digests[f'{name}.json'] = hashlib.sha256(data).hexdigest()
    (out / 'dataset_info.json').write_text(json.dumps({
        f'intent_sft_{name}': {
            'file_name': f'{name}.json', 'formatting': 'sharegpt',
            'columns': {'messages': 'messages', 'system': 'system'},
            'tags': {'role_tag': 'role', 'content_tag': 'content',
                     'user_tag': 'user', 'assistant_tag': 'assistant'}}
        for name in splits}, ensure_ascii=False, indent=2), encoding='utf-8')
    manifest = {
        'seed': args.seed, 'requested': args.count, 'kept': len(examples), 'attempts': attempts,
        'splits': {name: len(rows) for name, rows in splits.items()},
        'categories': Counter(row['category'] for row in examples),
        'fictional': sum(row['fictional'] for row in examples),
        'rejected': dict(rejected.most_common()), 'sha256': digests,
        'generator_sha256': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                             for name in ('training/intent_sft/generate.py',
                                          'training/intent_sft/lexicon.py', SFT_PROMPT)},
    }
    (out / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                                       encoding='utf-8')
    print(json.dumps({key: manifest[key] for key in ('kept', 'attempts', 'splits', 'categories')},
                     ensure_ascii=False))
    print('top rejections:', rejected.most_common(12))


if __name__ == '__main__':
    main()
