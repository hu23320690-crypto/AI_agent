"""Maintenance extraction preserves complete validated evidence, not gold facts."""
from langchain_core.documents import Document
from unittest.mock import Mock
import pytest

from rag.maintenance_answer import extract_maintenance_answer


def doc(text, source='test-source', version='v1'):
    return Document(page_content=text, metadata={'source_id': source, 'source_version': version,
                                                 'chunk_index': 0, 'chunk_count': 1})


def test_complete_entry_retains_all_actions_periods_and_triggers():
    evidence = doc('11. 部件甲（机型乙）：每两周用清水冲洗，不可揉搓，完全晾干后使用，7个月更换一次，裂口时立即更换。')
    result = extract_maintenance_answer('部件甲多久清洗和更换？破损时要等吗？', [evidence])
    assert result.endswith('部件甲（机型乙）：每两周用清水冲洗，不可揉搓，完全晾干后使用，7个月更换一次，裂口时立即更换。')
    assert '7个月' in result
    assert '6个月' not in result


def test_names_and_facts_are_discovered_without_component_constants():
    evidence = doc('8. 风道组件Z：每9天检查，用干布擦拭，严禁浸泡，变形立即更换。')
    result = extract_maintenance_answer('风道组件Z多久检查？', [evidence])
    assert '每9天' in result and '严禁浸泡' in result and '变形立即更换' in result


def test_expanded_history_target_is_only_used_for_pronoun_question():
    evidence = doc('2. 部件甲：每周清理，晾干后安装，破损立即更换。')
    result = extract_maintenance_answer('部件甲多久清理和更换', [evidence], question='那它多久清理？坏了还要等吗？')
    assert '部件甲' in result and '晾干后安装' in result
    assert extract_maintenance_answer('部件甲多久清理', [evidence], question='部件丙多久清理？') is None


def test_original_explicit_target_overrides_retrieval_expansion():
    evidence = doc('1. 部件甲：每周清理，破损立即更换。\n2. 部件乙：每月清理，晾干后使用。')
    result = extract_maintenance_answer('部件甲多久清理', [evidence], question='部件乙多久清理？')
    assert '部件乙：每月清理' in result
    assert '部件甲' not in result


def test_generic_component_does_not_guess_subtype_even_with_one_retrieved_subtype():
    evidence = doc('1. HEPA滤网：每周清理，晾干后使用。\n2. 污水仓滤网：每月清理，破损立即更换。')
    assert extract_maintenance_answer('滤网多久清理？', [evidence]) is None
    assert extract_maintenance_answer('滤网多久清理？', [doc('1. HEPA滤网：每周清理，晾干后使用。')]) is None
    assert extract_maintenance_answer('污水仓滤网多久清理？', [evidence]).endswith('污水仓滤网：每月清理，破损立即更换。')


def test_generic_entry_and_named_subtypes_are_ambiguous():
    evidence = doc('1. 滤网：每周清理。\n2. HEPA滤网：每月清理。')
    assert extract_maintenance_answer('滤网多久清理？', [evidence]) is None


def test_multiple_objects_are_not_silently_reduced_to_one():
    evidence = doc('1. 部件甲：每周清理。\n2. 部件乙：每月清理。')
    assert extract_maintenance_answer('部件甲和部件乙多久清理？', [evidence]) is None


def test_comparison_is_not_reduced_to_the_only_structured_entry():
    evidence = doc('1. 部件甲：每周润滑一滴。\n部件乙应每月润滑两滴。')
    assert extract_maintenance_answer('部件甲与部件乙各自的润滑周期是什么？请分开回答。', [evidence]) is None


def test_replacement_entry_does_not_answer_a_different_maintenance_action():
    evidence = doc('1. 部件甲：破损立即更换。')
    assert extract_maintenance_answer('部件甲转轴多久润滑一次？', [evidence]) is None


def test_qualifier_variants_require_unambiguous_matching_qualifier():
    evidence = doc('1. 清洁片（可水洗）：每周清洗，晾干后安装。\n2. 清洁片（一次性）：每次更换，不可清洗。')
    assert extract_maintenance_answer('清洁片怎么清洗？', [evidence]) is None
    result = extract_maintenance_answer('可水洗清洁片多久清洗？', [evidence])
    assert '晾干后安装' in result
    assert '一次性' not in result


