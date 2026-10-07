"""Explicit comparable measurements support only their own numeric condition."""
from copy import deepcopy

import pytest
from langchain_core.documents import Document

from utils.record_evidence import record_evidence_reply


def record(fields):
    return {'status': 'ok', 'user_id': '1001', 'month': '2031-06',
            'data': {'效率': '\\n'.join(f'{key}:{value}' for key, value in fields.items()),
                     '耗材': '', '特征': '测试记录', '对比': ''}}


@pytest.mark.parametrize(('query', 'holds'), [
    ('这些记录能否证明覆盖率高于75%？', True),
    ('这些记录能否证明覆盖率低于75%？', False),
    ('覆盖率是否不低于80%？', True),
    ('覆盖率是否超过80%？', False),
    ('覆盖率是否≥80%？', True),
])
def test_same_literal_metric_and_unit_can_establish_an_explicit_condition(query, holds):
    reply = record_evidence_reply(query, record({'覆盖率': '80%'}))
    assert '覆盖率记录为80%' in reply
    assert ('数值满足' if holds else '数值不满足') in reply
    assert '尚不足以' not in reply


def test_comparison_converts_only_explicit_compatible_units():
    reply = record_evidence_reply('累计运行时长是否高于1小时？', record({'累计运行时长': '90分钟'}))
    assert '数值满足' in reply


def test_value_remaining_prefix_allows_the_same_quantity_in_the_user_label():
    reply = record_evidence_reply('耗材剩余寿命是否低于30天？', record({'耗材寿命': '剩余45天'}))
    assert '数值不满足' in reply and '剩余45天' in reply


def test_similar_names_do_not_turn_a_loss_percentage_into_runtime():
    reply = record_evidence_reply(
        '只列容量衰减和人工干预占比；这些记录能否直接证明实际运转时长已达到维护门槛？',
        record({'容量衰减': '35%', '人工干预占比': '65%'}),
        source_documents=[Document(page_content='运转时长降低至原始运转时长40%以下时需处理。')])
    assert '尚不足以确认' in reply
    assert '不同名称' in reply
    assert '数值满足' not in reply and '数值不满足' not in reply


def test_current_and_original_same_quantity_can_support_a_relative_threshold():
    result = record({'当前运转时长': '35分钟', '原始运转时长': '100分钟'})
    reply = record_evidence_reply('这些记录能否证明实际运转时长低于原始运转时长40%？', result)
    assert '同量数值比较' in reply
    assert '35分钟' in reply and '100分钟' in reply and '数值满足' in reply


def test_a_source_relative_threshold_uses_only_the_named_quantity():
    result = record({'当前运转时长': '45分钟', '原始运转时长': '100分钟'})
    reply = record_evidence_reply('这些记录能否判断运转时长已经达到维护门槛？', result,
        source_documents=[Document(page_content='运转时长降低至原始运转时长40%以下时需处理。')])
    assert '数值不满足' in reply


def test_relative_source_rule_is_bound_to_its_own_requested_quantity():
    result = record({'当前覆盖率': '95%', '当前续航': '30分钟', '原始续航': '100分钟'})
    source = Document(page_content='续航降低至原始续航的80%以下时应维修。')
    unrelated = record_evidence_reply('能否确认覆盖率已经达标？', result,
                                      source_documents=[source])
    matching = record_evidence_reply('能否确认续航已经达到维护门槛？', result,
                                     source_documents=[source])
    assert '尚不足以确认' in unrelated
    assert '30分钟' not in unrelated and '同量数值比较' not in unrelated
    assert '数值满足' in matching and '30分钟' in matching


def test_relative_rule_for_another_field_does_not_override_an_unresolved_named_rule():
    result = record({'当前灯罩透光率': '90%', '当前液体存量': '20个', '原始液体存量': '100个'})
    sources = [Document(page_content='灯罩透光率低于原始灯罩透光率的70%时需处理。'),
               Document(page_content='液体存量低于原始液体存量的30%时需处理。')]
    reply = record_evidence_reply('能否确认灯罩透光率已达到处理门槛？', result,
                                  source_documents=sources)
    assert '尚不足以确认' in reply and '同量数值比较' not in reply


