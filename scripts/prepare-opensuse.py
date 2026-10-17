#!/usr/bin/env python3
"""Prepare only the openSUSE dependencies needed by this desktop session."""
import argparse
import datetime
import os
from pathlib import Path
import re
import shutil
import subprocess


def is_virtualbox():
    path = Path('/sys/class/dmi/id/product_name')
    return path.exists() and 'virtualbox' in path.read_text().lower()


def mirrors(repo_dir=Path('/etc/zypp/repos.d'), backup_root=Path('/var/lib/macshell-niri/backups')):
    # Upgrade official endpoints only; leave custom mirrors and credentials intact.
    pattern = re.compile(r'http://((?:download|codecs)\.opensuse\.org)(?=[:/\s]|$)')
    changes = []
    for path in sorted(repo_dir.glob('*.repo')):
        original = path.read_text()
        updated = pattern.sub(r'https://\1', original)
        if updated != original:
            changes.append((path, updated))
    if not changes:
        return
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backup = backup_root / ('repos-' + stamp)
    backup.mkdir(parents=True)
    for path, updated in changes:
        shutil.copy2(path, backup / path.name)
        path.write_text(updated)
        print(f'Official repository switched to HTTPS: {path}', flush=True)
    print(f'Repository backups: {backup}', flush=True)


def graphics():
    if not is_virtualbox():
        return
    base = subprocess.run(['rpm', '-q', 'kernel-default-base'], stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL).returncode == 0
    if base:
        # Explicit removal request resolves the full/base kernel conflict without
        # --force-resolution and without changing the host's VirtualBox settings.
        print('VirtualBox: replacing the stripped kernel with the graphics-capable kernel-default.', flush=True)
        subprocess.run(['zypper', '--non-interactive', 'install', '--no-recommends',
                        '--', 'kernel-default', '-kernel-default-base'], check=True)
    if not list(Path('/dev/dri').glob('renderD*')):
        result = subprocess.run(['modprobe', 'vmwgfx'], check=False)
        if result.returncode or not list(Path('/dev/dri').glob('renderD*')):
            print('VirtualBox: graphics driver needs a guest reboot before starting niri.', flush=True)
            return
    print('VirtualBox: DRM render device is available.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=['mirrors', 'graphics'])
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error('This helper is called by the installer through sudo')
    release = Path('/etc/os-release').read_text().lower()
    if 'suse' not in release:
        parser.error('This helper supports openSUSE only')
    if not is_virtualbox():
        parser.error('VM preparation is restricted to VirtualBox guests')
    (mirrors if args.phase == 'mirrors' else graphics)()
