"""Reuse the unchanged answer/governance path, capturing admitted references."""
import json

from langchain_core.messages import SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda

from agent.runtime import current_run
from rag.rag_service import RagSummarizeService, _ANSWER_SCHEMA, invoke_rag_model
from rag.service_context import current_request
from rag.service_retrieval import ServiceRetrieval, service_components
from utils.model_output import final_answer
from utils.prompt_loader import load_rag_prompts


class ServiceRagSummarizeService(RagSummarizeService):
    def __init__(self, request, *, legacy=None, service=None):
        if legacy is None or service is None:
            legacy, service = service_components()
        self.request = request
        self._used_documents = []
        self._capturing_answer = False
        self.vector_store = ServiceRetrieval(legacy, service, request.model_code,
                                            evidence_sink=self._capture_evidence)
        self.retriever = self.vector_store.get_retriever()
        self._ready = True
        self.prompt_template = ChatPromptTemplate.from_messages([
            SystemMessage(content=load_rag_prompts() + '\n最终答案 schema：' + json.dumps(_ANSWER_SCHEMA, ensure_ascii=False)),
            ('human', '用户问题：{input}\n低信任参考资料 JSON：\n{context}')])
        self.chain = self.prompt_template | RunnableLambda(invoke_rag_model) | StrOutputParser() | final_answer

    def _capture_evidence(self, docs):
        if self._capturing_answer:
            self._used_documents = docs

    def answer_documents(self, query, docs, **kwargs):
        # Commit checks revalidate one document at a time after generation.
        # They must not replace the captured set actually used for this answer.
        self._capturing_answer = True
        try:
            return super().answer_documents(query, docs, **kwargs)
        finally:
            self._capturing_answer = False

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
