import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('safe_installer',ROOT/'scripts/install.py')
installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)

class InstalledFileSafety(unittest.TestCase):
    def test_uninstall_preserves_user_edits_and_original_desktop_configs(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp);config=home/'config';data=home/'data';bindir=home/'bin'
            paths=[config/'kdeglobals',config/'niri/config.kdl',config/'gtk-4.0/gtk.css']
            for path in paths:path.parent.mkdir(parents=True,exist_ok=True);path.write_text('personal data\n')
            private=config/'niri/macshell.kdl';private.write_text('managed private config\n')
            launcher=bindir/'macshell-niri';launcher.parent.mkdir();launcher.write_text('managed launcher\n')
            updater=bindir/'macshell-niri-update';updater.write_text('managed updater\n')
            payload=config/'quickshell/macshell-niri';payload.mkdir(parents=True);(payload/'shell.qml').write_text('ShellRoot {}\n')
            installer.save_owned_files(config,data,bindir,private)
            launcher.write_text('my launcher edit\n');private.write_text('my private config edit\n')
            installer.remove_owned_files(config,data,bindir,private)
            self.assertEqual(launcher.read_text(),'my launcher edit\n')
            self.assertEqual(private.read_text(),'my private config edit\n')
            self.assertFalse(updater.exists())
            for path in paths:self.assertEqual(path.read_text(),'personal data\n')
    def test_identical_launcher_install_does_not_accumulate_backups(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'bin/macshell-niri'
            installer.write_managed_file(path,'#!/bin/sh\nexit 0\n')
            installer.write_managed_file(path,'#!/bin/sh\nexit 0\n')
            self.assertEqual(list(path.parent.glob('*.backup-*')),[])
            self.assertTrue(path.stat().st_mode & 0o100)
    def test_integration_does_not_mark_original_config_for_deletion(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp);config=home/'config';data=home/'data';bindir=home/'bin'
            original=config/'niri/config.kdl';original.parent.mkdir(parents=True);original.write_text('personal original\n')
            (config/'quickshell/macshell-niri').mkdir(parents=True)
            installer.save_owned_files(config,data,bindir,original,integrate=True)
            records=json.loads((data/'macshell-niri/install-files.json').read_text())
            self.assertNotIn('private-config',records)

if __name__=='__main__':unittest.main()
