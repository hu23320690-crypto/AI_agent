"""List-size request prose must not become part of a requested metric."""
import pytest

from utils.report_intent import resolve_report_intent
from utils.report_render import render_lookup


def record(month, *, rate='42%', count='3次/月'):
    return {'status': 'ok', 'user_id': 'test-account', 'month': month, 'data': {
        '特征': '虚构记录',
        '效率': f'碎屑回收次数:{count}\\n定位重试成功率:{rate}\\n清扫覆盖率:75%',
        '耗材': '滤网寿命:剩余24天', '对比': ''}}


@pytest.mark.parametrize('suffix', [
    '两个字段', '这两项', '两项指标', '2个字段', '这2项指标',
    '2项字段', '两个指标', '那两项',
])
@pytest.mark.parametrize('prefix', ['只需要', '查询2037年4月'])
def test_trailing_list_count_is_not_part_of_second_field(prefix, suffix):
    intent = resolve_report_intent(f'{prefix}碎屑回收次数和定位重试成功率{suffix}',
                                   known_fields=['碎屑回收次数', '定位重试成功率'])
    assert intent.fields == ('碎屑回收次数', '定位重试成功率')


@pytest.mark.parametrize('suffix', ['两个字段', '这两项', '两项指标', '2个字段'])
def test_user_history_retains_two_exact_fields_for_next_month_comparison(suffix):
    # Resolve from raw user history, with no metric catalog at the earlier turn.
    intent = resolve_report_intent('下一月这两项，与刚才相比变化多少', [
        f'查询2037年4月，只需要碎屑回收次数和定位重试成功率{suffix}'])
    assert intent.fields == ('碎屑回收次数', '定位重试成功率')
    assert (intent.target_month, intent.comparison_month) == ('2037-05', '2037-04')
    text = render_lookup(record('2037-05'), intent=intent,
                         lookup_results=[record('2037-04', rate='40%', count='1次/月')])
    assert '增加2次/月' in text and '增加2个百分点' in text
    assert '未提供' not in text and '清扫覆盖率' not in text


@pytest.mark.parametrize('ending', ['两个字段', '这两项是多少', '两项指标即可'])
def test_count_suffix_does_not_remove_unknown_component_qualifiers(ending):
    text = render_lookup(record('2037-04'),
                         query=f'只列墙角清扫覆盖率和污水仓滤网寿命{ending}')
    assert '墙角清扫覆盖率：未提供' in text
    assert '污水仓滤网寿命：未提供' in text
    assert '75%' not in text and '24天' not in text


@pytest.mark.parametrize('prefix', ['只列', '查询2037年4月'])
def test_digits_and_quantity_modifiers_inside_a_metric_name_are_preserved(prefix):
    result = record('2037-04')
    result['data']['效率'] = '月均2次启动次数:4次/月'
    text = render_lookup(result, query=f'{prefix}月均2次启动次数和月均3次启动次数两个字段')
    assert '月均2次启动次数：4次/月' in text
    assert '月均3次启动次数：未提供' in text


@pytest.mark.parametrize('prefix', ['只列', '查询2037年4月'])
def test_a_literal_catalog_name_is_not_stripped_as_request_prose(prefix):
    intent = resolve_report_intent(f'{prefix}计数组甲和计数组乙两项指标',
                                   known_fields=['计数组甲', '计数组乙两项指标'])
    assert intent.fields == ('计数组甲', '计数组乙两项指标')


def test_field_count_reference_without_labels_cannot_invent_a_selection():
    intent = resolve_report_intent('只需要这两项', known_fields=['定位重试成功率'])
    assert intent.limited and intent.fields == ()
