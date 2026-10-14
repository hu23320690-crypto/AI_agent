"""Reuse the unchanged answer/governance path, capturing admitted references."""
import json

from langchain_core.messages import SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_core.runnables.config import merge_configs
from langchain_core.callbacks import BaseCallbackHandler

from agent.runtime import current_run
from rag import rag_service as rag_core
from rag.rag_service import (RagSummarizeService, _ANSWER_SCHEMA, invoke_rag_model,
                             EvidenceCheck, _evidence_check, _requested_sources)
from rag.security import SourceCatalog
from rag.answer_policy import (requires_conditional_guarantee, conditional_guarantee_reply,
                               missing_individual_lifetime_reply, missing_named_manufacturer_reply)
from rag.maintenance_answer import quote_scoped_entries, extract_maintenance_answer
from rag.qa_answer import extract_boolean_answer
from langchain_core.documents import Document
from langchain_ollama import ChatOllama
from rag.service_context import current_request, evaluation_rag_dispatch
from rag.service_retrieval import ServiceRetrieval, service_components
from service_desk.evaluation_context import kb_overlay
from utils.model_output import final_answer
from utils.prompt_loader import load_rag_prompts


class _EvaluationRagInputTrace(BaseCallbackHandler):
    """Observe the sanitized request at the actual model dispatch boundary."""
    raise_error = True

    def __init__(self, request):
        self.request = request

    def on_chat_model_start(self, serialized, messages, **kwargs):
        context = self.request.evaluation_context
        if kb_overlay(context) is None:
            return
        trace = context.get('turn_trace')
        if trace is not None:
            trace.observe_rag_model(messages, parameters=kwargs.get('invocation_params', {}))


class ServiceRagSummarizeService(RagSummarizeService):
    def __init__(self, request, *, legacy=None, service=None):
        if legacy is None or service is None:
            legacy, service = service_components()
        self.request = request
        self._used_documents = []
        self._capturing_answer = False
        self.vector_store = ServiceRetrieval(legacy, service, request.model_code,
                                            evidence_sink=self._capture_evidence,
                                            evaluation_context=request.evaluation_context)
        self.retriever = self.vector_store.get_retriever()
        self._ready = True
        self.prompt_template = ChatPromptTemplate.from_messages([
            SystemMessage(content=load_rag_prompts() + '\n最终答案 schema：' + json.dumps(_ANSWER_SCHEMA, ensure_ascii=False)),
            ('human', '用户问题：{input}\n低信任参考资料 JSON：\n{context}')])
        self.chain = self.prompt_template | RunnableLambda(self._invoke_model) | StrOutputParser() | final_answer

    def _invoke_model(self, prompt, config):
        if kb_overlay(self.request.evaluation_context) is None:
            return invoke_rag_model(prompt, config)
        # Explicitly pass the observer into the nested RAG call. Ordinary tool
        # callbacks need not propagate through rag_summerize.func.
        config = merge_configs(config, {'callbacks': [_EvaluationRagInputTrace(self.request)]})
        with evaluation_rag_dispatch():
            return invoke_rag_model(prompt, config)

    def _capture_evidence(self, docs):
        if self._capturing_answer:
            self._used_documents = docs

    def answer_documents(self, query, docs, **kwargs):
        # Commit checks revalidate one document at a time after generation.
        # They must not replace the captured set actually used for this answer.
        self._capturing_answer = True
        try:
            if kb_overlay(self.request.evaluation_context) is None:
                return super().answer_documents(query, docs, **kwargs)
            return self._answer_overlay_documents(query, docs, **kwargs)
        finally:
            self._capturing_answer = False

    def _answer_overlay_documents(self, query, docs, *, config=None, question=None, scoped_entries=()):
        """Keep legacy answer policy intact while protecting the extra carrier.

        The legacy implementation is byte-frozen. Reuse its policy helpers and
        checks here; only budget pruning differs in this capability-only path.
        """
        catalog = getattr(self.vector_store, 'catalog', None)
        if isinstance(catalog, SourceCatalog):
            _, requested = _requested_sources(catalog, question or query)
            if requested:
                docs = [doc for doc in docs if doc.metadata.get('source_id') in requested]
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
        extracted = missing_individual_lifetime_reply(question or query, evidence)
        extraction_event = 'rag_individual_lifetime_unconfirmed'
        if extracted is None:
            extracted = missing_named_manufacturer_reply(question or query, evidence)
            extraction_event = 'rag_named_manufacturer_value_unconfirmed'
        if extracted is None and scoped_entries:
            if any(not any(doc.page_content == entry.page_content and doc.metadata == entry.metadata
                           for doc in evidence) for entry in scoped_entries):
                raise ValueError('来源专项条目必须属于本轮已校验的参考资料。')
            self.vector_store.validate_documents(scoped_entries)
            extracted = quote_scoped_entries(query, scoped_entries, question=question,
                                             boundary_check=self.vector_store.maintenance_entry_complete)
            extraction_event = 'rag_explicit_source_entries_preserved'
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
                run.check_size(extracted, run.limits.max_output_chars, 'RAG资料回答')
                run.note(extraction_event)
                for document in evidence:
                    run.add_commit_check(EvidenceCheck(self.vector_store, document))
            self.vector_store.validate_documents(evidence)
            return extracted
        policy = rag_core.load_context_policy()
        model = rag_core.rag_chat_model(policy)
        response_format = model.format if isinstance(model, ChatOllama) else None
        selected = list(evidence)
        def prepared_messages():
            return self.prompt_template.invoke({'input': task, 'context': self.format_context(selected)}).to_messages()
        if supplement and rag_core.estimate_request(prepared_messages(), response_format=response_format,
                                                     model=model) > rag_core.effective_input_limit(policy, model):
            task = primary_task
            if run is not None:
                run.note('rag_answer_context_omitted', reason='input_budget')
        # Preserve whole ranked references; never cut text halfway through a
        # condition or feed a prompt larger than its conservative admission limit.
        while len(selected) > 1 and rag_core.estimate_request(prepared_messages(), response_format=response_format,
                                                             model=model) > rag_core.effective_input_limit(policy, model):
            if self.vector_store._is_overlay(selected[-1]):
                selected.pop(-2)
            else:
                selected.pop()
        estimated = rag_core.enforce_request(prepared_messages(), response_format=response_format,
                                             policy=policy, model=model, run=run, label='rag.context')
        if run is not None:
            run.note('rag_context_admitted', retrieved_references=len(evidence),
                     selected_references=len(selected), estimated_tokens=estimated,
                     input_limit=rag_core.effective_input_limit(policy, model),
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

    def ensure_index(self):
        # Only administrator sync writes indexes. In particular no legacy sync.
        if current_run() is not None:
            current_run().check()

    def rag_summarize(self, query, *, question=None, query_context=None):
        self._used_documents = []
        text = super().rag_summarize(query, question=question, query_context=query_context)
        self.request.references = self.vector_store.references(list(self._used_documents))
        return text


def get_service_rag_service():
    request = current_request()
    if request is None:
        raise RuntimeError('service RAG requires a bound request')
    # The model scope and commit-check store live on this call's instance.
    return ServiceRagSummarizeService(request)
