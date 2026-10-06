"""Offline archive integrity checks; no models, services, or business imports."""
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts.seal_evaluation_run import seal_run


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def row_sha256(row):
    return sha256(json.dumps(row, ensure_ascii=False, sort_keys=True,
                             separators=(',', ':')).encode('utf-8'))


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows),
                    encoding='utf-8')


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def read_rows(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()
            if line.strip()]


class EvaluationSealTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.run = self.make_run('run')

    def make_run(self, name, variant=False):
        run = self.root / name
        run.mkdir()
        frozen = {'agent/example.py': b'frozen business\n',
                  'evaluation/run.py': b'frozen evaluator\n',
                  'data/source.txt': '冻结的证据来源\n'.encode('utf-8')}
        for relative, data in frozen.items():
            target = run / 'snapshot' / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        cases = [{'id': 'K1', 'kind': 'knowledge', 'query': '如何清理主刷？'},
                 {'id': 'A1', 'kind': 'agent', 'turns': [{'query': '本月报告'}]}]
        write_rows(run / 'cases.jsonl', cases)
        source_hashes = {'data/source.txt': sha256(frozen['data/source.txt'])}
        dataset = {'version': 'offline-fixture-1', 'case_count': len(cases),
                   'dataset_sha256': sha256((run / 'cases.jsonl').read_bytes()),
                   'files': source_hashes}
        write_json(run / 'snapshot/dataset_manifest.json', dataset)
        manifest = {'identity_version': 2,
                    'code_sha256': {'agent/example.py': sha256(frozen['agent/example.py'])},
                    'evaluation_sha256': {'evaluation/run.py': sha256(frozen['evaluation/run.py'])},
                    'source_sha256': source_hashes,
                    'dataset_sha256': dataset['dataset_sha256'],
                    'dataset_manifest_sha256': sha256((run / 'snapshot/dataset_manifest.json').read_bytes()),
                    'variant_identity': None, 'variant_identity_sha256': None}
        if variant:
            identity = {'label': 'historical_optimized_v1', 'definition': '冻结历史业务版本',
                        'historical_code_sha256': manifest['code_sha256'],
                        'source_sha256': source_hashes}
            write_json(run / 'snapshot/variant_identity.json', identity)
            manifest.update(variant_identity=identity,
                            variant_identity_sha256=sha256((run / 'snapshot/variant_identity.json').read_bytes()))
        write_json(run / 'manifest.json', manifest)
        # Deliberately use a different key order from the canonical review hash.
        results = [{'answer': '先断开电源。', 'status': 'ok', 'id': 'K1', 'mode': 'qa'},
                   {'status': 'timeout', 'id': 'A1', 'mode': 'agent', 'turns': [],
                    'error': 'local evaluation timed out'}]
        reviews = [{'id': 'K1', 'answer_score': 2, 'grounded': True,
                    'result_sha256': row_sha256(results[0])},
                   {'id': 'A1', 'answer_score': None, 'grounded': None, 'task_pass': None,
                    'result_sha256': row_sha256(results[1])}]
        write_rows(run / 'results.jsonl', results)
        write_rows(run / 'reviews.jsonl', reviews)
        for relative, content in {'cache/retrieval.json': b'{"K1": []}\n',
                                  'raw/A1.json': b'{"status": "timeout"}\n',
                                  'summary.json': b'{"unknown": 1}\n',
                                  'audit/review.md': '人工复核记录\n'.encode('utf-8'),
                                  'snapshot/seal.json': b'nested file remains publishable\n'}.items():
            target = run / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        return run

    def update_manifest(self, run, **changes):
        manifest = read_json(run / 'manifest.json')
        manifest.update(changes)
        write_json(run / 'manifest.json', manifest)

    def refresh_dataset_hashes(self, run):
        dataset_path = run / 'snapshot/dataset_manifest.json'
        dataset = read_json(dataset_path)
        dataset['dataset_sha256'] = sha256((run / 'cases.jsonl').read_bytes())
        write_json(dataset_path, dataset)
        self.update_manifest(run, dataset_sha256=dataset['dataset_sha256'],
                             dataset_manifest_sha256=sha256(dataset_path.read_bytes()))

    def add_tokenizer_cache(self, run, **descriptor_changes):
        cache = run / 'snapshot/config/tokenizers/tiny.json.gz'
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(gzip.compress(b'{"offline": "fixture"}', mtime=0))
        descriptor = {'cache_file': 'tokenizers/tiny.json.gz',
                      'cache_sha256': sha256(cache.read_bytes())}
        descriptor.update(descriptor_changes)
        descriptor_path = run / 'snapshot/config/context_tokenizer.json'
        write_json(descriptor_path, descriptor)
        manifest = read_json(run / 'manifest.json')
        manifest['code_sha256']['config/context_tokenizer.json'] = sha256(descriptor_path.read_bytes())
        write_json(run / 'manifest.json', manifest)
        return cache

    def assert_rejected(self, run, verify=False):
        with self.assertRaises((ValueError, OSError)):
            seal_run(run, verify=verify)

    def test_complete_archive_seals_all_publishable_files_offline(self):
        with patch('urllib.request.urlopen', side_effect=AssertionError('network is forbidden')), \
             patch('socket.create_connection', side_effect=AssertionError('network is forbidden')):
            result = seal_run(self.run)
        seal = read_json(self.run / 'seal.json')
        self.assertIsInstance(result, dict)
        self.assertEqual(seal['seal_version'], 1)
        expected = {path.relative_to(self.run).as_posix(): sha256(path.read_bytes())
                    for path in self.run.rglob('*') if path.is_file() and path != self.run / 'seal.json'}
        self.assertEqual(seal['files'], expected)
        self.assertIn('cache/retrieval.json', seal['files'])
        self.assertIn('snapshot/seal.json', seal['files'])
        self.assertTrue(all('\\' not in name for name in seal['files']))

    def test_existing_seal_is_verified_without_rewriting_its_bytes(self):
        seal_run(self.run)
        value = read_json(self.run / 'seal.json')
        original = ('\n' + json.dumps(value, ensure_ascii=False, indent=4) + '\n\n').encode('utf-8')
        (self.run / 'seal.json').write_bytes(original)
        self.assertIsInstance(seal_run(self.run), dict)
        self.assertEqual((self.run / 'seal.json').read_bytes(), original)
        self.assertIsInstance(seal_run(self.run, verify=True), dict)
        self.assertEqual((self.run / 'seal.json').read_bytes(), original)

    def test_verify_requires_an_existing_seal(self):
        self.assert_rejected(self.run, verify=True)
        self.assertFalse((self.run / 'seal.json').exists())

    def test_cache_tampering_never_overwrites_an_existing_seal(self):
        seal_run(self.run)
        original = (self.run / 'seal.json').read_bytes()
        (self.run / 'cache/retrieval.json').write_bytes(b'{"changed": true}\n')
        self.assert_rejected(self.run)
        self.assert_rejected(self.run, verify=True)
        self.assertEqual((self.run / 'seal.json').read_bytes(), original)

    def test_publishable_file_additions_and_deletions_are_rejected(self):
        for change in ('add', 'delete'):
            with self.subTest(change=change):
                run = self.make_run(change)
                seal_run(run)
                if change == 'add':
                    (run / 'audit/new.txt').write_bytes(b'new published file')
                else:
                    (run / 'summary.json').unlink()
                self.assert_rejected(run, verify=True)

    def test_transient_directories_are_excluded_at_every_depth(self):
        excluded = ('logs/current.txt', 'workers/A1.json', '__pycache__/compiled.pyc',
                    'tmp/staging.json', 'snapshot/logs/debug.txt', 'cache/tmp/partial.json',
                    'raw/workers/partial.json', 'audit/__pycache__/cached.pyc')
        for relative in excluded:
            target = self.run / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b'transient')
        seal_run(self.run)
        seal = read_json(self.run / 'seal.json')
        self.assertTrue(set(excluded).isdisjoint(seal['files']))
        for relative in excluded:
            (self.run / relative).write_bytes(b'changed transient')
        (self.run / 'logs/new.txt').write_bytes(b'new log')
        (self.run / 'workers/A1.json').unlink()
        seal_run(self.run, verify=True)
        self.assertEqual(read_json(self.run / 'seal.json'), seal)

    def test_windows_manifest_paths_are_normalized_to_portable_seal_names(self):
        manifest = read_json(self.run / 'manifest.json')
        for field in ('code_sha256', 'evaluation_sha256', 'source_sha256'):
            manifest[field] = {name.replace('/', '\\'): value for name, value in manifest[field].items()}
        write_json(self.run / 'manifest.json', manifest)
        dataset_path = self.run / 'snapshot/dataset_manifest.json'
        dataset = read_json(dataset_path)
        dataset['files'] = manifest['source_sha256']
        write_json(dataset_path, dataset)
        self.update_manifest(self.run, dataset_manifest_sha256=sha256(dataset_path.read_bytes()))
        seal_run(self.run)
        seal = read_json(self.run / 'seal.json')
        self.assertIn('snapshot/agent/example.py', seal['files'])
        self.assertIn('snapshot/evaluation/run.py', seal['files'])
        self.assertIn('snapshot/data/source.txt', seal['files'])
        seal_run(self.run, verify=True)
        self.assertEqual(read_json(self.run / 'seal.json'), seal)

    def test_snapshot_bytes_must_match_each_manifest_hash_map(self):
        for relative in ('agent/example.py', 'evaluation/run.py', 'data/source.txt'):
            with self.subTest(relative=relative):
                run = self.make_run('snapshot-' + relative.split('/')[0])
                (run / 'snapshot' / relative).write_bytes(b'tampered frozen file')
                self.assert_rejected(run)
                self.assertFalse((run / 'seal.json').exists())

    def test_manifest_cannot_claim_a_different_snapshot_hash(self):
        for field in ('code_sha256', 'evaluation_sha256', 'source_sha256'):
            with self.subTest(field=field):
                run = self.make_run(field)
                manifest = read_json(run / 'manifest.json')
                relative = next(iter(manifest[field]))
                manifest[field][relative] = '0' * 64
                write_json(run / 'manifest.json', manifest)
                self.assert_rejected(run)

    def test_required_snapshot_file_cannot_be_missing(self):
        (self.run / 'snapshot/agent/example.py').unlink()
        self.assert_rejected(self.run)
        self.assertFalse((self.run / 'seal.json').exists())

    def test_tokenizer_descriptor_requires_its_bound_cache_and_preserves_seal(self):
        cache = self.add_tokenizer_cache(self.run)
        seal_run(self.run)
        original = (self.run / 'seal.json').read_bytes()
        seal = read_json(self.run / 'seal.json')
        self.assertEqual(seal['files']['snapshot/config/tokenizers/tiny.json.gz'],
                         sha256(cache.read_bytes()))
        seal_run(self.run, verify=True)
        cache.write_bytes(b'damaged compressed cache')
        with self.assertRaisesRegex(ValueError, 'Frozen hash mismatch'):
            seal_run(self.run, verify=True)
        self.assertEqual((self.run / 'seal.json').read_bytes(), original)

    def test_tokenizer_cache_missing_damaged_or_invalid_digest_is_rejected(self):
        for change in ('missing', 'damaged', 'digest-mismatch', 'digest-invalid', 'digest-missing'):
            with self.subTest(change=change):
                run = self.make_run('tokenizer-' + change)
                changes = ({'cache_sha256': '0' * 64} if change == 'digest-mismatch' else
                           {'cache_sha256': 'invalid'} if change == 'digest-invalid' else
                           {'cache_sha256': None} if change == 'digest-missing' else {})
                cache = self.add_tokenizer_cache(run, **changes)
                if change == 'missing':
                    cache.unlink()
                elif change == 'damaged':
                    cache.write_bytes(b'damaged compressed cache')
                self.assert_rejected(run)
                self.assertFalse((run / 'seal.json').exists())

    def test_tokenizer_cache_paths_cannot_escape_config(self):
        paths = (None, '', '.', '../outside.gz', 'tokenizers/../../outside.gz',
                 '/outside.gz', '\\outside.gz', 'C:\\outside.gz', 'C:outside.gz',
                 '\\\\server\\share\\outside.gz', 'tokenizers/cache.gz:stream')
        for index, unsafe in enumerate(paths):
            with self.subTest(path=unsafe):
                run = self.make_run('tokenizer-path-' + str(index))
                self.add_tokenizer_cache(run, cache_file=unsafe)
                with self.assertRaisesRegex(ValueError, 'Unsafe relative path'):
                    seal_run(run)
                self.assertFalse((run / 'seal.json').exists())

    def test_tokenizer_descriptor_must_be_bound_and_cache_must_be_in_inventory(self):
        for change in ('unbound-descriptor', 'excluded-cache'):
            with self.subTest(change=change):
                run = self.make_run('tokenizer-' + change)
                cache = self.add_tokenizer_cache(run)
                if change == 'unbound-descriptor':
                    manifest = read_json(run / 'manifest.json')
                    del manifest['code_sha256']['config/context_tokenizer.json']
                    write_json(run / 'manifest.json', manifest)
                else:
                    excluded = run / 'snapshot/config/tmp/tiny.json.gz'
                    excluded.parent.mkdir(parents=True)
                    excluded.write_bytes(cache.read_bytes())
                    self.add_tokenizer_cache(run, cache_file='tmp/tiny.json.gz')
                self.assert_rejected(run)
                self.assertFalse((run / 'seal.json').exists())

    def test_dataset_and_dataset_manifest_hashes_are_bound(self):
        for relative in ('cases.jsonl', 'snapshot/dataset_manifest.json'):
            with self.subTest(relative=relative):
                run = self.make_run('dataset-' + relative.replace('/', '-'))
                with (run / relative).open('ab') as stream:
                    stream.write(b'\n')
                self.assert_rejected(run)

    def test_dataset_count_and_unique_ids_are_required_even_with_updated_hashes(self):
        for change in ('count', 'duplicate'):
            with self.subTest(change=change):
                run = self.make_run('dataset-' + change)
                if change == 'count':
                    dataset_path = run / 'snapshot/dataset_manifest.json'
                    dataset = read_json(dataset_path)
                    dataset['case_count'] = 3
                    write_json(dataset_path, dataset)
                else:
                    rows = read_rows(run / 'cases.jsonl')
                    rows[1]['id'] = rows[0]['id']
                    write_rows(run / 'cases.jsonl', rows)
                self.refresh_dataset_hashes(run)
                self.assert_rejected(run)

    def test_results_and_reviews_must_cover_all_planned_ids_exactly_once(self):
        for filename in ('results.jsonl', 'reviews.jsonl'):
            for change in ('missing', 'duplicate', 'unknown'):
                with self.subTest(filename=filename, change=change):
                    run = self.make_run(filename + '-' + change)
                    rows = read_rows(run / filename)
                    if change == 'missing':
                        rows.pop()
                    elif change == 'duplicate':
                        rows.append(rows[0])
                    else:
                        rows[1]['id'] = 'unplanned'
                    write_rows(run / filename, rows)
                    self.assert_rejected(run)
                    self.assertFalse((run / 'seal.json').exists())

    def test_review_hash_must_bind_the_exact_final_result_row(self):
        reviews = read_rows(self.run / 'reviews.jsonl')
        reviews[0]['result_sha256'] = '0' * 64
        write_rows(self.run / 'reviews.jsonl', reviews)
        self.assert_rejected(self.run)

    def test_review_hash_is_independent_of_jsonl_whitespace_and_key_order(self):
        rows = read_rows(self.run / 'results.jsonl')
        (self.run / 'results.jsonl').write_text(
            '\n'.join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
                      for row in reversed(rows)) + '\n', encoding='utf-8')
        seal_run(self.run)
        self.assertTrue((self.run / 'seal.json').exists())

    def test_error_timeout_and_truncated_records_with_unknown_scores_can_be_sealed(self):
        for status in ('error', 'timeout', 'truncated'):
            with self.subTest(status=status):
                run = self.make_run('status-' + status)
                rows = read_rows(run / 'results.jsonl')
                rows[1]['status'] = status
                write_rows(run / 'results.jsonl', rows)
                reviews = read_rows(run / 'reviews.jsonl')
                reviews[1]['result_sha256'] = row_sha256(rows[1])
                write_rows(run / 'reviews.jsonl', reviews)
                seal_run(run)
                self.assertTrue((run / 'seal.json').exists())

    def test_running_records_are_not_complete_archives(self):
        rows = read_rows(self.run / 'results.jsonl')
        rows[1]['status'] = 'running'
        write_rows(self.run / 'results.jsonl', rows)
        reviews = read_rows(self.run / 'reviews.jsonl')
        reviews[1]['result_sha256'] = row_sha256(rows[1])
        write_rows(self.run / 'reviews.jsonl', reviews)
        self.assert_rejected(self.run)

    def test_variant_identity_hash_and_object_are_both_bound(self):
        valid = self.make_run('variant-valid', variant=True)
        seal_run(valid)
        for change in ('hash', 'object', 'missing'):
            with self.subTest(change=change):
                run = self.make_run('variant-' + change, variant=True)
                if change == 'hash':
                    self.update_manifest(run, variant_identity_sha256='0' * 64)
                elif change == 'object':
                    self.update_manifest(run, variant_identity={'label': 'different'})
                else:
                    (run / 'snapshot/variant_identity.json').unlink()
                self.assert_rejected(run)

    def test_historical_variant_paths_are_normalized_for_identity_comparison(self):
        run = self.make_run('variant-normalized', variant=True)
        identity_path = run / 'snapshot/variant_identity.json'
        identity = read_json(identity_path)
        for field in ('historical_code_sha256', 'source_sha256'):
            identity[field] = {name.replace('/', '\\'): value for name, value in identity[field].items()}
        write_json(identity_path, identity)
        self.update_manifest(run, variant_identity=identity,
                             variant_identity_sha256=sha256(identity_path.read_bytes()))
        seal_run(run)
        seal_run(run, verify=True)

    def test_self_consistent_run_cannot_change_the_historical_business_or_sources(self):
        for field, relative, message in (
                ('code_sha256', 'agent/example.py', 'Historical variant code hashes'),
                ('source_sha256', 'data/source.txt', 'Historical variant source hashes')):
            with self.subTest(field=field):
                run = self.make_run('variant-drift-' + field, variant=True)
                frozen_path = run / 'snapshot' / relative
                frozen_path.write_bytes(b'changed after historical preparation')
                manifest = read_json(run / 'manifest.json')
                manifest[field][relative] = sha256(frozen_path.read_bytes())
                write_json(run / 'manifest.json', manifest)
                if field == 'source_sha256':
                    dataset_path = run / 'snapshot/dataset_manifest.json'
                    dataset = read_json(dataset_path)
                    dataset['files'] = manifest['source_sha256']
                    write_json(dataset_path, dataset)
                    self.refresh_dataset_hashes(run)
                with self.assertRaisesRegex(ValueError, message):
                    seal_run(run)
                self.assertFalse((run / 'seal.json').exists())

    def test_manifest_paths_cannot_be_absolute_traversal_or_drive_relative(self):
        paths = ('../outside.txt', 'data/../../outside.txt', '/outside.txt',
                 '\\outside.txt', 'C:\\outside.txt', 'C:outside.txt',
                 '\\\\server\\share\\outside.txt')
        for index, unsafe in enumerate(paths):
            with self.subTest(path=unsafe):
                run = self.make_run('unsafe-' + str(index))
                self.update_manifest(run, code_sha256={unsafe: sha256(b'frozen business\n')})
                self.assert_rejected(run)

    def test_seal_paths_cannot_be_absolute_traversal_or_drive_relative(self):
        seal_run(self.run)
        original = read_json(self.run / 'seal.json')
        for unsafe in ('../outside.txt', '/outside.txt', 'C:\\outside.txt', 'C:outside.txt'):
            with self.subTest(path=unsafe):
                seal = dict(original)
                seal['files'] = {**original['files'], unsafe: '0' * 64}
                write_json(self.run / 'seal.json', seal)
                self.assert_rejected(self.run, verify=True)

    def test_symlink_files_and_directories_are_rejected(self):
        external = self.root / 'external'
        external.mkdir()
        (external / 'target.json').write_bytes(b'external bytes')
        for directory in (False, True):
            with self.subTest(directory=directory):
                run = self.make_run('link-' + str(directory))
                target = external if directory else external / 'target.json'
                link = run / 'raw' / ('external-dir' if directory else 'external.json')
                try:
                    link.symlink_to(target, target_is_directory=directory)
                except (OSError, NotImplementedError) as error:
                    self.skipTest('Symlinks are unavailable on this host: ' + str(error))
                self.assert_rejected(run)
                self.assertFalse((run / 'seal.json').exists())

    def test_link_checks_include_the_run_root_and_excluded_directories(self):
        # Windows test users may lack symlink privileges. Simulate only the
        # filesystem link flag to exercise rejection on those hosts as well.
        original_is_symlink = Path.is_symlink
        for index, relative in enumerate(('', 'logs', 'workers', '__pycache__', 'tmp')):
            with self.subTest(relative=relative):
                run = self.make_run('link-check-' + str(index))
                linked = run / relative
                if relative:
                    linked.mkdir()

                def marked_link(path):
                    return path == linked or original_is_symlink(path)

                with patch.object(Path, 'is_symlink', marked_link):
                    self.assert_rejected(run)
                self.assertFalse((run / 'seal.json').exists())

    def test_invalid_review_scores_and_flags_are_rejected(self):
        invalid = (('answer_score', True), ('answer_score', 3),
                   ('grounded', 1), ('task_pass', 'true'))
        for index, (field, value) in enumerate(invalid):
            with self.subTest(field=field, value=value):
                run = self.make_run('invalid-review-' + str(index))
                reviews = read_rows(run / 'reviews.jsonl')
                reviews[0][field] = value
                write_rows(run / 'reviews.jsonl', reviews)
                self.assert_rejected(run)

    def test_cli_runs_with_standard_library_only_and_preserves_existing_seal(self):
        script = Path(__file__).resolve().parents[1] / 'scripts/seal_evaluation_run.py'
        arguments = [sys.executable, '-X', 'utf8', '-B', '-S', str(script), '--run', str(self.run)]
        created = subprocess.run(arguments, cwd=self.root, capture_output=True,
                                 text=True, encoding='utf-8', timeout=20)
        self.assertEqual(created.returncode, 0, created.stdout + created.stderr)
        original = (self.run / 'seal.json').read_bytes()
        verified = subprocess.run(arguments + ['--verify'], cwd=self.root, capture_output=True,
                                  text=True, encoding='utf-8', timeout=20)
        self.assertEqual(verified.returncode, 0, verified.stdout + verified.stderr)
        self.assertEqual((self.run / 'seal.json').read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
