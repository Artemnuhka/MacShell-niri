"""Install the fork's freely licensed clock fonts into a private font directory."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


def install(data):
    source = Path(__file__).resolve().parents[1] / 'vendor/clock-fonts'
    manifest = json.loads((source / 'manifest.json').read_text())
    target = Path(data) / 'fonts/macshell-clock'
    changed = False
    for name, digest in manifest['files'].items():
        original = source / name
        if Path(name).is_absolute() or '..' in Path(name).parts:
            raise RuntimeError('Invalid bundled clock font path')
        if hashlib.sha256(original.read_bytes()).hexdigest() != digest:
            raise RuntimeError(f'Clock font checksum mismatch: {name}')
        destination = target / name
        if target.is_symlink() or destination.is_symlink() or destination.parent.is_symlink():
            raise RuntimeError('Refusing a symlinked private font directory')
        if destination.is_file() and hashlib.sha256(destination.read_bytes()).hexdigest() == digest:
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original, destination)
        changed = True
    if changed and shutil.which('fc-cache'):
        subprocess.run(['fc-cache', str(target)], check=True)
    print('Clock fonts ready: Roboto Flex, Nunito, Noto Serif Display (OFL).')
