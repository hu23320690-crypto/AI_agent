from rag.vector_store import VectorStoreService
from utils.prompt_loader import load_rag_prompts
from langchain_core.prompts import PromptTemplate
from model.factory import chat_model
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document
from utils.model_output import final_answer

class RagSummarizeService:
    def __init__(self):
        self.vector_store = VectorStoreService()
        self._ready = False
        self.retriever = self.vector_store.get_retriever()
        self.prompt_template = PromptTemplate.from_template(load_rag_prompts())
        self.chain = self.prompt_template | chat_model | StrOutputParser() | final_answer

    def ensure_index(self):
        if not self._ready:
            stats = self.vector_store.load_document()
            if stats["failed"]:
                raise RuntimeError("部分知识文档入库失败，请检查知识库日志后重试。")
            self._ready = True

    def retriever_docs(self, query: str) -> list[Document]:
        self.ensure_index()
        return self.retriever.invoke(query)

    def rag_summarize(self, query: str) -> str:
        docs = self.retriever_docs(query)
        if not docs:
            return "知识库中没有可用参考资料，无法据此回答。"
        context = "\n".join(
            f"[参考资料{index}] {doc.page_content} | 来源：{doc.metadata.get('source', '未知')}"
            for index, doc in enumerate(docs, 1)
        )
        return self.chain.invoke({"input": query, "context": context})

if __name__ == "__main__":
    print(RagSummarizeService().rag_summarize("小户型适合哪一种扫地机器人？"))
