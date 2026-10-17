#!/usr/bin/env python3
"""Recover the active private compositor's glass mode when restarting via SSH."""
import os
from pathlib import Path
import re
import runpy
import sys


def recover_glass():
    match = re.search(r'\.(\d+)\.sock$', os.environ.get('NIRI_SOCKET', ''))
    if not match:
        return
    process = Path('/proc') / match[1]
    try:
        if process.stat().st_uid != os.getuid():
            return
        data = Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share')))
        binary = data / 'macshell-niri/niri-glass/bin/niri-glass'
        if (process / 'exe').resolve() != binary.resolve() or not binary.is_file():
            return
        environment = dict(entry.split(b'=', 1) for entry in
                           (process / 'environ').read_bytes().split(b'\0') if b'=' in entry)
        for name in ('MACSHELL_REAL_GLASS', 'MACSHELL_GLASS_CONFIG', 'MACSHELL_GLASS_BINARY'):
            value = environment.get(name.encode())
            if value is not None:
                os.environ[name] = os.fsdecode(value)
    except OSError:
        return


if __name__ == '__main__':
    recover_glass()
    binary, config, *arguments = sys.argv[1:]
    if not arguments:
        runpy.run_path(str(Path(__file__).with_name('start-session.py')), run_name='__main__')
    os.execv(binary, [binary, '-c', config, *arguments])
