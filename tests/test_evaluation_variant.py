import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.prepare_evaluation_variant import prepare_variant, relative_path


class HistoricalVariantTests(unittest.TestCase):
    def test_exact_snapshot_and_sources_without_current_business_or_indexes(self):
        with TemporaryDirectory() as directory:
            root = Path(directory) / 'project'
            root.mkdir()
            snapshot = root / 'evaluation/results/optimized_v1/snapshot'
            (snapshot / 'agent').mkdir(parents=True)
            (snapshot / 'agent/example.py').write_bytes(b'historical business')
            (root / 'agent').mkdir()
            (root / 'agent/current_only.py').write_bytes(b'current business')
            (root / 'rag/chroma_db').mkdir(parents=True)
            (root / 'rag/chroma_db/old-index').write_bytes(b'must not be copied')
            (root / 'data').mkdir()
            (root / 'data/source.txt').write_bytes(b'frozen source')
            hash_of = lambda value: hashlib.sha256(value).hexdigest()
            manifest = {'code_sha256': {'agent\\example.py': hash_of(b'historical business')},
                        'source_sha256': {'data\\source.txt': hash_of(b'frozen source')}}
            (snapshot.parent / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
            cases = b'{"id":"K1","kind":"knowledge"}\n'
            scoring = b'frozen scoring rules'
            for rel in ('evaluation', 'evaluation/holdout_v1', 'evaluation/holdout_v2'):
                folder = root / rel
                folder.mkdir(exist_ok=True)
                (folder / 'cases.jsonl').write_bytes(cases)
                (folder / 'dataset_manifest.json').write_text(json.dumps({
                    'dataset_sha256': hash_of(cases), 'files': manifest['source_sha256'],
                    **({'scoring_sha256': hash_of(scoring)} if rel.endswith('holdout_v2') else {})}), encoding='utf-8')
            (root / 'evaluation/holdout_v2/SCORING.md').write_bytes(scoring)
            unified_rules = b'frozen unified semantic review rules'
            (root / 'evaluation/SEMANTIC_REVIEW_V2.md').write_bytes(unified_rules)
            (root / 'evaluation/run.py').write_bytes(b'current observer')
            target = root.parent / 'isolated'
            result = prepare_variant(root, target, 'evaluation/holdout_v2/cases.jsonl')
            self.assertEqual((target / 'agent/example.py').read_bytes(), b'historical business')
            self.assertEqual((target / 'evaluation/run.py').read_bytes(), b'current observer')
            self.assertEqual((target / 'evaluation/holdout_v2/SCORING.md').read_bytes(), scoring)
            self.assertEqual((target / 'evaluation/SEMANTIC_REVIEW_V2.md').read_bytes(), unified_rules)
            self.assertFalse((target / 'agent/current_only.py').exists())
            self.assertFalse((target / 'rag/chroma_db').exists())
            self.assertFalse(result['index_copied'])
            with self.assertRaisesRegex(ValueError, 'already exists'):
                prepare_variant(root, target, 'evaluation/holdout_v2/cases.jsonl')
            (root / 'evaluation/holdout_v2/SCORING.md').write_bytes(b'changed scoring')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                prepare_variant(root, root.parent / 'invalid-scoring', 'evaluation/holdout_v2/cases.jsonl')
            self.assertFalse((root.parent / 'invalid-scoring').exists())
            (root / 'evaluation/holdout_v2/SCORING.md').write_bytes(scoring)
            (root / 'data/source.txt').write_bytes(b'changed source')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                prepare_variant(root, root.parent / 'invalid', 'evaluation/holdout_v2/cases.jsonl')
            self.assertFalse((root.parent / 'invalid').exists())

    def test_manifest_cannot_escape_the_experiment_directory(self):
        for path in ('../secret', '/secret', 'C:\\secret', 'data/../../secret'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                relative_path(path)
        self.assertEqual(relative_path('data\\source.txt'), Path('data/source.txt'))
