"""Post-P3 amendments: invented metrics, dates and scripted responses only."""
import pytest

from agent.intent.validate import _metric_mention
from utils.report_intent import ReportIntent, resolve_report_intent
from utils.report_render import render_lookup
from test_llm_intent import (
    CATALOG, TODAY, fictional_record, install_model, no_real_intent_model, proposal, resolve,
)


@pytest.mark.parametrize('month', [
    '2036-7', '2036/07', '2036年七月', '二〇三六年七月', '二零三六年7月',
    '同年七月', '7月', '七月', '上个月', '下一月', '上上个月',
    '三个月前', '两个月之前', '往前三个月', '往后2个月',
])
def test_month_prose_is_not_a_component_qualifier(monkeypatch, month):
    mention = month + '晶片寿命的报告'
    install_model(monkeypatch, proposal(fields=[{'mention': mention, 'field': '晶片寿命'}]))
    result = resolve('2032年11月只列' + mention)
    assert result.intent.fields == ('晶片寿命',)
    assert 'qualifier_dropped' not in result.trace['conflicts']


@pytest.mark.parametrize('label', [
    '2036-7', '2036年七月的报告', '二〇三六年七月使用记录',
    '同年七月的数据', '7月的记录', '七月数据', '下一月的报告',
    '往前三个月使用记录', '报告', '的记录', '使用记录', '数据',
])
def test_non_metric_unknown_does_not_block_an_unspecified_report(monkeypatch, label):
    install_model(monkeypatch, proposal(fields=[{'mention': label, 'field': None}]))
    result = resolve('2032年11月看看' + label)
    assert result.intent.fields == ()
    assert not result.intent.limited
    assert result.final_scope == 'unspecified'
    assert 'non_metric_unknown_dropped' in result.trace['conflicts']
    answer = render_lookup(fictional_record(), intent=result.intent)
    assert '星辉率' in answer and '晶片寿命' in answer


@pytest.mark.parametrize('label', ['北舱星辉率', '2036年七月北舱星辉率的报告'])
def test_real_scope_qualifier_is_not_stripped(monkeypatch, label):
    install_model(monkeypatch, proposal(fields=[{'mention': label, 'field': '星辉率'}]))
    result = resolve('2032年11月只列' + label)
    assert result.intent.fields == (label,)
    assert 'qualifier_dropped' in result.trace['conflicts']
    assert 'non_metric_unknown_dropped' not in result.trace['conflicts']


@pytest.mark.parametrize('label', ['北舱流晶消耗', '2036年七月北舱流晶消耗的记录',
                                   '每日10次晶片更换', '北舱报告完成率'])
def test_meaningful_unknown_retains_its_original_anchored_label(monkeypatch, label):
    install_model(monkeypatch, proposal(fields=[{'mention': label, 'field': None}]))
    result = resolve('2032年11月只列' + label)
    assert result.intent.fields == (label,)
    assert 'non_metric_unknown_dropped' not in result.trace['conflicts']


def test_dropping_date_noise_keeps_real_known_and_unknown_selection_order(monkeypatch):
    install_model(monkeypatch, proposal(fields=[
        {'mention': '2032年11月的报告', 'field': None},
        {'mention': '星辉率', 'field': '星辉率'},
        {'mention': '流晶消耗', 'field': None},
        {'mention': '晶片寿命', 'field': '晶片寿命'}]))
    result = resolve('2032年11月的报告只列星辉率、流晶消耗、晶片寿命')
    assert result.intent.fields == ('星辉率', '流晶消耗', '晶片寿命')
    assert result.intent.limited


def test_explicit_empty_only_request_stays_limited(monkeypatch):
    install_model(monkeypatch, proposal(fields=[{'mention': '2032年11月', 'field': None}]))
    result = resolve('只列2032年11月的报告')
    assert result.intent.limited and result.final_scope == 'only_listed'


def test_catalog_label_named_data_is_not_an_unknown(monkeypatch):
    install_model(monkeypatch, proposal(fields=[{'mention': '数据', 'field': '数据'}]))
    result = resolve('2032年11月只列数据', known_fields=(*CATALOG, '数据'))
    assert result.intent.fields == ('数据',)
    assert 'non_metric_unknown_dropped' not in result.trace['conflicts']


