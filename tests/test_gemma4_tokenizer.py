"""Offline gemma4 BPE rebuild tests using a tiny synthetic vocabulary."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from model.token_count import (
    build_gemma4_tokenizer, write_counter_cache, get_text_counter, load_cache_identity,
)


def metadata():
    specials = ['<pad>', '<eos>', '<bos>', '<unk>']
    byte_tokens = [f'<0x{byte:02X}>' for byte in range(256)]
    pieces = ['a', 'b', 'ab', '▁', '▁a', '▁ab']
    controls = ['<|turn>', '<|"|>']
    tokens = specials + byte_tokens + pieces + controls
    kinds = [3] * 4 + [6] * 256 + [1] * len(pieces) + [3, 4]
    return {'tokenizer.ggml.model': 'gemma4', 'tokenizer.ggml.add_space_prefix': False,
            'tokenizer.ggml.add_bos_token': True, 'tokenizer.ggml.tokens': tokens,
            'tokenizer.ggml.token_type': kinds,
            # Rank order matters: '▁a' must merge before 'ab' for ' ab' to become one token.
            'tokenizer.ggml.merges': ['▁ a', '▁a b', 'a b']}


class Gemma4TokenizerTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'gemma.json.gz'
        write_counter_cache(self.path, metadata(), model_digest='c' * 64, template='t',
                            model_name='gemma4:12b')
        self.model = SimpleNamespace(model='gemma4:12b', metadata={'tokenizer_model_digest': 'c' * 64})

    def test_space_marker_merges_byte_fallback_and_control_literals(self):
        tokenizer = build_gemma4_tokenizer(metadata())
        count = lambda text: len(tokenizer.encode(text, add_special_tokens=False).ids)
        self.assertEqual(count('ab'), 1)
        self.assertEqual(count(' ab'), 1)
        self.assertEqual(count('ab ab'), 2)
        # Three UTF-8 bytes, no merges available.
        self.assertEqual(count('主'), 3)
        self.assertEqual(count('<|turn>'), 1)
        self.assertEqual(count('<|"|>'), 1)
        self.assertEqual(tokenizer.decode(tokenizer.encode('ab 主 ab').ids), 'ab 主 ab')

    def test_cache_is_bound_to_gemma_name_and_method(self):
        counter = get_text_counter(self.model, cache_path=self.path)
        self.assertEqual((counter.model_name, counter.method), ('gemma4:12b', 'local_gemma4_bpe'))
        self.assertEqual(counter.count(' ab'), 1)
        self.assertEqual(load_cache_identity(self.path, model_name='gemma4:12b')['model_digest'], 'c' * 64)
        # A Qwen pin cannot load a gemma cache, and the reverse identity read fails.
        qwen = SimpleNamespace(model='qwen3:4b', metadata={'tokenizer_model_digest': 'c' * 64})
        self.assertIsNone(get_text_counter(qwen, cache_path=self.path))
        self.assertIsNone(load_cache_identity(self.path))

    def test_reject_unsupported_metadata(self):
        missing_byte = metadata()
        missing_byte['tokenizer.ggml.tokens'] = list(missing_byte['tokenizer.ggml.tokens'])
        missing_byte['tokenizer.ggml.tokens'][4] = '<0xZZ>'
        for info in ({**metadata(), 'tokenizer.ggml.model': 'gpt2'},
                     {**metadata(), 'tokenizer.ggml.add_space_prefix': True},
                     {**metadata(), 'tokenizer.ggml.merges': ['a missing']},
                     {**metadata(), 'tokenizer.ggml.merges': ['a b'] * 600001},
                     missing_byte):
            with self.subTest(info=info.get('tokenizer.ggml.model')), self.assertRaises(ValueError):
                build_gemma4_tokenizer(info)


if __name__ == '__main__':
    unittest.main()
