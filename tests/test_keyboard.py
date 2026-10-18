import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('keyboard_settings', ROOT/'scripts/niri-settings.py')
settings = importlib.util.module_from_spec(spec)
spec.loader.exec_module(settings)
CATALOG = {'available': [
    {'code':'us','name':'English','variants':[{'code':'','name':'Default'},{'code':'dvorak','name':'Dvorak'}]},
    {'code':'ru','name':'Russian','variants':[{'code':'','name':'Default'}]},
    {'code':'de','name':'German','variants':[{'code':'','name':'Default'}]}],
    'shortcuts':[{'code':'','name':'None'},{'code':'grp:alt_shift_toggle','name':'Alt+Shift'},{'code':'grp:win_space_toggle','name':'Super+Space'}]}
BEFORE = '''// personal configuration
input {
 keyboard {
  repeat-rate 38
  xkb { layout "us,ru"; variant "dvorak,"; options "compose:ralt,grp:alt_shift_toggle,caps:escape"; }
 }
 mouse { accel-speed 0.3; }
}
output "DP-1" { scale 1.25; }
'''

class KeyboardSettings(unittest.TestCase):
    def test_reads_existing_layouts_variants_and_shortcut(self):
        value = settings.keyboard_values(BEFORE)
        self.assertEqual(value['layouts'],[{'code':'us','variant':'dvorak'},{'code':'ru','variant':''}])
        self.assertEqual(value['shortcut'],'grp:alt_shift_toggle')

    def test_changes_sources_preserving_compose_remaps_and_other_input(self):
        value={'layouts':[{'code':'ru','variant':''},{'code':'de','variant':''}], 'shortcut':'grp:win_space_toggle'}
        after=settings.keyboard_update(BEFORE,value,CATALOG)
        read=settings.keyboard_values(after)
        self.assertEqual(read['layouts'],value['layouts'])
        self.assertEqual(read['options'],['compose:ralt','caps:escape','grp:win_space_toggle'])
        for text in ['repeat-rate 38','mouse { accel-speed 0.3; }','output "DP-1" { scale 1.25; }','// personal configuration']:
            self.assertIn(text,after)
        self.assertEqual(settings.keyboard_values(settings.keyboard_update(after,value,CATALOG)),read)

    def test_rejects_invalid_or_duplicate_sources_and_shortcuts(self):
        for layouts,shortcut in [([],''),([{'code':'unknown'}],''),([{'code':'us','variant':'bad'}],''),
                                  ([{'code':'us'}]*2,''),([{'code':'us'}],'arbitrary'),([{'code':'us'}]*5,'')]:
            with self.subTest(layouts=layouts,shortcut=shortcut),self.assertRaises(ValueError):
                settings.keyboard_update(BEFORE,{'layouts':layouts,'shortcut':shortcut},CATALOG)

    def test_failed_validation_leaves_original_and_no_candidates(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'macshell-glass.kdl';path.write_text(BEFORE)
            with patch.object(settings,'config_path',return_value=path),patch.object(settings,'keyboard_catalog',return_value=CATALOG), \
                 patch.object(settings.subprocess,'run',side_effect=subprocess.CalledProcessError(1,['niri'])):
                with self.assertRaises(subprocess.CalledProcessError):
                    settings.keyboard_settings({'layouts':[{'code':'us'}],'shortcut':''})
            self.assertEqual(path.read_text(),BEFORE)
            self.assertEqual(list(path.parent.glob('.macshell-keyboard-*')),[])
            self.assertFalse(path.with_suffix('.before-keyboard').exists())

    def test_successful_apply_saves_backup_and_returns_current_state(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'macshell-glass.kdl';path.write_text(BEFORE)
            with patch.object(settings,'config_path',return_value=path),patch.object(settings,'keyboard_catalog',return_value=CATALOG), \
                 patch.object(settings.subprocess,'run'),contextlib.redirect_stdout(io.StringIO()) as output:
                settings.keyboard_settings({'layouts':[{'code':'ru'}],'shortcut':'grp:win_space_toggle'})
            self.assertEqual(json.loads(output.getvalue())['layouts'],[{'code':'ru','variant':''}])
            self.assertEqual(path.with_suffix('.before-keyboard').read_text(),BEFORE)

if __name__=='__main__':unittest.main()
