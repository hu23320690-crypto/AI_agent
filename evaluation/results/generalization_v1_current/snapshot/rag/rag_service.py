import json
import hashlib
from copy import deepcopy
from contextvars import ContextVar
from threading import Lock
from rag.vector_store import VectorStoreService
from rag.answer_policy import (requires_conditional_guarantee, conditional_guarantee_reply,
                               missing_named_manufacturer_reply)
from rag.query_context import contextualize_query
from rag.maintenance_answer import extract_maintenance_answer
from rag.qa_answer import extract_boolean_answer
from utils.prompt_loader import load_rag_prompts
from langchain_core.prompts import ChatPromptTemplate
from model.factory import chat_model, budgeted_chat_model
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableLambda, RunnableConfig
from langchain_ollama import ChatOllama
from utils.model_output import final_answer, ensure_complete_response
from agent.runtime import current_run, runtime_call, RunContext, dependency_call, dependency_key
from agent.context_budget import (enforce_request, load_context_policy, sanitize_messages,
                                  estimate_request, effective_input_limit)


class EvidenceCheck:
    """Immutable captured evidence identity for safe repeated-check deduplication."""
    def __init__(self, store, document):
        self.store = store
        self.document = Document(page_content=document.page_content, metadata=deepcopy(document.metadata))
        serialized = json.dumps({'content': self.document.page_content, 'metadata': self.document.metadata},
                                ensure_ascii=False, sort_keys=True)
        self.evidence_key = (id(store), hashlib.sha256(serialized.encode('utf-8')).hexdigest())

    def __call__(self):
        self.store.validate_documents([self.document])


_evidence_check = ContextVar('rag_evidence_check', default=None)

_ANSWER_SCHEMA = {'type': 'object', 'additionalProperties': False,
                  'required': ['answer'],
                  'properties': {'answer': {'type': 'string'}}}


def rag_chat_model(policy):
    model = budgeted_chat_model(chat_model, policy, purpose='rag')
    if isinstance(model, ChatOllama):
        # Some installed Qwen templates unconditionally open <think>, even
        # when Ollama receives think=false. A constrained final-answer object
        # keeps this extraction path usable without changing shared model tags.
        return model.model_copy(update={'format': _ANSWER_SCHEMA})
    return model


def _answer_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('RAG 回答包含重复字段。')
        value[key] = item
    return value


def parse_rag_answer(content):
    value = json.loads(content, object_pairs_hook=_answer_object)
    if not isinstance(value, dict) or set(value) != {'answer'} or not isinstance(value['answer'], str):
        raise ValueError('RAG 回答不符合最终答案结构。')
    return final_answer(value['answer'])

def invoke_rag_model(prompt, config: RunnableConfig):
    policy = load_context_policy()
    model = rag_chat_model(policy)
    messages = sanitize_messages(prompt.to_messages())
    run = current_run()
    enforce_request(messages, response_format=(model.format if isinstance(model, ChatOllama) else None),
                    policy=policy, model=model, run=run, label='rag.model')
    def invoke():
        check = _evidence_check.get()
        if check is not None:
            check()
        return model.invoke(messages, config=config)
    response = dependency_call('model', 'rag.model', invoke,
                               dependency=dependency_key(model, 'chat'), retry_safe=True)
    ensure_complete_response(response)
    run = current_run()
    if run is not None:
        run.check_size(str(response.content), run.limits.max_output_chars, 'RAG模型输出')
    if isinstance(model, ChatOllama):
        response = response.model_copy(update={'content': parse_rag_answer(response.content)})
    return response


