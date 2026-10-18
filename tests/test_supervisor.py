import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ShellSupervisor(unittest.TestCase):
    def test_restarts_failed_shell_and_does_not_restart_clean_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            shutil.copy(ROOT / 'scripts/shell-session.py', base / 'shell-session.py')
            (base / 'start-session.py').write_text('')
            fake = base / 'quickshell'
            fake.write_text('#!' + sys.executable + '\nfrom pathlib import Path\nimport sys\np=Path(__file__).with_name("runs")\nn=int(p.read_text())+1 if p.exists() else 1\np.write_text(str(n))\nsys.exit(1 if n==1 else 0)\n')
            fake.chmod(0o755)
            result = subprocess.run([sys.executable, str(base / 'shell-session.py'), str(fake), str(base)],
                                    env=dict(os.environ, XDG_RUNTIME_DIR=str(base), NIRI_SOCKET=''), capture_output=True, timeout=8)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((base / 'runs').read_text(), '2')

    def test_ipc_is_one_shot_even_on_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            shutil.copy(ROOT / 'scripts/shell-session.py', base / 'shell-session.py')
            (base / 'start-session.py').write_text('raise RuntimeError("must not run for IPC")')
            fake = base / 'quickshell'
            fake.write_text('#!/bin/sh\nexit 7\n')
            fake.chmod(0o755)
            result = subprocess.run([sys.executable, str(base / 'shell-session.py'), str(fake), str(base), 'ipc', 'call'],
                                    env=dict(os.environ, XDG_RUNTIME_DIR=str(base), NIRI_SOCKET=''), capture_output=True, timeout=3)
            self.assertEqual(result.returncode, 7, result.stderr)
            self.assertEqual(list(base.glob('*.lock')), [])

    def test_prevents_duplicate_and_terminates_child(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            shutil.copy(ROOT / 'scripts/shell-session.py', base / 'shell-session.py')
            (base / 'start-session.py').write_text('')
            fake = base / 'quickshell'
            fake.write_text('#!' + sys.executable + '\nimport os,time\nfrom pathlib import Path\nPath(__file__).with_name("child").write_text(str(os.getpid()))\ntime.sleep(30)\n')
            fake.chmod(0o755)
            command = [sys.executable, str(base / 'shell-session.py'), str(fake), str(base)]
            env = dict(os.environ, XDG_RUNTIME_DIR=str(base), NIRI_SOCKET='')
            process = subprocess.Popen(command, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                deadline = time.monotonic() + 3
                while not (base / 'child').exists() and time.monotonic() < deadline:
                    time.sleep(.02)
                self.assertTrue((base / 'child').is_file())
                duplicate = subprocess.run(command, env=env, capture_output=True, timeout=3)
                self.assertEqual(duplicate.returncode, 0)
                self.assertIn(b'already running', duplicate.stderr)
                child = int((base / 'child').read_text())
                process.terminate()
                self.assertEqual(process.wait(timeout=3), 0)
                with self.assertRaises(ProcessLookupError):
                    os.kill(child, 0)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
