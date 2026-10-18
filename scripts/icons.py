"""Install the pinned original MacOS-Like icon themes in the user's data directory."""
import configparser
import datetime
import hashlib
import json
from pathlib import Path
import posixpath
import shutil
import subprocess
import tarfile
import tempfile

DIGEST = '47943b06cf99b444618fa4ad3a78b8a8de23d1a140f5460a50aa96973de16988'
THEMES = ('MacOS-Like-Light', 'MacOS-Like-Dark')


def validate(package):
    for member in package.getmembers():
        parts = Path(member.name).parts
        if not parts or parts[0] not in THEMES or Path(member.name).is_absolute() or '..' in parts:
            raise RuntimeError('Unsafe icon archive path')
        if not (member.isfile() or member.isdir() or member.issym()):
            raise RuntimeError('Unsupported icon archive entry')
        if member.issym():
            destination = posixpath.normpath(posixpath.join(posixpath.dirname(member.name), member.linkname))
            if member.linkname.startswith('/') or destination.split('/')[0] not in THEMES:
                raise RuntimeError('Icon alias escapes the theme')


def verify():
    bundle = Path(__file__).resolve().parents[1] / 'vendor/macos-like/themes.tar.xz'
    if hashlib.sha256(bundle.read_bytes()).hexdigest() != DIGEST:
        raise RuntimeError('Bundled MacOS-Like checksum mismatch')
    with tarfile.open(bundle) as package:
        validate(package)
    return bundle


def apply(config, data, theme, dry=False, global_preferences=True):
    if theme == 'keep':
        return
    if theme not in THEMES:
        raise ValueError('Unknown icon theme')
    if dry:
        print(f'Would install and select bundled {theme} icons (user-only).')
        return
    destination = data / 'icons'
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    def current(name):
        marker = destination / name / '.macshell-icon-bundle'
        return marker.is_file() and marker.read_text().strip() == DIGEST
    if not all(current(name) for name in THEMES):
        bundle = verify()
        destination = data / 'icons'
        destination.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        with tempfile.TemporaryDirectory(prefix='.macshell-icons-', dir=destination) as directory:
            stage = Path(directory)
            with tarfile.open(bundle) as package:
                validate(package)
                package.extractall(stage, filter='data')
            for name in THEMES:
                target = destination / name
                marker = target / '.macshell-icon-bundle'
                if marker.is_file() and marker.read_text().strip() == DIGEST:
                    continue
                if (target.exists() or target.is_symlink()) and not marker.is_file():
                    raise RuntimeError(f'Kept existing unmanaged icon theme: {target}. Use --icons keep.')
                if target.exists() or target.is_symlink():
                    target.rename(target.with_name(name + '.backup-' + stamp))
                (stage / name / '.macshell-icon-bundle').write_text(DIGEST + '\n')
                (stage / name).rename(target)
    if global_preferences:
        for folder, section, key in [('gtk-3.0/settings.ini', 'Settings', 'gtk-icon-theme-name'),
                                     ('gtk-4.0/settings.ini', 'Settings', 'gtk-icon-theme-name'),
                                     ('qt6ct/qt6ct.conf', 'Appearance', 'icon_theme')]:
            path = config / folder
            if folder.startswith('qt6ct') and not path.is_file():
                continue
            if path.is_symlink():
                raise RuntimeError(f'Refusing a symlinked icon preference file: {path}')
            preferences = configparser.ConfigParser(interpolation=None)
            preferences.optionxform = str
            if path.is_file():
                preferences.read(path)
            if preferences.has_section(section) and preferences.get(section, key, fallback='') == theme:
                continue
            if path.exists():
                shutil.copy2(path, path.with_name(path.name + '.icons-backup-' + stamp))
            path.parent.mkdir(parents=True, exist_ok=True)
            if not preferences.has_section(section):
                preferences.add_section(section)
            preferences[section][key] = theme
            with path.open('w') as stream:
                preferences.write(stream)
    state = data / 'macshell-niri/icon-theme.json'
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(json.dumps({'theme': theme, 'digest': DIGEST}))
    if global_preferences and shutil.which('gsettings'):
        subprocess.run(['gsettings', 'set', 'org.gnome.desktop.interface', 'icon-theme', theme],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f'Icons ready: {theme}; existing preference files were backed up.')
