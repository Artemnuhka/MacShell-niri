#!/usr/bin/env python3
"""Compatibility entry point for MacShell's selected default terminal."""
import importlib.util
from pathlib import Path
import sys

spec=importlib.util.spec_from_file_location('default_apps',Path(__file__).with_name('default-apps.py'))
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
try:
    module.launch_terminal(sys.argv[1:])
except (ImportError,ValueError,RuntimeError,OSError) as error:
    sys.exit(str(error))
