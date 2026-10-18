import hashlib
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('emoji', Path(__file__).resolve().parents[1] / 'scripts/emoji.py')
emoji = importlib.util.module_from_spec(spec)
spec.loader.exec_module(emoji)


class EmojiFont(unittest.TestCase):
    def test_does_not_mistake_fontconfig_substitution_for_apple(self):
        outputs = [subprocess.CompletedProcess([], 0, 'Noto Color Emoji|True'), subprocess.CompletedProcess([], 0, 'Noto Color Emoji|True')]
        with patch.object(emoji.subprocess, 'run', side_effect=outputs):
            self.assertEqual(emoji.family(), 'Noto Color Emoji|true')

    def test_apple_font_is_preferred(self):
        with patch.object(emoji.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, 'Apple Color Emoji|True')):
            self.assertEqual(emoji.family(), 'Apple Color Emoji|true')

    def test_rejects_invalid_download_before_creating_font_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = root / 'fake.ttf'; source.write_bytes(b'invalid')
            with patch.dict(os.environ, XDG_DATA_HOME=str(root / 'data')):
                with self.assertRaisesRegex(RuntimeError, 'checksum'):
                    emoji.install(source)
            self.assertFalse((root / 'data').exists())
