#!/usr/bin/env python3
"""Start the niri portal session and publish the shell's colour preference."""
import json
import os
from pathlib import Path
import re
import select
import shutil
import subprocess
import sys

CONFIG = '''# Managed by MacShell niri; applies only to niri sessions.
[preferred]
default=gnome;gtk;
org.freedesktop.impl.portal.Settings=gtk;
org.freedesktop.impl.portal.Screenshot=wlr;
org.freedesktop.impl.portal.ScreenCast=gnome;
org.freedesktop.impl.portal.FileChooser=gtk;
org.freedesktop.impl.portal.Access=gtk;
org.freedesktop.impl.portal.Notification=gtk;
org.freedesktop.impl.portal.Secret=gnome-keyring;
'''
UNIT = 'macshell-niri-session-anchor.service'


def configure(config):
    path = config/'xdg-desktop-portal/niri-portals.conf'
    if path.exists():
        text=path.read_text()
        # A user's hand-written portal routing has priority.
        if not text.startswith('# Managed by MacShell niri;') or text==CONFIG:
            return False
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(CONFIG)
    return True


def compositor_pid():
    match=re.search(r'\.(\d+)\.sock$',os.environ.get('NIRI_SOCKET',''))
    if not match:return None
    pid=int(match[1]);proc=Path('/proc')/str(pid)
    try:
        if proc.stat().st_uid!=os.getuid():return None
        if (proc/'comm').read_text().strip() not in ('niri','niri-glass'):return None
        return pid
    except OSError:return None


def appearance(dark):
    if not compositor_pid() or not shutil.which('gsettings'):return
    subprocess.run(['gsettings','set','org.gnome.desktop.interface','color-scheme','prefer-dark' if dark else 'prefer-light'],check=True)


def ensure():
    pid=compositor_pid()
    if not pid or not shutil.which('systemctl'):return
    config=Path(os.environ.get('XDG_CONFIG_HOME',str(Path.home()/'.config')))
    changed=configure(config)
    variables=[v for v in ('WAYLAND_DISPLAY','DISPLAY','NIRI_SOCKET','XDG_CURRENT_DESKTOP','XDG_SESSION_TYPE') if os.environ.get(v)]
    subprocess.run(['systemctl','--user','import-environment',*variables],check=True)
    if shutil.which('dbus-update-activation-environment'):
        subprocess.run(['dbus-update-activation-environment',*variables],check=True)
    # Direct `niri --session` imports its environment but doesn't own the
    # graphical-session target. Portal units have Requisite= on that target.
    # Bind its lifetime to the compositor, not the restartable Quickshell UI.
    active=subprocess.run(['systemctl','--user','is-active','--quiet',UNIT]).returncode==0
    if not active:
        subprocess.run(['systemd-run','--user','--quiet','--collect','--unit='+UNIT,
                        '--property=BindsTo=graphical-session.target','--property=Before=graphical-session.target',
                        sys.executable,str(Path(__file__).resolve()),'watch',str(pid)],check=True)
    subprocess.run(['systemctl','--user','reset-failed','xdg-desktop-portal.service','xdg-desktop-portal-gtk.service'],check=False,stderr=subprocess.DEVNULL)
    subprocess.run(['systemctl','--user','start','xdg-desktop-portal-gtk.service','xdg-desktop-portal.service'],check=True)
    if changed:
        subprocess.run(['systemctl','--user','restart','xdg-desktop-portal.service'],check=True)


if __name__=='__main__':
    command=sys.argv[1] if len(sys.argv)>1 else 'ensure'
    if command=='watch':
        try:
            fd=os.pidfd_open(int(sys.argv[2]))
        except ProcessLookupError:sys.exit(0)
        try:select.select([fd],[],[])
        finally:os.close(fd)
    elif command=='ensure':ensure()
    elif command=='dark':appearance(True)
    elif command=='light':appearance(False)
