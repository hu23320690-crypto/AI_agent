"""P2.1 contract changes: fictional metrics and calendar evidence only."""
import pytest

from agent.intent.schema import IntentProposal
from agent.intent.validate import _directional_offset, _explicit_months, validate_proposal
from utils.report_intent import ReportIntent, resolve_report_intent
from test_llm_intent import (
    CATALOG, TODAY, install_model, no_real_intent_model, proposal, resolve,
)


def checked(query, **changes):
    return validate_proposal(
        IntentProposal.model_validate(proposal(**changes)), query=query,
        known_fields=CATALOG, today=TODAY,
        rule_intent=resolve_report_intent(query, known_fields=CATALOG))


def test_unanchored_catalog_mapping_is_kept_without_exposing_its_mention():
    value = checked('2032年11月只列星辉率', fields=[
        {'mention': '没写出的晶片耐用天数', 'field': '晶片寿命'}])
    assert value.proposal.fields[0].field == '晶片寿命'
    assert value.conflicts == ('mention_unanchored_kept',)


@pytest.mark.parametrize('field', [None, '虚构目录外寿命'])
def test_unknown_or_outside_catalog_unanchored_name_is_still_deleted(field):
    value = checked('2032年11月只列星辉率', fields=[
        {'mention': '没写出的晶片耐用天数', 'field': field}])
    assert value.proposal.fields == []
    assert 'mention_not_in_text' in value.conflicts
    assert 'mention_unanchored_kept' not in value.conflicts


def test_catalog_mapping_downgraded_by_v4_must_not_display_an_unanchored_unknown():
    value = checked('2032年11月只列星辉率', fields=[
        {'mention': '北舱星辉率', 'field': '星辉率'}])
    assert value.proposal.fields == []
    assert set(value.conflicts) == {
        'mention_unanchored_kept', 'qualifier_dropped', 'mention_not_in_text'}


def test_known_unanchored_mapping_is_still_subject_to_current_negation_v9():
    value = checked('2032年11月只列星辉率，不要晶片寿命', fields=[
        {'mention': '改写的晶片耐用天数', 'field': '晶片寿命'}])
    assert value.proposal.fields == []
    assert 'mention_unanchored_kept' in value.conflicts
    assert 'negated_field_selected' in value.conflicts


def test_original_unknown_name_stays_anchored_and_knowns_keep_their_order(monkeypatch):
    install_model(monkeypatch, proposal(fields=[
        {'mention': '改写的晶片耐用天数', 'field': '晶片寿命'},
        {'mention': '流晶消耗量', 'field': None},
        {'mention': '星辉率', 'field': '星辉率'}]))
    result = resolve('2032年11月只列晶片、流晶消耗量、星辉率')
    assert result.intent.fields == ('晶片寿命', '流晶消耗量', '星辉率')
    assert result.trace['conflicts'] == ['mention_unanchored_kept']


@pytest.mark.parametrize('year,month,expected', [
    ('二〇三七', '十一', '2037-11'),
    ('二零三七', '6', '2037-06'),
    ('二〇四二', '十二', '2042-12'),
    ('零零三七', '一', '0037-01'),
])
def test_digit_by_digit_chinese_year_and_valid_month_are_evidence(year, month, expected):
    assert expected in _explicit_months(f'{year}年{month}月星辉率', ReportIntent(), None)


@pytest.mark.parametrize('text,candidate', [
    ('一二〇三七年四月', '2037-04'),
    ('二〇三年四月', '2037-04'),
    ('二千零三十七年四月', '2037-04'),
    ('零零零零年六月', '0000-06'),
    ('二〇三七年零月', '2037-01'),
    ('二〇三七年十三月', '2037-10'),
    ('二〇三七年十三月', '2037-03'),
    ('二〇三七年两三月', '2037-03'),
])
def test_malformed_chinese_year_or_month_does_not_prove_a_partial_date(text, candidate):
    assert candidate not in _explicit_months(text, ReportIntent(), '2037-11')


def test_chinese_year_validates_proposal_without_forcing_a_background_month(monkeypatch):
    install_model(monkeypatch, proposal(
        target_month='2037-11', target_mention='二〇三七年十一月'))
    result = resolve('二〇三七年六月只是背景，二〇三七年十一月只列星辉率',
                     fallback_month='2037-11')
    assert result.intent.target_month == '2037-11'
    assert 'month_unsupported' not in result.trace['conflicts']


