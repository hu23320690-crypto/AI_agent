"""Service catalog: existing governance plus frozen manifest model labels."""
import hashlib
import json
from pathlib import Path
import re

import yaml

from rag.security import ALLOWED, CatalogSnapshot, KnowledgeAccessError, SourceCatalog

ROOT = Path(__file__).resolve().parents[1]
MODEL_CODES = frozenset({'SV-100', 'SV-200', 'SV-300', 'SV-400'})
RETRIEVAL_KEYS = ('k', 'retrieval_mode', 'candidate_k', 'rrf_constant',
                  'chunk_size', 'chunk_overlap', 'separators')


def load_service_rag_config(path=None, *, root=ROOT):
    root = Path(root)
    path = root / 'config/service_rag.yml' if path is None else Path(path)
    value = yaml.safe_load(path.read_text(encoding='utf-8'))
    legacy = yaml.safe_load((root / 'config/chroma.yml').read_text(encoding='utf-8'))
    if (not isinstance(value, dict) or any(value.get(key) != legacy.get(key) for key in RETRIEVAL_KEYS)
            or value.get('collection_name') == legacy['collection_name']
            or not all(isinstance(value.get(key), str) and value[key].strip() for key in
                       ('collection_name', 'persist_directory', 'data_path', 'source_catalog',
                        'manifest_path', 'security_policy'))):
        raise ValueError('invalid service RAG configuration or legacy parameter drift')
    if (root / value['data_path']).resolve() == (root / legacy['data_path']).resolve():
        raise ValueError('service and legacy data roots must differ')
    if (root / value['source_catalog']).resolve() == (root / legacy['source_catalog']).resolve():
        raise ValueError('service and legacy catalogs must differ')
    return value


class ServiceSourceCatalog(SourceCatalog):
    def __init__(self, data_root, ledger_path, manifest_path, policy_path=None):
        super().__init__(data_root, ledger_path, policy_path)
        self.manifest_path = Path(manifest_path)
        self._manifest_cache = None

    def manifest(self):
        raw = self.manifest_path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if self._manifest_cache is not None and self._manifest_cache[0] == digest:
            return self._manifest_cache[1]
        try:
            value = json.loads(raw)
            if value['version'] != 1 or not isinstance(value['files'], list):
                raise ValueError('invalid manifest')
            entries = {}
            for item in value['files']:
                name, models = item['file'], item['models']
                if (not isinstance(name, str) or not re.fullmatch(r'[a-z0-9_-]+\.txt', name)
                        or name in entries or not re.fullmatch(r'[a-f0-9]{64}', item['sha256'])
                        or not isinstance(models, list) or not models or len(models) != len(set(models))
                        or (models != ['all'] and not set(models) <= MODEL_CODES)):
                    raise ValueError('invalid service manifest entry')
                entries[name] = dict(item, models=sorted(models), manifest_sha256=digest)
            if not entries:
                raise ValueError('empty manifest')
        except (KeyError, TypeError, ValueError) as exc:
            raise KnowledgeAccessError('invalid_service_manifest') from exc
        self._manifest_cache = digest, entries
        return entries

    def validate_approved_hashes(self):
        manifest = self.manifest()
        approved = [item for item in self._read_ledger()['sources'] if item['status'] in ALLOWED]
        for item in approved:
            expected = manifest.get(item['path'])
            if expected is None or expected['sha256'] != item['sha256']:
                raise KnowledgeAccessError('service_approval_manifest_mismatch')
        return len(approved)

    def approve(self, relative_path, *, expected_sha256=None, **kwargs):
        expected = self.manifest().get(relative_path)
        if expected is None or expected_sha256 != expected['sha256']:
            raise KnowledgeAccessError('service_approval_manifest_mismatch')
        return super().approve(relative_path, expected_sha256=expected_sha256, **kwargs)

    def snapshot(self):
        snapshot = super().snapshot()
        manifest = self.manifest()
        authorized, blocked = {}, list(snapshot.blocked)
        for source_id, entry in snapshot.authorized.items():
            expected = manifest.get(entry['path'])
            if expected is None or expected['sha256'] != entry['sha256']:
                blocked.append({'path': entry['path'], 'source_id': source_id,
                                'reason': 'service_source_not_in_frozen_manifest'})
            else:
                authorized[source_id] = entry
        stamp = hashlib.sha256(json.dumps({'prior': snapshot.stamp, 'manifest': manifest},
                                         sort_keys=True).encode()).hexdigest()
        return CatalogSnapshot(authorized, blocked, stamp)

    def load_source(self, entry):
        docs = super().load_source(entry)
        expected = self.manifest()[entry['path']]
        for doc in docs:
            doc.metadata.update(knowledge_catalog='service', source_file=entry['path'],
                                models=json.dumps(expected['models'], separators=(',', ':')),
                                manifest_sha256=expected['manifest_sha256'])
        return docs

    def document_allowed(self, doc, snapshot):
        if not super().document_allowed(doc, snapshot):
            return False
        entry = snapshot.authorized[doc.metadata['source_id']]
        expected = self.manifest().get(entry['path'])
        return bool(expected and doc.metadata.get('knowledge_catalog') == 'service'
                    and doc.metadata.get('source_file') == entry['path']
                    and doc.metadata.get('models') == json.dumps(expected['models'], separators=(',', ':'))
                    and doc.metadata.get('manifest_sha256') == expected['manifest_sha256'])


def service_catalog(config=None, *, root=ROOT):
    config = load_service_rag_config(root=root) if config is None else config
    root = Path(root)
    return ServiceSourceCatalog(root / config['data_path'], root / config['source_catalog'],
                                root / config['manifest_path'], root / config['security_policy'])
