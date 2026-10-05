"""Offline cache/identity/BPE tests using a tiny synthetic byte vocabulary."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import gzip
import json
import unittest
from unittest.mock import patch

from tokenizers.pre_tokenizers import ByteLevel
from model.token_count import (
    build_qwen_tokenizer, write_counter_cache, get_text_counter, QwenTextCounter,
    _local_client, load_cache_identity,
)


def metadata():
    vocab = sorted(ByteLevel.alphabet()) + ['ab', '<think>', '<|im_start|>']
    return {'tokenizer.ggml.model': 'gpt2', 'tokenizer.ggml.pre': 'qwen2',
            'tokenizer.ggml.add_bos_token': False, 'tokenizer.ggml.tokens': vocab,
            'tokenizer.ggml.token_type': [1] * 257 + [4, 3], 'tokenizer.ggml.merges': ['a b']}


class OfflineTokenizerTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'qwen.json.gz'
        self.model = SimpleNamespace(model='qwen3:4b', base_url='http://127.0.0.1:11434',
                                     metadata={'tokenizer_model_digest': 'a' * 64})
        write_counter_cache(self.path, metadata(), model_digest='a' * 64, template='local template')

    def test_bpe_bytelevel_split_and_user_defined_literals(self):
        tokenizer = build_qwen_tokenizer(metadata())
        self.assertEqual(len(tokenizer.encode('ab', add_special_tokens=False).ids), 1)
        self.assertEqual(len(tokenizer.encode('a b', add_special_tokens=False).ids), 3)
        self.assertEqual(len(tokenizer.encode('<think>', add_special_tokens=False).ids), 1)
        self.assertEqual(len(tokenizer.encode('<|im_start|>', add_special_tokens=False).ids), 1)
        self.assertEqual(tokenizer.decode(tokenizer.encode('主刷 123\n').ids), '主刷 123\n')

    def test_cache_loaded_once_without_any_network_or_generation(self):
        with patch('httpx.Client', side_effect=AssertionError('offline counting must not access network')):
            first = get_text_counter(self.model, cache_path=self.path)
            second = get_text_counter(self.model, cache_path=self.path)
            self.assertIs(first, second)
            self.assertEqual(first.count('ab'), 1)
            self.assertEqual(first.model_digest, 'a' * 64)

    def test_unknown_model_remote_host_and_wrong_digest_use_fallback(self):
        for model in (None, SimpleNamespace(model='other'),
                      SimpleNamespace(model='qwen3:4b', base_url='http://127.0.0.1:11434'),
                      SimpleNamespace(model='qwen3:4b', base_url='https://example.com'),
                      SimpleNamespace(model='qwen3:4b', base_url='http://user:pass@localhost')):
            self.assertIsNone(get_text_counter(model, cache_path=self.path))
        self.assertIsNone(get_text_counter(self.model, cache_path=self.path, expected_digest='b' * 64))
        self.assertIsNotNone(get_text_counter(self.model, cache_path=self.path, expected_digest='a' * 64))

    def test_bound_model_and_metadata_digest_pin(self):
        model = SimpleNamespace(model='qwen3:4b', metadata={'tokenizer_model_digest': 'a' * 64})
        self.assertIsNotNone(get_text_counter(SimpleNamespace(bound=model), cache_path=self.path))
        model.metadata['tokenizer_model_digest'] = 'b' * 64
        self.assertIsNone(get_text_counter(model, cache_path=self.path))

    def test_administrator_identity_read_does_not_enable_unpinned_model(self):
        identity = load_cache_identity(self.path)
        self.assertEqual(identity['model_digest'], 'a' * 64)
        unpinned = SimpleNamespace(model='qwen3:4b', base_url='http://127.0.0.1:11434')
        self.assertIsNone(get_text_counter(unpinned, cache_path=self.path))
        self.assertIsNotNone(get_text_counter(unpinned, cache_path=self.path,
                                             expected_digest=identity['model_digest']))

    def test_missing_invalid_changed_hash_or_version_cache_use_fallback(self):
        self.assertIsNone(get_text_counter(self.model, cache_path=self.path.with_name('missing.gz')))
        original = json.loads(gzip.decompress(self.path.read_bytes()))
        cases = [b'not gzip', gzip.compress(b'not json')]
        for field, value in (('version', 999), ('model_name', 'other'),
                             ('tokenizer_sha256', 'b' * 64), ('model_digest', 'invalid')):
            payload = {**original, field: value}
            cases.append(gzip.compress(json.dumps(payload).encode()))
        for index, content in enumerate(cases):
            path = self.path.with_name(f'bad-{index}.gz')
            path.write_bytes(content)
            self.assertIsNone(get_text_counter(self.model, cache_path=path))

    def test_reject_incomplete_and_unsupported_metadata(self):
        for field, value in (('tokenizer.ggml.pre', 'other'), ('tokenizer.ggml.model', 'llama'),
                             ('tokenizer.ggml.add_bos_token', True), ('tokenizer.ggml.tokens', []),
                             ('tokenizer.ggml.merges', ['a missing']), ('tokenizer.ggml.token_type', [1])):
            with self.subTest(field=field), self.assertRaises(ValueError):
                build_qwen_tokenizer({**metadata(), field: value})

    def test_non_string_and_oversized_text_fail_or_fall_back(self):
        counter = get_text_counter(self.model, cache_path=self.path)
        with self.assertRaises(ValueError):
            counter.count(None)
        with patch('model.token_count.MAX_TEXT_BYTES', 2):
            self.assertEqual(counter.count('abab'), 4)

    def test_export_client_rejects_nonlocal_or_credential_hosts(self):
        for host in ('https://example.com', 'http://user:pass@localhost', 'file:///tmp'):
            with self.subTest(host=host), self.assertRaises(ValueError):
                _local_client(host, 10)

    def test_controlled_manifest_pins_hashes_and_relative_cache_location(self):
        manifest = Path(self.directory.name) / 'context_tokenizer.json'
        write_counter_cache(self.path, metadata(), model_digest='a' * 64,
                            template='local template', manifest_path=manifest)
        counter = get_text_counter(self.model, manifest_path=manifest)
        self.assertIsNotNone(counter)
        values = json.loads(manifest.read_text())
        self.assertEqual(values['cache_file'], self.path.name)
        values['template_sha256'] = 'b' * 64
        bad_manifest = manifest.with_name('changed.json')
        bad_manifest.write_text(json.dumps(values))
        self.assertIsNone(get_text_counter(self.model, manifest_path=bad_manifest))
        values['cache_file'] = '../outside.json.gz'
        bad_manifest = manifest.with_name('traversal.json')
        bad_manifest.write_text(json.dumps(values))
        self.assertIsNone(get_text_counter(self.model, manifest_path=bad_manifest))


if __name__ == '__main__':
    unittest.main()
