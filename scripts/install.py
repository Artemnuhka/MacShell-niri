#!/usr/bin/env python3
"""MacShell niri installer. Does not start a graphical session or shell."""
import argparse
import datetime
import importlib.util
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

# Even dry-run must not create import caches in the source checkout.
sys.dont_write_bytecode = True

SOURCE = Path(__file__).resolve().parent.parent
QS_TAG = 'v0.3.2'


def load_icons():
    spec = importlib.util.spec_from_file_location('macshell_icons', SOURCE / 'scripts/icons.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def os_release():
    info = {}
    for line in Path('/etc/os-release').read_text().splitlines():
        if '=' in line:
            key, value = line.split('=', 1)
            info[key] = value.strip('"')
    return info


def run(command, dry=False, **kwargs):
    print('+ ' + shlex.join(map(str, command)), flush=True)
    if dry:
        return None
    return subprocess.run(list(map(str, command)), check=True, **kwargs)


def version(binary, minimum, dry=False):
    if dry:
        print(f'Would require {binary} >= {minimum}')
        return True
    if Path(binary).name == 'xwayland-satellite':
        # satellite forwards Xserver options and has no --version flag.
        # Asking the package database does not accidentally start an X server.
        if shutil.which('rpm'):
            command = ['rpm', '-q', '--qf', '%{VERSION}', 'xwayland-satellite']
        elif shutil.which('pacman'):
            command = ['pacman', '-Q', 'xwayland-satellite']
        else:
            raise RuntimeError('Cannot check satellite version: install a distribution package >= 0.7')
    else:
        command = [str(binary), '--version']
    output = subprocess.check_output(command, stderr=subprocess.STDOUT, text=True)
    match = re.search(r'(?<!\d)(\d+)\.(\d+)(?:\.(\d+))?', output)
    if not match:
        raise RuntimeError(f'Cannot determine version of {binary}: {output.strip()}')
    current = tuple(int(x or 0) for x in match.groups())
    wanted = tuple(int(x) for x in minimum.split('.'))
    wanted += (0,) * (3 - len(wanted))
    return current >= wanted


def compatible_quickshell(private_prefix):
    candidates = [private_prefix / 'bin/quickshell', shutil.which('qs'), shutil.which('quickshell')]
    for candidate in dict.fromkeys(str(p) for p in candidates if p):
        try:
            if Path(candidate).is_file() and version(candidate, '0.3.2'):
                return Path(candidate)
        except (OSError, RuntimeError, subprocess.SubprocessError):
            continue
    return None


def guard_suse_transaction(xml):
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise RuntimeError('Cannot validate the package plan; installation cancelled') from exc
    summary = root.find('.//install-summary')
    if summary is None:
        return
    blocked = []
    for group in summary:
        for package in group.iter('solvable'):
            name = package.get('name', '')
            protected = re.search(r'(^kernel-|(^|-)kmp-|nvidia|cuda|nouveau|bbswitch)', name, re.I)
            if group.tag in ('to-remove', 'to-change-vendor') or protected:
                blocked.append(f'{group.tag}: {name}')
    if blocked:
        raise RuntimeError('Unsafe package plan rejected before installation: ' + ', '.join(blocked))


def package_install(manager, packages, dry=False):
    prefix = ['sudo'] if os.geteuid() else []
    if manager == 'zypper':
        if not dry:
            plan = subprocess.run(prefix + ['zypper', '--xmlout', '--non-interactive', 'install',
                '--dry-run', '--no-recommends'] + packages, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            if plan.returncode:
                raise RuntimeError('Package plan could not be resolved; no packages were installed.\n' + plan.stdout)
            guard_suse_transaction(plan.stdout)
        command = prefix + ['zypper', '--non-interactive', 'install', '--no-recommends']
    elif manager == 'pacman':
        command = prefix + ['pacman', '-S', '--needed', '--noconfirm']
    elif manager == 'dnf':
        command = prefix + ['dnf', 'install', '-y']
    else:
        raise RuntimeError('Unsupported package manager; install dependencies manually and use --skip-deps')
    run(command + packages, dry)


def suse_available(package, dry=False):
    if dry:
        return True
    query = subprocess.run(['zypper', '--xmlout', '--non-interactive', 'search', '--provides', '--match-exact', package],
                           stdout=subprocess.PIPE, text=True, check=False)
    if query.returncode == 104:  # ZYPPER_EXIT_INF_CAP_NOT_FOUND
        return False
    if query.returncode:
        raise RuntimeError('Cannot query zypper repositories; refresh repositories and retry')
    tree = ET.fromstring(query.stdout)
    return any(n.get('kind') == 'package' for n in tree.iter('solvable'))


def build_quickshell(manager, prefix, dry):
    if manager != 'zypper':
        raise RuntimeError('Automatic source build is implemented for openSUSE. Install Quickshell >= 0.3.2 and retry.')
    package_install(manager, ['git', 'cmake', 'ninja', 'gcc-c++', 'pkgconf-pkg-config',
        'qt6-base-devel', 'qt6-base-private-devel', 'qt6-declarative-devel', 'qt6-declarative-private-devel',
        'qt6-wayland-devel', 'qt6-wayland-private-devel', 'qt6-shadertools-devel',
        'libdrm-devel', 'pkgconfig(gbm)', 'pkgconfig(wayland-client)', 'wayland-protocols-devel',
        'pipewire-devel', 'vulkan-headers', 'spirv-tools', 'cli11-devel', 'jemalloc-devel', 'pam-devel'], dry)
    # Kept in a private installation prefix so system Quickshell is unaffected.
    if dry:
        build_root = Path('<temporary-build>')
        context = None
    else:
        context = tempfile.TemporaryDirectory(prefix='macshell-quickshell-')
        build_root = Path(context.name)
    try:
        src, build = build_root / 'src', build_root / 'build'
        run(['git', 'clone', '--depth', '1', '--branch', QS_TAG,
             'https://github.com/quickshell-mirror/quickshell.git', src], dry)
        run(['cmake', '-S', src, '-B', build, '-G', 'Ninja', '-DCMAKE_BUILD_TYPE=Release',
             f'-DCMAKE_INSTALL_PREFIX={prefix}', '-DINSTALL_QML_PREFIX=share/quickshell/qml',
             '-DDISTRIBUTOR=MacShell-niri-local-build', '-DCRASH_HANDLER=OFF',
             '-DHYPRLAND=OFF', '-DSCREENCOPY_HYPRLAND_TOPLEVEL=OFF', '-DX11=OFF',
             '-DI3=OFF', '-DSERVICE_PAM=ON', '-DSERVICE_POLKIT=OFF',
             '-DSERVICE_GREETD=OFF', '-DBLUETOOTH=OFF', '-DNETWORK=OFF'], dry)
        run(['nice', '-n', '19', 'cmake', '--build', build, '--parallel', '1'], dry)
        run(['cmake', '--install', build], dry)
    finally:
        if context:
            context.cleanup()
    return prefix / 'bin' / 'quickshell'


def install_dependencies(info, args, private_prefix):
    distro = info.get('ID', '')
    family = info.get('ID_LIKE', '')
    if 'suse' in distro or 'suse' in family:
        manager = 'zypper'
        if distro in ('opensuse-microos', 'aeon', 'kalpa'):
            raise RuntimeError('For transactional openSUSE install dependencies with transactional-update, reboot, then use --skip-deps')
        required = ['distribution-logos-openSUSE-icons', 'libwayland-server0', 'niri', 'xwayland-satellite', 'xwayland', 'python3',
                    'qt6-declarative-imports', 'qt6-wayland', 'libQt6Svg6', 'qt6-shadertools', 'xdg-utils']
        extras = ['gvfs', 'gvfs-backends', 'udisks2', 'xdg-user-dirs', 'grim', 'wl-clipboard', 'cliphist', 'wf-recorder', 'libnotify-tools',
                  'brightnessctl', 'NetworkManager', 'bluez', 'pipewire', 'wireplumber', 'upower', 'inotify-tools',
                  'wtype', 'wlsunset', 'swaybg', 'swaylock', 'inter-fonts', 'dejavu-fonts', 'google-noto-coloremoji-fonts',
                  'adwaita-icon-theme', 'adwaita-icon-theme-legacy', 'kitty', 'zenity', 'jq', 'ImageMagick', 'ffmpeg', 'mpvpaper', 'qt6-multimedia-imports']
        if args.with_wayland_repo:
            release = 'openSUSE_Tumbleweed' if distro == 'opensuse-tumbleweed' else info.get('VERSION_ID', '')
            if not re.fullmatch(r'[A-Za-z0-9_.-]+', release):
                raise RuntimeError('Cannot determine openSUSE repository target')
            run(['sudo', 'zypper', 'addrepo', '--refresh',
                 f'https://download.opensuse.org/repositories/X11:/Wayland/{release}/X11:Wayland.repo',
                 'macshell-wayland'], args.dry_run)
        if args.prepare_vm:
            run(['sudo', sys.executable, SOURCE / 'scripts/prepare-opensuse.py', 'mirrors'], args.dry_run)
        run(['sudo', 'zypper', '--non-interactive', 'refresh'], args.dry_run)
        unavailable = [p for p in required if not suse_available(p, args.dry_run)]
        if unavailable:
            raise RuntimeError('Missing packages in enabled repositories: ' + ', '.join(unavailable) +
                               '. For Leap/Slowroll consider --with-wayland-repo (X11:Wayland), or install them manually.')
        package_install(manager, required, args.dry_run)
        if args.prepare_vm:
            run(['sudo', sys.executable, SOURCE / 'scripts/prepare-opensuse.py', 'graphics'], args.dry_run)
        if args.extras:
            available = [p for p in extras if suse_available(p, args.dry_run)]
            missing = sorted(set(extras) - set(available))
            if missing:
                print('Optional packages unavailable (features disabled): ' + ', '.join(missing))
            if available:
                package_install(manager, available, args.dry_run)
        if not args.build_quickshell and suse_available('quickshell', args.dry_run):
            package_install(manager, ['quickshell'], args.dry_run)
    elif distro == 'arch' or 'arch' in family:
        manager = 'pacman'
        package_install(manager, ['niri', 'xwayland-satellite', 'xorg-xwayland', 'python', 'quickshell',
            'qt6-declarative', 'qt6-wayland', 'qt6-svg', 'qt6-shadertools', 'xdg-utils'] +
            (['gvfs', 'udisks2', 'xdg-user-dirs', 'grim', 'wl-clipboard', 'cliphist', 'wf-recorder', 'libnotify', 'brightnessctl',
              'networkmanager', 'bluez-utils', 'wireplumber', 'inotify-tools', 'wtype', 'wlsunset',
              'swaybg', 'swaylock', 'ttf-inter', 'ttf-dejavu', 'noto-fonts-emoji', 'adwaita-icon-theme', 'kitty', 'zenity', 'jq', 'imagemagick', 'ffmpeg', 'mpvpaper', 'qt6-multimedia'] if args.extras else []), args.dry_run)
    elif distro == 'fedora' or 'fedora' in family:
        manager = 'dnf'
        package_install(manager, ['niri', 'xwayland-satellite', 'xorg-x11-server-Xwayland', 'python3',
            'quickshell', 'qt6-qtdeclarative', 'qt6-qtwayland', 'qt6-qtsvg', 'qt6-qtshadertools', 'xdg-utils'] +
            (['grim', 'wl-clipboard', 'cliphist', 'wf-recorder', 'libnotify', 'brightnessctl',
              'NetworkManager', 'bluez', 'pipewire', 'wireplumber', 'upower', 'inotify-tools', 'wtype', 'wlsunset',
              'swaybg', 'swaylock', 'dejavu-sans-mono-fonts', 'google-noto-emoji-color-fonts', 'adwaita-icon-theme', 'kitty', 'zenity', 'jq', 'ImageMagick', 'ffmpeg-free', 'qt6-qtmultimedia'] if args.extras else []), args.dry_run)
    else:
        raise RuntimeError('Automatic dependencies support openSUSE, Arch and Fedora. Use --skip-deps elsewhere.')
    candidates = [private_prefix / 'bin' / 'quickshell', shutil.which('qs'), shutil.which('quickshell')]
    for binary in candidates:
        if binary and Path(binary).is_file() and not args.build_quickshell:
            try:
                if version(binary, '0.3.2', args.dry_run):
                    return Path(binary)
            except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
                print(f'Quickshell is not usable; will build a private copy: {exc}')
    return build_quickshell(manager, private_prefix, args.dry_run)


def pam_capable(binary):
    """Probe the module itself: distro forks may use a different version scheme."""
    with tempfile.TemporaryDirectory(prefix='macshell-pam-probe-') as directory:
        path = Path(directory)
        (path / 'shell.qml').write_text('import QtQuick\nimport Quickshell\nimport Quickshell.Wayland\nimport Quickshell.Services.Pam\nShellRoot { Timer { interval: 10; running: true; onTriggered: Qt.quit() } }\n')
        try:
            result = subprocess.run([str(binary), '-p', str(path)],
                env=dict(os.environ, QT_QPA_PLATFORM='offscreen'), stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, timeout=8)
            return result.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False


def backup(path):
    if path.exists() or path.is_symlink():
        stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        dest = path.with_name(path.name + '.backup-' + stamp)
        path.rename(dest)
        print(f'Backup: {dest}')


def write_managed_file(path, text):
    """Avoid launcher backup clutter on an identical reinstall."""
    if path.is_file() and not path.is_symlink() and path.read_text() == text:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    backup(path)
    path.write_text(text)
    path.chmod(0o644 if path.suffix == '.desktop' else 0o755)


def payload_hashes(root):
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(root.rglob('*'))
            if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc'}


def owned_paths(config, data, bindir, niri_config):
    names = ['macshell-niri', 'macshell-niri-session', 'macshell-glass-session', 'macshell-niri-update',
             'macshell-niri-doctor', 'macshell-niri-emoji', 'macshell-terminal', 'macshell-lock']
    result = {name: bindir / name for name in names}
    result.update({'desktop': data / 'applications/macshell-niri.desktop',
                   'private-config': niri_config, 'glass-config': config / 'niri/macshell-glass.kdl',
                   'ghostty-launcher': bindir / 'ghostty', 'ghostty-desktop': data / 'applications/com.mitchellh.ghostty.desktop'})
    return result


def save_owned_files(config, data, bindir, niri_config, integrate=False, no_config=False):
    records = {}
    for name, path in owned_paths(config, data, bindir, niri_config).items():
        if name == 'private-config' and integrate: continue
        if name in ('private-config','glass-config') and no_config: continue
        if name == 'ghostty-launcher' and (not path.is_file() or str(config / 'quickshell/macshell-niri/scripts/ghostty-compat.py') not in path.read_text()): continue
        if name == 'ghostty-desktop' and (not path.is_file() or 'X-MacShell-VirtualBox-Ghostty=true' not in path.read_text()): continue
        if path.is_file() and not path.is_symlink():
            records[name] = {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    state = data / 'macshell-niri/install-files.json'
    state.parent.mkdir(parents=True, exist_ok=True)
    records['__payload__'] = payload_hashes(config / 'quickshell/macshell-niri')
    state.write_text(json.dumps(records, indent=2) + '\n')


def remove_owned_files(config, data, bindir, niri_config):
    state = data / 'macshell-niri/install-files.json'
    if not state.is_file():
        print('Legacy installation: preserving launcher/config files without an ownership manifest.')
        return
    records = json.loads(state.read_text())
    keep_ghostty = False
    for key in ('ghostty-launcher','ghostty-desktop'):
        record = records.get(key)
        if record:
            path = owned_paths(config,data,bindir,niri_config)[key]
            if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() != record.get('sha256'): keep_ghostty = True
    for name, path in owned_paths(config, data, bindir, niri_config).items():
        if keep_ghostty and name.startswith('ghostty-'):
            print(f'Kept customized Ghostty integration: {path}')
            continue
        record = records.get(name, {})
        if record.get('path') != str(path) or not path.exists(): continue
        if not path.is_symlink() and path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == record.get('sha256'):
            path.unlink()
        else:
            print(f'Kept user-modified file: {path}')
    # Keep the manifest until payload preservation has been decided.


def load_configurer():
    spec = importlib.util.spec_from_file_location('configure_niri', SOURCE / 'scripts/configure-niri.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def virtualbox_guest():
    product = Path('/sys/class/dmi/id/product_name')
    return product.exists() and 'virtualbox' in product.read_text().lower()


def load_glass_builder():
    spec = importlib.util.spec_from_file_location('build_glass', SOURCE / 'scripts/build-glass.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--deps-only', action='store_true', help='Only install/check dependencies; do not deploy or start the shell')
    parser.add_argument('--dry-run', action='store_true', help='Print plan without commands, downloads or writes')
    parser.add_argument('--cursor', choices=['bibata-modern-classic', 'keep'], default='bibata-modern-classic', help='Cursor theme, default: Bibata Modern Classic')
    parser.add_argument('--cursor-size', type=int, default=20, help='Cursor size in logical pixels, default: 20')
    parser.add_argument('--no-clock-fonts', action='store_true', help='Keep existing fonts instead of installing the bundled OFL clock fonts')
    parser.add_argument('--build-glass', action='store_true', help='Build a separate niri-glass compositor and session for real refraction (openSUSE)')
    parser.add_argument('--no-glass', action='store_true', help='Use ordinary niri instead of installing the Liquid Glass session')
    parser.add_argument('--no-login-session', action='store_true', help='Do not register the Liquid Glass session in the login manager; keep the TTY launcher')
    parser.add_argument('--icons', choices=['macos-like-dark', 'macos-like-light', 'keep'], default=None, help='Icon theme from original MacShell; use keep to preserve current icons')
    parser.add_argument('--theme', choices=['tahoe-light', 'tahoe-dark', 'keep'], help='Window styling; a new installation defaults to tahoe-dark')
    parser.add_argument('--restore-theme', action='store_true', help='Restore GTK and niri settings saved before Tahoe; do not install anything')
    parser.add_argument('--prepare-vm', action='store_true', help='Opt in to openSUSE VirtualBox kernel and official HTTPS mirror preparation')
    parser.add_argument('--skip-deps', action='store_true', help='Do not install packages or build Quickshell')
    parser.add_argument('--no-extras', dest='extras', action='store_false', help='Skip optional feature packages')
    parser.add_argument('--build-quickshell', action='store_true', help='Rebuild private Quickshell (openSUSE)')
    parser.add_argument('--with-wayland-repo', action='store_true', help='Opt in to the openSUSE X11:Wayland development repository')
    parser.add_argument('--global-appearance', action='store_true', help='Opt in to changing shared GTK/Qt/kitty/icon preferences; default is private-session styling only')
    parser.add_argument('--integrate-config', action='store_true', help='Opt in to editing the original niri config with backups; default creates a separate macshell.kdl')
    parser.add_argument('--no-config', action='store_true', help='Copy example only; do not edit niri configuration')
    parser.add_argument('--keep-xwayland-config', action='store_true', help='Leave existing Xwayland settings alone')
    parser.add_argument('--bin-dir', type=Path, help='User launcher directory, default: ~/.local/bin')
    parser.add_argument('--niri-config', type=Path, help='Seed config to copy; unchanged unless --integrate-config is explicitly supplied')
    parser.add_argument('--uninstall', action='store_true', help='Remove shell files and managed config block, keep dependencies/settings/backups')
    args = parser.parse_args()
    if args.build_glass and args.no_glass:
        parser.error('--build-glass and --no-glass cannot be combined')
    if args.theme == 'keep':
        args.theme = None
    elif args.theme is None and not args.no_config and not args.uninstall and not args.restore_theme and not args.deps_only:
        existing = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'quickshell/macshell-niri'
        if not existing.exists():
            args.theme = 'tahoe-dark'
    if not 12 <= args.cursor_size <= 96:
        parser.error('--cursor-size must be between 12 and 96')
    if os.geteuid() == 0:
        raise RuntimeError('Run as your normal user, without sudo. Only package commands use sudo.')
    if args.prepare_vm:
        if not virtualbox_guest():
            raise RuntimeError('--prepare-vm is restricted to VirtualBox guests; no changes have been made')
    if args.skip_deps and (args.build_quickshell or args.with_wayland_repo or args.prepare_vm):
        parser.error('--skip-deps cannot be combined with build/repository/VM preparation options')
    config = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))).expanduser().absolute()
    data = Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share'))).expanduser().absolute()
    bindir = (args.bin_dir or Path.home() / '.local/bin').expanduser().absolute()
    target = config / 'quickshell/macshell-niri'
    private_prefix = data / 'macshell-niri/quickshell'
    launcher = bindir / 'macshell-niri'
    if args.icons is None:
        try:
            saved_icons = json.loads((data / 'macshell-niri/icon-theme.json').read_text()).get('theme')
        except (OSError, ValueError):
            saved_icons = None
        args.icons = 'macos-like-light' if saved_icons == 'MacOS-Like-Light' or (saved_icons is None and args.theme == 'tahoe-light') else 'macos-like-dark'
    original_niri_config = (args.niri_config or config / 'niri/config.kdl').expanduser().absolute()
    niri_config = original_niri_config if args.integrate_config else original_niri_config.with_name('macshell.kdl')
    if args.restore_theme:
        if args.dry_run:
            print('Would restore GTK and niri settings from Tahoe backup')
        else:
            import tahoe
            tahoe.restore(config, data)
        return
    if (args.theme or args.build_glass) and (args.no_config or args.uninstall):
        parser.error('Theme/refraction options require niri configuration and cannot be used with --uninstall')
    print(f'Shell: {target}\nLauncher: {launcher}\nPrivate niri config: {niri_config}\nOriginal config preserved: {original_niri_config}')
    if not args.no_config and not args.uninstall and niri_config.exists():
        configurer = load_configurer()
        current = configurer.managed(niri_config.read_text())
        if not args.keep_xwayland_config:
            configurer.migrate(current)
    if not args.dry_run and target.is_symlink():
        raise RuntimeError('Refusing a symlinked installation directory')
    if not args.dry_run and not args.uninstall and target.exists() and not (target / '.macshell-niri-install').is_file():
        raise RuntimeError('Refusing to replace an unmanaged shell directory. Move it aside before installing.')
    if args.uninstall:
        if args.dry_run:
            print('Would remove installed shell, launcher, desktop entry and managed niri block; keep packages and backups.')
            return
        if target.is_symlink():
            raise RuntimeError('Refusing to uninstall a symlinked shell directory')
        if target.exists():
            if not (target / '.macshell-niri-install').is_file():
                raise RuntimeError('Directory is not marked as a MacShell niri installation; refusing to delete it')
        if args.integrate_config and not args.no_config and niri_config.exists():
            load_configurer().configure(niri_config, launcher, remove=True)
        glass_helper = load_glass_builder()
        glass_helper.remove_login_session(sys.modules[__name__], data, bindir)
        remove_owned_files(config, data, bindir, niri_config)
        if target.exists():
            manifest_path = data / 'macshell-niri/install-files.json'
            previous = json.loads(manifest_path.read_text()).get('__payload__') if manifest_path.is_file() else None
            if previous is None or payload_hashes(target) != previous:
                backup(target)
                print('Preserved the modified/legacy shell payload as a recovery backup.')
            else:
                shutil.rmtree(target)
        (data / 'macshell-niri/install-files.json').unlink(missing_ok=True)
        print('Removed MacShell session. Personal settings, recovery backups and installed dependencies/assets were kept. Select Plasma at login to return.')
        return
    if args.skip_deps:
        binary = Path('quickshell') if args.dry_run else compatible_quickshell(private_prefix)
        if not args.dry_run and binary is None:
            raise RuntimeError('Quickshell >= 0.3.2 is required')
    else:
        binary = install_dependencies(os_release(), args, private_prefix)
    if args.deps_only:
        print('Dependencies checked/installed. No shell files or compositor configuration changed.')
        return
    if not args.dry_run and not (config / 'user-dirs.dirs').exists() and shutil.which('xdg-user-dirs-update'):
        run(['xdg-user-dirs-update'])
    for tool, minimum in [('niri', '26.04'), ('xwayland-satellite', '0.7')]:
        if not version(tool, minimum, args.dry_run):
            raise RuntimeError(f'{tool} >= {minimum} required for rootless Xwayland integration')
    glass_binary = None
    use_glass = not args.no_glass and not args.no_config and ('suse' in os_release().get('ID', '') or args.build_glass)
    if use_glass:
        glass_builder = load_glass_builder()
        glass_binary = glass_builder.ensure(sys.modules[__name__], data, args.skip_deps, args.dry_run, args.build_glass)
    if args.dry_run:
        icons = load_icons()
        icons.apply(config, data, {'macos-like-dark': 'MacOS-Like-Dark', 'macos-like-light': 'MacOS-Like-Light', 'keep': 'keep'}[args.icons], dry=True, global_preferences=args.global_appearance)
        print(f'Would copy QML/assets/scripts to {target}, backing up any previous install.')
        print('Would write launcher and desktop entry. Would NOT launch the shell.')
        if not args.no_config:
            print('Would create/update a separate niri config, validate it and preserve the original. Shared configuration changes require --integrate-config.')
        if args.cursor != 'keep' and not args.no_config:
            print(f'Would install Bibata Modern Classic cursor at {args.cursor_size}px.')
        if args.theme:
            print('Would apply bundled Tahoe GTK theme assets and private niri window styles; shared preferences require --global-appearance.')
        if not args.no_clock_fonts:
            print('Would install bundled OFL clock fonts into the private user font directory.')
        if glass_binary:
            glass_builder.session(sys.modules[__name__], data, config, bindir, niri_config, glass_binary, dry=True)
            if not args.no_login_session:
                glass_builder.login_session(sys.modules[__name__], data, bindir, dry=True)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.resolve() == SOURCE.resolve():
        raise RuntimeError('Source and destination are identical; run installer from a separate checkout')
    # Reject malformed shipped templates before replacing any installed payload.
    load_configurer().nodes((SOURCE / 'config/niri.example.kdl').read_text())
    migration_spec = importlib.util.spec_from_file_location('widget_migration', SOURCE / 'scripts/widget-migration.py')
    migration = importlib.util.module_from_spec(migration_spec)
    migration_spec.loader.exec_module(migration)
    migration.migrate(config)
    if args.icons != 'keep':
        load_icons().verify()
    # Stage the payload before replacing an existing install.
    stage = Path(tempfile.mkdtemp(prefix='.macshell-stage-', dir=target.parent))
    try:
        for pattern in ('*.qml', '*.js', '*.svg', '*.frag', '*.qsb', '*.md'):
            for file in SOURCE.glob(pattern):
                shutil.copy2(file, stage / file.name)
        for directory in ('scripts', 'config', 'vendor', 'assets', 'MacLock'):
            shutil.copytree(SOURCE / directory, stage / directory, ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copy2(SOURCE / 'LICENSE', stage / 'LICENSE')
        shutil.copy2(SOURCE / 'UPSTREAM_REVISION', stage / 'UPSTREAM_REVISION')
        try:
            revision = subprocess.check_output(['git', '-C', str(SOURCE), 'rev-parse', 'HEAD'], text=True, stderr=subprocess.DEVNULL).strip()
        except (OSError, subprocess.CalledProcessError):
            revision = 'local'
        (stage / '.macshell-version.json').write_text(json.dumps({'repository': 'Artemnuhka/MacShell-niri', 'revision': revision,
            'upstream': (SOURCE / 'UPSTREAM_REVISION').read_text().strip()}))
        (stage / '.macshell-niri-install').write_text('1\n')
        if target.is_dir() and payload_hashes(target) == payload_hashes(stage):
            print('Installed payload is identical; no extra backup created.')
        else:
            backup(target)
            stage.rename(target)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    icons = load_icons()
    icons.apply(config, data, {'macos-like-dark': 'MacOS-Like-Dark', 'macos-like-light': 'MacOS-Like-Light', 'keep': 'keep'}[args.icons], global_preferences=args.global_appearance)
    bindir.mkdir(parents=True, exist_ok=True)
    write_managed_file(launcher, '#!/bin/sh\nset -eu\n' +
        'if [ -z "${NIRI_SOCKET:-}" ]; then echo "Start this shell inside a niri session." >&2; exit 1; fi\n' +
        'export QT_QPA_PLATFORM=wayland\n' +
        'export MALLOC_ARENA_MAX="${MALLOC_ARENA_MAX:-2}"\n' +
        'export QSG_USE_SIMPLE_ANIMATION_DRIVER="${QSG_USE_SIMPLE_ANIMATION_DRIVER:-1}"\n' +
        'exec ' + shlex.quote(sys.executable) + ' ' +
        shlex.quote(str(target / 'scripts/shell-session.py')) + ' ' + shlex.quote(str(binary)) +
        ' ' + shlex.quote(str(target)) + ' "$@"\n')
    updater = bindir / 'macshell-niri-update'
    write_managed_file(updater, '#!/bin/sh\nexec ' + shlex.quote(sys.executable) + ' ' + shlex.quote(str(target / 'scripts/update.py')) + ' "$@"\n')
    for name, script in [('macshell-niri-doctor', 'graphics.py'), ('macshell-niri-emoji', 'emoji.py')]:
        helper = bindir / name
        write_managed_file(helper, '#!/bin/sh\nexec ' + shlex.quote(sys.executable) + ' ' + shlex.quote(str(target / 'scripts' / script)) + ' "$@"\n')
    run([sys.executable, target / 'scripts/graphics.py', 'configure'])
    lock_binary = next((candidate for candidate in [binary, shutil.which('qs'), shutil.which('quickshell'), Path('/usr/bin/qs'), Path('/usr/bin/quickshell')]
                        if candidate and pam_capable(candidate)), None)
    lock_launcher = bindir / 'macshell-lock'
    if lock_binary:
        write_managed_file(lock_launcher, '#!/bin/sh\nexport QT_QPA_PLATFORM=wayland\nexport MACSHELL_LOCK_BINARY=' +
            shlex.quote(str(lock_binary)) + '\nexec ' + shlex.quote(sys.executable) + ' ' +
            shlex.quote(str(target / 'scripts/maclock.py')) + ' "$@"\n')
        print(f'MacLock PAM backend: {lock_binary}')
    else:
        write_managed_file(lock_launcher, '#!/bin/sh\necho "MacLock requires Quickshell with PAM support. Reinstall with --build-quickshell." >&2\nexit 1\n')
        print('MacLock unavailable: no PAM-capable Quickshell; existing screen-lock keybinding preserved.')
    terminal = bindir / 'macshell-terminal'
    write_managed_file(terminal, '#!/bin/sh\nexec ' + shlex.quote(sys.executable) + ' ' +
        shlex.quote(str(target / 'scripts/launch-kitty.py')) + ' \"$@\"\n')
    ghostty_spec = importlib.util.spec_from_file_location('ghostty_compat', SOURCE / 'scripts/ghostty-compat.py')
    ghostty = importlib.util.module_from_spec(ghostty_spec)
    ghostty_spec.loader.exec_module(ghostty)
    ghostty.install(target, bindir, data)
    apps = data / 'applications'
    apps.mkdir(parents=True, exist_ok=True)
    desktop = apps / 'macshell-niri.desktop'
    desktop_exec = str(launcher).replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$').replace('%', '%%')
    write_managed_file(desktop, '[Desktop Entry]\nType=Application\nName=MacShell for niri\n' +
        f'Exec="{desktop_exec}"\nIcon=' + str(target / 'assets/icons/settings.svg') + '\nTerminal=false\nCategories=Settings;\n')
    if not args.no_config:
        if not args.integrate_config and not niri_config.exists() and original_niri_config.is_file():
            niri_config.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original_niri_config, niri_config)
        load_configurer().configure(niri_config, launcher, not args.keep_xwayland_config, lock_launcher=lock_launcher if lock_binary else None)
    private_glass_config = config / 'niri/macshell-glass.kdl'
    private_glass_binary = data / 'macshell-niri/niri-glass/bin/niri-glass'
    if not args.no_config and private_glass_config.is_file() and private_glass_binary.is_file():
        # Refresh managed bindings/rules while retaining the private optics and input settings.
        load_configurer().configure(private_glass_config, launcher, not args.keep_xwayland_config,
            validator=private_glass_binary, lock_launcher=lock_launcher if lock_binary else None)
    if args.theme:
        import tahoe
        tahoe.apply(config, data, niri_config, 'Dark' if args.theme.endswith('dark') else 'Light', global_preferences=args.global_appearance)
    if args.cursor != 'keep' and not args.no_config:
        import cursor
        cursor.apply(sys.modules[__name__], config, data, niri_config, args.cursor_size, global_preferences=args.global_appearance)
    if not args.no_clock_fonts:
        font_spec = importlib.util.spec_from_file_location('clock_fonts', SOURCE / 'scripts/clock-fonts.py')
        fonts = importlib.util.module_from_spec(font_spec)
        font_spec.loader.exec_module(fonts)
        fonts.install(data)
    if not args.no_config:
        session_launcher = bindir / 'macshell-niri-session'
        write_managed_file(session_launcher, '#!/bin/sh\nset -eu\n' +
            'if [ -n "${WAYLAND_DISPLAY:-}" ] || [ -n "${DISPLAY:-}" ]; then echo "Start this session from a TTY or login manager." >&2; exit 1; fi\n' +
            'export MACSHELL_NIRI_CONFIG=' + shlex.quote(str(niri_config)) + '\n' +
            'exec niri --session --config ' + shlex.quote(str(niri_config)) + ' "$@"\n')
        session_launcher.chmod(0o755)
    if glass_binary:
        glass_builder.session(sys.modules[__name__], data, config, bindir, niri_config, glass_binary)
        if not args.no_login_session:
            glass_builder.login_session(sys.modules[__name__], data, bindir)
    save_owned_files(config, data, bindir, niri_config, args.integrate_config, args.no_config)
    if glass_binary:
        if not args.no_login_session:
            print('Installed. Log out and select MacShell Liquid Glass in the login manager.')
        else:
            print('Installed. Login-manager registration was disabled; use the TTY launcher.')
        print(f'Without a login manager, start from a text TTY: {bindir / "macshell-glass-session"}')
    else:
        print(f'Installed. Log into the niri session to use rootless Xwayland. Start the shell with: {launcher}')
    print('MacShell uses a separate session/config by default. Existing Plasma, GTK/Qt preferences and the original niri configuration are preserved.')
    print('Stop overlapping bars/notification daemons manually. This installer does not stop services or start the shell.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
        print(f'Installation failed: {exc}', file=sys.stderr)
        sys.exit(1)
