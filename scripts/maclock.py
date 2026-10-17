#!/usr/bin/env python3
"""Launch the independently installed niri MacLock with a PAM-capable Quickshell."""
import os
from pathlib import Path
import subprocess
import sys
import time

config=Path(__file__).resolve().parent.parent/'MacLock'
binary=os.environ.get('MACSHELL_LOCK_BINARY','qs')
def ipc(name):
    result=subprocess.run([binary,'-p',str(config),'ipc','call','lockscreen',name],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
    return result.stdout.strip() if result.returncode==0 else ''

pam_directory = next((p for p in (Path('/etc/pam.d'),Path('/usr/lib/pam.d'),Path('/usr/etc/pam.d')) if (p/'swaylock').is_file()),None)
if pam_directory: os.environ['MACSHELL_PAM_DIR']=str(pam_directory)
if os.environ.get('MACLOCK_PREVIEW')=='1':
    os.execvp(binary,[binary,'-p',str(config)])
if not pam_directory:
    sys.exit('MacLock needs the distro swaylock PAM service. Install swaylock before locking.')
state=ipc('state')
if state=='busy':sys.exit(0)
if state=='stopping':
    for _ in range(60):
        time.sleep(.1);state=ipc('state')
        if state!='stopping':break
    if state=='stopping':sys.exit('Previous MacLock is still stopping.')
if state!='ready':
    process=subprocess.Popen([binary,'-p',str(config)],env=dict(os.environ,MACLOCK_DAEMON='1'),start_new_session=True)
    for _ in range(60):
        state=ipc('state')
        if state in ('ready','busy'):break
        if process.poll() is not None:sys.exit('MacLock could not load. Check the PAM-capable Quickshell selected by the installer.')
        time.sleep(.1)
if state=='busy':sys.exit(0)
if state!='ready':sys.exit('MacLock did not become ready.')
raise SystemExit(subprocess.call([binary,'-p',str(config),'ipc','call','lockscreen','lock']))
