import importlib.util
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('macshell_portals',ROOT/'scripts/portals.py')
portals=importlib.util.module_from_spec(spec);spec.loader.exec_module(portals)

class PortalSession(unittest.TestCase):
    def test_routing_is_niri_specific_and_preserves_user_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            config=Path(directory)
            portals.configure(config)
            path=config/'xdg-desktop-portal/niri-portals.conf'
            self.assertIn('org.freedesktop.impl.portal.Settings=gtk;',path.read_text())
            self.assertIn('org.freedesktop.impl.portal.Screenshot=wlr;',path.read_text())
            self.assertIn('org.freedesktop.impl.portal.ScreenCast=gnome;',path.read_text())
            self.assertFalse((path.parent/'portals.conf').exists())
            self.assertFalse((path.parent/'kde-portals.conf').exists())
            path.write_text('[preferred]\ndefault=kde;\n')
            portals.configure(config)
            self.assertEqual(path.read_text(),'[preferred]\ndefault=kde;\n')

    def test_no_services_or_preferences_change_outside_niri(self):
        with patch.object(portals,'compositor_pid',return_value=None),patch.object(portals.subprocess,'run') as run:
            portals.ensure();portals.appearance(True)
            run.assert_not_called()

    def test_session_target_lifetime_is_bound_to_compositor_not_shell(self):
        with tempfile.TemporaryDirectory() as directory,patch.dict(portals.os.environ,{'XDG_CONFIG_HOME':directory,'WAYLAND_DISPLAY':'wayland-9'}), \
             patch.object(portals,'compositor_pid',return_value=1234),patch.object(portals.shutil,'which',return_value='/usr/bin/tool'), \
             patch.object(portals.subprocess,'run') as run:
            run.side_effect=lambda args,**kw:SimpleNamespace(returncode=1 if 'is-active' in args else 0)
            portals.ensure()
            commands=[call.args[0] for call in run.call_args_list]
            anchor=next(cmd for cmd in commands if cmd[0]=='systemd-run')
            self.assertIn('--property=BindsTo=graphical-session.target',anchor)
            self.assertEqual(anchor[-2:],['watch','1234'])
            self.assertIn(['systemctl','--user','start','xdg-desktop-portal-gtk.service','xdg-desktop-portal.service'],commands)

if __name__=='__main__':unittest.main()
