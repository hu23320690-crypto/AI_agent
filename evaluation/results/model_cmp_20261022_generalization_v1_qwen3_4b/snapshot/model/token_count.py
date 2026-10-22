"""Offline text counting for pinned local models from an exported Ollama cache.

The cache is application-controlled input. It pins model digest and template
hash, and checks the tokenizer serialization hash; it is not a trust boundary
against someone who can rewrite application files. A mutable Ollama tag must be
verified explicitly at startup/doctor with verify_local_cache, not on each model
request. Missing/unknown/invalid caches return None for UTF-8 fallback.

Qwen2 splitting: official HF/Qwen implementation, Apache-2.0:
https://github.com/huggingface/transformers/blob/main/src/transformers/models/qwen2/tokenization_qwen2.py
GGUF qwen2 and gemma4 behavior:
https://github.com/ggml-org/llama.cpp/blob/master/src/llama-vocab.cpp
gemma4 counts were checked against Ollama prompt_eval_count with
scripts/check_tokenizer_counts.py; rerun it after re-exporting a cache.
This counts text; chat/tool-template framing still needs separate allowances.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.parse import urlparse
from uuid import uuid4


MODEL_NAME = 'qwen3:4b'
# Paths are relative to config/. Qwen keeps its original names so existing
# pins, doctor checks and frozen evidence remain valid.
PINNED_MODELS = {
    'qwen3:4b': {'cache': 'tokenizers/qwen3_4b.json.gz', 'manifest': 'context_tokenizer.json',
                 'method': 'local_qwen2_bpe'},
    'gemma4:12b': {'cache': 'tokenizers/gemma4_12b.json.gz', 'manifest': 'context_tokenizer_gemma4_12b.json',
                   'method': 'local_gemma4_bpe'},
}
CACHE_VERSION = 1
MAX_CACHE_BYTES = 12 * 1024 * 1024
MAX_EXPANDED_BYTES = 24 * 1024 * 1024
MAX_TEXT_BYTES = 2 * 1024 * 1024
_HEX = re.compile(r'^[0-9a-f]{64}$')
_PATTERN = r"(?i:'s|'t|'re|'ve|'m|'ll|'d)|[^\r\n\p{L}\p{N}]?\p{L}+|\p{N}| ?[^\s\p{L}\p{N}]+[\r\n]*|\s*[\r\n]+|\s+(?!\S)|\s+"


def _sha(value):
    return hashlib.sha256(value).hexdigest()


def default_cache_path(model_name=MODEL_NAME):
    return Path(__file__).resolve().parents[1] / 'config' / PINNED_MODELS[model_name]['cache']


def default_manifest_path(model_name=MODEL_NAME):
    return Path(__file__).resolve().parents[1] / 'config' / PINNED_MODELS[model_name]['manifest']


@dataclass(frozen=True)
class LocalTextCounter:
    model_name: str
    model_digest: str
    template_sha256: str
    tokenizer_sha256: str
    tokenizer: object
    method: str = 'local_qwen2_bpe'

    def count(self, text):
        if not isinstance(text, str):
            raise ValueError('tokenizer text must be a string')
        byte_count = len(text.encode('utf-8'))
        # Do not feed an arbitrarily large or pathological input into BPE.
        if byte_count > MAX_TEXT_BYTES:
            return byte_count
        try:
            return len(self.tokenizer.encode(text, add_special_tokens=False).ids)
        except Exception:
            # Admission still has a safe conservative fallback.
            return byte_count


QwenTextCounter = LocalTextCounter


def _checked_vocabulary(info, max_merges):
    """Validate GGUF tokens, types and merge list shape shared by both builders."""
    values = info.get('tokenizer.ggml.tokens')
    kinds = info.get('tokenizer.ggml.token_type')
    raw_merges = info.get('tokenizer.ggml.merges')
    if (not isinstance(values, list) or not 256 <= len(values) <= 300000
            or not all(isinstance(value, str) for value in values)
            or len(set(values)) != len(values)):
        raise ValueError('unsupported tokenizer vocabulary')
    if (not isinstance(kinds, list) or len(kinds) != len(values)
            or any(isinstance(kind, bool) or not isinstance(kind, int)
                   or kind not in (1, 2, 3, 4, 5, 6) for kind in kinds)):
        raise ValueError('unsupported tokenizer token types')
    if not isinstance(raw_merges, list) or len(raw_merges) > max_merges:
        raise ValueError('unsupported tokenizer merges')
    return values, kinds, raw_merges, {text: index for index, text in enumerate(values)}


def _checked_merges(raw_merges, vocab):
    merges = []
    for value in raw_merges:
        if not isinstance(value, str):
            raise ValueError('tokenizer merge must be a string')
        parts = value.split(' ')
        if len(parts) != 2 or any(part not in vocab for part in parts) or ''.join(parts) not in vocab:
            raise ValueError('invalid tokenizer merge')
        merges.append(tuple(parts))
    return merges


def build_qwen_tokenizer(info):
    """Reconstruct local GGUF Qwen2 BPE; no downloads or generation calls."""
    from tokenizers import AddedToken, Regex, Tokenizer, decoders, pre_tokenizers
    from tokenizers.models import BPE
    if (info.get('tokenizer.ggml.model') != 'gpt2'
            or info.get('tokenizer.ggml.pre') != 'qwen2'
            or info.get('tokenizer.ggml.add_bos_token', False) is not False):
        raise ValueError('unsupported GGUF tokenizer model/pre/BOS configuration')
    values, kinds, raw_merges, vocab = _checked_vocabulary(info, 300000)
    if not set(pre_tokenizers.ByteLevel.alphabet()).issubset(vocab):
        raise ValueError('tokenizer vocabulary must cover all 256 byte symbols')
    merges = _checked_merges(raw_merges, vocab)
    tokenizer = Tokenizer(BPE(vocab=vocab, merges=merges, unk_token=None, byte_fallback=False))
    tokenizer.pre_tokenizer = pre_tokenizers.Sequence([
        pre_tokenizers.Split(Regex(_PATTERN), behavior='isolated', invert=False),
        pre_tokenizers.ByteLevel(add_prefix_space=False, use_regex=False),
    ])
    tokenizer.decoder = decoders.ByteLevel()
    # GGUF CONTROL and USER_DEFINED tokens are both kept as atomic literals.
    # No NFC normalizer: the local GGUF qwen2 tokenizer does not declare one.
    tokenizer.add_special_tokens([AddedToken(text, special=True, normalized=False)
                                  for text, kind in zip(values, kinds) if kind in (3, 4)])
    return tokenizer


def build_gemma4_tokenizer(info):
    """Reconstruct local GGUF gemma4 BPE; no downloads or generation calls.

    Spaces become U+2581 with no prefix and no pre-split; bytes outside the
    vocabulary use the <0xXX> fallback tokens. BOS is template framing, not text.
    """
    from tokenizers import AddedToken, Tokenizer, decoders, normalizers
    from tokenizers.models import BPE
    if (info.get('tokenizer.ggml.model') != 'gemma4'
            or info.get('tokenizer.ggml.add_space_prefix', False) is not False):
        raise ValueError('unsupported GGUF tokenizer model/space-prefix configuration')
    # gemma4 ships about 515k merges, beyond the Qwen bound.
    values, kinds, raw_merges, vocab = _checked_vocabulary(info, 600000)
    if '<unk>' not in vocab or any(f'<0x{byte:02X}>' not in vocab for byte in range(256)):
        raise ValueError('tokenizer vocabulary must include <unk> and all 256 byte fallback tokens')
    merges = _checked_merges(raw_merges, vocab)
    tokenizer = Tokenizer(BPE(vocab=vocab, merges=merges, unk_token='<unk>', byte_fallback=True, fuse_unk=True))
    tokenizer.normalizer = normalizers.Replace(' ', '▁')
    tokenizer.decoder = decoders.Sequence([decoders.Replace('▁', ' '), decoders.ByteFallback(), decoders.Fuse()])
    tokenizer.add_special_tokens([AddedToken(text, special=True, normalized=False)
                                  for text, kind in zip(values, kinds) if kind in (3, 4)])
    return tokenizer


_BUILDERS = {'qwen3:4b': build_qwen_tokenizer, 'gemma4:12b': build_gemma4_tokenizer}


def write_counter_cache(path, info, *, model_digest, template, manifest_path=None, model_name=MODEL_NAME):
    """Explicit administrator export; path is trusted, not from model arguments."""
    if not isinstance(model_digest, str) or not _HEX.fullmatch(model_digest):
        raise ValueError('a full model SHA-256 digest is required')
    if not isinstance(template, str) or not template:
        raise ValueError('a nonempty local chat template is required')
    tokenizer = _BUILDERS[model_name](info)
    tokenizer_json = tokenizer.to_str()
    payload = {'version': CACHE_VERSION, 'model_name': model_name, 'model_digest': model_digest,
               'template_sha256': _sha(template.encode('utf-8')),
               'tokenizer_sha256': _sha(tokenizer_json.encode('utf-8')),
               'tokenizer_json': tokenizer_json}
    encoded = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    if len(encoded) > MAX_EXPANDED_BYTES:
        raise ValueError('tokenizer cache is too large')
    compressed = gzip.compress(encoded, compresslevel=6, mtime=0)
    if len(compressed) > MAX_CACHE_BYTES:
        raise ValueError('compressed tokenizer cache is too large')
    path = Path(path)
    manifest = {key: value for key, value in payload.items() if key != 'tokenizer_json'}
    if manifest_path is not None:
        manifest_path = Path(manifest_path)
        # A manifest never permits traversal outside the controlled config dir.
        relative_cache = path.resolve().relative_to(manifest_path.parent.resolve())
        manifest.update(cache_file=relative_cache.as_posix(), cache_sha256=_sha(compressed))
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid4().hex + '.tmp')
    try:
        temporary.write_bytes(compressed)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    if manifest_path is not None:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = manifest_path.with_name(manifest_path.name + '.' + uuid4().hex + '.tmp')
        try:
            temporary.write_text(json.dumps(manifest, ensure_ascii=True, indent=2) + '\n', encoding='utf-8')
            temporary.replace(manifest_path)
        finally:
            temporary.unlink(missing_ok=True)
    return manifest


@lru_cache(maxsize=4)
def _load_cache(path, mtime_ns, compressed_size, expected_cache_sha256=None, model_name=MODEL_NAME):
    from tokenizers import Tokenizer
    if not 0 < compressed_size <= MAX_CACHE_BYTES:
        raise ValueError('invalid tokenizer cache size')
    if expected_cache_sha256 is not None and _sha(Path(path).read_bytes()) != expected_cache_sha256:
        raise ValueError('compressed tokenizer cache hash mismatch')
    with gzip.open(path, 'rb') as handle:
        content = handle.read(MAX_EXPANDED_BYTES + 1)
    if len(content) > MAX_EXPANDED_BYTES:
        raise ValueError('expanded tokenizer cache is too large')
    payload = json.loads(content)
    if (not isinstance(payload, dict) or type(payload.get('version')) is not int or payload.get('version') != CACHE_VERSION
            or model_name not in PINNED_MODELS or payload.get('model_name') != model_name):
        raise ValueError('unsupported tokenizer cache version/model')
    for key in ('model_digest', 'template_sha256', 'tokenizer_sha256'):
        if not isinstance(payload.get(key), str) or not _HEX.fullmatch(payload[key]):
            raise ValueError('invalid tokenizer cache identity')
    serialized = payload.get('tokenizer_json')
    if not isinstance(serialized, str) or _sha(serialized.encode('utf-8')) != payload['tokenizer_sha256']:
        raise ValueError('tokenizer cache hash mismatch')
    tokenizer = Tokenizer.from_str(serialized)
    return LocalTextCounter(model_name, payload['model_digest'], payload['template_sha256'],
                            payload['tokenizer_sha256'], tokenizer, PINNED_MODELS[model_name]['method'])


@lru_cache(maxsize=4)
def _load_manifest(path, mtime_ns, size, model_name=MODEL_NAME):
    if not 0 < size <= 4096:
        raise ValueError('invalid tokenizer manifest size')
    values = json.loads(Path(path).read_text(encoding='utf-8'))
    if (not isinstance(values, dict) or type(values.get('version')) is not int
            or values.get('version') != CACHE_VERSION or values.get('model_name') != model_name):
        raise ValueError('unsupported tokenizer manifest version/model')
    for key in ('model_digest', 'template_sha256', 'tokenizer_sha256', 'cache_sha256'):
        if not isinstance(values.get(key), str) or not _HEX.fullmatch(values[key]):
            raise ValueError('invalid tokenizer manifest hash')
    relative = values.get('cache_file')
    if not isinstance(relative, str):
        raise ValueError('invalid tokenizer cache path')
    relative = Path(relative)
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('tokenizer cache must remain within controlled config directory')
    parent = Path(path).resolve().parent
    cache_path = (parent / relative).resolve()
    cache_path.relative_to(parent)
    return values, cache_path


def _model_identity(model):
    seen = set()
    for _ in range(8):
        if model is None or id(model) in seen:
            break
        seen.add(id(model))
        name = getattr(model, 'model', None)
        if isinstance(name, str):
            host = getattr(model, 'base_url', None)
            if host is not None:
                parsed = urlparse(host)
                if (parsed.scheme not in ('http', 'https')
                        or parsed.hostname not in ('localhost', '127.0.0.1', '::1')
                        or parsed.username or parsed.password):
                    return None, None
            metadata = getattr(model, 'metadata', None)
            digest = metadata.get('tokenizer_model_digest') if isinstance(metadata, Mapping) else None
            return name, digest
        model = getattr(model, 'bound', None)
    return None, None


def get_text_counter(model, *, cache_path=None, expected_digest=None, manifest_path=None):
    """Read only cached controlled metadata of a pinned model; unknown inputs use fallback.

    Require model.metadata['tokenizer_model_digest'] or explicit expected_digest.
    Factory sets the pin only after explicit startup verification. A matching
    model name alone is insufficient. No live validation happens per request.
    """
    try:
        name, metadata_digest = _model_identity(model)
        if name not in PINNED_MODELS:
            return None
        expected_digest = expected_digest if expected_digest is not None else metadata_digest
        if not isinstance(expected_digest, str) or not _HEX.fullmatch(expected_digest):
            return None
        manifest = None
        if cache_path is None:
            manifest_path = Path(manifest_path) if manifest_path is not None else default_manifest_path(name)
            manifest_stat = manifest_path.stat()
            manifest, path = _load_manifest(str(manifest_path.resolve()), manifest_stat.st_mtime_ns,
                                            manifest_stat.st_size, name)
        else:
            path = Path(cache_path)
        stat = path.stat()
        counter = _load_cache(str(path.resolve()), stat.st_mtime_ns, stat.st_size,
                              manifest['cache_sha256'] if manifest is not None else None, name)
        if expected_digest is not None and counter.model_digest != expected_digest:
            return None
        if manifest is not None and any(getattr(counter, key) != manifest[key]
                                        for key in ('model_digest', 'template_sha256', 'tokenizer_sha256')):
            return None
        return counter
    except Exception:
        return None


def load_cache_identity(path=None, *, manifest_path=None, model_name=MODEL_NAME):
    """Read validated local identity for explicit administrator verification.

    This does not enable a model counter. Factory must verify this identity
    against local Ollama before assigning a request-time model metadata pin.
    """
    try:
        if path is None:
            manifest_path = Path(manifest_path) if manifest_path is not None else default_manifest_path(model_name)
            stat = manifest_path.stat()
            manifest, path = _load_manifest(str(manifest_path.resolve()), stat.st_mtime_ns, stat.st_size, model_name)
            expected_cache_hash = manifest['cache_sha256']
        else:
            path = Path(path)
            manifest = None
            expected_cache_hash = None
        stat = path.stat()
        counter = _load_cache(str(path.resolve()), stat.st_mtime_ns, stat.st_size, expected_cache_hash, model_name)
        identity = {key: getattr(counter, key) for key in
                    ('model_name', 'model_digest', 'template_sha256', 'tokenizer_sha256')}
        if manifest is not None and any(identity[key] != manifest[key] for key in identity):
            return None
        return identity
    except Exception:
        return None


def _local_client(host, timeout):
    import httpx
    def origin(value):
        parsed = urlparse(value)
        if (parsed.scheme not in ('http', 'https') or not parsed.hostname
                or parsed.username is not None or parsed.password is not None
                or parsed.path not in ('', '/') or parsed.query or parsed.fragment):
            raise ValueError('tokenizer endpoint must be an HTTP origin without credentials')
        return parsed.scheme, parsed.hostname, parsed.port or (443 if parsed.scheme == 'https' else 80)

    endpoint = origin(host)
    if endpoint[1] not in ('localhost', '127.0.0.1', '::1'):
        allowed = os.environ.get('TOKENIZER_ALLOWED_ORIGIN', '')
        if not allowed or endpoint != origin(allowed):
            raise ValueError('tokenizer export/verification requires a local or explicitly trusted Ollama origin')
    return httpx.Client(base_url=host, timeout=timeout, trust_env=False)


def _digest(client, model_name=MODEL_NAME):
    response = client.get('/api/tags')
    response.raise_for_status()
    for model in response.json().get('models', []):
        if model.get('name') == model_name or model.get('model') == model_name:
            digest = model.get('digest')
            if isinstance(digest, str) and _HEX.fullmatch(digest):
                return digest
    raise ValueError('configured local model digest is unavailable')


def export_local_cache(path=None, *, manifest_path=None, host='http://127.0.0.1:11434', timeout=20,
                       model_name=MODEL_NAME):
    """Explicit read-only Ollama calls + local cache export; never generate."""
    with _local_client(host, timeout) as client:
        before = _digest(client, model_name)
        response = client.post('/api/show', json={'model': model_name, 'verbose': True})
        response.raise_for_status()
        payload = response.json()
        if _digest(client, model_name) != before:
            raise ValueError('local model changed during tokenizer export')
    path = Path(path) if path is not None else default_cache_path(model_name)
    manifest_path = (Path(manifest_path) if manifest_path is not None
                     else path.parent.parent / PINNED_MODELS[model_name]['manifest'])
    return write_counter_cache(path, payload['model_info'], model_digest=before,
                               template=payload['template'], manifest_path=manifest_path,
                               model_name=model_name)


def verify_local_cache(path=None, *, manifest_path=None, host='http://127.0.0.1:11434', timeout=10,
                       model_name=MODEL_NAME):
    """Explicit startup/doctor validation; failure must keep the UTF-8 fallback."""
    from types import SimpleNamespace
    identity = load_cache_identity(path, manifest_path=manifest_path, model_name=model_name)
    if identity is None:
        return False
    counter = get_text_counter(SimpleNamespace(model=model_name, base_url=host),
                               expected_digest=identity['model_digest'], cache_path=path,
                               manifest_path=manifest_path)
    if counter is None:
        return False
    with _local_client(host, timeout) as client:
        before = _digest(client, model_name)
        response = client.post('/api/show', json={'model': model_name, 'verbose': False})
        response.raise_for_status()
        template = response.json().get('template', '')
        return (before == identity['model_digest'] and before == _digest(client, model_name)
                and _sha(template.encode('utf-8')) == identity['template_sha256'])


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Export/verify a pinned local tokenizer cache; no generation/downloads.')
    parser.add_argument('action', choices=('export', 'verify'))
    parser.add_argument('--model', choices=sorted(PINNED_MODELS), default=MODEL_NAME)
    parser.add_argument('--path', type=Path, default=None)
    parser.add_argument('--manifest', type=Path, default=None)
    args = parser.parse_args()
    host = os.environ.get('OLLAMA_HOST', 'http://127.0.0.1:11434')
    result = (export_local_cache(args.path, manifest_path=args.manifest, host=host, model_name=args.model)
              if args.action == 'export'
              else {'verified': verify_local_cache(args.path, manifest_path=args.manifest, host=host,
                                                   model_name=args.model)})
    print(json.dumps(result, ensure_ascii=True))
