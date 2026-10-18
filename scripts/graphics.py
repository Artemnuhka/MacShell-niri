#!/usr/bin/env python3
"""Read-only graphics diagnostics and an isolated NVIDIA compositor profile."""
import json
import os
from pathlib import Path
import sys

PROFILE_NAME = 'MacShell niri buffer pool'


def detect(root=Path('/sys')):
    cards = []
    for device in sorted((root / 'class/drm').glob('card[0-9]*')):
        if '-' in device.name:
            continue
        try:
            vendor = (device / 'device/vendor').read_text().strip().lower()
            driver = (device / 'device/driver').resolve().name if (device / 'device/driver').exists() else 'unknown'
            cards.append({'card': device.name, 'vendor': vendor, 'driver': driver})
        except OSError:
            continue
    kms = root / 'module/nvidia_drm/parameters/modeset'
    try:
        modeset = kms.read_text().strip().lower() in ('y', '1', 'yes')
    except OSError:
        modeset = None
    return {'gpus': cards, 'nvidia': any(c['vendor'] == '0x10de' for c in cards), 'nvidia_drm_modeset': modeset}


def configure(home=None, root=Path('/sys')):
    state = detect(root)
    if not state['nvidia']:
        return False
    folder = (home or Path.home()) / '.nv/nvidia-application-profiles-rc.d'
    path = folder / '50-macshell-niri.json'
    profile = {'rules': [{'pattern': {'feature': 'procname', 'matches': name}, 'profile': PROFILE_NAME}
                         for name in ('niri', 'niri-glass')],
               'profiles': [{'name': PROFILE_NAME, 'settings': [{'key': 'GLVidHeapReuseRatio', 'value': 0}]}]}
    content = json.dumps(profile, indent=2) + '\n'
    if path.is_file() and path.read_text() == content:
        return False
    folder.mkdir(parents=True, exist_ok=True)
    # Only our own dedicated file is managed; all other driver profiles remain intact.
    if path.exists():
        import shutil
        import time
        backups = folder.parent / 'macshell-profile-backups'
        backups.mkdir(exist_ok=True)
        shutil.copy2(path, backups / (path.name + '-' + str(time.time_ns())))
    temporary = folder / '.macshell-niri.tmp'
    temporary.write_text(content)
    temporary.replace(path)
    return True


def report():
    state = detect()
    state['environment'] = {name: os.environ[name] for name in (
        'QT_QPA_PLATFORM', 'QT_QUICK_BACKEND', 'QSG_RHI_BACKEND', 'LIBGL_ALWAYS_SOFTWARE',
        'GBM_BACKEND', '__GLX_VENDOR_LIBRARY_NAME', '__NV_PRIME_RENDER_OFFLOAD', '__GL_APPLICATION_PROFILE') if name in os.environ}
    notes = []
    if state['nvidia'] and state['nvidia_drm_modeset'] is not True:
        notes.append('Check NVIDIA DRM KMS (nvidia_drm modeset=1); MacShell does not edit boot or driver configuration.')
    if state['environment'].get('LIBGL_ALWAYS_SOFTWARE') == '1' or state['environment'].get('QT_QUICK_BACKEND') == 'software':
        notes.append('Inherited software rendering is enabled; hardware glass may be unavailable.')
    if state['environment'].get('__GL_APPLICATION_PROFILE') == '0':
        notes.append('NVIDIA application profiles are explicitly disabled in the environment.')
    state['notes'] = notes
    print(json.dumps(state, indent=2))


if __name__ == '__main__':
    if sys.argv[1:] == ['configure']:
        if configure():
            print('Installed user NVIDIA profile for niri and niri-glass; applies on next compositor start.')
    else:
        report()
