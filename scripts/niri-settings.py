#!/usr/bin/env python3
"""Conservative niri adapters for the upstream Settings panes."""
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

def parser():
    spec=importlib.util.spec_from_file_location('configure_niri',Path(__file__).with_name('configure-niri.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def edit_block(text,name,changes):
    node=next((n for n in parser().nodes(text) if n[0]==name),None)
    if node:
        _,tokens,a,b=node
        start=next(t[2] for t in tokens if t[0]=='{')
        stop=next(t[1] for t in reversed(tokens) if t[0]=='}')
        inner=text[start:stop]
    else:
        a=b=len(text);inner='';start=stop=0
    if isinstance(changes,dict):
        for key,value in changes.items():inner=edit_block(inner,key,value)
    else:
        keys={key for key,line in changes}
        for key,_,x,y in reversed(parser().nodes(inner)):
            if key in keys:
                tail=inner[y:]
                separator=__import__('re').match(r'[ \t]*;',tail)
                if separator:y+=separator.end()
                inner=inner[:x]+inner[y:]
        inner=inner.rstrip()+'\n'+'\n'.join(line for key,line in changes if line is not None)+'\n'
    if node:return text[:start]+inner+text[stop:]
    return text+'\n'+name+' {\n'+inner+'\n}\n'

def input_settings(values):
    v=values
    # Boolean niri options are flags: remove the node to turn one off.
    def boolean(name,value):return (name,name if value else None)
    blocks={'keyboard':[('repeat-rate',f'repeat-rate {max(1,min(100,int(v["repeatRate"])))}'),('repeat-delay',f'repeat-delay {max(100,min(2000,int(v["repeatDelay"])))}')],
            'mouse':[('accel-speed',f'accel-speed {max(-1,min(1,float(v["mouseSens"])))}'),boolean('natural-scroll',v['mouseNatural'])],
            'touchpad':[boolean('natural-scroll',v['tpNatural']),boolean('tap',v['tpTap']),boolean('dwt',v['tpDwt']),('scroll-factor',f'scroll-factor {max(.1,min(10,float(v["tpScroll"])))}')]}
    path=Path(os.environ.get('MACSHELL_GLASS_CONFIG',str(Path.home()/'.config/niri/config.kdl')))
    with path.with_suffix('.optics.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        before=path.read_text();after=edit_block(before,'input',blocks)
        if after==before:return
        fd,name=tempfile.mkstemp(prefix='.macshell-input-',suffix='.kdl',dir=path.parent);os.close(fd)
        candidate=Path(name)
        try:
            candidate.write_text(after)
            subprocess.run([os.environ.get('MACSHELL_GLASS_BINARY','niri'),'validate','--config',str(candidate)],check=True,stdout=subprocess.DEVNULL)
            backup=path.with_suffix('.before-input')
            if not backup.exists():backup.write_text(before)
            candidate.chmod(path.stat().st_mode & 0o777);candidate.replace(path)
        finally:candidate.unlink(missing_ok=True)

def monitors():
    outputs=json.loads(subprocess.check_output(['niri','msg','--json','outputs']))
    result=[]
    for name,o in outputs.items():
        l=o.get('logical');modes=o.get('modes',[]);idx=o.get('current_mode')
        if not l or idx is None:continue
        m=modes[idx]
        result.append(dict(name=name,description=' '.join(filter(None,[o.get('make'),o.get('model')])),width=m['width'],height=m['height'],refreshRate=m['refresh_rate']/1000,scale=l['scale'],x=l['x'],y=l['y'],availableModes=[f'{m["width"]}x{m["height"]}@{m["refresh_rate"]/1000:.3f}Hz' for m in modes]))
    print(json.dumps(result))

if __name__=='__main__':
    if sys.argv[1]=='monitors':monitors()
    elif sys.argv[1]=='input':input_settings(json.loads(sys.argv[2]))
    elif sys.argv[1]=='gaming':
        os.environ.setdefault('MACSHELL_GLASS_CONFIG','')
        spec=importlib.util.spec_from_file_location('glass',Path(__file__).with_name('update-glass.py'))
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        settings=Path.home()/'.config/macbar/settings.json'
        values=json.loads(settings.read_text()) if settings.exists() else {}
        mod.update(0 if sys.argv[2]=='on' else float(values.get('glassLiquid',1)),0 if sys.argv[2]=='on' else float(values.get('glassBlur',5)))
