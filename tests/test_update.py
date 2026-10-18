import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('niri_update', ROOT / 'scripts/update.py')
updater = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updater)


class UpdateRollback(unittest.TestCase):
    def test_restores_shell_and_nested_locker_together_and_retains_displaced(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            current = parent / 'shell'
            previous = parent / 'shell.backup-20261018'
            for path, version in [(current, 'new'), (previous, 'old')]:
                (path / 'MacLock').mkdir(parents=True)
                (path / '.macshell-niri-install').write_text('1')
                (path / 'shell.qml').write_text(version)
                (path / 'MacLock/shell.qml').write_text(version)
            updater.rollback(current)
            self.assertEqual((current / 'shell.qml').read_text(), 'old')
            self.assertEqual((current / 'MacLock/shell.qml').read_text(), 'old')
            displaced = next(parent.glob('shell.rollback-*'))
            self.assertEqual((displaced / 'shell.qml').read_text(), 'new')

    def test_refuses_an_unmanaged_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            current = Path(directory) / 'shell'
            current.mkdir()
            (current / '.macshell-niri-install').write_text('1')
            (Path(directory) / 'shell.backup-unmanaged').mkdir()
            with self.assertRaisesRegex(RuntimeError, 'No managed'):
                updater.rollback(current)
            self.assertTrue(current.is_dir())
