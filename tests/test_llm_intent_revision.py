"""P1 review regressions: invented metrics, dates and scripted models only."""
from datetime import date
import json

import pytest
from langchain_core.messages import HumanMessage

from agent.intent.schema import IntentProposal
from agent.intent.validate import validate_proposal
from utils.report_intent import ReportIntent, resolve_report_intent, shift_month
from test_llm_intent import (
    CATALOG, TODAY, install_model, no_real_intent_model, proposal, resolve,
)


def test_first_relative_target_uses_today_without_shifting_lookup_twice(monkeypatch):
    install_model(monkeypatch, proposal(
        target_month='2033-02', target_mention='上个月', target_anchor='today'))
    result = resolve('上个月只列星辉率', fallback_month='2033-02', today=TODAY)
    assert result.intent.target_month == '2033-02'
    assert not result.intent.unresolved_month
    assert 'no_anchor' not in result.trace['conflicts']
    assert 'month_unsupported' not in result.trace['conflicts']


def test_explicit_lookup_origin_uses_current_lookup_instead_of_today(monkeypatch):
    install_model(monkeypatch, proposal(
        target_month='2033-02', target_mention='前一个月', target_anchor='current_lookup'))
    result = resolve('以刚查到的那份为起点，前一个月只列星辉率',
                     fallback_month='2032-11', today=TODAY,
                     previous_intent=ReportIntent(target_month='2033-01'))
    assert result.intent.target_month == '2032-10'
    assert 'relative_month_recomputed' in result.trace['conflicts']


def test_unknown_event_origin_remains_unresolved_despite_other_available_anchors(monkeypatch):
    install_model(monkeypatch, proposal(
        target_month='2032-10', target_mention='前一个月', target_anchor='none'))
    previous = ReportIntent(target_month='2032-12')
    result = resolve('搬到虚构星舱前一个月只列星辉率', previous_intent=previous,
                     fallback_month='2032-11', today=TODAY)
    assert result.intent.target_month is None
    assert result.intent.unresolved_month
    assert 'no_anchor' in result.trace['conflicts']


def test_multi_turn_target_uses_previous_target_instead_of_lookup(monkeypatch):
    install_model(monkeypatch, proposal(
        target_month='2033-02', target_mention='下一月', target_anchor='previous_target'))
    previous = ReportIntent(fields=('星辉率',), target_month='2032-12', limited=True)
    result = resolve('下一月只列星辉率', previous_intent=previous,
                     fallback_month='2033-02', today=TODAY)
    assert result.intent.target_month == '2033-01'
    assert 'relative_month_recomputed' in result.trace['conflicts']


@pytest.mark.parametrize('anchor, previous, lookup', [
    ('previous_target', None, '2032-11'),
    ('previous_target', ReportIntent(target_month='2032-13'), '2032-11'),
    ('current_lookup', ReportIntent(target_month='2032-12'), None),
    ('current_lookup', ReportIntent(target_month='2032-12'), '2032-13'),
])
def test_declared_missing_anchor_is_not_replaced_by_another(monkeypatch, anchor, previous, lookup):
    install_model(monkeypatch, proposal(
        target_month='2033-02', target_mention='上个月', target_anchor=anchor))
    result = resolve('上个月只列星辉率', previous_intent=previous,
                     fallback_month=lookup, today=TODAY)
    assert result.intent.target_month is None
    assert result.intent.unresolved_month
    assert 'no_anchor' in result.trace['conflicts']


def test_missing_today_anchor_is_unresolved_even_when_other_months_exist():
    query = '上个月只列星辉率'
    previous = ReportIntent(target_month='2032-12')
    value = IntentProposal.model_validate(proposal(
        target_month='2033-02', target_mention='上个月', target_anchor='today'))
    checked = validate_proposal(value, query=query, previous_intent=previous,
        known_fields=CATALOG, fallback_month='2032-11', today=None,
        rule_intent=resolve_report_intent(query, known_fields=CATALOG,
            fallback_month='2032-11', previous_intent=previous))
    assert checked.proposal.target_month is None
    assert checked.unresolved_month
    assert 'no_anchor' in checked.conflicts


@pytest.mark.parametrize('anchor', ['previous_target', 'current_lookup', 'today', 'none'])
def test_target_anchor_enum_accepts_all_declared_values(monkeypatch, anchor):
    install_model(monkeypatch, proposal(target_anchor=anchor))
    result = resolve()
    assert result.trace['source'] == 'llm'
    assert result.intent.target_month == '2032-11'


@pytest.mark.parametrize('anchor', ['lookup', 'TODAY', None, True, 1, []])
def test_target_anchor_rejects_invalid_enum_and_type(monkeypatch, anchor):
    install_model(monkeypatch, proposal(target_anchor=anchor))
    result = resolve()
    assert result.trace['source'] == 'rule'
    assert result.trace['fallback_reason'] == 'invalid_proposal'


