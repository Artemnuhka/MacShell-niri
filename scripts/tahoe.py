#!/usr/bin/env python3
"""User-only, reversible MacTahoe GTK and niri window styling."""
import configparser
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

REVISION = '1e45e19f510edb8cde18fa84d6cd5319f60b086b'
DIGESTS = {'Light': 'cfbc592771b487e51375f28d4a3d25cb94d3abaaaece57d6b371d8186d308991',
           'Dark': '08e816e5352247955d1cfa64b44af0aeee77cfbc52b52b4f4d4becf650cf5e15'}
BEGIN = '// BEGIN macshell Tahoe windows'
END = '// END macshell Tahoe windows'
RULE = '''window-rule {
    geometry-corner-radius 18
    clip-to-geometry true
    border { off; }
    focus-ring { off; }
    shadow {
        on
        softness 28
        spread 2
        offset x=0 y=8
        color "#00000045"
        inactive-color "#00000025"
    }
}
'''


def copy(source, target):
    if source.is_symlink():
        target.symlink_to(os.readlink(source))
    elif source.is_dir():
        shutil.copytree(source, target, symlinks=True)
    else:
        shutil.copy2(source, target)


def erase(path):
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)


def locations(config, data):
    return data / 'macshell-niri/tahoe-backup', [config / 'gtk-3.0', config / 'gtk-4.0']


def restore(config, data):
    state, _ = locations(config, data)
    manifest = state / 'manifest.json'
    if not manifest.exists():
        raise RuntimeError('No Tahoe backup exists')
    records = json.loads(manifest.read_text())
    current = state.with_name('tahoe-before-restore-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    current.mkdir()
    (current / 'manifest.json').write_text(manifest.read_text())
    for i, record in enumerate(records):
        path = Path(record['path'])
        if path.exists() or path.is_symlink():
            copy(path, current / str(i))
        erase(path)
        if record['existed']:
            copy(state / str(i), path)
    shutil.rmtree(state)
    print('Restored GTK and niri settings saved before Tahoe installation. Theme assets remain installed.')


def apply(config, data, niri_config, color):
    state, paths = locations(config, data)
    paths.append(niri_config)
    paths.append(config / 'kitty')
    for path in paths:
        if path.is_symlink():
            raise RuntimeError(f'Refusing to replace symlinked configuration: {path}')
    spec = importlib.util.spec_from_file_location('niri_configurer', Path(__file__).with_name('configure-niri.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    text = niri_config.read_text()
    if BEGIN in text:
        if text.count(BEGIN) != 1 or text.count(END) != 1:
            raise RuntimeError('Malformed Tahoe window block')
        a, b = text.index(BEGIN), text.index(END) + len(END)
        text = text[:a] + text[b:]
    for name, _, a, b in reversed(module.nodes(text)):
        if name == 'prefer-no-csd':
            text = text[:a] + text[b:]
    text = text.rstrip() + '\n\n' + BEGIN + '\n' + RULE + END + '\n'
    theme = 'MacTahoe-' + color
    archive = Path(__file__).resolve().parent.parent / 'vendor/tahoe' / (theme + '.tar.xz')
    if hashlib.sha256(archive.read_bytes()).hexdigest() != DIGESTS[color]:
        raise RuntimeError('Bundled Tahoe theme checksum mismatch')
    # Stage and validate before touching user settings. Never run an upstream installer.
    with tempfile.TemporaryDirectory(prefix='macshell-tahoe-') as directory:
        stage = Path(directory)
        candidate = stage / 'config.kdl'
        candidate.write_text(text)
        subprocess.run(['niri', 'validate', '--config', str(candidate)], check=True)
        with tarfile.open(archive) as package:
            for member in package.getmembers():
                if not member.name.startswith((theme + '/gtk-3.0/', theme + '/gtk-4.0/')):
                    continue
                if (Path(member.name).is_absolute() or '..' in Path(member.name).parts
                        or member.islnk() or not (member.isfile() or member.isdir() or member.issym())
                        or (member.issym() and (Path(member.linkname).name != member.linkname))):
                    raise RuntimeError('Unsafe member in bundled Tahoe archive')
            selected = [m for m in package.getmembers() if m.name == theme or
                        m.name.startswith((theme + '/gtk-3.0/', theme + '/gtk-4.0/')) or
                        m.name in (theme + '/index.theme', theme + '/gtk-3.0', theme + '/gtk-4.0')]
            package.extractall(stage, members=selected)
        theme_root = data / 'themes' / theme
        theme_root.parent.mkdir(parents=True, exist_ok=True)
        if theme_root.exists() and not (theme_root / '.macshell-theme').exists():
            raise RuntimeError(f'Existing theme is not managed by this installer: {theme_root}')
        state.mkdir(parents=True, exist_ok=True)
        manifest = state / 'manifest.json'
        records = json.loads(manifest.read_text()) if manifest.exists() else []
        for path in paths:
            if any(record['path'] == str(path) for record in records):
                continue
            exists = path.exists() or path.is_symlink()
            if exists:
                copy(path, state / str(len(records)))
            records.append({'path': str(path), 'existed': exists})
        manifest.write_text(json.dumps(records, indent=2))
        erase(theme_root)
        shutil.copytree(stage / theme, theme_root)
        (theme_root / '.macshell-theme').write_text(REVISION + '\n')
        for version in ('3.0', '4.0'):
            dest = config / ('gtk-' + version)
            dest.mkdir(parents=True, exist_ok=True)
            settings = configparser.ConfigParser(interpolation=None)
            settings.optionxform = str
            settings.read(dest / 'settings.ini')
            if not settings.has_section('Settings'):
                settings.add_section('Settings')
            settings['Settings'].update({'gtk-theme-name': theme, 'gtk-decoration-layout': 'close,minimize,maximize:',
                'gtk-application-prefer-dark-theme': 'true' if color == 'Dark' else 'false',
                'gtk-font-name': 'Inter 11'})
            with (dest / 'settings.ini').open('w') as output:
                settings.write(output)
        # GTK4/libadwaita reads user CSS independently of gtk-theme-name.
        gtk4 = config / 'gtk-4.0'
        for filename in ('gtk.css', 'gtk-dark.css'):
            erase(gtk4 / filename)
            (gtk4 / filename).write_text('@import url(' + json.dumps(str(theme_root / 'gtk-4.0' / filename)) + ');\n')
        kitty = config / 'kitty'
        kitty.mkdir(parents=True, exist_ok=True)
        kitty_config = kitty / 'kitty.conf'
        kitty_text = kitty_config.read_text() if kitty_config.exists() else ''
        include = 'include macshell-tahoe.conf'
        if include not in kitty_text.splitlines():
            kitty_config.write_text(kitty_text.rstrip() + '\n' + include + '\n')
        background, foreground = ('#1e1e20', '#f2f2f7') if color == 'Dark' else ('#f5f5f7', '#242426')
        (kitty / 'macshell-tahoe.conf').write_text(
            '# Managed by MacShell Tahoe; restore with install.sh --restore-theme\n'
            f'background {background}\nforeground {foreground}\n'
            'font_family DejaVu Sans Mono\nfont_size 12\nwindow_padding_width 16\n'
            'wayland_titlebar_color background\nhide_window_decorations titlebar-only\n'
            'cursor_shape beam\ncursor_trail 0\nbackground_opacity 1\n')
        niri_config.write_text(text)
    print(f'Applied {theme}: GTK3/GTK4, left window controls, rounded corners and shadows.')
    print(f'Rollback: ./install.sh --restore-theme (backup: {state})')
