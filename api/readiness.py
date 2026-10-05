"""Bounded, coalesced dependency checks; never generate or auto-index."""
import asyncio
import os
from pathlib import Path
import time

import httpx
import yaml

ROOT = Path(__file__).resolve().parents[1]


class ReadinessProbe:
    def __init__(self):
        self.task = None
        self.expires = 0
        self.result = {'ready': False, 'reason': 'not_checked'}

    async def __call__(self):
        if time.monotonic() < self.expires:
            return self.result
        if self.task is None:
            self.task = asyncio.create_task(self._check())
        task = self.task
        done, _ = await asyncio.wait({task}, timeout=3)
        if not done:
            return {'ready': False, 'reason': 'check_pending'}
        self.result = task.result()
        if self.task is task:
            self.task = None
        self.expires = time.monotonic()+5
        return self.result

    async def _check(self):
        try:
            rag = yaml.safe_load((ROOT/'config/rag.yml').read_text(encoding='utf-8'))
            host = os.environ.get('OLLAMA_HOST', 'http://127.0.0.1:11434')
            async with httpx.AsyncClient(base_url=host, timeout=2, trust_env=False) as client:
                response = await client.get('/api/tags')
                response.raise_for_status()
                available = {item['name'] for item in response.json()['models']}
            if not all(rag[key] in available for key in ('chat_model_name', 'embedding_model_name')):
                return {'ready': False, 'reason': 'models_missing'}
            # The only sync probe is coalesced: timeout callers do not start more workers.
            return await asyncio.to_thread(self._local_checks, host)
        except Exception:
            return {'ready': False, 'reason': 'dependencies_unavailable'}

    @staticmethod
    def _local_checks(host):
        from model.token_count import verify_local_cache
        if not verify_local_cache(host=host):
            return {'ready': False, 'reason': 'tokenizer_identity'}
        chroma = yaml.safe_load((ROOT/'config/chroma.yml').read_text(encoding='utf-8'))
        if not (ROOT/chroma['persist_directory']/'chroma.sqlite3').is_file():
            return {'ready': False, 'reason': 'index_missing'}
        from rag.vector_store import VectorStoreService
        store = VectorStoreService()
        snapshot = store.catalog.snapshot()
        if not store._eligible(snapshot):
            return {'ready': False, 'reason': 'authorized_index_empty'}
        return {'ready': True}

    async def close(self):
        if self.task is not None:
            # Cancel async HTTP, but do not pretend this kills any filesystem worker.
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