def test_target_anchor_is_required(monkeypatch):
    value = proposal()
    value.pop('target_anchor')
    install_model(monkeypatch, value)
    result = resolve()
    assert result.trace['source'] == 'rule'
    assert result.trace['fallback_reason'] == 'invalid_proposal'


@pytest.mark.parametrize('lookup', ['2032-11', None])
def test_llm_input_contains_current_lookup_month(monkeypatch, lookup):
    model = install_model(monkeypatch, proposal())
    resolve(fallback_month=lookup)
    payload = json.loads(next(message.content for message in model.seen[0]
                              if isinstance(message, HumanMessage)))
    assert 'current_lookup_month' in payload
    assert payload['current_lookup_month'] == lookup
    assert payload['today'] == '2033-03-14'


@pytest.mark.parametrize('mention, offset', [
    ('三个月前', -3),
    ('3个月前', -3),
    ('3个月之前', -3),
    ('两个月之前', -2),
    ('之前两个月', -2),
    ('之前4个月', -4),
    ('4个月后', 4),
    ('十三个月后', 13),
    ('上上个月', -2),
    ('下下个月', 2),
])
def test_multi_month_target_offsets_are_recomputed_from_declared_anchor(monkeypatch, mention, offset):
    install_model(monkeypatch, proposal(
        target_month='2031-08', target_mention=mention, target_anchor='today'))
    result = resolve(f'{mention}只列星辉率', today=TODAY)
    assert result.intent.target_month == shift_month('2033-03', offset)
    assert 'relative_month_recomputed' in result.trace['conflicts']
    assert 'month_unsupported' not in result.trace['conflicts']


def test_double_previous_month_crosses_year_using_previous_target(monkeypatch):
    install_model(monkeypatch, proposal(
        target_month='2032-11', target_mention='上上个月', target_anchor='previous_target'))
    result = resolve('上上个月只列星辉率',
                     previous_intent=ReportIntent(target_month='2033-01'))
    assert result.intent.target_month == '2032-11'
    assert not result.intent.unresolved_month
    assert 'month_unsupported' not in result.trace['conflicts']


def test_three_month_relative_baseline_uses_validated_explicit_target(monkeypatch):
    install_model(monkeypatch, proposal(
        target_month='2033-02', target_mention='2033年2月', target_anchor='none',
        compare=True, baseline_month='2033-01', baseline_mention='三个月前'))
    result = resolve('2033年2月只列星辉率，与三个月前相比',
                     fallback_month='2033-02', previous_intent=ReportIntent(target_month='2032-09'))
    assert result.intent.target_month == '2033-02'
    assert result.intent.comparison_month == '2032-11'
    assert 'relative_month_recomputed' in result.trace['conflicts']


def test_double_previous_target_and_three_month_baseline_are_both_recomputed(monkeypatch):
    install_model(monkeypatch, proposal(
        target_month='2033-02', target_mention='上上个月', target_anchor='today',
        compare=True, baseline_month='2032-12', baseline_mention='三个月前'))
    result = resolve('上上个月只列星辉率，与三个月前相比', today=date(2033, 1, 14))
    assert result.intent.target_month == '2032-11'
    assert result.intent.comparison_month == '2032-08'
    assert 'relative_month_recomputed' in result.trace['conflicts']


def test_relative_baseline_cannot_substitute_previous_lookup_or_today_for_missing_target(monkeypatch):
    install_model(monkeypatch, proposal(
        target_month=None, target_mention='', target_anchor='none', unresolved=True,
        compare=True, baseline_month='2032-09', baseline_mention='三个月前'))
    result = resolve('目标月份尚未确定，只列星辉率，与三个月前相比',
                     previous_intent=ReportIntent(target_month='2032-12'),
                     fallback_month='2032-11', today=TODAY)
    assert result.intent.target_month is None
    assert result.intent.comparison_month is None
    assert result.intent.unresolved_month
    assert 'no_anchor' in result.trace['conflicts']


@pytest.mark.parametrize('mention', ['前三个月', '前3个月', '前两个月'])
def test_ambiguous_front_n_months_is_not_calculated(monkeypatch, mention):
    query = f'2033年2月只列星辉率，与{mention}相比'
    install_model(monkeypatch, proposal(
        target_month='2033-02', target_mention='2033年2月', target_anchor='today',
        compare=True, baseline_month='2032-11', baseline_mention=mention))
    result = resolve(query, fallback_month='2033-02')
    rule = resolve_report_intent(query, known_fields=CATALOG, fallback_month='2033-02')
    assert result.intent.comparison_month == rule.comparison_month
    assert 'month_unsupported' in result.trace['conflicts']
    assert 'relative_month_recomputed' not in result.trace['conflicts']


def test_fabricated_multi_month_mention_cannot_justify_a_month(monkeypatch):
    install_model(monkeypatch, proposal(
        target_month='2032-08', target_mention='三个月前', target_anchor='current_lookup'))
    result = resolve('2032年11月只列星辉率')
    assert result.intent.target_month == '2032-11'
    assert 'month_unsupported' in result.trace['conflicts']
    assert 'relative_month_recomputed' not in result.trace['conflicts']


