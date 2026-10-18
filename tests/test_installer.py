"""Run only in CI/an isolated environment; never touches a real desktop session."""
import contextlib
import importlib.util
import io
import os
import shutil
import subprocess
import sys
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


config = load('configurer', 'configure-niri.py')
installer = load('installer', 'install.py')
prepare = load('prepare_opensuse', 'prepare-opensuse.py')
glass = load('glass_builder', 'build-glass.py')
widgets = load('widget_migration', 'widget-migration.py')


class WidgetMigration(unittest.TestCase):
    def test_preserves_legacy_layout_and_maps_music_and_size(self):
        import json
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory)
            old = config / 'macwidgets/settings.json'
            old.parent.mkdir()
            original = json.dumps({'widgets': [{'id': 'music-1', 'type': 'player',
                'style': 'liquid', 'size': 'medium', 'x': 30, 'y': 200}]})
            old.write_text(original)
            widgets.migrate(config)
            new = json.loads((config / 'macshell/widgets.json').read_text())
            self.assertEqual(new['widgets'][0]['type'], 'music')
            self.assertEqual(new['widgets'][0]['size'], 'm')
            self.assertEqual(new['widgets'][0]['style'], 'glass')
            self.assertEqual(new['widgets'][0]['id'], 'music-1')
            self.assertEqual(old.read_text(), original)
            (config / 'macshell/widgets.json').write_text('{"widgets": []}')
            widgets.migrate(config)
            self.assertEqual((config / 'macshell/widgets.json').read_text(), '{"widgets": []}')

    def test_preserves_selected_images_and_scale(self):
        import json
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory)
            old = config / 'macwidgets/settings.json'
            old.parent.mkdir()
            original = json.dumps({'widgetScale': 1.3, 'widgets': [{'id': 'photo', 'type': 'image',
                'size': 'large', 'src': '/home/example/Pictures/my photo.png'}]})
            old.write_text(original)
            widgets.migrate(config)
            new = json.loads((config / 'macshell/widgets.json').read_text())
            self.assertEqual(new['widgetScale'], 1.3)
            self.assertEqual(new['widgets'][0]['type'], 'image')
            self.assertEqual(new['widgets'][0]['src'], '/home/example/Pictures/my photo.png')
            self.assertEqual(old.read_text(), original)

    def test_invalid_legacy_scale_does_not_block_installation(self):
        import json
        for scale in [None, 'invalid', True, float('nan')]:
            with self.subTest(scale=scale), tempfile.TemporaryDirectory() as directory:
                config = Path(directory)
                old = config / 'macwidgets/settings.json'
                old.parent.mkdir()
                old.write_text(json.dumps({'widgetScale': scale, 'widgets': []}))
                widgets.migrate(config)
                new = json.loads((config / 'macshell/widgets.json').read_text())
                self.assertEqual(new['widgetScale'], 1)


