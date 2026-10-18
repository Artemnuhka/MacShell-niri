#!/usr/bin/env python3
"""Restore session services and wallpaper when launching MacShell, never for IPC."""
import json
import os
from pathlib import Path
import shutil
import subprocess


def start_audio():
    if not shutil.which('systemctl'):
        return
    units = []
    for unit in ('pipewire.socket', 'wireplumber.service'):
        if any((Path(prefix) / unit).exists() for prefix in ('/usr/lib/systemd/user', '/lib/systemd/user')):
            units.append(unit)
    if units:
        subprocess.run(['systemctl', '--user', 'daemon-reload'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(['systemctl', '--user', 'start', *units], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def restore_wallpaper():
    if not os.environ.get('WAYLAND_DISPLAY') or not shutil.which('swaybg'):
        return
    # Wallpaper processes in another TTY belong to another Wayland display.
    display = ('WAYLAND_DISPLAY=' + os.environ['WAYLAND_DISPLAY']).encode()
    for process in ('swaybg', 'swww-daemon', 'awww-daemon', 'wpaperd', 'noctalia-shell'):
        result = subprocess.run(['pgrep', '-u', str(os.getuid()), '-x', process],
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        for pid in result.stdout.split():
            try:
                if display in (Path('/proc') / pid / 'environ').read_bytes().split(b'\0'):
                    return
            except OSError:
                continue
    wallpaper = None
    for name in ('macbar', 'macdock'):
        config = Path.home() / '.config' / name / 'settings.json'
        try:
            value = json.loads(config.read_text()).get('wallpaperPath', '')
            candidate = Path(value).expanduser() if value else None
            if candidate and candidate.is_file():
                wallpaper = candidate
                break
        except (OSError, ValueError, TypeError):
            continue
    if wallpaper:
        subprocess.Popen(['swaybg', '-i', str(wallpaper), '-m', 'fill'], stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


if __name__ == '__main__':
    try:
        subprocess.run([__import__('sys').executable, str(Path(__file__).with_name('portals.py')), 'ensure'], check=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as error:
        print('MacShell portal startup failed:', error, file=__import__('sys').stderr)
    start_audio()
    restore_wallpaper()