def test_chinese_year_negative_month_still_uses_v9(monkeypatch):
    install_model(monkeypatch, proposal(
        target_month='2037-06', target_mention='二〇三七年六月'))
    result = resolve('不要二〇三七年六月，改为2037-11只列星辉率',
                     fallback_month='2037-11')
    assert result.intent.target_month == '2037-11'
    assert 'negated_month_selected' in result.trace['conflicts']


@pytest.mark.parametrize('previous,fallback,expected', [
    (ReportIntent(target_month='2037-12'), '2038-05', '2037-02'),
    (ReportIntent(), '2038-05', '2038-02'),
    (ReportIntent(target_month='2037-13'), '2038-05', '2038-02'),
])
def test_same_year_uses_an_existing_effective_year(previous, fallback, expected):
    assert _explicit_months('同年二月星辉率', previous, fallback) == {expected}


def test_same_year_prefers_a_written_current_year_before_inherited_year():
    values = _explicit_months('2038年十一月与同年二月',
                             ReportIntent(target_month='2037-12'), '2039-06')
    assert values == {'2038-11', '2038-02'}


@pytest.mark.parametrize('text,candidate,previous,fallback', [
    ('同年二月', '2037-02', ReportIntent(), None),
    ('同年十三月', '2037-03', ReportIntent(target_month='2037-12'), None),
    ('同年零月', '2037-01', ReportIntent(), '2037-12'),
    ('不同年二月', '2037-02', ReportIntent(), '2037-12'),
])
def test_same_year_without_a_valid_year_or_month_is_not_evidence(text, candidate, previous, fallback):
    assert candidate not in _explicit_months(text, previous, fallback)


def test_same_year_does_not_use_today_as_an_implicit_year(monkeypatch):
    install_model(monkeypatch, proposal(
        target_month='2033-02', target_mention='同年二月', target_anchor='today'))
    result = resolve('同年二月只列星辉率', fallback_month=None)
    assert result.intent.target_month is None
    assert 'month_unsupported' in result.trace['conflicts']


def test_same_year_reuses_previous_year_and_negative_date_is_not_selected(monkeypatch):
    install_model(monkeypatch, proposal(
        target_month='2037-02', target_mention='同年二月'))
    result = resolve('同年二月只列星辉率',
                     previous_intent=ReportIntent(target_month='2037-12'),
                     fallback_month='2038-02')
    assert result.intent.target_month == '2037-02'
    assert 'month_unsupported' not in result.trace['conflicts']


@pytest.mark.parametrize('phrase,offset', [
    ('往前三个月', -3), ('往前3个月', -3), ('往前两个月', -2),
    ('往后十二个月', 12), ('往后2个月', 2), ('往 前 三 个 月', -3),
])
def test_directional_count_is_general_and_calendar_based(phrase, offset):
    assert _directional_offset(phrase) == offset


@pytest.mark.parametrize('phrase', [
    '前三个月', '前3个月', '过去三个月', '往前三个月内',
    '往前三个月后', '往前三个月与往后二个月', '往前两三个月',
    '往前-3个月', '往前3.5个月', '往前三个月期间',
])
def test_ambiguous_ranges_or_invalid_counts_are_not_directional_point_evidence(phrase):
    assert _directional_offset(phrase) is None


@pytest.mark.parametrize('phrase,baseline_mention', [
    ('往前三个月', '往前三个月'),
    ('往前3个月', '2036-11'),
    ('往前两个月', '2036-12'),
])
def test_baseline_evidence_uses_validated_target_even_when_mention_is_rewritten(
        monkeypatch, phrase, baseline_mention):
    expected = '2036-12' if '两' in phrase else '2036-11'
    install_model(monkeypatch, proposal(
        target_month='2037-02', target_mention='2037年二月', target_anchor='none',
        compare=True, baseline_month=expected, baseline_mention=baseline_mention))
    result = resolve(f'2037年二月只列星辉率，与{phrase}的数相比', fallback_month='2037-02')
    assert result.intent.comparison_month == expected
    assert 'month_unsupported' not in result.trace['conflicts']
    assert 'relative_month_recomputed' not in result.trace['conflicts']


