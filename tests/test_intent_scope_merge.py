"""Three-valued scope regressions use only fictitious reports and scripted models."""
import pytest

from test_llm_intent import (
    CATALOG,
    install_model,
    make_run,
    no_real_intent_model,
    proposal,
    resolve,
)
from utils.report_intent import ReportIntent, resolve_report_intent


STAR = [{'mention': '星辉率', 'field': '星辉率'}]


@pytest.mark.parametrize('query, offered_scope, offered_fields, expected_scope, expected_fields', [
    ('2032年11月完整报告', 'unspecified', [], 'full_report', ()),
    ('2032年11月完整报告，星辉率也包括在内', 'only_listed', STAR, 'full_report', ()),
    ('2032年11月只列星辉率', 'full_report', STAR, 'only_listed', ('星辉率',)),
    ('2032年11月不要完整报告了，只列星辉率', 'full_report', STAR,
     'only_listed', ('星辉率',)),
    ('2032年11月完整报告，随后改为只列星辉率', 'full_report', STAR,
     'only_listed', ('星辉率',)),
    ('2032年11月只列星辉率，改为完整报告', 'only_listed', STAR, 'full_report', ()),
    ('2032年11月仅列星辉率', 'unspecified', STAR, 'only_listed', ('星辉率',)),
    ('2032年11月只列星辉率，改为全部字段', 'unspecified', STAR, 'full_report', ()),
])
def test_explicit_scope_is_compared_as_three_values(
        monkeypatch, query, offered_scope, offered_fields, expected_scope, expected_fields):
    install_model(monkeypatch, proposal(scope=offered_scope, fields=offered_fields))
    result = resolve(query)
    assert result.final_scope == expected_scope
    assert result.final_excluded_fields == ()
    assert result.intent.fields == expected_fields
    assert result.intent.limited == (expected_scope == 'only_listed')
    assert result.trace['source'] == 'merged'
    assert result.trace['conflicts'].count('scope_rule_override') == 1


@pytest.mark.parametrize('scope', ['only_listed', 'full_report', 'unspecified'])
def test_without_an_explicit_or_rule_limited_scope_the_proposal_is_preserved(monkeypatch, scope):
    query = '2032年11月查询报告'
    assert not resolve_report_intent(query, known_fields=CATALOG).limited
    install_model(monkeypatch, proposal(scope=scope, fields=[]))
    result = resolve(query)
    assert result.final_scope == scope
    assert result.final_excluded_fields == ()
    assert 'scope_rule_override' not in result.trace['conflicts']


@pytest.mark.parametrize('query, scope, fields', [
    ('2032年11月完整报告', 'full_report', []),
    ('2032年11月只列星辉率', 'only_listed', STAR),
    ('2032年11月查询报告', 'unspecified', []),
])
def test_matching_scope_does_not_record_an_override(monkeypatch, query, scope, fields):
    install_model(monkeypatch, proposal(scope=scope, fields=fields))
    result = resolve(query)
    assert result.final_scope == scope
    assert 'scope_rule_override' not in result.trace['conflicts']


@pytest.mark.parametrize('query, scope, fields', [
    ('2032年11月完整报告', 'unspecified', []),
    ('2032年11月完整报告，星辉率也包括在内', 'only_listed', STAR),
    ('2032年11月只列星辉率', 'full_report', STAR),
    ('2032年11月不要完整报告了，只列星辉率', 'full_report', STAR),
])
def test_llm_only_preserves_conflicting_scope(monkeypatch, query, scope, fields):
    install_model(monkeypatch, proposal(scope=scope, fields=fields))
    result = resolve(query, mode='llm_only')
    assert result.final_scope == scope
    assert result.final_excluded_fields == ()
    assert 'scope_rule_override' not in result.trace['conflicts']
    assert result.intent.fields == (() if scope == 'full_report' else tuple(
        item['field'] for item in fields))


@pytest.mark.parametrize('query, history, previous, expected_scope', [
    ('2032年11月完整报告', (), None, 'full_report'),
    ('2032年11月全部字段', (), None, 'full_report'),
    ('2032年11月只列星辉率', (), None, 'only_listed'),
    ('2032年11月不要完整报告了，只列星辉率', (), None, 'only_listed'),
    ('2032年11月完整报告，改为只列星辉率', (), None, 'only_listed'),
    ('2032年11月只列星辉率，改为完整报告', (), None, 'full_report'),
    ('2032年11月查询报告', (), None, 'unspecified'),
    ('2032年11月不要完整报告', (), None, 'unspecified'),
    ('2032年11月星辉率是多少', (), None, 'only_listed'),
    ('继续', ('2032年11月只列星辉率',), None, 'only_listed'),
    ('继续', (), ReportIntent(fields=('星辉率',), target_month='2032-11', limited=True),
     'only_listed'),
])
def test_rule_scope_is_exposed_without_changing_legacy_intent_or_calling_a_model(
        query, history, previous, expected_scope):
    run = make_run()
    result = resolve(query, mode='rule', history_queries=history, previous_intent=previous,
                     run=run)
    expected = resolve_report_intent(query, history, known_fields=CATALOG,
                                     fallback_month='2032-11', previous_intent=previous)
    assert result.intent == expected
    assert result.final_scope == expected_scope
    assert result.final_excluded_fields == ()
    assert result.proposal is None
    assert result.trace['source'] == 'rule'
    assert run.counts['model'] == 0


