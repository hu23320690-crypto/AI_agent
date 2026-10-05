import hashlib
import json
from pathlib import Path
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from utils.config_hander import chroma_conf
from model.factory import embedding_model
from utils.path_tool import get_abs_path
from utils.file_hander import pdf_loader, txt_loader, listdir_with_allowed_type, get_file_md5_hex
from utils.logger_hander import logger

class VectorStoreService:
    def __init__(self, *, config=None, embedding=None, vector_store=None):
        self.config = dict(chroma_conf if config is None else config)
        self.vector_store = vector_store if vector_store is not None else Chroma(
            collection_name=self.config["collection_name"],
            embedding_function=embedding if embedding is not None else embedding_model,
            persist_directory=get_abs_path(self.config["persist_directory"]),
        )
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.config["chunk_size"],
            chunk_overlap=self.config["chunk_overlap"],
            separators=self.config["separators"], length_function=len,
            add_start_index=True,
        )
        self.pipeline = hashlib.sha256(json.dumps({
            "version": 1, "size": self.config["chunk_size"],
            "overlap": self.config["chunk_overlap"], "separators": self.config["separators"],
            "embedding": getattr(embedding if embedding is not None else embedding_model,
                                 "model", type(embedding).__qualname__),
        }, sort_keys=True).encode()).hexdigest()

    def get_retriever(self):
        return self.vector_store.as_retriever(search_kwargs={"k": self.config["k"]})

    def load_document(self):
        """Split before indexing; upsert new chunks before removing stale chunks.

        Deduplication is based on actual index metadata, not the old md5.txt.
        A partially failed batch is retried instead of being marked completed.
        """
        paths = listdir_with_allowed_type(
            get_abs_path(self.config["data_path"]),
            tuple(self.config["allow_knowledge_file_type"]),
        )
        stats = {"indexed": 0, "skipped": 0, "chunks": 0, "failed": []}
        for path in paths:
            try:
                source_key = hashlib.sha256(str(Path(path).resolve()).casefold().encode()).hexdigest()
                file_hash = get_file_md5_hex(path)
                old = self.vector_store.get(where={"source_key": source_key}, include=["metadatas"])
                metadata = old.get("metadatas") or []
                if metadata and all(
                    item.get("file_hash") == file_hash
                    and item.get("pipeline") == self.pipeline
                    and item.get("chunk_count") == len(metadata)
                    for item in metadata
                ):
                    stats["skipped"] += 1
                    continue
                documents = pdf_loader(path) if Path(path).suffix.lower() == ".pdf" else txt_loader(path)
                chunks = [doc for doc in self.splitter.split_documents(documents) if doc.page_content.strip()]
                if not chunks:
                    raise ValueError("文档没有可入库的文本")
                ids = []
                for index, doc in enumerate(chunks):
                    doc.metadata.update(source_key=source_key, file_hash=file_hash,
                                        pipeline=self.pipeline, chunk_index=index, chunk_count=len(chunks))
                    ids.append(hashlib.sha256(
                        f"{source_key}:{file_hash}:{self.pipeline}:{index}".encode()
                    ).hexdigest())
                for offset in range(0, len(chunks), 64):
                    self.vector_store.add_documents(chunks[offset:offset+64], ids=ids[offset:offset+64])
                stale = sorted(set(old["ids"]) - set(ids))
                if stale:
                    self.vector_store.delete(ids=stale)
                stats["indexed"] += 1
                stats["chunks"] += len(chunks)
                logger.info("[加载知识库]%s 入库 %d 个分块", path, len(chunks))
            except Exception:
                stats["failed"].append(str(path))
                logger.exception("[加载知识库]%s 加载失败", path)
        return stats

if __name__ == "__main__":
    stats = VectorStoreService().load_document()
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    if stats["failed"]:
        raise SystemExit(1)
