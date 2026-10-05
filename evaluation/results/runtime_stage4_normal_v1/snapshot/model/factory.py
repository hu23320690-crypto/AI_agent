from abc import ABC,abstractmethod
from typing import Optional
from langchain_core.embeddings import Embeddings
from langchain_ollama import OllamaEmbeddings
from langchain_ollama.chat_models import ChatOllama
from langchain_ollama.chat_models import BaseChatModel
from utils.config_hander import rag_conf
from agent.runtime import dependency_call, dependency_key

class BaseModelFactory(ABC):
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        pass

class ChatmodelFactory(BaseModelFactory):
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        return ChatOllama(
            model=rag_conf["chat_model_name"], temperature=0,
            reasoning=rag_conf.get("reasoning", False),
            num_ctx=rag_conf.get("num_ctx", 8192),
            client_kwargs={"timeout": rag_conf.get("request_timeout", 120)},
        )

class EmbeddingFactory(BaseModelFactory):
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        embedding_class = QwenRetrievalEmbeddings if rag_conf["embedding_model_name"].startswith("qwen3-embedding") else RuntimeEmbeddings
        return embedding_class(
            model=rag_conf["embedding_model_name"],
            client_kwargs={"timeout": rag_conf.get("request_timeout", 120)},
        )

class RuntimeEmbeddings(OllamaEmbeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        # embed_query delegates here, so each HTTP embedding attempt counts once.
        operation = super().embed_documents
        return dependency_call('embedding', 'ollama.embed', lambda: operation(texts),
                               dependency=dependency_key(self, 'embedding'), retry_safe=True)


class QwenRetrievalEmbeddings(RuntimeEmbeddings):
    """Qwen query instructions apply to questions, never to indexed passages."""
    def embed_query(self, text: str) -> list[float]:
        return super().embed_query(
            "Instruct: Given a question about robot vacuum cleaners, retrieve relevant passages that answer the question.\nQuery: " + text
        )

chat_model = ChatmodelFactory().generator()
embedding_model = EmbeddingFactory().generator()
