#!/usr/bin/env python3
"""Send one typed niri request without shell interpolation or index/ID ambiguity."""
import json
import os
import socket
import sys
import subprocess
import time


def request(payload):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(3)
        sock.connect(os.environ['NIRI_SOCKET'])
        sock.sendall((json.dumps(payload) + '\n').encode())
        with sock.makefile('r') as reply:
            result = json.loads(reply.readline())
        if 'Err' in result:
            raise RuntimeError(result['Err'])
        return result['Ok']


if __name__ == '__main__':
    try:
        if sys.argv[1] == '--window-action':
            time.sleep(0.08)  # allow a layer-shell menu to release keyboard focus
            request({'Action': {'FocusWindow': {'id': int(sys.argv[2])}}})
            subprocess.run(['niri', 'msg', 'action', *sys.argv[3:]], check=True)
        else:
            request(json.loads(sys.argv[1]))
    except (OSError, ValueError, KeyError, RuntimeError, IndexError, subprocess.CalledProcessError) as exc:
        print(f'macshell-niri IPC: {exc}', file=sys.stderr)
        sys.exit(1)
