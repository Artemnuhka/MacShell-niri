#!/usr/bin/env python3
"""Launch kitty with a narrowly scoped workaround for VirtualBox's virtual GPU."""
import os
from pathlib import Path
import shutil
import sys

product = Path('/sys/class/dmi/id/product_name')
if product.exists() and 'virtualbox' in product.read_text().lower():
    os.environ.setdefault('LIBGL_ALWAYS_SOFTWARE', '1')
binary = shutil.which('kitty')
if not binary:
    sys.exit('kitty is not installed')
os.execv(binary, [binary, *sys.argv[1:]])
