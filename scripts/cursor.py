#!/usr/bin/env python3
"""Install the bundled Bibata cursor and conservatively configure niri/GTK."""
import configparser
import hashlib
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

THEME = 'Bibata-Modern-Classic'
SHA256 = '7d3495864e5bbef02f5e77de760b2905903b63c71495a78ef6306d19a3b556d8'


def apply(installer, config, data, niri_config, size=20, dry=False, global_preferences=True):
    if dry:
        print(f'Would install {THEME}, set niri and GTK cursor size {size}, backing up configuration.')
        return
    archive = Path(__file__).resolve().parent.parent / 'vendor/bibata' / (THEME + '.tar.xz')
    if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
        raise RuntimeError('Bibata archive checksum mismatch')
    parser = installer.load_configurer()
    text = niri_config.read_text()
    root = next((node for node in parser.nodes(text) if node[0] == 'cursor'), None)
    settings = f'    xcursor-theme "{THEME}"\n    xcursor-size {size}\n'
    if root:
        _, tokens, start, end = root
        a = next(t[2] for t in tokens if t[0] == '{')
        b = next(t[1] for t in reversed(tokens) if t[0] == '}')
        inner = text[a:b]
        for name, _, x, y in reversed(parser.nodes(inner)):
            if name in ('xcursor-theme', 'xcursor-size'):
                inner = inner[:x] + inner[y:]
        text = text[:a] + '\n' + settings + inner.strip() + '\n' + text[b:]
    else:
        text = text.rstrip() + '\n\ncursor {\n' + settings + '}\n'
    target = data / 'icons' / THEME
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='macshell-cursor-') as directory:
        stage = Path(directory)
        candidate = stage / 'niri.kdl'
        candidate.write_text(text)
        subprocess.run(['niri', 'validate', '--config', str(candidate)], check=True)
        if not target.exists():
            with tarfile.open(archive) as package:
                for member in package.getmembers():
                    path = Path(member.name)
                    if (path.is_absolute() or '..' in path.parts or path.parts[0] != THEME
                        or not (member.isfile() or member.isdir() or member.issym())
                        or (member.issym() and Path(member.linkname).name != member.linkname)):
                        raise RuntimeError('Unsafe member in bundled Bibata archive')
                package.extractall(stage)
            shutil.copytree(stage / THEME, target, symlinks=True)
        # Some xcursor loaders omit /icons when XDG_DATA_HOME is explicitly set.
        # Keep the XDG installation and expose the conventional search path too.
        legacy = Path.home() / '.icons' / THEME
        if not legacy.exists() and not legacy.is_symlink():
            legacy.parent.mkdir(parents=True, exist_ok=True)
            legacy.symlink_to(target.resolve(), target_is_directory=True)
        if text != niri_config.read_text():
            backup = niri_config.with_name(niri_config.name + '.before-bibata')
            if not backup.exists():
                shutil.copy2(niri_config, backup)
            niri_config.write_text(text)
    if not global_preferences:
        print(f'Cursor installed for the private niri session only: {THEME}, {size}px.')
        return
    for version in ('3.0', '4.0'):
        path = config / ('gtk-' + version) / 'settings.ini'
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and not path.with_suffix('.before-bibata').exists():
            shutil.copy2(path, path.with_suffix('.before-bibata'))
        settings = configparser.ConfigParser(interpolation=None)
        settings.optionxform = str
        settings.read(path)
        if not settings.has_section('Settings'):
            settings.add_section('Settings')
        settings['Settings'].update({'gtk-cursor-theme-name': THEME, 'gtk-cursor-theme-size': str(size)})
        with path.open('w') as output:
            settings.write(output)
    print(f'Cursor: {THEME}, {size}px. New applications inherit the niri cursor environment.')