def test_overlapping_duplicate_chunks_are_deduplicated_without_dropping_conditions():
    first = doc('1. 部件甲：每周清理，晾干后安装，破损立即更换。')
    second = doc('部件甲：每周清理，晾干后安装，破损立即更换。')
    result = extract_maintenance_answer('部件甲多久清理？', [first, second])
    assert result.count('破损立即更换') == 1


@pytest.mark.parametrize('other', [
    doc('1. 部件甲：每月清理，晾干后安装，破损立即更换。', source='other-source'),
    doc('1. 部件甲：每周清理，晾干后安装，破损立即更换。', version='v2'),
])
def test_conflicting_sources_or_versions_fall_back_instead_of_merging(other):
    first = doc('1. 部件甲：每周清理，晾干后安装，破损立即更换。')
    assert extract_maintenance_answer('部件甲多久清理？', [first, other]) is None


@pytest.mark.parametrize('text', [
    '1. 部件甲：每周清理，晾干后安装，破损立即',
    '每周清理部件甲，晾干后安装。',
    '部件甲的情况：性能很好。',
])
def test_partial_or_unstructured_entries_are_not_repaired(text):
    assert extract_maintenance_answer('部件甲多久清理？', [doc(text)]) is None


def test_missing_provenance_and_unrelated_questions_fall_back():
    text = '部件甲：每周清理，晾干后安装。'
    assert extract_maintenance_answer('部件甲多久清理？', [Document(page_content=text)]) is None
    assert extract_maintenance_answer('部件甲购买价格是多少？', [doc(text)]) is None
    assert extract_maintenance_answer('机器人能连5G网络吗？', [doc(text)]) is None


def test_replacement_entry_does_not_omit_a_separately_requested_cleaning_procedure():
    evidence = doc('1. 部件甲：破损立即更换原装部件。')
    assert extract_maintenance_answer('部件甲怎么清理？哪些损坏必须更换？', [evidence]) is None
    assert extract_maintenance_answer('部件甲多久清理和更换？', [evidence]) is None


def test_replacement_cycle_does_not_answer_an_unspecified_drying_duration():
    evidence = doc('1. 部件甲：每周清洗，晾干后使用，7个月更换。')
    assert extract_maintenance_answer('部件甲晾干需要多久？', [evidence]) is None


@pytest.mark.parametrize('query', ['我不是问部件甲多久清理', '不要把部件甲当成维护目标', '我不问部件甲保养周期'])
def test_negated_only_component_is_not_selected(query):
    assert extract_maintenance_answer(query, [doc('部件甲：每周清理，晾干后安装。')]) is None


def test_positive_target_is_not_replaced_by_excluded_component():
    evidence = doc('1. 部件甲：每周清理。\n2. 部件乙：每月清理。')
    result = extract_maintenance_answer('我问部件乙多久清理，不是部件甲', [evidence])
    assert '部件乙：每月清理' in result
    assert '部件甲' not in result


def test_full_stop_at_chunk_edge_does_not_prove_complete_item():
    evidence = doc('11. 部件甲：每周清理。')
    evidence.metadata['chunk_count'] = 2
    assert extract_maintenance_answer('部件甲多久清理', [evidence]) is None
    # The next numbered item establishes a complete structural boundary.
    evidence.page_content += '\n12. 部件乙：每月清理。'
    result = extract_maintenance_answer('部件甲多久清理', [evidence])
    assert result.endswith('部件甲：每周清理。')


def test_wrapped_additional_conditions_are_not_silently_discarded():
    evidence = doc('11. 部件甲：每周清理。\n清理后晾干，破损立即更换。\n12. 部件乙：每月清理。')
    assert extract_maintenance_answer('部件甲多久清理', [evidence]) is None


def test_provided_source_checker_cannot_be_bypassed_by_claimed_source_end_metadata():
    line = '11. 部件甲：每周清理，晾干后使用。'
    evidence = doc(line)
    # A caller-supplied authoritative check outranks this plausible EOF hint.
    checker = Mock(return_value=False)
    assert extract_maintenance_answer('部件甲多久清理', [evidence], boundary_check=checker) is None
    checker.assert_called_once_with(evidence, line)


def test_provided_source_checker_cannot_be_bypassed_by_a_next_item_in_chunk():
    line = '11. 部件甲：每周清理，晾干后使用。'
    evidence = doc(line + '\n12. 部件乙：每月清理。')
    checker = Mock(return_value=False)
    assert extract_maintenance_answer('部件甲多久清理', [evidence], boundary_check=checker) is None
    assert any(call.args == (evidence, line) for call in checker.call_args_list)