@pytest.mark.parametrize('anchor', ['current_lookup', 'today'])
@pytest.mark.parametrize('phrase,previous,lookup', [
    ('下一月', '2036-12', '2037-01'),
    ('前一个月', '2037-01', '2036-12'),
    ('上上个月', '2037-02', '2036-12'),
    ('三个月后', '2036-11', '2037-02'),
])
def test_previous_offset_agrees_with_actual_lookup(monkeypatch, anchor, phrase, previous, lookup):
    install_model(monkeypatch, proposal(target_month=lookup, target_mention=phrase,
                                       target_anchor=anchor))
    result = resolve(phrase + '只列星辉率', previous_intent=ReportIntent(target_month=previous),
                     fallback_month=lookup)
    assert result.intent.target_month == lookup
    assert 'anchor_lookup_consistency' in result.trace['conflicts']
    assert 'relative_month_recomputed' not in result.trace['conflicts']


@pytest.mark.parametrize('anchor', ['current_lookup', 'today'])
@pytest.mark.parametrize('previous,lookup', [(None, '2037-01'), ('2036-13', '2037-01'),
                                            ('2036-11', '2037-01'), ('2036-12', None)])
def test_no_previous_or_two_mismatches_do_not_adjust(monkeypatch, anchor, previous, lookup):
    install_model(monkeypatch, proposal(target_month='2037-01', target_mention='下一月',
                                       target_anchor=anchor))
    result = resolve('下一月只列星辉率', previous_intent=ReportIntent(target_month=previous),
                     fallback_month=lookup)
    assert 'anchor_lookup_consistency' not in result.trace['conflicts']
    expected = '2033-04' if anchor == 'today' else '2037-02' if lookup else None
    assert result.intent.target_month == expected


def test_declared_calculation_already_agrees_with_lookup(monkeypatch):
    install_model(monkeypatch, proposal(target_month='2033-04', target_mention='下一月',
                                       target_anchor='today'))
    result = resolve('下一月只列星辉率', previous_intent=ReportIntent(target_month='2033-03'),
                     fallback_month='2033-04')
    assert result.intent.target_month == '2033-04'
    assert 'anchor_lookup_consistency' not in result.trace['conflicts']


@pytest.mark.parametrize('anchor', ['none', 'previous_target'])
def test_other_declared_anchors_keep_their_contract(monkeypatch, anchor):
    install_model(monkeypatch, proposal(target_month='2037-01', target_mention='下一月',
                                       target_anchor=anchor))
    result = resolve('下一月只列星辉率', previous_intent=ReportIntent(target_month='2036-12'),
                     fallback_month='2037-01')
    assert result.intent.target_month == (None if anchor == 'none' else '2037-01')
    assert 'anchor_lookup_consistency' not in result.trace['conflicts']


def test_deliberate_null_safe_failure_stays_null(monkeypatch):
    install_model(monkeypatch, proposal(target_month=None, unresolved=True,
                                       target_mention='下一月', target_anchor='current_lookup'))
    result = resolve('下一月只列星辉率', previous_intent=ReportIntent(target_month='2036-12'),
                     fallback_month='2037-01')
    assert result.intent.target_month is None and result.intent.unresolved_month
    assert 'anchor_lookup_consistency' not in result.trace['conflicts']


def test_negated_relative_phrase_cannot_supply_lookup_consistency(monkeypatch):
    install_model(monkeypatch, proposal(target_month='2037-01', target_mention='下一月',
                                       target_anchor='current_lookup'))
    result = resolve('不要下一月的报告，只列2036年12月星辉率',
                     previous_intent=ReportIntent(target_month='2036-12'), fallback_month='2037-01')
    assert 'anchor_lookup_consistency' not in result.trace['conflicts']
    assert result.intent.target_month == '2036-12'
    assert 'month_unsupported' in result.trace['conflicts']


@pytest.mark.parametrize('query', ['2036年七月的使用记录', '二〇三六年七月晶片寿命的报告',
                                  '下一月只列星辉率', '前一个月的记录'])
def test_rule_equivalence_and_zero_intent_calls(query):
    previous = ReportIntent(target_month='2036-12')
    result = resolve(query, mode='rule', previous_intent=previous, fallback_month='2037-01')
    assert result.intent == resolve_report_intent(query, known_fields=CATALOG,
        previous_intent=previous, fallback_month='2037-01')


def test_llm_only_does_not_apply_either_amendment(monkeypatch):
    install_model(monkeypatch, proposal(fields=[{'mention': '2037年一月的报告', 'field': None}],
        target_month='2037-02', target_mention='下一月', target_anchor='current_lookup'))
    result = resolve('下一月只列2037年一月的报告', mode='llm_only',
        previous_intent=ReportIntent(target_month='2036-12'), fallback_month='2037-01')
    assert result.intent.fields == ('2037年一月的报告',)
    assert result.intent.target_month == '2037-02'
    assert not result.trace['conflicts']
