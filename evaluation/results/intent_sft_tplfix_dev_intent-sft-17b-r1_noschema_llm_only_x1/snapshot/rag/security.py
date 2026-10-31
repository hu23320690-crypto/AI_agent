"""Source approval and retrieval validation for the local RAG demonstration.

The ledger and application configuration are administrator-controlled. This
module treats source files as untrusted, including files previously approved.
Rules are risk signals; neither approval nor hashing establishes factual truth.
"""
from collections import OrderedDict
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path, PureWindowsPath
import re
import tempfile
from threading import RLock
import time
import unicodedata

from langchain_core.documents import Document
import yaml

from agent.runtime import RuntimeControlError


class KnowledgeAccessError(RuntimeControlError):
    """An administrator policy or current source version denied access."""

    def __init__(self, code):
        self.code = code
        super().__init__('参考资料未通过来源或版本校验，本轮未提交回答，请联系资料管理员。')


@dataclass(frozen=True)
class SecurityPolicy:
    max_file_bytes: int = 8 * 1024 * 1024
    max_text_chars: int = 500_000
    max_chunks_per_source: int = 3
    max_sources: int = 512
    max_pdf_pages: int = 500
    cache_entries: int = 8
    cache_text_chars: int = 1_000_000
    deduplicate_chunks: bool = True
    reject_invisible_chars: bool = True
    risk_rules: tuple = ()


@dataclass(frozen=True)
class CatalogSnapshot:
    authorized: dict
    blocked: list
    stamp: str


STATUSES = frozenset({'approved', 'demo_allowed', 'quarantined', 'revoked'})
ALLOWED = frozenset({'approved', 'demo_allowed'})
ROOT = Path(__file__).resolve().parents[1]


def _relative_path(value):
    if not isinstance(value, str) or not value or '\x00' in value:
        raise KnowledgeAccessError('invalid_source_path')
    value = value.replace('\\', '/')
    windows = PureWindowsPath(value)
    parts = value.split('/')
    if windows.drive or windows.root or value.startswith('/') or any(
        part in ('', '.', '..') or ':' in part or part.endswith(('.', ' '))
        for part in parts
    ):
        raise KnowledgeAccessError('invalid_source_path')
    if any(unicodedata.category(ch) in ('Cc', 'Cf') for ch in value):
        raise KnowledgeAccessError('invalid_source_path')
    return '/'.join(parts)


def stable_source_id(relative_path):
    """Stable across installation directories; Windows paths are case-insensitive."""
    normalized = _relative_path(relative_path).casefold()
    return 'src_' + hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:24]


