"""Source-scoped complete entries and uncertainty use governed offline fixtures."""
import hashlib
import json
from unittest.mock import Mock, patch

import pytest
from langchain_core.documents import Document

from agent.runtime import RunContext, runtime_call, BudgetExceeded
from rag.answer_policy import missing_individual_lifetime_reply
from rag.maintenance_answer import requested_source_ids, scoped_entry_documents
from rag.qa_answer import extract_boolean_answer
from rag.rag_service import RagSummarizeService
from rag.security import SourceCatalog, KnowledgeAccessError, stable_source_id, chunk_sha256
from rag.vector_store import VectorStoreService


@pytest.fixture
def store(tmp_path):
    root = tmp_path.resolve()
    data = root / 'data'
    data.mkdir()
    ledger = root / 'sources.json'
    ledger.write_text('{"schema_version":1,"sources":[]}', encoding='utf-8')
    result = VectorStoreService.__new__(VectorStoreService)
    result.catalog = SourceCatalog(data, ledger)
    result.pipeline = 'offline-test-pipeline'
    result.config = {'k': 5}
    result.get_retriever = Mock()
    return result


def source(store, name, text, *, status='approved'):
    path = store.catalog.data_root / name
    path.write_text(text, encoding='utf-8')
    record = {'path': name, 'source_id': stable_source_id(name), 'version': 1,
              'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'status': status,
              'allow_risk': False, 'review_note': 'synthetic offline fixture'}
    raw = json.loads(store.catalog.ledger_path.read_text(encoding='utf-8'))
    raw['sources'].append(record)
    store.catalog.ledger_path.write_text(json.dumps(raw), encoding='utf-8')
    return record


def indexed(store, record, text):
    return Document(page_content=text, metadata={
        'source': str(store.catalog.data_root / record['path']),
        'source_id': record['source_id'], 'source_version': 1,
        'source_sha256': record['sha256'], 'pipeline': store.pipeline,
        'chunk_id': 'initial-' + record['source_id'], 'chunk_sha256': chunk_sha256(text),
        'start_index': 0, 'chunk_index': 0, 'chunk_count': 1})


def service(store, initial=()):
    with patch('rag.rag_service.VectorStoreService', return_value=store):
        result = RagSummarizeService()
    result.retriever_docs = Mock(return_value=list(initial))
    result.chain = Mock()
    result.chain.invoke.return_value = '生成路径的完整回答。'
    return result


def test_explicit_source_recovers_complete_entry_topk_missed_and_retains_commit_check(store):
    source(store, '配件保养.txt', '# 配件保养\n## 耗材专项\n'
           '1. 驱动单元Z：正常9年更换，输出低于原值40%或鼓包立即更换原装件。\n'
           '2. 清洁片：每月清理。')
    other_text = '1. 驱动单元Z：正常4年更换，破损时更换。'
    other = source(store, '问答示例.txt', other_text)
    instance = service(store, [indexed(store, other, other_text)])
    run = RunContext()
    result = runtime_call('run', 'test.source', lambda: instance.rag_summarize(
        '按配件保养中的驱动单元Z专项条目，通常更换周期和异常条件是什么？'), run=run)
    assert '9年' in result and '40%' in result and '原装件' in result
    assert '4年' not in result
    instance.chain.invoke.assert_not_called()
    assert len(run.get_commit_checks()) == 1
    raw = json.loads(store.catalog.ledger_path.read_text(encoding='utf-8'))
    raw['sources'][0]['status'] = 'revoked'
    store.catalog.ledger_path.write_text(json.dumps(raw), encoding='utf-8')
    with pytest.raises(KnowledgeAccessError):
        run.complete()


def test_generic_request_does_not_load_full_source_or_widen_extraction(store):
    source(store, '配件保养.txt', '1. 清洁片：每月清理，完全晾干。')
    instance = service(store)
    with patch.object(store.catalog, 'load_source', wraps=store.catalog.load_source) as load:
        assert instance.rag_summarize('清洁片多久清理？') == '知识库中没有可用参考资料，无法据此回答。'
    load.assert_not_called()


def test_source_title_abbreviation_requires_explicit_unique_attribution():
    ledger = {'one': {'path': '配件保养.txt'}, 'two': {'path': '其他问答.txt'}}
    assert requested_source_ids('清理配件要多久？', ledger) == set()
    assert requested_source_ids('按配件资料说清理周期', ledger) == {'one'}
    assert requested_source_ids('不要按配件保养，问其他问答', ledger) == {'two'}
    ledger['three'] = {'path': '配件操作.txt'}
    assert requested_source_ids('按配件资料说清理周期', ledger) == set()


