#!/usr/bin/env python3
"""Scope the Ghostty OpenGL compatibility workaround to VirtualBox and this app."""
import os
from pathlib import Path
import shlex
import sys

APP='com.mitchellh.ghostty.desktop'
MARKER='X-MacShell-VirtualBox-Ghostty=true'


def virtualbox():
    try:return 'virtualbox' in Path('/sys/class/dmi/id/product_name').read_text().lower()
    except OSError:return False


def binary():
    # Never resolve the user wrapper back into itself.
    return next((p for p in (Path('/usr/bin/ghostty'),Path('/usr/local/bin/ghostty')) if p.is_file()),None)


def install(config_root, bindir, data):
    exe=binary()
    if not virtualbox() or not exe:return False
    desktop_source=next((p for p in (Path('/usr/share/applications')/APP,Path('/usr/local/share/applications')/APP) if p.is_file()),None)
    desktop=data/'applications'/APP
    launcher=bindir/'ghostty'
    if launcher.exists() and 'ghostty-compat.py' not in launcher.read_text(errors='replace'):
        print('Kept existing user ghostty launcher; no override installed.')
        return False
    if desktop.exists() and MARKER not in desktop.read_text():
        print('Kept existing user Ghostty desktop override; no override installed.')
        return False
    bindir.mkdir(parents=True,exist_ok=True)
    launcher.write_text('#!/bin/sh\nexec '+shlex.quote(sys.executable)+' '+shlex.quote(str(config_root/'scripts/ghostty-compat.py'))+' "$@"\n')
    launcher.chmod(0o755)
    if desktop_source:
        text=desktop_source.read_text()
        lines=[]
        for line in text.splitlines():
            if line.startswith('Exec='):
                command=line[len('Exec='):]
                prefix=next((name for name in (str(exe),'ghostty') if command==name or command.startswith(name+' ')),None)
                if prefix is None:continue
                suffix=command[len(prefix):]
                line='Exec="'+str(launcher).replace('\\','\\\\').replace('"','\\"')+'"'+suffix
            elif line.startswith('TryExec='):line='TryExec='+str(launcher)
            elif line.startswith('DBusActivatable='):line='DBusActivatable=false'
            lines.append(line)
        lines.insert(1,MARKER)
        desktop.parent.mkdir(parents=True,exist_ok=True)
        desktop.write_text('\n'.join(lines)+'\n')
    print('Installed Ghostty compatibility launcher for VirtualBox (OpenGL via Mesa software rendering).')
    return True


def launch():
    exe=binary()
    if not exe:sys.exit('Ghostty is not installed.')
    if virtualbox() and os.environ.get('NIRI_SOCKET'):
        os.environ.setdefault('LIBGL_ALWAYS_SOFTWARE','1')
        os.environ.setdefault('GSK_RENDERER','cairo')
    os.execv(str(exe),[str(exe),*sys.argv[1:]])

if __name__=='__main__':
    if sys.argv[1:]==['--install']:
        home=Path.home()
        install(Path(__file__).resolve().parent.parent,home/'.local/bin',Path(os.environ.get('XDG_DATA_HOME',str(home/'.local/share'))))
    else:launch()
