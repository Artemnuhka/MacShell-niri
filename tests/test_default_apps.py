import contextlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('default_apps',ROOT/'scripts/default-apps.py')
apps=importlib.util.module_from_spec(spec);spec.loader.exec_module(apps)

class App:
    def __init__(self,app_id='test.desktop',command='terminal %U',separator=None):
        self.app_id=app_id;self.command=command;self.separator=separator
    def get_id(self):return self.app_id
    def get_commandline(self):return self.command
    def get_string(self,key):return self.separator if key=='X-TerminalArgExec' else None

class DefaultApplications(unittest.TestCase):
    def test_terminal_command_preserves_literal_arguments_without_a_shell(self):
        value=App(command='env MODE=one terminal --single-instance %U',separator='--')
        self.assertEqual(apps.command_for_terminal(value,['-e','python3','a b','$(touch nope)']),
                         ['env','MODE=one','terminal','--single-instance','--','python3','a b','$(touch nope)'])

    def test_terminal_exec_arg_and_compatibility_fallback(self):
        self.assertEqual(apps.command_for_terminal(App(separator='-e'),['-e','top']),['terminal','-e','top'])
        self.assertEqual(apps.command_for_terminal(App(separator=''),['-e','top']),['terminal','top'])
        self.assertEqual(apps.command_for_terminal(App('org.gnome.Terminal.desktop'),['-e','top']),['terminal','--','top'])
        self.assertEqual(apps.command_for_terminal(App(separator='--'),[]),['terminal'])
        with self.assertRaises(ValueError):apps.command_for_terminal(App(),['-e'])

    def test_terminal_preference_preserves_other_preferences_and_list_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            config=Path(directory);(config/'macshell').mkdir()
            (config/'macshell/default-apps.json').write_text('{"custom": true}')
            (config/'xdg-terminals.list').write_text('# personal preferences\nold.desktop\n-new.desktop\n')
            (config/'niri-xdg-terminals.list').write_text('other.desktop\n')
            apps.terminal_preferences(config,'new.desktop')
            self.assertTrue(json.loads((config/'macshell/default-apps.json').read_text())['custom'])
            self.assertEqual((config/'xdg-terminals.list').read_text(),'new.desktop\n# personal preferences\nold.desktop\n')
            self.assertEqual((config/'niri-xdg-terminals.list').read_text(),'new.desktop\nother.desktop\n')

    def test_unknown_categories_rejected_before_any_preference_changes(self):
        with patch.object(apps,'libraries',side_effect=AssertionError('must validate first')):
            with self.assertRaises(ValueError):apps.apply({'unknown':'test.desktop'})

    def exercise(self,fail=False,terminal=False):
        with tempfile.TemporaryDirectory() as directory:
            config=Path(directory)/'config';data=Path(directory)/'data';config.mkdir()
            mime=config/'mimeapps.list';original=b'[Default Applications]\ntext/plain=personal.desktop\n';mime.write_bytes(original)
            calls=[]
            entry=App()
            def change(mime_type):
                calls.append(mime_type);mime.write_text('changed\n')
                if fail and len(calls)>1:raise RuntimeError('test association failure')
                return True
            entry.set_as_default_for_type=change
            desktop=SimpleNamespace(new=lambda _:entry)
            role='terminal' if terminal else 'browser'
            catalog={'roles':[{'id':role,'apps':[{'id':'test.desktop'}]}]}
            with patch.object(apps,'paths',return_value=(config,data)),patch.object(apps,'libraries',return_value=(None,desktop)),patch.object(apps,'catalog',return_value=catalog):
                if fail:
                    with self.assertRaises(RuntimeError):apps.apply({role:'test.desktop'})
                    self.assertEqual(mime.read_bytes(),original)
                    self.assertFalse(mime.with_name('mimeapps.list.before-macshell-defaults').exists())
                else:
                    apps.apply({role:'test.desktop'})
                    if terminal:
                        self.assertEqual(calls,[]);self.assertEqual(mime.read_bytes(),original)
                        self.assertEqual(json.loads((config/'macshell/default-apps.json').read_text())['terminal'],'test.desktop')
                    else:
                        self.assertEqual(calls,apps.ROLES['browser'][1])
                        self.assertEqual(mime.with_name('mimeapps.list.before-macshell-defaults').read_bytes(),original)
            self.assertEqual(list(config.rglob('.macshell-default-*')),[])

    def test_browser_changes_only_its_mime_types_and_backs_up_existing_preferences(self):self.exercise()
    def test_partial_failure_restores_original_associations(self):self.exercise(fail=True)
    def test_terminal_does_not_rewrite_mime_associations(self):self.exercise(terminal=True)

    def test_explicit_kitty_launch_does_not_launch_selected_default_instead(self):
        with tempfile.TemporaryDirectory() as directory:
            config=Path(directory);(config/'macshell').mkdir()
            (config/'macshell/default-apps.json').write_text('{"terminal":"other.desktop"}')
            entry=App('kitty.desktop',command='/usr/bin/kitty',separator='--')
            entry.get_categories=lambda:'TerminalEmulator;'
            entry.get_boolean=lambda key:False
            desktop=SimpleNamespace(new=lambda app_id:entry if app_id=='kitty.desktop' else None)
            with patch.object(apps,'paths',return_value=(config,config)),patch.object(apps,'libraries',return_value=(None,desktop)),patch.object(apps.os,'execvpe') as execute:
                apps.launch_terminal(['--app','kitty.desktop'])
                self.assertEqual(execute.call_args.args[0:2],('/usr/bin/kitty',['/usr/bin/kitty']))

    @unittest.skipUnless(importlib.util.find_spec('gi'),'Python GObject bindings unavailable')
    def test_native_gio_and_terminal_launcher_in_isolated_xdg_home(self):
        with tempfile.TemporaryDirectory() as directory:
            home=Path(directory);config=home/'.config';data=home/'.local/share';entries=data/'applications';entries.mkdir(parents=True);config.mkdir()
            mime=config/'mimeapps.list';mime.write_text('[Default Applications]\ntext/plain=keep-editor.desktop\n')
            (entries/'test-browser.desktop').write_text('[Desktop Entry]\nType=Application\nName=Test browser\nExec=/usr/bin/true %U\nMimeType=x-scheme-handler/http;x-scheme-handler/https;text/html;application/xhtml+xml;\nCategories=Network;WebBrowser;\n')
            stub=home/'terminal-stub.py';result=home/'terminal-argv.json'
            stub.write_text('import json,sys\nfrom pathlib import Path\nPath('+repr(str(result))+').write_text(json.dumps(sys.argv[1:]))\n')
            (entries/'test-terminal.desktop').write_text('[Desktop Entry]\nType=Application\nName=Test terminal\nExec='+sys.executable+' '+str(stub)+'\nCategories=System;TerminalEmulator;\nX-TerminalArgExec=--\n')
            env=dict(os.environ,HOME=str(home),XDG_CONFIG_HOME=str(config),XDG_DATA_HOME=str(data),XDG_CACHE_HOME=str(home/'.cache'))
            applied=subprocess.run([sys.executable,str(ROOT/'scripts/default-apps.py'),'apply',json.dumps({'browser':'test-browser.desktop','terminal':'test-terminal.desktop'})],env=env,capture_output=True,text=True,check=True)
            values={role['id']:role for role in json.loads(applied.stdout)['roles']}
            self.assertEqual(values['browser']['current'],'test-browser.desktop')
            self.assertEqual(values['terminal']['current'],'test-terminal.desktop')
            self.assertIn('text/plain=keep-editor.desktop',mime.read_text())
            subprocess.run([sys.executable,str(ROOT/'scripts/launch-kitty.py'),'-e','echo','literal argument'],env=env,check=True,capture_output=True)
            self.assertEqual(json.loads(result.read_text()),['--','echo','literal argument'])

if __name__=='__main__':unittest.main()
