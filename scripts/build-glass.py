#!/usr/bin/env python3
"""Build an opt-in niri compositor with scene refraction in a private user prefix.

No system compositor binary, GPU driver or existing session entry is replaced.
The third-party install scripts are deliberately not executed.
"""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import pwd
import shlex

NIRI_REPO = 'https://github.com/niri-wm/niri.git'
NIRI_REV = '49fc6117fd6c043adaa2ead316b82db5ed735d36'
GLASS_REPO = 'https://github.com/zaroutt/Niri-glass.git'
GLASS_REV = '72ee16331994b43a9460b713b828a218a023a857'
OVERLAY = ['src/render_helpers/liquid_glass.rs', 'src/render_helpers/background_effect.rs',
           'src/render_helpers/framebuffer_effect.rs', 'src/render_helpers/xray.rs',
           'src/render_helpers/mod.rs', 'src/render_helpers/shaders/clipped_surface.frag',
           'src/render_helpers/shaders/mod.rs', 'niri-config/src/appearance.rs']
DEPS = ['rust', 'cargo', 'clang', 'git', 'gcc-c++', 'pkgconf-pkg-config',
        'pkgconfig(libudev)', 'pkgconfig(gbm)', 'pkgconfig(xkbcommon)', 'pkgconfig(egl)',
        'pkgconfig(wayland-client)', 'pkgconfig(libinput)', 'pkgconfig(dbus-1)',
        'pkgconfig(libsystemd)', 'pkgconfig(libseat)', 'pkgconfig(libpipewire-0.3)',
        'pkgconfig(pango)', 'pkgconfig(pangocairo)', 'pkgconfig(cairo-gobject)', 'pkgconfig(libdisplay-info)']


def ensure(installer, data, skip_deps=False, dry=False, force=False):
    prefix = data / 'macshell-niri/niri-glass'
    binary = prefix / 'bin/niri-glass'
    if not force and binary.is_file():
        try:
            sources = json.loads((prefix / 'sources.json').read_text())
            if sources.get('niri') == NIRI_REV and sources.get('glass') == GLASS_REV:
                installer.run([binary, '--version'], dry)
                print('Reusing the installed pinned Liquid Glass compositor; no compilation.')
                return binary
        except (OSError, ValueError):
            pass
    if skip_deps and not dry:
        raise RuntimeError('Liquid Glass compositor is not installed. Run without --skip-deps, or use --no-glass.')
    print('Building Liquid Glass: one compilation job, low CPU priority. The first build can take a long time.')
    return build(installer, data, skip_deps, dry)


def session_path():
    return Path('/usr/local/share/wayland-sessions') / f'macshell-glass-{os.getuid()}.desktop'


def login_session(installer, data, bindir, dry=False):
    destination = session_path()
    if dry:
        print(f'Would register MacShell Liquid Glass in the login manager: {destination}')
        return
    if destination.exists() and f'X-MacShell-Owner={os.getuid()}\n' not in destination.read_text():
        raise RuntimeError(f'Refusing to overwrite an unmanaged session: {destination}')
    path = str(bindir / 'macshell-glass-session')
    escaped = path.replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$').replace('%', '%%')
    staged = data / 'macshell-niri/login-session.desktop'
    staged.parent.mkdir(parents=True, exist_ok=True)
    staged.write_text('[Desktop Entry]\nType=Application\n' +
        f'Name=MacShell Liquid Glass ({pwd.getpwuid(os.getuid()).pw_name})\n' +
        'Comment=MacShell with live scene refraction on niri\n' +
        f'Exec="{escaped}"\nDesktopNames=niri;\nX-MacShell-Owner={os.getuid()}\n')
    installer.run(['sudo', 'install', '-D', '-m', '0644', staged, destination])
    print('At the next login, select MacShell Liquid Glass. No session is started by this installer.')


def remove_login_session(installer):
    path = session_path()
    if path.exists():
        if f'X-MacShell-Owner={os.getuid()}\n' not in path.read_text():
            raise RuntimeError(f'Refusing to remove an unmanaged session: {path}')
        installer.run(['sudo', 'rm', '--', path])


def pinned_checkout(installer, repo, revision, path, dry):
    if not path.exists():
        installer.run(['git', 'init', path], dry)
        installer.run(['git', '-C', path, 'remote', 'add', 'origin', repo], dry)
    installer.run(['git', '-C', path, 'fetch', '--depth', '1', 'origin', revision], dry)
    installer.run(['git', '-C', path, 'checkout', '--detach', '--force', revision], dry)
    if not dry:
        actual = subprocess.check_output(['git', '-C', path, 'rev-parse', 'HEAD'], text=True).strip()
        if actual != revision:
            raise RuntimeError('Compositor source revision mismatch')