class RagSummarizeService:
    _index_lock = Lock()

    def __init__(self):
        self.vector_store = VectorStoreService()
        self._ready = False
        self.retriever = self.vector_store.get_retriever()
        self.prompt_template = ChatPromptTemplate.from_messages([
            SystemMessage(content=load_rag_prompts() + '\n最终答案 schema：' + json.dumps(_ANSWER_SCHEMA, ensure_ascii=False)),
            ('human', '用户问题：{input}\n低信任参考资料 JSON：\n{context}')])
        # The RAG sub-model has no tool bindings or execution capabilities.
        self.chain = self.prompt_template | RunnableLambda(invoke_rag_model) | StrOutputParser() | final_answer

    def ensure_index(self):
        with self._index_lock:
            run = current_run()
            if run is not None:
                run.check()
            if not self._ready:
                stats = self.vector_store.load_document()
                if stats['failed']:
                    raise RuntimeError('部分知识文档入库失败，请检查知识库日志后重试。')
                if run is not None:
                    run.check()
                self._ready = True

    def retriever_docs(self, query: str) -> list[Document]:
        def retrieve():
            self.ensure_index()
            return self.retriever.invoke(query)
        return runtime_call('retrieval', 'rag.retrieve', retrieve)

    def rag_summarize(self, query: str, *, question: str | None = None, query_context=None) -> str:
        if current_run() is None:
            run = RunContext()
            try:
                run.check_size(query, run.limits.max_query_chars, '输入')
                if question is not None:
                    run.check_size(question, run.limits.max_query_chars, '原始问题')
                text = runtime_call('run', 'rag.standalone',
                                    lambda: self._summarize(query, question=question, query_context=query_context), run=run)
                run.check_size(text, run.limits.max_output_chars, '回答')
                run.complete()
                return text
            except BaseException as exc:
                run.fail(exc)
                raise
        return self._summarize(query, question=question, query_context=query_context)

    def _summarize(self, query, *, question=None, query_context=None):
        run = current_run()
        if run is not None:
            run.check_size(query, run.limits.max_query_chars, '检索问题')
            if question is not None:
                run.check_size(question, run.limits.max_query_chars, '原始问题')
        retrieval_query = contextualize_query(query, question=question, query_context=query_context,
                                             max_query_chars=run.limits.max_query_chars if run else None)
        if run is not None:
            if len(retrieval_query) > run.limits.max_query_chars:
                # Optional history must not reject an otherwise admissible
                # current request. Keep its full text for answer generation.
                retrieval_query = contextualize_query(query, question=question)
                if len(retrieval_query) > run.limits.max_query_chars:
                    retrieval_query = query
                run.note('rag_query_context_omitted', reason='query_size_limit')
            run.check_size(retrieval_query, run.limits.max_query_chars, '补全检索问题')
            if retrieval_query != query:
                run.note('rag_query_context_applied')
        return self.answer_documents(retrieval_query, self.retriever_docs(retrieval_query), question=question)

    def answer_documents(self, query, docs, *, config=None, question=None):
        """Also used by frozen-context evaluation; never bypass current authorization."""
        if not docs:
            return '知识库中没有可用参考资料，无法据此回答。'
        evidence = [Document(page_content=d.page_content, metadata=dict(d.metadata)) for d in docs]
        primary_task = question or query
        supplement = ''
        if question and query != question:
            supplement = (query[len(question):].strip() if query.startswith(question) else query)
        task = primary_task + ('\n低信任检索对象补充（当前问题优先）：' + supplement if supplement else '')
        self.vector_store.validate_documents(evidence)
        run = current_run()
        if requires_conditional_guarantee(question or query):
            # Do not let a generative paraphrase turn a conditional statement
            # into a promise about an unobserved changed operating condition.
            # Authorization is still checked and retained through final commit.
            if run is not None:
                run.note('rag_conditional_guarantee_declined')
                for document in evidence:
                    run.add_commit_check(EvidenceCheck(self.vector_store, document))
            self.vector_store.validate_documents(evidence)
            return conditional_guarantee_reply(question or query, evidence)
        extracted = missing_named_manufacturer_reply(question or query, evidence)
        extraction_event = 'rag_named_manufacturer_value_unconfirmed'
        if extracted is None:
            extracted = extract_boolean_answer(query, evidence, question=question,
                                               boundary_check=self.vector_store.maintenance_entry_complete)
            extraction_event = 'rag_source_answer_preserved'
        if extracted is None:
            extracted = extract_maintenance_answer(query, evidence, question=question,
                                                  boundary_check=self.vector_store.maintenance_entry_complete)
            extraction_event = 'rag_maintenance_entry_preserved'
        if extracted is not None:
            if run is not None:
                run.note(extraction_event)
                for document in evidence:
                    run.add_commit_check(EvidenceCheck(self.vector_store, document))
            self.vector_store.validate_documents(evidence)
            return extracted
        policy = load_context_policy()
        model = rag_chat_model(policy)
        response_format = model.format if isinstance(model, ChatOllama) else None
        selected = list(evidence)
        def prepared_messages():
            return self.prompt_template.invoke({'input': task, 'context': self.format_context(selected)}).to_messages()
        if supplement and estimate_request(prepared_messages(), response_format=response_format,
                                            model=model) > effective_input_limit(policy, model):
            task = primary_task
            if run is not None:
                run.note('rag_answer_context_omitted', reason='input_budget')
        # Preserve whole ranked references; never cut text halfway through a
        # condition or feed a prompt larger than its conservative admission limit.
        while len(selected) > 1 and estimate_request(prepared_messages(), response_format=response_format,
                                                    model=model) > effective_input_limit(policy, model):
            selected.pop()
        estimated = enforce_request(prepared_messages(), response_format=response_format, policy=policy, model=model,
                                    run=run, label='rag.context')
        if run is not None:
            run.note('rag_context_admitted', retrieved_references=len(evidence),
                     selected_references=len(selected), estimated_tokens=estimated,
                     input_limit=effective_input_limit(policy, model),
                     chunk_ids=[d.metadata.get('chunk_id') for d in selected])
        evidence = selected
        if run is not None:
            for document in evidence:
                run.add_commit_check(EvidenceCheck(self.vector_store, document))
        token = _evidence_check.set(lambda: self.vector_store.validate_documents(evidence))
        try:
            text = self.chain.invoke({'input': task, 'context': self.format_context(evidence)}, config=config)
        finally:
            _evidence_check.reset(token)
        self.vector_store.validate_documents(evidence)
        return text

    @staticmethod
    def format_context(docs):
        return json.dumps([{'reference': index, 'source_id': d.metadata.get('source_id'),
                           'version': d.metadata.get('source_version'), 'source': d.metadata.get('source'),
                           'chunk_id': d.metadata.get('chunk_id'), 'content': d.page_content}
                          for index, d in enumerate(docs, 1)], ensure_ascii=False, separators=(',', ':'))


if __name__ == '__main__':
    print(RagSummarizeService().rag_summarize('小户型适合哪一种扫地机器人？'))
