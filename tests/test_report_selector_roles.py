"""Follow-up selectors must preserve month roles and metric identity."""
import pytest

from utils.report_intent import ReportIntent, resolve_report_intent
from utils.report_render import render_lookup


def record(month, *, user='account', rate='64.8%', life='剩余37天'):
    return {'status': 'ok', 'user_id': user, 'month': month, 'data': {
        '特征': '独立测试记录', '效率': '除尘率:' + rate,
        '耗材': '电池寿命:' + life + '\\n水泵寿命:剩余80小时', '对比': ''}}


@pytest.mark.parametrize('requested', [
    '电池剩余寿命', '电池寿命剩余', '剩余电池寿命',
    '电池剩余天数', '电池剩余使用时间',
])
def test_remaining_life_aliases_resolve_only_against_recorded_labels(requested):
    text = render_lookup(record('2041-08'), query=f'2041年8月只列{requested}')
    assert '电池寿命：剩余37天' in text
    assert '未提供' not in text and '水泵寿命' not in text


def test_life_alias_does_not_merge_component_or_decay_fields():
    result = record('2041-08')
    result['data']['耗材'] += '\\n电池衰减:12%'
    text = render_lookup(result, query='电池剩余寿命和电池衰减是多少')
    assert '电池寿命：剩余37天' in text and '电池衰减：12%' in text
    assert '水泵寿命' not in text
    missing = render_lookup(result, query='只列电机剩余寿命')
    assert '电机剩余寿命：未提供' in missing
    assert '37天' not in missing and '80小时' not in missing


@pytest.mark.parametrize('query', [
    '只列墙角除尘率', '墙角除尘率和耗电量是多少',
    '只列污水仓电池寿命', '污水仓电池寿命和耗电量是多少',
    '查询2041年8月墙角除尘率', '污水仓电池寿命是多少',
])
def test_unknown_subtype_metric_cannot_inherit_generic_record_value(query):
    text = render_lookup(record('2041-08'), query=query)
    requested = '墙角除尘率' if '墙角' in query else '污水仓电池寿命'
    assert requested + '：未提供' in text
    assert '64.8%' not in text and '37天' not in text and '80小时' not in text
    if '耗电量' in query:
        assert '耗电量：未提供' in text


def test_relative_single_subtype_selector_does_not_reuse_the_generic_field():
    previous = ReportIntent(fields=('除尘率',), target_month='2041-07', limited=True)
    intent = resolve_report_intent('下一月墙角除尘率', previous_intent=previous,
                                   known_fields=['除尘率'])
    text = render_lookup(record('2041-08'), intent=intent)
    assert '墙角除尘率：未提供' in text and '64.8%' not in text


def test_relative_reference_alone_inherits_fields_without_becoming_unknown_noun():
    previous = ReportIntent(fields=('除尘率',), target_month='2041-07', limited=True)
    intent = resolve_report_intent('下一月前面两项', previous_intent=previous,
                                   known_fields=['除尘率'])
    assert intent.fields == ('除尘率',) and intent.target_month == '2041-08'


def test_rate_display_alias_requires_a_verified_percentage_value():
    result = record('2041-08')
    result['data']['效率'] = '颗粒清理:82%\\n避障失败:3次/周'
    text = render_lookup(result, query='只列颗粒清理率和避障失败率')
    assert '颗粒清理：82%' in text
    assert '避障失败率：未提供' in text
    assert '3次/周' not in text
    subtype = render_lookup(result, query='只列墙角颗粒清理率')
    assert '墙角颗粒清理率：未提供' in subtype and '82%' not in subtype


def test_percent_display_alias_survives_cross_month_name_variation():
    current = record('2041-08')
    current['data']['效率'] = '颗粒清理:82%'
    previous = record('2041-07')
    previous['data']['效率'] = '颗粒清理率:78%'
    text = render_lookup(current, query='2041年8月只列颗粒清理率，与2041年7月相比',
                         lookup_results=[previous])
    assert '增加4个百分点' in text
    assert '未提供' not in text


@pytest.mark.parametrize('query', [
    '前一个月这两项是多少？与刚才的8月相比各变化多少？',
    '与刚才的2041年8月相比，上一月这两项变化多少？',
    '查前一月这两项，和2041年8月比有哪些变化？',
])
def test_relative_target_is_not_overwritten_by_explicit_comparison_month(query):
    previous = ReportIntent(fields=('除尘率', '电池寿命'), target_month='2041-08', limited=True)
    intent = resolve_report_intent(query, previous_intent=previous,
                                   known_fields=['除尘率', '电池寿命'])
    assert (intent.target_month, intent.comparison_month) == ('2041-07', '2041-08')
    before = record('2041-08', rate='64.8%', life='剩余37天')
    target = record('2041-07', rate='62.3%', life='剩余43天')
    text = render_lookup(target, intent=intent, lookup_results=[before])
    assert '2041-07 与 2041-08' in text
    assert '减少2.5个百分点' in text and '增加6天' in text
    assert '水泵寿命' not in text
    assert '寿命延长' not in text


