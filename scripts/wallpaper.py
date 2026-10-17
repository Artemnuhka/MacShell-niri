#!/usr/bin/env python3
"""Apply pictures or video to this Wayland session; never stop another session's provider."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys


def stop_own(providers):
    display=('WAYLAND_DISPLAY='+os.environ['WAYLAND_DISPLAY']).encode()
    for p in Path('/proc').glob('[0-9]*'):
        try:
            if (p/'comm').read_text().strip() in providers and display in (p/'environ').read_bytes().split(b'\0'):
                os.kill(int(p.name),signal.SIGTERM)
        except (OSError,ValueError):continue


def prepare(path):
    cache=Path.home()/'.cache/macshell/thumbs';cache.mkdir(parents=True,exist_ok=True)
    key=hashlib.md5(f'{path}:{int(path.stat().st_mtime)}'.encode()).hexdigest()[:16]
    frame=cache/(key+'.jpg');preview=cache/(key+'.webp')
    if not frame.exists():subprocess.run(['ffmpeg','-loglevel','error','-y','-ss','1','-i',str(path),'-frames:v','1','-vf','scale=1280:-2',str(frame)],stdin=subprocess.DEVNULL,check=True)
    if not preview.exists():subprocess.run(['ffmpeg','-loglevel','error','-y','-i',str(path),'-t','3','-vf','fps=8,scale=320:-2','-loop','0',str(preview)],stdin=subprocess.DEVNULL,check=True)
    return frame

if __name__=='__main__':
    only_prepare=sys.argv[1]=='--prepare'
    path=Path(sys.argv[2] if only_prepare else sys.argv[1]).expanduser().resolve(strict=True)
    video=path.suffix.lower() in ('.mp4','.webm','.mkv','.mov','.m4v')
    still=prepare(path) if video else path
    if only_prepare:sys.exit(0)
    if video:
        if not shutil.which('mpvpaper'):sys.exit('Animated wallpaper requires mpvpaper; the current wallpaper was kept.')
        stop_own({'swaybg','mpvpaper'})
        command=['mpvpaper','-o','no-audio loop-file=inf hwdec=auto','*',str(path)]
    else:
        stop_own({'swaybg','mpvpaper'})
        command=['swaybg','-i',str(path),'-m','fill']
    subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
    state=Path.home()/'.config/macshell/wallpaper-video';state.parent.mkdir(parents=True,exist_ok=True)
    state.write_text(str(path) if video else '')
    print(still)