@pytest.mark.parametrize('scope', ['only_listed', 'full_report', 'unspecified'])
def test_rule_limited_without_scope_words_preserves_llm_scope(monkeypatch, scope):
    query = '2032年11月星辉率是多少'
    assert resolve_report_intent(query, known_fields=CATALOG).limited
    install_model(monkeypatch, proposal(scope=scope, fields=STAR))
    result = resolve(query)
    assert result.final_scope == scope
    assert result.intent.fields == (() if scope == 'full_report' else ('星辉率',))
    assert result.intent.limited == (scope != 'full_report')
    assert 'scope_rule_override' not in result.trace['conflicts']


@pytest.mark.parametrize('query', [
    '2032年10月覆盖率也在里面，给我整份报告',
    '2032年10月的报告全给我，包括覆盖率',
])
def test_full_report_paraphrases_with_named_metric_do_not_trigger_scope_override(monkeypatch, query):
    catalog = ('覆盖率', '晶片寿命')
    assert resolve_report_intent(query, known_fields=catalog).limited
    install_model(monkeypatch, proposal(
        scope='full_report', fields=[{'mention': '覆盖率', 'field': '覆盖率'}],
        target_month='2032-10', target_mention='2032年10月'))
    result = resolve(query, known_fields=catalog, fallback_month='2032-10')
    assert result.final_scope == 'full_report'
    assert result.intent.fields == ()
    assert not result.intent.limited
    assert 'scope_rule_override' not in result.trace['conflicts']


@pytest.mark.parametrize('query, expected_scope', [
    ('2032年11月完整报告', 'full_report'),
    ('2032年11月只列星辉率', 'only_listed'),
    ('2032年11月查询报告', 'unspecified'),
])
def test_invalid_proposal_fallback_exposes_only_the_rule_scope(monkeypatch, query, expected_scope):
    install_model(monkeypatch, proposal(excluded_fields=list(CATALOG), unexpected='invalid'))
    result = resolve(query)
    assert result.final_scope == expected_scope
    assert result.final_excluded_fields == ()
    assert result.intent == resolve_report_intent(query, known_fields=CATALOG,
                                                  fallback_month='2032-11')
    assert result.proposal is None
    assert result.trace['fallback_reason'] == 'invalid_proposal'


def test_budget_fallback_exposes_final_scope_without_calling_the_model(monkeypatch):
    model = install_model(monkeypatch, proposal(scope='only_listed', fields=STAR,
                                               excluded_fields=['晶片寿命']))
    run = make_run(max_model_calls=1)
    run.reserve('model')
    result = resolve('2032年11月完整报告', run=run)
    assert result.final_scope == 'full_report'
    assert result.final_excluded_fields == ()
    assert result.intent.fields == ()
    assert result.trace['fallback_reason'] == 'model_budget'
    assert model.seen == []


@pytest.mark.parametrize('offered_scope', ['only_listed', 'unspecified'])
def test_full_scope_override_lists_remaining_catalog_fields_after_valid_exclusions(
        monkeypatch, offered_scope):
    install_model(monkeypatch, proposal(scope=offered_scope, fields=STAR,
                                       excluded_fields=['晶片寿命', '晶片寿命']))
    result = resolve('2032年11月完整报告，星辉率也包括在内，不要晶片寿命')
    assert result.final_scope == 'full_report'
    assert result.final_excluded_fields == ('晶片寿命',)
    assert result.intent.fields == ('星辉率', '幻尘消耗')
    assert not result.intent.limited
    assert 'scope_rule_override' in result.trace['conflicts']


def test_full_scope_remains_full_when_exclusions_leave_no_catalog_fields(monkeypatch):
    install_model(monkeypatch, proposal(scope='unspecified', fields=[],
                                       excluded_fields=list(CATALOG)))
    result = resolve('2032年11月完整报告，不要星辉率、晶片寿命、幻尘消耗')
    assert result.final_scope == 'full_report'
    assert result.final_excluded_fields == CATALOG
    assert result.intent.fields == ()
    assert result.intent.limited  # The renderer must not expand an empty remainder.
    assert 'scope_rule_override' in result.trace['conflicts']


def test_only_scope_override_keeps_validated_fields_and_exclusions(monkeypatch):
    install_model(monkeypatch, proposal(scope='full_report', fields=[
        *STAR, {'mention': '晶片寿命', 'field': '晶片寿命'}],
        excluded_fields=['晶片寿命']))
    result = resolve('2032年11月只列星辉率，不要晶片寿命')
    assert result.final_scope == 'only_listed'
    assert result.final_excluded_fields == ('晶片寿命',)
    assert result.intent.fields == ('星辉率',)
    assert result.intent.limited
    assert 'scope_rule_override' in result.trace['conflicts']
    assert 'negated_field_selected' in result.trace['conflicts']


@pytest.mark.parametrize('excluded, conflict', [
    (['晶片寿命'], 'exclusion_not_in_text'),
    (['虚构目录外指标'], 'field_not_in_catalog'),
])
def test_final_exclusions_contain_only_validated_exclusions(monkeypatch, excluded, conflict):
    install_model(monkeypatch, proposal(scope='full_report', fields=[], excluded_fields=excluded))
    result = resolve('2032年11月完整报告')
    assert result.final_scope == 'full_report'
    assert result.final_excluded_fields == ()
    assert result.intent.fields == ()
    assert conflict in result.trace['conflicts']


def test_llm_only_final_exclusions_keep_catalog_validation_without_text_validation(monkeypatch):
    install_model(monkeypatch, proposal(scope='full_report', fields=[],
                                       excluded_fields=['晶片寿命', '虚构目录外指标']))
    result = resolve('2032年11月查询报告', mode='llm_only')
    assert result.final_scope == 'full_report'
    assert result.final_excluded_fields == ('晶片寿命',)
    assert result.intent.fields == ('星辉率', '幻尘消耗')
    assert result.trace['conflicts'] == ['field_not_in_catalog']
