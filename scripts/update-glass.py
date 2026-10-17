#!/usr/bin/env python3
"""Apply the MacShell Liquid strength slider to the private compositor config."""
import fcntl
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

BEGIN = '// BEGIN MacShell compositor lenses'
END = '// END MacShell compositor lenses'


def update(strength, blur):
    if not math.isfinite(strength) or not 0 <= strength <= 4:
        raise ValueError('Liquid strength must be between 0 and 4')
    if not math.isfinite(blur) or not 0 <= blur <= 64:
        raise ValueError('Blur must be between 0 and 64')
    value = os.environ.get('MACSHELL_GLASS_CONFIG', '')
    if not value:
        return
    config = Path(value)
    binary = Path(os.environ.get('MACSHELL_GLASS_BINARY', str(Path.home()/'.local/share/macshell-niri/niri-glass/bin/niri-glass')))
    if config.is_symlink():
        raise RuntimeError('Refusing a symlinked private compositor config')
    with config.with_suffix('.optics.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        text = config.read_text()
        if text.count(BEGIN) != 1 or text.count(END) != 1:
            raise RuntimeError('Private compositor lens markers are missing')
        a, b = text.index(BEGIN), text.index(END)
        changed = re.sub(r'refraction-strength [0-9.eE+-]+', f'refraction-strength {strength * 2.2:.5g}', text[a:b])
        changed = re.sub(r'blur (true|false)', 'blur ' + ('true' if blur > 0 else 'false'), changed)
        changed = re.sub(r'offset [0-9.eE+-]+', f'offset {min(12, blur * .08):.5g}', changed)
        candidate_text = text[:a] + changed + text[b:]
        if candidate_text == text:
            return
        fd, filename = tempfile.mkstemp(prefix='.macshell-optics-', suffix='.kdl', dir=config.parent)
        os.close(fd)
        candidate = Path(filename)
        try:
            candidate.write_text(candidate_text)
            subprocess.run([str(binary), 'validate', '--config', str(candidate)], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            candidate.chmod(config.stat().st_mode & 0o777)
            candidate.replace(config)
        finally:
            candidate.unlink(missing_ok=True)


if __name__ == '__main__':
    update(float(sys.argv[1]), float(sys.argv[2]) if len(sys.argv) > 2 else 5)