def test_directional_target_evidence_uses_declared_previous_anchor_without_recomputing(monkeypatch):
    install_model(monkeypatch, proposal(
        target_month='2036-11', target_mention='往前三个月', target_anchor='previous_target'))
    result = resolve('往前三个月只列星辉率',
                     previous_intent=ReportIntent(target_month='2037-02'), fallback_month='2036-11')
    assert result.intent.target_month == '2036-11'
    assert 'month_unsupported' not in result.trace['conflicts']
    assert 'relative_month_recomputed' not in result.trace['conflicts']


@pytest.mark.parametrize('phrase,candidate', [
    ('往前三个月', '2036-10'),
    ('前三个月', '2036-11'),
    ('过去三个月', '2036-11'),
    ('往前三个月内', '2036-11'),
    ('往前两三个月', '2036-11'),
])
def test_wrong_or_ambiguous_baseline_does_not_get_directional_evidence(monkeypatch, phrase, candidate):
    install_model(monkeypatch, proposal(
        target_month='2037-02', target_mention='2037年二月', target_anchor='none',
        compare=True, baseline_month=candidate, baseline_mention=candidate))
    result = resolve(f'2037年二月只列星辉率，与{phrase}相比', fallback_month='2037-02')
    assert result.intent.comparison_month is None
    assert 'month_unsupported' in result.trace['conflicts']
    assert 'relative_month_recomputed' not in result.trace['conflicts']


def test_negated_directional_date_is_not_evidence(monkeypatch):
    install_model(monkeypatch, proposal(
        target_month='2037-02', target_mention='2037年二月', target_anchor='none',
        compare=True, baseline_month='2036-11', baseline_mention='2036-11'))
    result = resolve('2037年二月只列星辉率，不要往前三个月的对照', fallback_month='2037-02')
    assert result.intent.comparison_month is None
    assert 'month_unsupported' in result.trace['conflicts']


def test_unknown_event_without_declared_anchor_is_not_directional_evidence(monkeypatch):
    install_model(monkeypatch, proposal(
        target_month='2036-11', target_mention='虚构舱室启用日往前三个月', target_anchor='none'))
    result = resolve('虚构舱室启用日往前三个月只列星辉率', fallback_month=None)
    assert result.intent.target_month is None
    assert 'month_unsupported' in result.trace['conflicts']


def test_baseline_direction_requires_a_validated_target(monkeypatch):
    install_model(monkeypatch, proposal(
        target_month='2037-02', target_mention='2037-02', target_anchor='none',
        compare=True, baseline_month='2036-11', baseline_mention='2036-11'))
    result = resolve('星辉率与往前三个月对照', fallback_month=None)
    assert result.intent.target_month is None
    assert result.intent.comparison_month is None
    assert 'month_unsupported' in result.trace['conflicts']


def test_no_new_date_evidence_forces_null_unresolved_to_a_month(monkeypatch):
    install_model(monkeypatch, proposal(
        target_month=None, target_mention='二〇三七年六月', unresolved=True))
    result = resolve('二〇三七年六月只列星辉率', fallback_month='2037-06')
    assert result.intent.target_month is None
    assert result.intent.unresolved_month


@pytest.mark.parametrize('query', [
    '二〇三七年六月只列星辉率', '同年二月只列星辉率',
    '往前三个月只列星辉率',
])
def test_rule_mode_stays_identical_without_model_calls(query):
    previous = ReportIntent(target_month='2037-11')
    result = resolve(query, mode='rule', previous_intent=previous, fallback_month='2037-06')
    assert result.intent == resolve_report_intent(
        query, known_fields=CATALOG, previous_intent=previous, fallback_month='2037-06')


def test_llm_only_still_does_not_run_v3_or_v6(monkeypatch):
    install_model(monkeypatch, proposal(fields=[{'mention': '没有写出的未知名', 'field': None}],
                                       target_month='2037-04', target_mention='凭空日期'))
    result = resolve('只列星辉率', mode='llm_only')
    assert result.intent.fields == ('没有写出的未知名',)
    assert result.intent.target_month == '2037-04'
    assert not result.trace['conflicts']
