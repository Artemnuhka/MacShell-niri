#!/usr/bin/env python3
"""Update the niri fork and its nested MacLock together, never the Hyprland tree."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

REPO = 'Artemnuhka/MacShell-niri'


def latest(channel):
    ref = 'refs/heads/main'
    if channel == 'release':
        try:
            request = urllib.request.Request(f'https://api.github.com/repos/{REPO}/releases/latest', headers={'Accept': 'application/vnd.github+json'})
            with urllib.request.urlopen(request, timeout=15) as response:
                tag = json.load(response)['tag_name']
            ref = 'refs/tags/' + tag
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
    output = subprocess.check_output(['git', 'ls-remote', f'https://github.com/{REPO}.git', ref, ref + '^{}'], text=True, timeout=30)
    commits = [line.split()[0] for line in output.splitlines()]
    if not commits or not re.fullmatch('[0-9a-f]{40}', commits[-1]):
        raise RuntimeError('Could not resolve the update channel')
    return commits[-1]


def metadata(target):
    path = target / '.macshell-version.json'
    return json.loads(path.read_text()) if path.is_file() else {'revision': 'unknown'}


def rollback(target):
    if target.is_symlink() or not (target / '.macshell-niri-install').is_file():
        raise RuntimeError('Not a managed MacShell-niri installation')
    backups = sorted((p for p in target.parent.glob(target.name + '.backup-*')
                      if p.is_dir() and not p.is_symlink() and (p / '.macshell-niri-install').is_file()), reverse=True)
    if not backups:
        raise RuntimeError('No managed installation backup found')
    previous = backups[0]
    displaced = Path(tempfile.mkdtemp(prefix=target.name + '.rollback-', dir=target.parent))
    displaced.rmdir()
    target.rename(displaced)
    try:
        previous.rename(target)
    except BaseException:
        displaced.rename(target)
        raise
    print(f'Restored {previous.name}; replaced version preserved at {displaced}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('command', choices=['check', 'status', 'log', 'update', 'rollback', 'channel'])
    parser.add_argument('channel', nargs='?', choices=['main', 'release'])
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--ref')
    parser.add_argument('--yes', action='store_true', help='Accepted for compatibility; the installer still handles sudo normally')
    args = parser.parse_args()
    target = args.target.absolute()
    data = Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share'))) / 'macshell-niri'
    data.mkdir(parents=True, exist_ok=True)
    channel_file = data / 'update-channel'
    channel = channel_file.read_text().strip() if channel_file.exists() else 'main'
    if channel not in ('main', 'release'):
        raise RuntimeError('Invalid saved update channel')
    if args.command == 'channel':
        if args.channel:
            channel_file.write_text(args.channel + '\n')
            channel = args.channel
        print(channel)
        return 0
    state = metadata(target)
    if args.command == 'status':
        print(json.dumps(dict(state, repository=REPO, channel=channel, path=str(target)), indent=2))
        return 0
    if args.command == 'log':
        revision = state.get('revision', 'unknown')
        url = f'https://github.com/{REPO}/compare/{revision}...main' if re.fullmatch('[0-9a-f]{40}', revision) else f'https://github.com/{REPO}/commits/main'
        print(url)
        return 0
    if args.command == 'check':
        revision = latest(channel)
        changed = state.get('revision') != revision
        result = dict(status='update_available' if changed else 'up_to_date', installed=state.get('revision'), latest=revision,
                      url=f'https://github.com/{REPO}/commit/{revision}')
        print(json.dumps(result) if args.json else ('Update available: ' if changed else 'Up to date: ') + revision[:12])
        return 10 if changed else 0
    with (data / 'update.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.command == 'rollback':
            rollback(target)
            return 0
        revision = args.ref or latest(channel)
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/-]{0,199}', revision) or '..' in revision:
            raise RuntimeError('Invalid update ref')
        if not args.ref and state.get('revision') == revision:
            print('Already up to date')
            return 0
        with tempfile.TemporaryDirectory(prefix='macshell-niri-update-') as directory:
            checkout = Path(directory) / 'source'
            subprocess.run(['git', 'init', str(checkout)], check=True, stdout=subprocess.DEVNULL)
            subprocess.run(['git', '-C', str(checkout), 'fetch', '--depth', '1', f'https://github.com/{REPO}.git', revision], check=True)
            subprocess.run(['git', '-C', str(checkout), 'checkout', '--detach', 'FETCH_HEAD'], check=True)
            # Execute the new niri installer so dependency and configuration changes come with the update.
            subprocess.run([sys.executable, str(checkout / 'scripts/install.py')], check=True)
        print('MacShell-niri and MacLock updated. Restart MacShell to load the new version.')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
