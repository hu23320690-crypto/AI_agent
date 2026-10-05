import json
from contextvars import ContextVar
from threading import Lock
from rag.vector_store import VectorStoreService
from utils.prompt_loader import load_rag_prompts
from langchain_core.prompts import ChatPromptTemplate
from model.factory import chat_model
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document
from langchain_core.runnables import RunnableLambda, RunnableConfig
from utils.model_output import final_answer
from agent.runtime import current_run, runtime_call, RunContext, dependency_call, dependency_key


_evidence_check = ContextVar('rag_evidence_check', default=None)

def invoke_rag_model(prompt, config: RunnableConfig):
    def invoke():
        check = _evidence_check.get()
        if check is not None:
            check()
        return chat_model.invoke(prompt, config=config)
    response = dependency_call('model', 'rag.model', invoke,
                               dependency=dependency_key(chat_model, 'chat'), retry_safe=True)
    run = current_run()
    if run is not None:
        run.check_size(str(response.content), run.limits.max_output_chars, 'RAG模型输出')
    return response


class RagSummarizeService:
    _index_lock = Lock()

    def __init__(self):
        self.vector_store = VectorStoreService()
        self._ready = False
        self.retriever = self.vector_store.get_retriever()
        self.prompt_template = ChatPromptTemplate.from_messages([
            ('system', load_rag_prompts()),
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

    def rag_summarize(self, query: str) -> str:
        if current_run() is None:
            run = RunContext()
            try:
                run.check_size(query, run.limits.max_query_chars, '输入')
                text = runtime_call('run', 'rag.standalone', lambda: self._summarize(query), run=run)
                run.check_size(text, run.limits.max_output_chars, '回答')
                run.complete()
                return text
            except BaseException as exc:
                run.fail(exc)
                raise
        return self._summarize(query)

    def _summarize(self, query):
        return self.answer_documents(query, self.retriever_docs(query))

    def answer_documents(self, query, docs, *, config=None):
        """Also used by frozen-context evaluation; never bypass current authorization."""
        if not docs:
            return '知识库中没有可用参考资料，无法据此回答。'
        evidence = [Document(page_content=d.page_content, metadata=dict(d.metadata)) for d in docs]
        self.vector_store.validate_documents(evidence)
        run = current_run()
        if run is not None:
            run.add_commit_check(lambda: self.vector_store.validate_documents(evidence))
        token = _evidence_check.set(lambda: self.vector_store.validate_documents(evidence))
        try:
            text = self.chain.invoke({'input': query, 'context': self.format_context(evidence)}, config=config)
        finally:
            _evidence_check.reset(token)
        self.vector_store.validate_documents(evidence)
        return text

    @staticmethod
    def format_context(docs):
        return json.dumps([{'reference': index, 'source_id': d.metadata.get('source_id'),
                           'version': d.metadata.get('source_version'), 'source': d.metadata.get('source'),
                           'chunk_id': d.metadata.get('chunk_id'), 'content': d.page_content}
                          for index, d in enumerate(docs, 1)], ensure_ascii=False)


if __name__ == '__main__':
    print(RagSummarizeService().rag_summarize('小户型适合哪一种扫地机器人？'))
