#!/usr/bin/env python3
"""Optional, user-local Apple colour emoji font; never changes system aliases."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.request

URL = 'https://github.com/samuelngs/apple-emoji-ttf/releases/download/macos-26-20260722-484daf4e/AppleColorEmoji-Linux.ttf'
SHA256 = 'e37c7af6265ac4a0af6d57bc65e86109a776d9966e8343334557f63da482516f'


def family():
    # fc-match silently substitutes missing families, so inspect the actual match.
    for requested in ('Apple Color Emoji', 'emoji'):
        result = subprocess.run(['fc-match', '-f', '%{family[0]}|%{color}', requested], capture_output=True, text=True)
        name, _, color = result.stdout.strip().partition('|')
        if color.lower() == 'true' and (requested == 'emoji' or name == requested):
            return name + '|true'
    return 'Noto Color Emoji|true'


def install(source=None):
    data = Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share')))
    folder = data / 'fonts/macshell-emoji'
    with tempfile.TemporaryDirectory(prefix='macshell-emoji-') as stage:
        candidate = Path(source) if source else Path(stage) / 'AppleColorEmoji-Linux.ttf'
        if source is None:
            urllib.request.urlretrieve(URL, candidate)
        if hashlib.sha256(candidate.read_bytes()).hexdigest() != SHA256:
            raise RuntimeError('Apple emoji download checksum mismatch')
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / 'AppleColorEmoji-Linux.ttf'
        if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest() != SHA256:
            temporary = folder / '.AppleColorEmoji-Linux.ttf.tmp'
            temporary.write_bytes(candidate.read_bytes())
            temporary.replace(target)
    subprocess.run(['fc-cache', '-f', str(folder)], check=True)
    print('Installed Apple Color Emoji for this user. Restart MacShell to refresh the font.')


if __name__ == '__main__':
    if sys.argv[1:] == ['family']:
        print(family())
    elif sys.argv[1:2] == ['install-apple'] and len(sys.argv) <= 3:
        install(sys.argv[2] if len(sys.argv) == 3 else None)
    else:
        sys.exit('Usage: macshell-niri-emoji family | install-apple [verified-font.ttf]')
