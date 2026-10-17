#!/usr/bin/env python3
"""Compact system information that fits a tiled terminal without a wide logo."""
import os
import platform
import re
import signal
import shutil
import subprocess
import sys
import textwrap


def main():
    print('\033]0;About This Linux\007', end='', flush=True)
    lines = []
    fastfetch = shutil.which('fastfetch')
    result = None
    if fastfetch:
        # Ignore personal fastfetch layouts: the original ASCII logo wraps across
        # the information in niri's narrow tiles. Keep this view predictable.
        result = subprocess.run([fastfetch, '--config', 'none', '--logo', 'none',
                                 '--structure', 'OS:Kernel:Uptime:WM:Terminal:CPU:GPU:Memory:Disk'],
                                check=False, stdout=subprocess.PIPE, text=True)
        for line in result.stdout.splitlines():
            lines.append(re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', line))
    if result is None or result.returncode:
        release = platform.freedesktop_os_release()
        lines = ['OS: ' + release.get('PRETTY_NAME', 'Linux'),
                 'Kernel: ' + platform.release(),
                 'Desktop: ' + os.environ.get('XDG_CURRENT_DESKTOP', 'niri')]

    def render(*_):
        try:
            width = max(10, os.get_terminal_size(sys.stdout.fileno()).columns - 1)
        except OSError:
            width = 79
        if sys.stdout.isatty():
            print('\033[2J\033[H', end='')
        print('\033[1mAbout This Linux\033[0m\n')
        for line in lines:
            print(textwrap.fill(line, width=width, subsequent_indent='  ',
                                replace_whitespace=False))
        print('\nPress Enter to close… ', end='', flush=True)

    # Niri can resize the tile just after launch or when another window opens.
    # Reflow the cached information without rerunning hardware detection.
    signal.signal(signal.SIGWINCH, render)
    render()
    try:
        input()
    except (EOFError, KeyboardInterrupt):
        pass


if __name__ == '__main__':
    main()