@pytest.mark.parametrize('fields', [
    {'当前运转时长': '35分钟'},
    {'当前运转时长': '35分钟', '原始运转时长': '0分钟'},
    {'当前运转时长': '35分钟', '原始运转时长': '100%', '容量衰减': '65%'},
    {'运转时长': '35%'},
])
def test_missing_or_undefined_relative_measurements_cannot_establish_runtime(fields):
    reply = record_evidence_reply('这些记录能否证明运转时长低于原始运转时长40%？', record(fields))
    assert '尚不足以确认' in reply


def test_an_unrelated_source_threshold_cannot_answer_a_different_judgment():
    reply = record_evidence_reply('这些记录能否证明设备已通过电气安全检测？',
        record({'覆盖率': '80%'}), source_documents=[Document(page_content='覆盖率高于75%即可。')])
    assert '尚不足以确认' in reply


@pytest.mark.parametrize(('fields', 'query'), [
    ({'覆盖率': '92%'}, '能否确认墙角覆盖率不低于90%？'),
    ({'滤网寿命': '剩余60天'}, '能否确认污水仓滤网寿命大于30天？'),
    ({'墙角覆盖率': '92%'}, '能否确认覆盖率不低于90%？'),
    ({'污水仓滤网寿命': '剩余60天'}, '能否确认滤网寿命大于30天？'),
])
def test_generic_and_qualified_metrics_are_not_interchangeable(fields, query):
    reply = record_evidence_reply(query, record(fields))
    assert '尚不足以确认' in reply
    assert '数值满足' not in reply and '数值不满足' not in reply


@pytest.mark.parametrize(('fields', 'query'), [
    ({'覆盖率': '92%'}, '能否确认覆盖率不低于90%？'),
    ({'墙角覆盖率': '92%'}, '能否确认墙角覆盖率不低于90%？'),
    ({'滤网寿命': '剩余60天'}, '能否确认滤网剩余寿命大于30天？'),
    ({'污水仓滤网寿命': '剩余60天'}, '能否确认污水仓滤网剩余寿命大于30天？'),
])
def test_full_same_quantity_names_and_explicit_remaining_alias_can_be_compared(fields, query):
    reply = record_evidence_reply(query, record(fields))
    assert '数值满足' in reply and '尚不足以确认' not in reply


def test_source_threshold_does_not_override_a_qualified_user_quantity():
    source = Document(page_content='覆盖率不低于90%时满足该条件。')
    result = record({'覆盖率': '92%'})
    wrong = record_evidence_reply('能否判断墙角覆盖率是否达到门槛？', result,
                                   source_documents=[source])
    same = record_evidence_reply('能否判断覆盖率是否达到门槛？', result,
                                  source_documents=[source])
    assert '尚不足以确认' in wrong
    assert '数值满足' in same


def test_relative_threshold_cannot_apply_generic_runtime_to_a_specific_component():
    result = record({'当前运转时长': '35分钟', '原始运转时长': '100分钟'})
    query = '能否证明主刷运转时长低于原始主刷运转时长40%？'
    reply = record_evidence_reply(query, result)
    with_source = record_evidence_reply('能否判断主刷运转时长是否达到维护门槛？', result,
        source_documents=[Document(page_content='运转时长低于原始运转时长40%时需要处理。')])
    assert '尚不足以确认' in reply and '尚不足以确认' in with_source


def test_relative_threshold_works_when_all_full_component_names_match():
    result = record({'当前主刷运转时长': '35分钟', '原始主刷运转时长': '100分钟'})
    query = '能否证明主刷运转时长低于原始主刷运转时长40%？'
    reply = record_evidence_reply(query, result)
    assert '数值满足' in reply and '35分钟' in reply


def test_model_strings_are_not_source_documents_and_records_are_not_mutated():
    result = record({'覆盖率': '80%'})
    before = deepcopy(result)
    reply = record_evidence_reply('这些记录能否确认覆盖率满足刚才的门槛？', result,
                                  source_documents=['覆盖率高于75%即可。'])
    assert '尚不足以确认' in reply and result == before


def test_no_record_judgment_request_does_not_add_extra_prose():
    result = record({'覆盖率': '80%'})
    assert record_evidence_reply('只列覆盖率。', result) is None
    assert record_evidence_reply('是否有这个月的记录？', result) is None
    assert record_evidence_reply('这些记录能否确认门槛？', {'status': 'not_found'}) is None
