import importlib.metadata
import unittest
from unittest.mock import patch
from scripts.manage import dependency_checks, run_python, ROOT
from scripts.package_project import selected_files


class DeliveryTests(unittest.TestCase):
    def test_missing_dependency_is_reported_without_import_crash(self):
        with patch('scripts.manage.importlib.metadata.version', side_effect=importlib.metadata.PackageNotFoundError('missing')):
            checks = dependency_checks()
        self.assertTrue(checks)
        self.assertTrue(all(not c['ok'] and c['actual']=='missing' for c in checks))

    def test_commands_use_this_interpreter_project_cwd_and_exit_code(self):
        import sys
        with patch('scripts.manage.subprocess.call', return_value=7) as child:
            self.assertEqual(run_python(['-m','unittest']),7)
        self.assertEqual(child.call_args.args[0],[sys.executable,'-B','-m','unittest'])
        self.assertEqual(child.call_args.kwargs['cwd'],ROOT)

    def test_package_excludes_local_state_and_includes_required_sources(self):
        names={p.relative_to(ROOT).as_posix() for p in selected_files()}
        self.assertIn('app.py',names)
        self.assertIn('requirements-lock.txt',names)
        self.assertIn('data/external/records.csv',names)
        self.assertFalse(any(any(part in {'logs','workers','chroma_db','.venv','__pycache__'} for part in name.split('/')) for name in names))