def build(installer, data, skip_deps=False, dry=False):
    if 'suse' not in installer.os_release().get('ID', ''):
        raise RuntimeError('Automatic glass compositor build is currently implemented for openSUSE')
    if not skip_deps:
        installer.package_install('zypper', DEPS, dry)
    prefix = data / 'macshell-niri/niri-glass'
    source, overlay = prefix / 'source', prefix / 'overlay'
    pinned_checkout(installer, NIRI_REPO, NIRI_REV, source, dry)
    pinned_checkout(installer, GLASS_REPO, GLASS_REV, overlay, dry)
    if not dry:
        for name in OVERLAY:
            shutil.copy2(overlay / name, source / name)
        # Suppress the upstream prototype's per-frame debug warnings.
        path = source / 'src/render_helpers/background_effect.rs'
        text = path.read_text().replace('warn!("LIQUID GLASS:', 'trace!("LIQUID GLASS:')
        if 'trace!("LIQUID GLASS:' in text and 'use tracing::trace;' not in text:
            text = 'use tracing::trace;\n' + text
        path.write_text(text)
        spec = importlib.util.spec_from_file_location('patch_refraction', Path(__file__).with_name('patch-refraction.py'))
        optical_patch = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(optical_patch)
        optical_patch.apply(source)
    env = dict(os.environ, CARGO_BUILD_JOBS='1', CARGO_PROFILE_RELEASE_DEBUG='0',
               CARGO_PROFILE_RELEASE_LTO='false', CARGO_PROFILE_RELEASE_CODEGEN_UNITS='8')
    installer.run(['nice', '-n', '19', 'cargo', 'build', '--release', '--locked', '--jobs', '1'], dry,
                  cwd=None if dry else source, env=env)
    binary = prefix / 'bin/niri-glass'
    if not dry:
        binary.parent.mkdir(parents=True, exist_ok=True)
        staged_binary = binary.with_suffix('.new')
        shutil.copy2(source / 'target/release/niri', staged_binary)
        staged_binary.replace(binary)
        shutil.copy2(overlay / 'LICENSE', prefix / 'LICENSE.Niri-glass')
        (prefix / 'sources.json').write_text(json.dumps({'niri': NIRI_REV, 'glass': GLASS_REV}, indent=2))
    return binary


def session(installer, data, config, bindir, niri_config, binary, dry=False):
    private_config = config / 'niri/macshell-glass.kdl'
    wrapper = bindir / 'macshell-glass-session'
    if dry:
        print(f'Would create private refraction config {private_config} and session launcher {wrapper}')
        return
    if private_config.is_symlink():
        raise RuntimeError('Refusing a symlinked private compositor config')
    text = niri_config.read_text()
    for name, _, a, b in reversed(installer.load_configurer().nodes(text)):
        if name == 'blur':
            text = text[:a] + text[b:]
    text += '\n// BEGIN MacShell compositor lenses\nblur { passes 1; offset 0.4; noise 0.005; saturation 1.0; }\n'
    # Rounded region requests are rasterized into rectangles by the protocol.
    # Each dedicated pane has its own namespace and geometry, so its lens gets the actual radius.
    for radius in range(65):
        text += f'''\nlayer-rule {{
    match namespace="^macglasspane-r{radius}$"
    geometry-corner-radius {radius}
    background-effect {{
        xray false
        blur true
        liquid-glass {{
            refraction-strength 2.2
        }}
    }}
}}
'''
    text += '// END MacShell compositor lenses\n'
    if private_config.exists():
        # Updates retain custom optics, input settings, outputs and keybindings.
        text = private_config.read_text()
    candidate = private_config.with_suffix('.candidate.kdl')
    try:
        candidate.write_text(text)
        installer.run([binary, 'validate', '--config', candidate])
        installer.backup(private_config)
        candidate.replace(private_config)
    finally:
        candidate.unlink(missing_ok=True)
    bindir.mkdir(parents=True, exist_ok=True)
    installer.backup(wrapper)
    wrapper.write_text('#!/bin/sh\nset -eu\n' +
        'if [ "$(id -u)" != ' + shlex.quote(str(os.getuid())) + ' ]; then\n' +
        '    echo "This MacShell session belongs to another user." >&2; exit 1\nfi\n' +
        'if [ -n "${WAYLAND_DISPLAY:-}" ] || [ -n "${DISPLAY:-}" ]; then\n' +
        '    echo "Start macshell-glass-session from a text TTY, outside a graphical session." >&2\n' +
        '    exit 1\nfi\nexport MACSHELL_REAL_GLASS=1\n' +
        'export MACSHELL_GLASS_CONFIG=' + shlex.quote(str(private_config)) + '\n' +
        'export MACSHELL_GLASS_BINARY=' + shlex.quote(str(binary)) + '\nexec ' +
        shlex.quote(str(binary)) + ' --session --config ' + shlex.quote(str(private_config)) + ' "$@"\n')
    wrapper.chmod(0o755)
    print(f'Real refraction session: {wrapper}')
    print('Log out before starting this session. The TTY launcher is also available.')