class GlassInstallation(unittest.TestCase):
    def test_update_reuses_pinned_binary_without_build_or_packages(self):
        import json
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            prefix = data / 'macshell-niri/niri-glass'
            (prefix / 'bin').mkdir(parents=True)
            binary = prefix / 'bin/niri-glass'
            binary.touch()
            (prefix / 'sources.json').write_text(json.dumps({'niri': glass.NIRI_REV, 'glass': glass.GLASS_REV}))
            with patch.object(glass, 'build', side_effect=AssertionError('unnecessary rebuild')), \
                 patch.object(installer, 'run') as run:
                self.assertEqual(glass.ensure(installer, data), binary)
                run.assert_called_once_with([binary, '--version'], False)

    def test_missing_glass_with_skip_deps_fails_without_partial_build(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(glass, 'build', side_effect=AssertionError('unexpected build')):
            with self.assertRaisesRegex(RuntimeError, '--no-glass'):
                glass.ensure(installer, Path(directory), skip_deps=True)

    def test_session_update_preserves_private_optics_and_custom_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / 'config'
            (config / 'niri').mkdir(parents=True)
            base = config / 'niri/config.kdl'
            base.write_text('binds {}\n')
            private = config / 'niri/macshell-glass.kdl'
            previous = '// custom output and optics\nblur { passes 1; offset 0.7; }\n'
            private.write_text(previous)
            with patch.object(installer, 'run'):
                glass.session(installer, root / 'data', config, root / 'bin', base, root / 'niri-glass')
            self.assertEqual(private.read_text(), previous)
            wrapper = (root / 'bin/macshell-glass-session').read_text()
            self.assertIn('MACSHELL_REAL_GLASS=1', wrapper)
            self.assertIn('--session --config', wrapper)
            self.assertIn('WAYLAND_DISPLAY', wrapper)

    def test_login_registration_refuses_unmanaged_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'existing.desktop'
            path.write_text('[Desktop Entry]\nName=Other session\n')
            with patch.object(glass, 'session_path', return_value=path), \
                 patch.object(installer, 'run', side_effect=AssertionError('unexpected sudo')):
                with self.assertRaisesRegex(RuntimeError, 'unmanaged'):
                    glass.login_session(installer, Path(directory), Path(directory))
                glass.remove_login_session(installer, Path(directory) / 'data', Path(directory) / 'bin')
                self.assertTrue(path.exists())

    def test_login_removal_is_scoped_to_installation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'session.desktop'
            bindir = root / 'bin'
            text = f'Exec="{bindir}/macshell-glass-session"\nX-MacShell-Owner={os.getuid()}\n'
            path.write_text(text)
            with patch.object(glass, 'session_path', return_value=path), patch.object(installer, 'run') as run:
                glass.remove_login_session(installer, root / 'other-data', bindir)
                run.assert_not_called()
                staged = root / 'data/macshell-niri/login-session.desktop'
                staged.parent.mkdir(parents=True)
                staged.write_text(text)
                glass.remove_login_session(installer, root / 'data', root / 'other-bin')
                run.assert_not_called()
                glass.remove_login_session(installer, root / 'data', bindir)
                run.assert_called_once()
                self.assertFalse(staged.exists())


class ConfigMigration(unittest.TestCase):
    def test_reinstall_keeps_managed_block_before_theme_and_cursor(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.kdl'
            launcher = Path(directory) / 'bin/macshell-niri'
            path.write_text('binds {}\n')
            with patch.object(config.subprocess, 'run', return_value=SimpleNamespace(returncode=0)):
                config.configure(path, launcher)
                path.write_text(path.read_text() + '\n// custom theme follows managed block\nwindow-rule { geometry-corner-radius 18; }\ncursor { xcursor-size 20; }\n')
                expected = path.read_text()
                backups = list(path.parent.glob('*.macshell-backup-*'))
                config.configure(path, launcher)
                self.assertEqual(path.read_text(), expected)
                self.assertEqual(list(path.parent.glob('*.macshell-backup-*')), backups)

    def test_number_shortcuts_do_not_precreate_nine_workspaces(self):
        example = (ROOT / 'config/niri.example.kdl').read_text()
        for number in range(1, 10):
            self.assertIn(f'Mod+{number} {{ focus-workspace {number}; }}', example)
        self.assertFalse(any(name == 'workspace' for name, *_ in config.nodes(example)))


    def test_adds_shortcuts_without_overwriting_existing_bindings(self):
        before = 'binds {\n    Mod+Space { toggle-window-floating; }\n}\n'
        after = config.merge_keybinds(before, Path('/tmp/my shell'))
        self.assertEqual(after.count('Mod+Space'), 1)
        self.assertIn('toggle-window-floating', after)
        self.assertIn('Mod+V { spawn "/tmp/my shell"', after)
        self.assertNotIn('ipc', config.managed(after))

    @unittest.skipUnless(shutil.which('niri'), 'niri validator unavailable in this environment')
    def test_starter_config_with_real_niri_parser(self):
        result = subprocess.run(['niri', 'validate', '--config', str(ROOT / 'config/niri.base.kdl')],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_removes_legacy_server_and_display_preserves_others(self):
        before = '''// Xwayland in a comment
spawn-at-startup "Xwayland" ":1"
spawn-at-startup "kitty"
environment {
    DISPLAY ":1"
    QT_QPA_PLATFORM "wayland"
}
xwayland-satellite { off; }
/-output "disabled" { off; }
'''
        after = config.migrate(before)
        self.assertNotIn('spawn-at-startup "Xwayland"', after)
        self.assertNotIn('DISPLAY ":1"', after)
        self.assertNotIn('xwayland-satellite { off;', after)
        self.assertIn('spawn-at-startup "kitty"', after)
        self.assertIn('QT_QPA_PLATFORM "wayland"', after)
        self.assertIn('/-output "disabled" { off; }', after)
        self.assertIn('// Xwayland in a comment', after)

    def test_shell_server_migration(self):
        after = config.migrate('spawn-at-startup "sh" "-c" "exec xwayland-satellite"\n')
        self.assertNotIn('spawn-at-startup', after)

    def test_rejects_combined_shell_commands(self):
        with self.assertRaises(ValueError):
            config.migrate('spawn-sh-at-startup "waybar & Xwayland :1"\n')

    def test_rejects_include_without_editing_other_files(self):
        with self.assertRaises(ValueError):
            config.migrate('include "extra.kdl"\n')

    def test_comments_and_raw_strings_are_not_edits(self):
        before = '''/* outer /* nested */ comment */
window-rule {
    match title=r#"Xwayland { DISPLAY }"#
    open-floating true
}
'''
        self.assertEqual(config.migrate(before), before)

    def test_idempotent_config_and_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.kdl'
            path.write_text('input { keyboard { xkb { } } }\n')
            with patch.object(config.subprocess, 'run') as validate:
                validate.return_value.returncode = 0
                config.configure(path, Path('/tmp/launcher with spaces'))
                once = path.read_text()
                config.configure(path, Path('/tmp/launcher with spaces'))
            self.assertEqual(path.read_text(), once)
            self.assertEqual(once.count(config.BEGIN), 1)
            self.assertEqual(len(list(Path(directory).glob('*.macshell-backup-*'))), 1)
            self.assertIn('spawn-at-startup "/tmp/launcher with spaces"', once)

    def test_failed_validation_preserves_original(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.kdl'
            original = 'input { }\n'
            path.write_text(original)
            with patch.object(config.subprocess, 'run') as validate:
                validate.return_value.returncode = 1
                with self.assertRaises(ValueError):
                    config.configure(path, Path('/tmp/launcher'))
            self.assertEqual(path.read_text(), original)
            self.assertFalse(list(Path(directory).glob('.macshell-candidate-*')))

    def test_fresh_config_created_after_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'niri/config.kdl'
            with patch.object(config.subprocess, 'run') as validate:
                validate.return_value.returncode = 0
                config.configure(path, Path('/tmp/launcher'))
            self.assertIn('xwayland-satellite', path.read_text())
            self.assertIn('Mod+Space', path.read_text())


class InstallerPlan(unittest.TestCase):
    def test_vm_preparation_refuses_physical_hosts_before_any_commands(self):
        with patch.object(installer.os, 'geteuid', return_value=1000), \
             patch.object(installer, 'virtualbox_guest', return_value=False), \
             patch.object(installer.subprocess, 'run', side_effect=AssertionError('command executed on physical host')), \
             patch('sys.argv', ['install.py', '--prepare-vm']):
            with self.assertRaises(RuntimeError):
                installer.main()

    def test_rejects_nvidia_changes_before_installation(self):
        xml = '<stream><install-summary><to-upgrade><solvable name="nvidia-open-driver-G06-signed-kmp-default"/></to-upgrade></install-summary></stream>'
        with self.assertRaises(RuntimeError):
            installer.guard_suse_transaction(xml)

    def test_rejects_kernel_changes_and_other_removals(self):
        for group, name in [('to-install', 'kernel-default'), ('to-remove', 'existing-desktop')]:
            xml = f'<stream><install-summary><{group}><solvable name="{name}"/></{group}></install-summary></stream>'
            with self.assertRaises(RuntimeError):
                installer.guard_suse_transaction(xml)

    def test_allows_desktop_libraries_without_driver_changes(self):
        installer.guard_suse_transaction('<stream><install-summary><to-install><solvable name="libQt6Svg6"/></to-install></install-summary></stream>')

    def test_https_migration_only_changes_official_endpoints_and_backs_up(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repos, backups = root / 'repos', root / 'backups'
            repos.mkdir()
            path = repos / 'test.repo'
            original = 'baseurl=http://download.opensuse.org/tumbleweed/\nbaseurl=http://my-mirror.local/repo/\n'
            path.write_text(original)
            prepare.mirrors(repos, backups)
            self.assertIn('https://download.opensuse.org/', path.read_text())
            self.assertIn('http://my-mirror.local/', path.read_text())
            saved = list(backups.glob('*/test.repo'))
            self.assertEqual(len(saved), 1)
            self.assertEqual(saved[0].read_text(), original)

    def test_satellite_version_uses_package_database(self):
        with patch.object(installer.shutil, 'which', side_effect=lambda name: '/usr/bin/rpm' if name == 'rpm' else None), \
             patch.object(installer.subprocess, 'check_output', return_value='0.8.3') as query:
            self.assertTrue(installer.version('xwayland-satellite', '0.7'))
        self.assertEqual(query.call_args.args[0], ['rpm', '-q', '--qf', '%{VERSION}', 'xwayland-satellite'])

    def test_suse_virtual_python_provider(self):
        reply = SimpleNamespace(returncode=0, stdout='<stream><solvable kind="package" name="python313"/></stream>')
        with patch.object(installer.subprocess, 'run', return_value=reply) as query:
            self.assertTrue(installer.suse_available('python3'))
        self.assertIn('--provides', query.call_args.args[0])

    def test_suse_missing_package_is_not_a_repository_failure(self):
        with patch.object(installer.subprocess, 'run', return_value=SimpleNamespace(returncode=104)):
            self.assertFalse(installer.suse_available('unavailable-feature'))

    def test_suse_repository_error_is_not_silently_ignored(self):
        with patch.object(installer.subprocess, 'run', return_value=SimpleNamespace(returncode=4)):
            with self.assertRaises(RuntimeError):
                installer.suse_available('niri')

    def test_suse_dry_run_has_no_side_effects(self):
        with tempfile.TemporaryDirectory() as directory:
            env = {'HOME': directory, 'XDG_CONFIG_HOME': directory + '/config', 'XDG_DATA_HOME': directory + '/data'}
            output = io.StringIO()
            with patch.dict(os.environ, env), patch.object(installer.os, 'geteuid', return_value=1000), \
                 patch.object(installer, 'os_release', return_value={'ID':'opensuse-tumbleweed'}), \
                 patch.object(installer.subprocess, 'run', side_effect=AssertionError('dry-run executed a command')), \
                 patch.object(installer.subprocess, 'check_output', side_effect=AssertionError('dry-run queried a binary')), \
                 patch('sys.argv', ['install.py', '--dry-run']), contextlib.redirect_stdout(output):
                installer.main()
            self.assertEqual(list(Path(directory).iterdir()), [])
            self.assertIn('zypper --non-interactive install', output.getvalue())
            self.assertIn('xwayland-satellite', output.getvalue())
            self.assertNotIn('prepare-opensuse.py', output.getvalue())
            self.assertIn('Would register MacShell Liquid Glass', output.getvalue())
            self.assertIn('Would apply bundled Tahoe GTK theme', output.getvalue())
            self.assertIn('Would install and select bundled MacOS-Like-Dark', output.getvalue())
            self.assertIn('--jobs 1', output.getvalue())

    def test_suse_build_plan_uses_private_prefix(self):
        with patch.object(installer.subprocess, 'run', side_effect=AssertionError('dry-run executed a command')):
            path = installer.build_quickshell('zypper', Path('/tmp/private-prefix'), True)
        self.assertEqual(path, Path('/tmp/private-prefix/bin/quickshell'))





class TahoeRoundtrip(unittest.TestCase):
    @unittest.skipUnless(shutil.which('niri'), 'real niri validator required')
    def test_theme_preserves_settings_and_restores_original_files(self):
        tahoe = load('tahoe', 'tahoe.py')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_home, data = root / 'config', root / 'data'
            gtk = config_home / 'gtk-3.0'
            gtk.mkdir(parents=True)
            (gtk / 'settings.ini').write_text('[Settings]\ngtk-cursor-theme-name=MyCursor\n')
            gtk4 = config_home / 'gtk-4.0'
            gtk4.mkdir()
            (gtk4 / 'gtk.css').write_text('/* personal CSS */\n')
            kitty = config_home / 'kitty'
            kitty.mkdir()
            (kitty / 'kitty.conf').write_text('scrollback_lines 12345\n')
            niri = config_home / 'niri.kdl'
            original = 'prefer-no-csd\nbinds {}\n'
            niri.write_text(original)
            tahoe.apply(config_home, data, niri, 'Dark')
            self.assertIn('MyCursor', (gtk / 'settings.ini').read_text())
            self.assertIn('scrollback_lines 12345', (kitty / 'kitty.conf').read_text())
            self.assertNotIn('prefer-no-csd', niri.read_text())
            tahoe.apply(config_home, data, niri, 'Light')
            self.assertEqual(niri.read_text().count(tahoe.BEGIN), 1)
            tahoe.restore(config_home, data)
            self.assertEqual(niri.read_text(), original)
            self.assertEqual((gtk4 / 'gtk.css').read_text(), '/* personal CSS */\n')
            self.assertEqual((kitty / 'kitty.conf').read_text(), 'scrollback_lines 12345\n')

class CursorConfiguration(unittest.TestCase):
    @unittest.skipUnless(shutil.which('niri'), 'real niri validator required')
    def test_bibata_preserves_cursor_behaviour_and_other_gtk_settings(self):
        cursor = load('cursor', 'cursor.py')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_home, data = root / 'config', root / 'data'
            config_home.mkdir()
            gtk = config_home / 'gtk-3.0'
            gtk.mkdir()
            (gtk / 'settings.ini').write_text('[Settings]\ngtk-theme-name=MyTheme\n')
            niri = config_home / 'niri.kdl'
            original = 'cursor {\n    xcursor-theme "Old"\n    xcursor-size 48\n    hide-when-typing\n}\nbinds {}\n'
            niri.write_text(original)
            with patch('pathlib.Path.home', return_value=root):
                cursor.apply(installer, config_home, data, niri, 20)
                cursor.apply(installer, config_home, data, niri, 20)
            self.assertTrue((root / '.icons/Bibata-Modern-Classic/cursors/default').is_file())
            text = niri.read_text()
            self.assertEqual(text.count('xcursor-theme'), 1)
            self.assertIn('hide-when-typing', text)
            self.assertIn('xcursor-size 20', text)
            self.assertIn('MyTheme', (gtk / 'settings.ini').read_text())
            self.assertEqual(niri.with_name(niri.name + '.before-bibata').read_text(), original)


class UpstreamSettings(unittest.TestCase):
    def test_input_preserves_layout_and_unrelated_settings(self):
        settings = load('niri_settings', 'niri-settings.py')
        original = 'input {\nkeyboard { xkb { layout "us,ru"; }; track-layout "window"; }\nmouse { natural-scroll; left-handed; }\n}\nlayout { gaps 8; }\n'
        after = settings.edit_block(original, 'input', {'keyboard': [('repeat-rate', 'repeat-rate 40')],
            'mouse': [('natural-scroll', None), ('accel-speed', 'accel-speed 0.2')]})
        self.assertIn('layout "us,ru"', after)
        self.assertIn('track-layout "window"', after)
        self.assertIn('left-handed', after)
        self.assertNotIn('natural-scroll', after)
        self.assertIn('layout { gaps 8; }', after)
        self.assertIn('repeat-rate 40', after)
        if shutil.which('niri'):
            with tempfile.TemporaryDirectory() as directory:
                candidate = Path(directory)/'config.kdl'
                candidate.write_text(after)
                result = subprocess.run(['niri','validate','--config',str(candidate)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                self.assertEqual(result.returncode, 0, result.stdout)


if __name__ == '__main__':
    unittest.main()

class QuickshellSelection(unittest.TestCase):
    def test_new_quickshell_is_found_even_when_old_qs_precedes_it(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); old = root / 'qs'; new = root / 'quickshell'
            old.touch(); new.touch()
            with patch.object(installer.shutil, 'which', side_effect=lambda name: str(old if name == 'qs' else new)), patch.object(installer, 'version', side_effect=lambda path, minimum: Path(path) == new):
                self.assertEqual(installer.compatible_quickshell(root / 'private'), new)
