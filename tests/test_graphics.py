import importlib.util
from pathlib import Path
import json
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('graphics', Path(__file__).resolve().parents[1] / 'scripts/graphics.py')
graphics = importlib.util.module_from_spec(spec)
spec.loader.exec_module(graphics)


class Graphics(unittest.TestCase):
    def test_no_nvidia_leaves_home_untouched(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertFalse(graphics.configure(root / 'home', root / 'sys'))
            self.assertFalse((root / 'home').exists())

    def test_hybrid_profile_is_user_local_and_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for n, vendor in enumerate(('0x8086', '0x10de')):
                device = root / f'sys/class/drm/card{n}/device'
                device.mkdir(parents=True)
                (device / 'vendor').write_text(vendor)
            kms = root / 'sys/module/nvidia_drm/parameters'
            kms.mkdir(parents=True); (kms / 'modeset').write_text('Y\n')
            profiles = root / 'home/.nv/nvidia-application-profiles-rc.d'
            profiles.mkdir(parents=True)
            existing = profiles / '00-custom.json'; existing.write_text('user settings')
            self.assertTrue(graphics.detect(root / 'sys')['nvidia_drm_modeset'])
            self.assertTrue(graphics.configure(root / 'home', root / 'sys'))
            self.assertFalse(graphics.configure(root / 'home', root / 'sys'))
            self.assertEqual(existing.read_text(), 'user settings')
            state = json.loads((profiles / '50-macshell-niri.json').read_text())
            self.assertEqual([r['pattern']['matches'] for r in state['rules']], ['niri', 'niri-glass'])
            self.assertEqual(state['profiles'][0]['settings'][0]['value'], 0)
