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

def config_path():
    config = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home()/'.config')))
    return Path(os.environ.get('MACSHELL_GLASS_CONFIG') or os.environ.get('MACSHELL_NIRI_CONFIG') or str(config/'niri/macshell.kdl'))


def keyboard_catalog(file=Path('/usr/share/X11/xkb/rules/evdev.xml')):
    import xml.etree.ElementTree as ET
    tree=ET.parse(file)
    def item(node):
        return {'code':node.findtext('configItem/name'), 'name':node.findtext('configItem/description')}
    layouts=[]
    for node in tree.findall('./layoutList/layout'):
        value=item(node)
        value['variants']=[{'code':'','name':'Default'}]+[item(v) for v in node.findall('./variantList/variant')]
        layouts.append(value)
    shortcuts=[{'code':'','name':'None'}]
    for node in tree.findall('./optionList/group'):
        if node.findtext('configItem/name')=='grp':
            shortcuts += [item(v) for v in node.findall('option')]
    return {'available':sorted(layouts,key=lambda v:v['name']), 'shortcuts':shortcuts}


def keyboard_values(text):
    def child(text,name):
        node=next((n for n in parser().nodes(text) if n[0]==name),None)
        if not node:return ''
        tokens=node[1]
        a=next(t[2] for t in tokens if t[0]=='{')
        b=next(t[1] for t in reversed(tokens) if t[0]=='}')
        return text[a:b]
    xkb=child(child(child(text,'input'),'keyboard'),'xkb')
    values={}
    for name,tokens,_,_ in parser().nodes(xkb):
        if name in ('layout','variant','options'):
            raw=tokens[1][0]
            values[name]=json.loads(raw) if raw.startswith('"') else raw
    codes=values.get('layout','us').split(',')
    variants=values.get('variant','').split(',')
    options=[v for v in values.get('options','').split(',') if v]
    return {'layouts':[{'code':code,'variant':variants[i] if i<len(variants) else ''} for i,code in enumerate(codes)],
            'shortcut':next((v for v in options if v.startswith('grp:')),''), 'options':options}


def keyboard_update(before, values, catalog):
    selected=values['layouts']
    if not 1<=len(selected)<=4:raise ValueError('Choose between one and four input sources.')
    available={v['code']:v for v in catalog['available']}
    seen=set()
    for value in selected:
        code=value['code'];variant=value.get('variant','')
        if code not in available or variant not in [v['code'] for v in available[code]['variants']]:
            raise ValueError('Unknown keyboard layout or variant.')
        if (code,variant) in seen:raise ValueError('This input source is already added.')
        seen.add((code,variant))
    shortcut=values['shortcut']
    if shortcut not in [v['code'] for v in catalog['shortcuts']]:raise ValueError('Unknown layout shortcut.')
    # Retain compose, Caps/Escape remaps, LEDs and all non-switching options.
    options=[v for v in keyboard_values(before)['options'] if not v.startswith('grp:')]
    if shortcut:options.append(shortcut)
    changes=[('layout','layout '+json.dumps(','.join(v['code'] for v in selected))),
             ('variant','variant '+json.dumps(','.join(v.get('variant','') for v in selected))),
             ('options','options '+json.dumps(','.join(options)))]
    return edit_block(before,'input',{'keyboard':{'xkb':changes}})


def keyboard_settings(values=None):
    catalog=keyboard_catalog();path=config_path()
    if values is not None:
        with path.with_suffix('.optics.lock').open('w') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            before=path.read_text();after=keyboard_update(before,values,catalog)
            if after!=before:
                fd,name=tempfile.mkstemp(prefix='.macshell-keyboard-',suffix='.kdl',dir=path.parent);os.close(fd)
                candidate=Path(name)
                try:
                    candidate.write_text(after)
                    subprocess.run([os.environ.get('MACSHELL_GLASS_BINARY','niri'),'validate','--config',str(candidate)],check=True,capture_output=True,text=True)
                    backup=path.with_suffix('.before-keyboard')
                    if not backup.exists():backup.write_text(before)
                    candidate.chmod(path.stat().st_mode & 0o777);candidate.replace(path)
                finally:candidate.unlink(missing_ok=True)
    print(json.dumps(dict(catalog,**keyboard_values(path.read_text()))))

def input_settings(values):
    v=values
    # Boolean niri options are flags: remove the node to turn one off.
    def boolean(name,value):return (name,name if value else None)
    blocks={'keyboard':[('repeat-rate',f'repeat-rate {max(1,min(100,int(v["repeatRate"])))}'),('repeat-delay',f'repeat-delay {max(100,min(2000,int(v["repeatDelay"])))}')],
            'mouse':[('accel-speed',f'accel-speed {max(-1,min(1,float(v["mouseSens"])))}'),boolean('natural-scroll',v['mouseNatural'])],
            'touchpad':[boolean('natural-scroll',v['tpNatural']),boolean('tap',v['tpTap']),boolean('dwt',v['tpDwt']),('scroll-factor',f'scroll-factor {max(.1,min(10,float(v["tpScroll"])))}')]}
    path=config_path()
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
        result.append(dict(name=name,description=' '.join(filter(None,[o.get('make'),o.get('model')])),width=m['width'],height=m['height'],refreshRate=m['refresh_rate']/1000,scale=l['scale'],x=l['x'],y=l['y'],logicalWidth=l['width'],logicalHeight=l['height'],availableModes=[f'{m["width"]}x{m["height"]}@{m["refresh_rate"]/1000:.3f}Hz' for m in modes]))
    print(json.dumps(result))

if __name__=='__main__':
    if sys.argv[1]=='monitors':monitors()
    elif sys.argv[1]=='keyboard':keyboard_settings(json.loads(sys.argv[2]) if len(sys.argv)>2 else None)
    elif sys.argv[1]=='input':input_settings(json.loads(sys.argv[2]))
    elif sys.argv[1]=='gaming':
        os.environ.setdefault('MACSHELL_GLASS_CONFIG','')
        spec=importlib.util.spec_from_file_location('glass',Path(__file__).with_name('update-glass.py'))
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        settings=Path.home()/'.config/macbar/settings.json'
        values=json.loads(settings.read_text()) if settings.exists() else {}
        mod.update(0 if sys.argv[2]=='on' else float(values.get('glassLiquid',1)),0 if sys.argv[2]=='on' else float(values.get('glassBlur',5)))