@pytest.mark.parametrize('excluded,selected', [('岚松指南', '星河手册'), ('星河手册', '岚松指南')])
@pytest.mark.parametrize('negation', ['不按', '不要按', '不要用', '别引用', '排除', '无需参考', '勿采用'])
def test_negated_source_clause_preserves_the_following_requested_source(excluded, selected, negation):
    ledger = {'north': {'path': '岚松指南.txt'}, 'south': {'path': '星河手册.txt'}}
    expected = next(key for key, value in ledger.items() if value['path'] == selected + '.txt')
    assert requested_source_ids(f'{negation}{excluded}回答，请按{selected}说明清理周期', ledger) == {expected}


@pytest.mark.parametrize('title', ['岚松指南', '星河手册'])
def test_later_source_correction_can_restore_or_withdraw_an_earlier_mention(title):
    ledger = {'north': {'path': '岚松指南.txt'}, 'south': {'path': '星河手册.txt'}}
    expected = next(key for key, value in ledger.items() if value['path'] == title + '.txt')
    assert requested_source_ids(f'不要引用{title}。更正：请按{title}回答', ledger) == {expected}
    assert requested_source_ids(f'先按{title}。更正：不要再引用{title}', ledger) == set()


def test_source_negation_stays_with_its_own_clause_without_a_short_distance_limit():
    ledger = {'north': {'path': '岚松指南.txt'}, 'south': {'path': '星河手册.txt'}}
    assert requested_source_ids('别引用已经过时而且针对其他设备版本的岚松指南，而是按星河手册回答', ledger) == {'south'}
    assert requested_source_ids('不按岚松指南而是按星河手册回答', ledger) == {'south'}


def test_longest_explicit_source_title_does_not_select_its_contained_title():
    ledger = {'short': {'path': '指南A.pdf'}, 'long': {'path': '指南A2.txt'}}
    assert requested_source_ids('请按指南A2说明维护周期', ledger) == {'long'}
    assert requested_source_ids('请按指南A说明维护周期', ledger) == {'short'}
    assert requested_source_ids('不要按指南A，改按指南A2说明', ledger) == {'long'}
    assert requested_source_ids('分别按指南A与指南A2说明差异', ledger) == {'short', 'long'}


def test_equal_source_titles_remain_ambiguous_unless_extension_is_explicit():
    ledger = {'pdf': {'path': '指南A2.pdf'}, 'text': {'path': '指南A2.txt'}}
    assert requested_source_ids('按指南A2说明维护周期', ledger) == {'pdf', 'text'}
    assert requested_source_ids('按指南A2.txt说明维护周期', ledger) == {'text'}
    assert requested_source_ids('按指南A2.pdf说明维护周期', ledger) == {'pdf'}


def test_original_source_scope_outranks_retrieval_reformulation(store):
    source(store, '配件保养.txt', '1. 清洁片：每月清理。')
    text = '1. 清洁片：每两周清理。'
    other = source(store, '用户指南.txt', text)
    instance = service(store, [indexed(store, other, text)])
    result = instance.rag_summarize('按配件保养清洁片多久清理？', question='按用户指南清洁片多久清理？')
    assert '每两周' in result and '每月' not in result


def test_revoked_requested_source_cannot_fall_back_to_another_source(store):
    source(store, '配件保养.txt', '1. 清洁片：每月清理。', status='revoked')
    text = '1. 清洁片：每周清理。'
    other = source(store, '其他指南.txt', text)
    instance = service(store, [indexed(store, other, text)])
    with pytest.raises(KnowledgeAccessError):
        instance.rag_summarize('按配件保养清洁片多久清理？')
    instance.chain.invoke.assert_not_called()


def test_same_component_frequencies_keep_original_sections_and_exclude_other_component(store):
    record = source(store, '配件保养.txt', '# 配件保养\n## 功能专属\n'
                    '1. 模式Q机型，每日清理清洁仓的刷A，挑出杂物。\n'
                    '2. 模式Q机型，每周清理底部模组刷A。\n## 耗材专项\n'
                    '1. 刷A（模式Q款）：每周清理，每月水洗，8个月更换，变形立即更换。\n'
                    '2. 底部模组刷A：与清洁片同步更换。')
    instance = service(store)
    query = '按配件保养，模式Q清洁仓刷A如何清理、多久水洗更换？请分章节说明，不是底部模组刷A。'
    result = instance.rag_summarize(query)
    assert '【功能专属】' in result and '【耗材专项】' in result
    assert '每日' in result and '每周' in result and '每月水洗' in result
    assert '变形立即更换' in result
    assert '底部模组' not in result and '同步' not in result
    instance.chain.invoke.assert_not_called()
    documents = scoped_entry_documents(query, store.catalog.load_source(record),
                                       pipeline=store.pipeline, max_entries=3)
    assert len(documents) == 2
    for document in documents:
        assert store.maintenance_entry_complete(document, document.page_content)


