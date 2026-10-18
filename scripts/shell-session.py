#!/usr/bin/env python3
"""Recover the active private compositor's glass mode when restarting via SSH."""
import os
import fcntl
import hashlib
import json
import signal
import subprocess
import time
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
    try:
        data_root = Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share')))
        appearance = json.loads((data_root / 'macshell-niri/session-appearance.json').read_text())
        if appearance.get('gtk_theme'): os.environ.setdefault('GTK_THEME', appearance['gtk_theme'])
    except (OSError, ValueError): pass
    if not os.environ.get('QS_ICON_THEME'):
        try:
            data = Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share')))
            theme = json.loads((data / 'macshell-niri/icon-theme.json').read_text()).get('theme', 'Adwaita')
            os.environ['QS_ICON_THEME'] = str(theme)
        except (OSError, ValueError):
            os.environ['QS_ICON_THEME'] = 'Adwaita'
    binary, config, *arguments = sys.argv[1:]
    if arguments:
        # IPC is one-shot and must never start or supervise another shell.
        os.execv(binary, [binary, '-c', config, *arguments])
    runpy.run_path(str(Path(__file__).with_name('start-session.py')), run_name='__main__')
    runtime = Path(os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}'))
    identity = (os.environ.get('NIRI_SOCKET', '') + str(Path(config).resolve())).encode()
    lock_path = runtime / ('macshell-niri-' + hashlib.sha256(identity).hexdigest()[:16] + '.lock')
    with lock_path.open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('MacShell is already running in this session.', file=sys.stderr)
            sys.exit(0)
        stopping = False
        child = None
        def stop(signum, frame):
            global stopping
            stopping = True
            if child and child.poll() is None:
                child.send_signal(signum)
        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        failures = 0
        while not stopping:
            started = time.monotonic()
            child = subprocess.Popen([binary, '-c', config])
            result = child.wait()
            if stopping or result == 0:
                break
            failures = failures + 1 if time.monotonic() - started < 30 else 1
            delay = min(15, failures)
            print(f'MacShell exited ({result}); restarting in {delay}s.', file=sys.stderr, flush=True)
            time.sleep(delay)
