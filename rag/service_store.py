"""A separate governed collection; model filtering precedes both rankers."""
from contextvars import ContextVar
import hashlib
import json

from rag.service_catalog import MODEL_CODES, load_service_rag_config, service_catalog
from rag.vector_store import VectorStoreService

_model_filter = ContextVar('service_index_model_filter', default=None)


class ServiceVectorStoreService(VectorStoreService):
    def __init__(self, *, config=None, embedding=None, vector_store=None):
        config = load_service_rag_config() if config is None else dict(config)
        super().__init__(config=config, embedding=embedding, vector_store=vector_store)
        self.catalog = service_catalog(config)
        manifest = self.catalog.manifest()
        self.pipeline = hashlib.sha256((self.pipeline + ':service:' +
                                       json.dumps(manifest, sort_keys=True)).encode()).hexdigest()

    def _eligible(self, snapshot):
        model = _model_filter.get()
        docs = super()._eligible(snapshot)
        return [doc for doc in docs if 'all' in json.loads(doc.metadata['models'])
                or model in json.loads(doc.metadata['models'])]

    def search(self, query, k=None, *, model_code=None):
        if model_code is not None and model_code not in MODEL_CODES:
            raise ValueError('unknown service model')
        token = _model_filter.set(model_code)
        try:
            return super().search(query, k)
        finally:
            _model_filter.reset(token)
