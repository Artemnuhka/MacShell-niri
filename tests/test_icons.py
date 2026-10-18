import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('macshell_icons', ROOT / 'scripts/icons.py')
icons = importlib.util.module_from_spec(spec)
spec.loader.exec_module(icons)


class IconArchives(unittest.TestCase):
    def archive(self, name, link=None):
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode='w') as package:
            entry = tarfile.TarInfo(name)
            if link is not None:
                entry.type = tarfile.SYMTYPE
                entry.linkname = link
            package.addfile(entry)
        buffer.seek(0)
        return tarfile.open(fileobj=buffer)

    def test_rejects_aliases_escaping_the_theme(self):
        with self.archive('MacOS-Like-Dark/apps/icon.svg', '../../../outside') as package:
            with self.assertRaisesRegex(RuntimeError, 'escapes'):
                icons.validate(package)

    def test_accepts_internal_aliases(self):
        with self.archive('MacOS-Like-Dark/apps/icon.svg', '../places/file.svg') as package:
            icons.validate(package)

    def test_dry_run_does_not_create_any_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            icons.apply(root / 'config', root / 'data', 'MacOS-Like-Dark', dry=True)
            self.assertEqual(list(root.iterdir()), [])