def chunk_sha256(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _positive_integer(value, name):
    if type(value) is not int or value <= 0:
        raise KnowledgeAccessError('invalid_policy:' + name)
    return value


def load_security_policy(path=None):
    path = ROOT / 'config/security.yml' if path is None else Path(path)
    try:
        raw = yaml.safe_load(path.read_text(encoding='utf-8-sig'))
        if not isinstance(raw, dict):
            raise ValueError('mapping required')
        fields = set(SecurityPolicy.__dataclass_fields__)
        if set(raw) - fields:
            raise ValueError('unknown policy field')
        values = {}
        for key in fields - {'risk_rules', 'deduplicate_chunks', 'reject_invisible_chars'}:
            values[key] = _positive_integer(raw.get(key, getattr(SecurityPolicy(), key)), key)
        for key in ('deduplicate_chunks', 'reject_invisible_chars'):
            values[key] = raw.get(key, True)
            if type(values[key]) is not bool:
                raise ValueError('boolean required')
        rules = raw.get('risk_rules', [])
        if not isinstance(rules, list) or len(rules) > 64:
            raise ValueError('invalid risk rules')
        compiled, ids = [], set()
        for rule in rules:
            if not isinstance(rule, dict) or set(rule) != {'id', 'pattern'}:
                raise ValueError('invalid risk rule')
            if not isinstance(rule['id'], str) or not rule['id'] or rule['id'] in ids:
                raise ValueError('duplicate risk rule')
            if not isinstance(rule['pattern'], str) or len(rule['pattern']) > 1_000:
                raise ValueError('invalid rule pattern')
            ids.add(rule['id'])
            compiled.append((rule['id'], re.compile(rule['pattern'], re.I | re.M)))
        values['risk_rules'] = tuple(compiled)
        return SecurityPolicy(**values)
    except KnowledgeAccessError:
        raise
    except Exception as exc:
        raise KnowledgeAccessError('invalid_security_policy') from exc


class SourceCatalog:
    def __init__(self, data_root, ledger_path, policy_path=None):
        self.data_root = Path(data_root).resolve()
        self.ledger_path = Path(ledger_path).resolve()
        self.policy = load_security_policy(policy_path)
        if not self.data_root.is_dir():
            raise KnowledgeAccessError('missing_data_root')
        # The ledger must not be writable through the attacker's document folder.
        if self.ledger_path.is_relative_to(self.data_root):
            raise KnowledgeAccessError('ledger_inside_untrusted_data_root')
        self._cache = OrderedDict()
        self._cache_chars = 0
        self._cache_lock = RLock()

    def _safe_path(self, relative):
        relative = _relative_path(relative)
        candidate = self.data_root
        for part in relative.split('/'):
            candidate = candidate / part
            if candidate.is_symlink() or getattr(candidate, 'is_junction', lambda: False)():
                raise KnowledgeAccessError('linked_source_path')
        resolved = candidate.resolve()
        if not resolved.is_relative_to(self.data_root):
            raise KnowledgeAccessError('source_outside_data_root')
        if resolved.suffix.lower() not in ('.txt', '.pdf'):
            raise KnowledgeAccessError('unsupported_source_type')
        if not resolved.is_file():
            raise KnowledgeAccessError('missing_source')
        return resolved

    def _read_ledger(self):
        try:
            if self.ledger_path.stat().st_size > 2 * 1024 * 1024:
                raise ValueError('ledger too large')
            raw = json.loads(self.ledger_path.read_text(encoding='utf-8-sig'))
            if not isinstance(raw, dict) or type(raw.get('schema_version')) is not int or raw['schema_version'] != 1:
                raise ValueError('invalid schema')
            entries = raw.get('sources')
            if not isinstance(entries, list) or len(entries) > self.policy.max_sources:
                raise ValueError('invalid sources')
            ids, paths, normalized = set(), set(), []
            for entry in entries:
                if not isinstance(entry, dict):
                    raise ValueError('invalid source entry')
                item = dict(entry)
                item['path'] = _relative_path(item.get('path'))
                if item.get('source_id') != stable_source_id(item['path']):
                    raise ValueError('invalid source id')
                if item['source_id'] in ids or item['path'].casefold() in paths:
                    raise ValueError('duplicate source')
                ids.add(item['source_id'])
                paths.add(item['path'].casefold())
                _positive_integer(item.get('version'), 'source_version')
                if not isinstance(item.get('sha256'), str) or not re.fullmatch('[0-9a-f]{64}', item['sha256']):
                    raise ValueError('invalid source digest')
                if item.get('status') not in STATUSES:
                    raise ValueError('invalid source status')
                item.setdefault('allow_risk', False)
                item.setdefault('review_note', '')
                if type(item['allow_risk']) is not bool or not isinstance(item['review_note'], str):
                    raise ValueError('invalid review record')
                if len(item['review_note']) > 2_000 or (item['allow_risk'] and not item['review_note'].strip()):
                    raise ValueError('risk override requires review note')
                normalized.append(item)
            return {'schema_version': 1, 'sources': normalized}
        except KnowledgeAccessError:
            raise
        except Exception as exc:
            raise KnowledgeAccessError('invalid_or_missing_knowledge_ledger') from exc

    def _parse_bytes(self, raw, suffix):
        if suffix == '.txt':
            try:
                pages = [(raw.decode('utf-8-sig'), None)]
            except UnicodeError as exc:
                raise KnowledgeAccessError('invalid_text_encoding') from exc
        else:
            try:
                from pypdf import PdfReader
                reader = PdfReader(BytesIO(raw))
                if reader.is_encrypted or len(reader.pages) > self.policy.max_pdf_pages:
                    raise KnowledgeAccessError('unsupported_or_oversized_pdf')
                pages, total = [], 0
                for index, page in enumerate(reader.pages):
                    text = page.extract_text() or ''
                    total += len(text)
                    if total > self.policy.max_text_chars:
                        raise KnowledgeAccessError('source_text_limit')
                    pages.append((text, index))
            except KnowledgeAccessError:
                raise
            except Exception as exc:
                raise KnowledgeAccessError('invalid_pdf') from exc
        if sum(len(text) for text, _ in pages) > self.policy.max_text_chars:
            raise KnowledgeAccessError('source_text_limit')
        if not any(text.strip() for text, _ in pages):
            raise KnowledgeAccessError('empty_source')
        return tuple(pages)

    def _inspect(self, relative, expected_sha256=None):
        # Concurrent first use must not corrupt cache accounting or mutate entries.
        with self._cache_lock:
            try:
                return self._inspect_locked(relative, expected_sha256)
            except OSError as exc:
                raise KnowledgeAccessError('source_read_failed') from exc

    def _inspect_locked(self, relative, expected_sha256=None):
        path = self._safe_path(relative)
        if path.stat().st_size > self.policy.max_file_bytes:
            raise KnowledgeAccessError('source_file_limit')
        with path.open('rb') as source:
            raw = source.read(self.policy.max_file_bytes + 1)
        if len(raw) > self.policy.max_file_bytes:
            raise KnowledgeAccessError('source_file_limit')
        digest = hashlib.sha256(raw).hexdigest()
        # Do not parse a changed PDF merely to discover that its bytes were revoked.
        if expected_sha256 is not None and digest != expected_sha256:
            raise KnowledgeAccessError('source_hash_changed')
        cache_key = (path.suffix.lower(), digest)
        if cache_key in self._cache:
            pages, risks = self._cache.pop(cache_key)
            self._cache[cache_key] = (pages, risks)
        else:
            pages = self._parse_bytes(raw, path.suffix.lower())
            text = '\n'.join(text for text, _ in pages)
            risks = [name for name, pattern in self.policy.risk_rules if pattern.search(text)]
            if self.policy.reject_invisible_chars and any(
                unicodedata.category(ch) in ('Cc', 'Cf') and ch not in '\n\r\t'
                for ch in text
            ):
                risks.append('invisible_or_control_character')
            size = sum(len(text) for text, _ in pages)
            if size <= self.policy.cache_text_chars:
                while self._cache and (len(self._cache) >= self.policy.cache_entries or
                                       self._cache_chars + size > self.policy.cache_text_chars):
                    _, (old_pages, _) = self._cache.popitem(last=False)
                    self._cache_chars -= sum(len(text) for text, _ in old_pages)
                self._cache[cache_key] = (pages, risks)
                self._cache_chars += size
        return path, digest, pages, tuple(risks)

    def snapshot(self):
        ledger = self._read_ledger()
        authorized, blocked = {}, []
        for entry in ledger['sources']:
            reason = None
            if entry['status'] not in ALLOWED:
                reason = 'source_' + entry['status']
            else:
                try:
                    _, digest, _, risks = self._inspect(entry['path'], entry['sha256'])
                    if digest != entry['sha256']:
                        reason = 'source_hash_changed'
                    elif risks and not entry['allow_risk']:
                        reason = 'source_risk:' + ','.join(risks)
                    else:
                        authorized[entry['source_id']] = dict(entry, risk_flags=list(risks))
                except KnowledgeAccessError as exc:
                    reason = exc.code
                except OSError:
                    reason = 'source_read_failed'
            if reason:
                blocked.append({'path': entry['path'], 'source_id': entry['source_id'], 'reason': reason})
        known = {entry['path'].casefold() for entry in ledger['sources']}
        for relative in self._discover():
            if relative.casefold() not in known:
                try:
                    source_id = stable_source_id(relative)
                    reason = 'new_source'
                except KnowledgeAccessError:
                    source_id, reason = None, 'invalid_source_path'
                blocked.append({'path': relative, 'source_id': source_id, 'reason': reason})
        stamp = hashlib.sha256(json.dumps(
            {'ledger': ledger, 'authorized': authorized, 'blocked': blocked},
            ensure_ascii=False, sort_keys=True,
        ).encode('utf-8')).hexdigest()
        return CatalogSnapshot(authorized, blocked, stamp)

    def load_source(self, entry):
        current = self.snapshot().authorized.get(entry.get('source_id'))
        if current is None or any(current.get(key) != entry.get(key) for key in
                                  ('path', 'version', 'sha256', 'status', 'allow_risk', 'review_note')):
            raise KnowledgeAccessError('source_not_currently_authorized')
        path, digest, pages, risks = self._inspect(current['path'], current['sha256'])
        if digest != current['sha256'] or (risks and not current['allow_risk']):
            raise KnowledgeAccessError('source_changed_during_load')
        documents = []
        for text, page in pages:
            metadata = {'source': str(path), 'source_id': current['source_id'],
                        'source_version': current['version'], 'source_sha256': digest}
            if page is not None:
                metadata['page'] = page
            documents.append(Document(page_content=text, metadata=metadata))
        # A changed ledger must not authorize a newly parsed snapshot implicitly.
        latest = self.snapshot().authorized.get(current['source_id'])
        if latest is None or any(latest.get(key) != current.get(key) for key in
                                 ('path', 'version', 'sha256', 'status', 'allow_risk', 'review_note')):
            raise KnowledgeAccessError('source_changed_during_load')
        return documents

    def document_allowed(self, doc, snapshot):
        metadata = doc.metadata
        entry = snapshot.authorized.get(metadata.get('source_id'))
        if entry is None or type(metadata.get('source_version')) is not int or \
                metadata.get('source_version') != entry['version'] or \
                metadata.get('source_sha256') != entry['sha256']:
            return False
        if metadata.get('chunk_sha256') != chunk_sha256(doc.page_content):
            return False
        try:
            expected = str(self.data_root / entry['path']).casefold()
            actual = str(Path(metadata.get('source', '')).absolute()).casefold()
            return actual == expected
        except (TypeError, ValueError, OSError):
            return False

    def validate_documents(self, docs):
        snapshot = self.snapshot()
        for doc in docs:
            if not self.document_allowed(doc, snapshot):
                raise KnowledgeAccessError('retrieved_document_not_authorized')

    @contextmanager
    def _mutation_lock(self):
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.ledger_path.with_name(self.ledger_path.name + '.lock')
        deadline, descriptor = time.monotonic() + 5, None
        try:
            while descriptor is None:
                try:
                    descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                except FileExistsError:
                    if time.monotonic() >= deadline:
                        raise KnowledgeAccessError('ledger_mutation_locked')
                    time.sleep(.02)
            os.write(descriptor, str(os.getpid()).encode('ascii'))
            yield
        finally:
            if descriptor is not None:
                os.close(descriptor)
                lock_path.unlink(missing_ok=True)

    def _write_ledger(self, ledger):
        name = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.ledger_path.parent,
                                             prefix='.knowledge-', suffix='.tmp', delete=False) as handle:
                name = handle.name
                json.dump(ledger, handle, ensure_ascii=False, indent=2)
                handle.write('\n')
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(name, self.ledger_path)
        finally:
            if name and Path(name).exists():
                Path(name).unlink()

    @staticmethod
    def _reason(reason):
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 2_000:
            raise KnowledgeAccessError('review_reason_required')
        return reason.strip()

    def approve(self, relative_path, *, status='approved', reason, allow_risk=False,
                expected_sha256=None):
        relative = _relative_path(relative_path)
        reason = self._reason(reason)
        if status not in ALLOWED or type(allow_risk) is not bool:
            raise KnowledgeAccessError('invalid_approval')
        with self._mutation_lock():
            ledger = self._read_ledger()
            _, digest, _, risks = self._inspect(relative, expected_sha256)
            if expected_sha256 is not None and digest != expected_sha256:
                raise KnowledgeAccessError('approval_hash_mismatch')
            if risks and not allow_risk:
                raise KnowledgeAccessError('risk_review_required:' + ','.join(risks))
            source_id = stable_source_id(relative)
            previous = next((e for e in ledger['sources'] if e['source_id'] == source_id), None)
            version = previous['version'] + int(previous['sha256'] != digest) if previous else 1
            entry = {'path': relative, 'source_id': source_id, 'version': version,
                     'sha256': digest, 'status': status, 'allow_risk': allow_risk,
                     'review_note': reason}
            ledger['sources'] = [e for e in ledger['sources'] if e['source_id'] != source_id] + [entry]
            if len(ledger['sources']) > self.policy.max_sources:
                raise KnowledgeAccessError('source_count_limit')
            # Hash/parse used the same bytes; confirm the on-disk version before commit.
            if self._inspect(relative)[1] != digest:
                raise KnowledgeAccessError('source_changed_during_approval')
            self._write_ledger(ledger)
            return dict(entry)

    def quarantine(self, relative_path, *, reason):
        relative = _relative_path(relative_path)
        reason = self._reason(reason)
        with self._mutation_lock():
            ledger = self._read_ledger()
            source_id = stable_source_id(relative)
            previous = next((e for e in ledger['sources'] if e['source_id'] == source_id), None)
            try:
                digest = self._inspect(relative)[1]
            except (KnowledgeAccessError, OSError):
                digest = previous['sha256'] if previous else '0' * 64
            version = previous['version'] + int(previous['sha256'] != digest) if previous else 1
            entry = {'path': relative, 'source_id': source_id, 'version': version,
                     'sha256': digest, 'status': 'quarantined', 'allow_risk': False,
                     'review_note': reason}
            ledger['sources'] = [e for e in ledger['sources'] if e['source_id'] != source_id] + [entry]
            if len(ledger['sources']) > self.policy.max_sources:
                raise KnowledgeAccessError('source_count_limit')
            self._write_ledger(ledger)
            return dict(entry)

    def revoke(self, source_id, *, reason):
        reason = self._reason(reason)
        with self._mutation_lock():
            ledger = self._read_ledger()
            entry = next((e for e in ledger['sources'] if e['source_id'] == source_id), None)
            if entry is None:
                raise KnowledgeAccessError('unknown_source_id')
            entry.update(status='revoked', allow_risk=False, review_note=reason)
            self._write_ledger(ledger)
            return dict(entry)

    def scan(self):
        """Administrator operation: quarantine new/changed sources, never approve."""
        with self._mutation_lock():
            return self._scan_locked()

    def _discover(self):
        """Discover candidate names without following links or parsing their data."""
        paths = []
        try:
            for directory, subdirectories, files in os.walk(self.data_root, followlinks=False):
                folder = Path(directory)
                subdirectories[:] = [name for name in subdirectories
                                     if not (folder / name).is_symlink()
                                     and not getattr(folder / name, 'is_junction', lambda: False)()]
                paths.extend((folder / name).relative_to(self.data_root).as_posix()
                             for name in files if Path(name).suffix.lower() in ('.txt', '.pdf'))
                if len(paths) > self.policy.max_sources:
                    raise KnowledgeAccessError('source_count_limit')
        except OSError as exc:
            raise KnowledgeAccessError('source_discovery_failed') from exc
        return sorted(paths)

    def _scan_locked(self):
        ledger = self._read_ledger()
        previous = {e['path'].casefold(): e for e in ledger['sources']}
        paths, report, changed = self._discover(), [], False
        for relative in paths:
            try:
                source_id = stable_source_id(relative)
            except KnowledgeAccessError:
                report.append({'path': relative, 'status': 'quarantined', 'reason': 'invalid_source_path'})
                continue
            entry = previous.get(relative.casefold())
            try:
                _, digest, _, risks = self._inspect(relative)
                reason = 'new_source' if entry is None else (
                    'source_hash_changed' if entry['sha256'] != digest else None)
                if risks and entry and entry['status'] in ALLOWED and not entry['allow_risk']:
                    reason = 'source_risk:' + ','.join(risks)
            except (KnowledgeAccessError, OSError) as exc:
                reason = exc.code if isinstance(exc, KnowledgeAccessError) else 'source_read_failed'
                digest, risks = None, ()
            if reason and (entry is None or entry['status'] != 'revoked'):
                new_digest = digest if digest else (entry['sha256'] if entry else '0' * 64)
                version = entry['version'] + int(entry['sha256'] != new_digest) if entry else 1
                entry = {'path': relative, 'source_id': source_id, 'version': version,
                         'sha256': new_digest, 'status': 'quarantined', 'allow_risk': False,
                         'review_note': reason}
                ledger['sources'] = [e for e in ledger['sources'] if e['source_id'] != source_id] + [entry]
                changed = True
            report.append({'path': relative, 'source_id': source_id,
                           'status': entry['status'] if entry else 'quarantined',
                           'sha256': digest, 'risk_flags': list(risks), 'reason': reason})
        for entry in ledger['sources']:
            if entry['path'] not in paths:
                report.append({'path': entry['path'], 'source_id': entry['source_id'],
                               'status': entry['status'], 'reason': 'missing_source'})
        if changed:
            if len(ledger['sources']) > self.policy.max_sources:
                raise KnowledgeAccessError('source_count_limit')
            self._write_ledger(ledger)
        return report