@pytest.mark.parametrize('phrase', [
    '去掉晶片寿命', '删除晶片寿命', '拿掉晶片寿命', '除了晶片寿命都要',
])
def test_current_catalog_field_can_be_excluded_without_rule_negation_words(monkeypatch, phrase):
    install_model(monkeypatch, proposal(
        fields=[], scope='full_report', excluded_fields=['晶片寿命']))
    result = resolve(f'2032年11月完整报告，{phrase}')
    assert result.intent.fields == ('星辉率', '幻尘消耗')
    assert 'exclusion_not_in_text' not in result.trace['conflicts']


def test_current_field_mention_can_anchor_exclusion_of_catalog_alias(monkeypatch):
    install_model(monkeypatch, proposal(
        fields=[{'mention': '晶片还能用多久', 'field': '晶片寿命'}],
        scope='full_report', excluded_fields=['晶片寿命']))
    result = resolve('2032年11月完整报告，拿掉晶片还能用多久这一项')
    assert result.intent.fields == ('星辉率', '幻尘消耗')
    assert 'exclusion_not_in_text' not in result.trace['conflicts']


def test_historical_field_cannot_anchor_an_unmentioned_current_exclusion(monkeypatch):
    install_model(monkeypatch, proposal(
        fields=[], scope='full_report', excluded_fields=['晶片寿命']))
    result = resolve('2032年11月完整报告', history_queries=('2032年10月晶片寿命',))
    assert result.intent.fields == ()
    assert not result.intent.limited
    assert 'exclusion_not_in_text' in result.trace['conflicts']


def test_outside_catalog_exclusion_cannot_remove_any_catalog_field(monkeypatch):
    install_model(monkeypatch, proposal(
        fields=[], scope='full_report', excluded_fields=['虚构耗能']))
    result = resolve('2032年11月完整报告，删除虚构耗能')
    assert result.intent.fields == ()
    assert not result.intent.limited
    assert 'field_not_in_catalog' in result.trace['conflicts']


def test_existing_v9_rule_negation_still_discards_selected_field(monkeypatch):
    install_model(monkeypatch, proposal(fields=[
        {'mention': '星辉率', 'field': '星辉率'},
        {'mention': '晶片寿命', 'field': '晶片寿命'},
    ]))
    result = resolve('2032年11月只列星辉率，不要晶片寿命')
    assert result.intent.fields == ('星辉率',)
    assert 'negated_field_selected' in result.trace['conflicts']


@pytest.mark.parametrize('suffix', [
    '还剩', '剩下', '几天', '多少天', '天数', '是多少', '还能用', '多久',
    '这一项', '这一栏', '这项', '一栏', '记录', '数据',
    '还剩几天', '剩下多少天', '还能用多久',
])
def test_question_and_quantity_suffixes_do_not_drop_valid_field_mapping(monkeypatch, suffix):
    mention = '晶片寿命' + suffix
    install_model(monkeypatch, proposal(fields=[{'mention': mention, 'field': '晶片寿命'}]))
    result = resolve(f'2032年11月只列{mention}')
    assert result.intent.fields == ('晶片寿命',)
    assert 'qualifier_dropped' not in result.trace['conflicts']


@pytest.mark.parametrize('mention, field', [
    ('墙角星辉率', '星辉率'),
    ('还剩晶片寿命', '晶片寿命'),
    ('几天晶片寿命', '晶片寿命'),
    ('记录晶片寿命', '晶片寿命'),
    ('晶片寿命还剩舱', '晶片寿命'),
    ('晶片寿命记录仓', '晶片寿命'),
    ('墙角晶片寿命还剩几天', '晶片寿命'),
])
def test_question_words_in_prefix_or_component_do_not_hide_qualifiers(monkeypatch, mention, field):
    install_model(monkeypatch, proposal(fields=[{'mention': mention, 'field': field}]))
    result = resolve(f'2032年11月只列{mention}')
    assert result.intent.fields == (mention,)
    assert 'qualifier_dropped' in result.trace['conflicts']


@pytest.mark.parametrize('mention, field, expected, rejected', [
    ('主刷寿命还剩几天', '主刷寿命', '主刷寿命', False),
    ('墙角覆盖率', '覆盖率', '墙角覆盖率', True),
])
def test_review_supplied_phrases_use_only_a_fictional_catalog(monkeypatch, mention, field, expected, rejected):
    # These phrases came from the review request, never a CSV or evaluation.
    fictional_catalog = ('主刷寿命', '覆盖率')
    install_model(monkeypatch, proposal(fields=[{'mention': mention, 'field': field}]))
    result = resolve(f'2032年11月只列{mention}', known_fields=fictional_catalog)
    assert result.intent.fields == (expected,)
    assert ('qualifier_dropped' in result.trace['conflicts']) is rejected
