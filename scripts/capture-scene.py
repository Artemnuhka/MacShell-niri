#!/usr/bin/env python3
"""Capture an output before opening translucent UI; keep textures window-local."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def capture(output):
    runtime = Path(os.environ.get('XDG_RUNTIME_DIR', tempfile.gettempdir()))
    folder = runtime / ('macshell-scenes-' + str(os.getuid()))
    folder.mkdir(mode=0o700, exist_ok=True)
    if folder.is_symlink() or folder.stat().st_uid != os.getuid():
        raise RuntimeError('Scene directory is not owned by this user')
    identity = hashlib.sha256((os.environ.get('NIRI_SOCKET', '') + output).encode()).hexdigest()[:16]
    fd, temporary = tempfile.mkstemp(prefix=identity + '-', suffix='.png', dir=folder)
    os.close(fd)
    path = Path(temporary)
    try:
        subprocess.run(['grim', '-o', output, str(path)], check=True, timeout=5,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if not path.stat().st_size:
            raise RuntimeError('Empty scene capture')
        # Leave recent images alive while existing Settings/switcher textures use them.
        previous = sorted(folder.glob(identity + '-*.png'), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in previous[8:]:
            old.unlink(missing_ok=True)
        return path.as_uri()
    except BaseException:
        path.unlink(missing_ok=True)
        raise


if __name__ == '__main__':
    try:
        print(capture(sys.argv[1]))
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print('Scene capture unavailable: ' + str(error), file=sys.stderr)
        sys.exit(1)