@pytest.mark.parametrize('query', [
    '下一月只列电池寿命，别拿12月或其他月的值代替。',
    '下一月只列电池寿命，不要使用2041年12月的数据。',
    '继续下一月这项，不是2041年12月。',
])
def test_excluded_month_cannot_override_year_rollover_target(query):
    previous = ReportIntent(fields=('电池寿命',), target_month='2041-12', limited=True)
    intent = resolve_report_intent(query, previous_intent=previous, known_fields=['电池寿命'])
    assert intent.target_month == '2042-01' and not intent.invalid_month
    missing = {'status': 'not_found', 'user_id': 'account', 'month': '2042-01'}
    text = render_lookup(missing, intent=intent, lookup_results=[record('2041-12')])
    assert '未找到' in text and '2042-01' in text and '37天' not in text


def test_negative_invalid_month_is_not_a_selector_but_positive_invalid_is():
    intent = resolve_report_intent('不要2041年13月，而是2041年11月只列电池寿命',
                                   known_fields=['电池寿命'])
    assert intent.target_month == '2041-11' and not intent.invalid_month
    for query in ['查2041年13月电池寿命', '查2041年11月电池寿命与2041年0月相比']:
        text = render_lookup(record('2041-11'), query=query)
        assert '月份无效' in text and '37天' not in text


def test_explicit_correction_and_negative_field_do_not_select_excluded_values():
    text = render_lookup(record('2041-08'),
                         query='不要2041年7月的水泵寿命，而是2041年8月只列电池剩余寿命')
    assert '2041-08' in text and '电池寿命：剩余37天' in text
    assert '水泵寿命' not in text and '80小时' not in text


@pytest.mark.parametrize(('query', 'target', 'baseline'), [
    ('2041年8月除尘率比2041年7月变化多少', '2041-08', '2041-07'),
    ('与2041年7月相比，2041年8月除尘率变化多少', '2041-08', '2041-07'),
    ('比较2041年7月和8月的除尘率', '2041-08', '2041-07'),
    ('下一月除尘率与上月相比变化多少', '2041-09', '2041-08'),
    ('查2041年8月除尘率，环比多少', '2041-08', '2041-07'),
    ('查2041年8月除尘率，比7月呢', '2041-08', '2041-07'),
])
def test_explicit_and_relative_baseline_roles(query, target, baseline):
    intent = resolve_report_intent(query, previous_intent=ReportIntent(target_month='2041-08'),
                                   known_fields=['除尘率'])
    assert (intent.target_month, intent.comparison_month) == (target, baseline)


def test_cross_year_relative_baseline_is_relative_to_new_target():
    previous = ReportIntent(target_month='2041-12', fields=('除尘率',), limited=True)
    intent = resolve_report_intent('下一月这项与上月相比', previous_intent=previous,
                                   known_fields=['除尘率'])
    assert (intent.target_month, intent.comparison_month) == ('2042-01', '2041-12')


@pytest.mark.parametrize('previous', [None, ReportIntent(target_month='2041-10')])
def test_explicit_target_anchors_relative_baseline_even_with_different_or_no_history(previous):
    intent = resolve_report_intent('查询2041年12月除尘率，与上个月相比',
                                   previous_intent=previous, known_fields=['除尘率'])
    assert (intent.target_month, intent.comparison_month) == ('2041-12', '2041-11')
    assert not intent.unresolved_month


def test_relative_baseline_can_use_verified_explicit_current_target_without_history():
    current = record('2041-12', rate='70%')
    baseline = record('2041-11', rate='68%')
    text = render_lookup(current, query='除尘率比上月变化多少', lookup_results=[baseline])
    assert '2041-12 与 2041-11' in text and '增加2个百分点' in text


@pytest.mark.parametrize('query', ['下一月只列除尘率', '前一个月除尘率与2041年8月相比'])
def test_relative_target_without_prior_anchor_cannot_be_guessed_from_tool_month(query):
    intent = resolve_report_intent(query, known_fields=['除尘率'], fallback_month='2041-08')
    assert intent.unresolved_month
    text = render_lookup(record('2041-08'), query=query)
    assert '参照月份' in text and '64.8%' not in text