def test_ambiguous_component_subtype_does_not_take_complete_entry_route(store):
    record = source(store, '配件保养.txt', '1. 滤片：每周清理。\n2. 高效滤片：每月清理。')
    assert scoped_entry_documents('按配件保养滤片多久清理？', store.catalog.load_source(record),
                                  pipeline=store.pipeline, max_entries=3) == []


def test_source_entries_respect_quota_and_do_not_drop_a_required_chapter(store):
    record = source(store, '配件保养.txt', '# 配件保养\n## 日常\n'
                    '1. 模式Q机型，每日清理刷A。\n## 耗材\n'
                    '1. 刷A（模式Q款）：每周清理，7个月更换，损坏立即更换。\n'
                    '2. 配件B：每月清理。\n3. 配件C：每周清理。')
    initial = indexed(store, record, store.catalog.load_source(record)[0].page_content)
    instance = service(store, [initial])
    query = '按配件保养，模式Q刷A多久清理更换？分章节说明。'
    store.config['k'] = 1
    captured = []
    original = instance.answer_documents
    def capture(query, documents, **kwargs):
        captured.append((documents, kwargs['scoped_entries']))
        return original(query, documents, **kwargs)
    instance.answer_documents = capture
    instance.rag_summarize(query)
    assert len(captured[0][0]) == 1 and captured[0][1] == []
    # The ordinary single-entry extractor must not misrepresent a reduced
    # chapter set as a complete answer to this explicit chapter request.
    instance.chain.invoke.assert_called_once()


def test_complete_direct_answer_still_enforces_runtime_output_limit(store):
    source(store, '配件保养.txt', '1. 清洁片：每月清理，完全晾干，损坏立即更换。')
    instance = service(store)
    from dataclasses import replace
    run = RunContext()
    run.limits = replace(run.limits, max_output_chars=20)
    with pytest.raises(BudgetExceeded):
        runtime_call('run', 'test.output', lambda: instance.rag_summarize(
            '按配件保养清洁片多久清理更换？'), run=run)


def test_scoped_quote_cannot_use_evidence_outside_the_delivered_reference_set(store):
    record = source(store, '配件保养.txt', '1. 清洁片：每月清理，损坏立即更换。')
    documents = scoped_entry_documents('清洁片多久清理？', store.catalog.load_source(record),
                                       pipeline=store.pipeline, max_entries=3)
    instance = service(store)
    with pytest.raises(ValueError, match='本轮已校验'):
        instance.answer_documents('清洁片多久清理？',
                                  [indexed(store, record, record['path'])], scoped_entries=documents)


@pytest.mark.parametrize('query', [
    '部件甲可以用在系统乙中吗，处理步骤是什么',
    '部件甲可以用在系统乙中吗，还要多久校准',
    '部件甲可以用在系统乙中吗，为什么',
])
def test_boolean_shortcut_does_not_drop_procedure_or_reason_subquestion(query):
    document = Document(page_content='1. 部件甲可以用在系统乙中吗？\n- 可以，条件甲成立时可用。',
                        metadata={'source_id': 'test', 'source_version': 1})
    assert extract_boolean_answer(query, [document], boundary_check=lambda *args: True) is None


def test_individual_prognosis_refusal_has_no_unobserved_damage_cause():
    evidence = Document(page_content='过滤片Z：每9个月更换，清洗后晾干。')
    result = missing_individual_lifetime_reply('假设这块过滤片Z受潮，准确预测它还能用多少小时才失效', [evidence])
    assert '不足以' in result and '实测剩余寿命' in result
    assert '立即' not in result and '9个月' not in result
    measured = Document(page_content='过滤片Z检测结果：剩余寿命12小时。')
    assert missing_individual_lifetime_reply('准确预测这块过滤片Z还能用多少小时', [measured]) is None


def test_frozen_context_answer_path_does_not_load_missing_source_entries(store):
    source(store, '配件保养.txt', '1. 清洁片：每月清理，损坏立即更换。')
    text = '1. 清洁片：每周清理。'
    other = source(store, '其他指南.txt', text)
    instance = service(store)
    with patch.object(store.catalog, 'load_source', wraps=store.catalog.load_source) as load:
        result = instance.answer_documents('按配件保养清洁片多久清理？', [indexed(store, other, text)])
    assert '没有可用参考资料' in result
    load.assert_not_called()