def test_relative_calendar_bounds_are_invalid_not_estimated():
    previous = ReportIntent(target_month='9999-12', fields=('除尘率',), limited=True)
    intent = resolve_report_intent('下一月这项', previous_intent=previous, known_fields=['除尘率'])
    assert intent.invalid_month and intent.target_month is None
    text = render_lookup(record('9999-12'), intent=intent)
    assert '月份无效' in text and '64.8%' not in text


def test_bare_just_queried_baseline_preserves_previous_year():
    intent = resolve_report_intent('查2042年1月这项，与刚才的12月相比',
                                   previous_intent=ReportIntent(target_month='2041-12'),
                                   known_fields=['除尘率'])
    assert (intent.target_month, intent.comparison_month) == ('2042-01', '2041-12')


def test_remaining_units_are_not_guessed_or_converted():
    previous = record('2041-07', life='剩余43小时')
    target = record('2041-08', life='剩余37天')
    intent = ReportIntent(fields=('电池寿命',), target_month='2041-08',
                          comparison_month='2041-07', compare=True, limited=True)
    text = render_lookup(target, intent=intent, lookup_results=[previous])
    assert '记录单位不同' in text
    assert '增加' not in text and '减少' not in text


def test_noncurrent_target_and_other_identity_cannot_supply_alias_value():
    intent = ReportIntent(fields=('电池寿命',), target_month='2041-08', limited=True)
    text = render_lookup(record('2041-09'), intent=intent,
                         lookup_results=[record('2041-08'), record('2041-08', user='foreign')])
    assert '不能用其他月份' in text and '37天' not in text


def test_current_comparison_record_supersedes_historical_version():
    intent = ReportIntent(fields=('除尘率',), target_month='2041-08',
                          comparison_month='2041-07', compare=True, limited=True)
    target = record('2041-08', rate='70%')
    fresh_baseline = record('2041-07', rate='68%')
    old_baseline = record('2041-07', rate='40%')
    text = render_lookup(old_baseline, intent=intent,
                         lookup_results=[old_baseline], current_results=[target, fresh_baseline])
    assert '增加2个百分点' in text and '40%' not in text


def test_agent_followup_retains_aliases_and_month_roles_from_committed_selectors():
    from unittest.mock import patch
    from agent.react_agent import ReactAgent
    from test_core_flows import ScriptedModel, answer, call, scripted_context_policy
    model = ScriptedModel(responses=[
        call('fetch_external_data', user_id='1001', month='2041-08'), answer('回充率999%'),
        call('fetch_external_data', user_id='1001', month='2041-07'), answer('寿命增加500天'),
    ])
    agent = ReactAgent('1001', model=model, context_policy=scripted_context_policy())
    august = {'特征': '测试', '效率': '回充率:70.1%', '耗材': '驱动轮寿命:剩余44天', '对比': ''}
    july = {'特征': '测试', '效率': '回充率:68.3%', '耗材': '驱动轮寿命:剩余52天', '对比': ''}
    with patch('agent.tools.agent_tools.load_records', return_value={
            ('1001', '2041-08'): august, ('1001', '2041-07'): july}):
        first = ''.join(agent.execute_stream('查2041年8月，只列回充率和驱动轮剩余寿命。'))
        second = ''.join(agent.execute_stream('前一个月这两项是多少，与刚才的8月比变化多少？'))
    assert '驱动轮寿命：剩余44天' in first and '999%' not in first
    assert '2041-07 与 2041-08' in second
    assert '减少1.8个百分点' in second and '增加8天' in second and '500天' not in second
    assert agent._report_intent.target_month == '2041-07'
    assert agent._report_intent.comparison_month == '2041-08'


def test_agent_missing_relative_month_does_not_commit_excluded_cached_month():
    from unittest.mock import patch
    from agent.react_agent import ReactAgent
    from test_core_flows import ScriptedModel, answer, call, scripted_context_policy
    model = ScriptedModel(responses=[
        call('fetch_external_data', user_id='1001', month='2041-12'), answer('完成'),
        call('fetch_external_data', user_id='1001', month='2042-01'), answer('仍是70%'),
    ])
    agent = ReactAgent('1001', model=model, context_policy=scripted_context_policy())
    december = {'特征': '测试', '效率': '回充率:70%', '耗材': '驱动轮寿命:剩余44天', '对比': ''}
    with patch('agent.tools.agent_tools.load_records', return_value={('1001', '2041-12'): december}):
        list(agent.execute_stream('查2041年12月，只列回充率和驱动轮剩余寿命。'))
        second = ''.join(agent.execute_stream('继续下一月这两项，没有记录就说未找到，别拿12月代替。'))
    assert '2042-01' in second and '未找到' in second
    assert '70%' not in second and '44天' not in second
    assert agent._report_intent.target_month == '2042-01'
