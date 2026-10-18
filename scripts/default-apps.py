#!/usr/bin/env python3
"""Read installed applications and change only explicitly selected user defaults."""
import fcntl
import json
import os
from pathlib import Path
import shlex
import shutil
import sys
import tempfile

ROLES = {
    'browser': ('Web browser', ['x-scheme-handler/https','x-scheme-handler/http','text/html','application/xhtml+xml']),
    'mail': ('Email', ['x-scheme-handler/mailto']),
    'files': ('File manager', ['inode/directory']),
    'terminal': ('Terminal', []),
    'text': ('Text editor', ['text/plain']),
    'pdf': ('PDF documents', ['application/pdf']),
    'images': ('Images', ['image/png','image/jpeg','image/webp','image/gif','image/tiff','image/bmp']),
    'audio': ('Audio', ['audio/mpeg','audio/flac','audio/ogg','audio/x-wav']),
    'video': ('Video', ['video/mp4','video/webm','video/x-matroska','video/x-msvideo','video/quicktime']),
}


def libraries():
    import gi
    from gi.repository import Gio
    try:
        gi.require_version('GioUnix','2.0')
        from gi.repository import GioUnix
        desktop=GioUnix.DesktopAppInfo
    except (ImportError,ValueError):
        desktop=Gio.DesktopAppInfo
    return Gio,desktop


def paths():
    home=Path.home()
    return Path(os.environ.get('XDG_CONFIG_HOME',str(home/'.config'))),Path(os.environ.get('XDG_DATA_HOME',str(home/'.local/share')))


def saved_terminal(config):
    try:return str(json.loads((config/'macshell/default-apps.json').read_text()).get('terminal',''))
    except (OSError,ValueError,TypeError):return ''


def desktop_entry(desktop,app_id):
    try:return desktop.new(app_id)
    except (TypeError,ValueError):return None


def is_terminal(app):
    categories=app.get_categories() or ''
    return 'TerminalEmulator' in categories.split(';') and not app.get_boolean('Terminal')


def terminal_id(config,desktop):
    selected=saved_terminal(config)
    if selected:return selected
    for name in ('niri-xdg-terminals.list','xdg-terminals.list'):
        path=config/name
        if not path.is_file():continue
        for line in path.read_text().splitlines():
            value=line.strip()
            if not value.endswith('.desktop') or value.startswith(('#','-','/')):continue
            app=desktop_entry(desktop,value.lstrip('+'))
            if app and is_terminal(app):return app.get_id()
    for value in ('kitty.desktop','org.kde.konsole.desktop','com.mitchellh.ghostty.desktop','Alacritty.desktop','foot.desktop'):
        if desktop_entry(desktop,value):return value
    return ''


def app_dict(app):
    icon=app.get_icon()
    return {'id':app.get_id(),'name':app.get_display_name(),'icon':icon.to_string() if icon else ''}


def catalog():
    gio,desktop=libraries();config,_=paths()
    apps=[app for app in gio.AppInfo.get_all() if app.get_id() and app.should_show()]
    result=[]
    for role,(name,mimes) in ROLES.items():
        current_id=terminal_id(config,desktop) if role=='terminal' else ''
        current=None
        if mimes:current=gio.AppInfo.get_default_for_type(mimes[0],False)
        if current:current_id=current.get_id() or ''
        options={}
        for app in apps:
            if role=='terminal':eligible=is_terminal(app)
            else:eligible=bool(set(app.get_supported_types() or []) & set(mimes))
            if eligible:options[app.get_id()]=app_dict(app)
        # Retain an existing association even when its entry is hidden or its
        # declared MIME types are incomplete. Never silently replace it.
        if current_id:
            current=current or desktop_entry(desktop,current_id)
            if current:options[current_id]=app_dict(current)
            elif role=='terminal':options[current_id]={'id':current_id,'name':current_id+' (not installed)','icon':''}
        result.append({'id':role,'name':name,'current':current_id,
                       'apps':sorted(options.values(),key=lambda app:(app['name'].casefold(),app['id']))})
    return {'roles':result}


def write_atomic(path,text):
    if path.is_symlink():raise ValueError('Refusing to replace a symlinked preference file.')
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.macshell-default-',dir=path.parent)
    candidate=Path(name)
    try:
        with os.fdopen(fd,'w') as stream:stream.write(text)
        candidate.chmod(path.stat().st_mode & 0o777 if path.exists() else 0o600)
        candidate.replace(path)
    finally:candidate.unlink(missing_ok=True)


def tracked_preferences(config,data):
    return set(config.glob('*mimeapps.list')) | {config/'mimeapps.list',data/'applications/mimeapps.list',
                config/'macshell/default-apps.json',config/'xdg-terminals.list',config/'niri-xdg-terminals.list'}


def terminal_preferences(config,app_id):
    path=config/'macshell/default-apps.json'
    values=json.loads(path.read_text()) if path.is_file() else {}
    values['terminal']=app_id
    write_atomic(path,json.dumps(values,indent=2)+'\n')
    # XDG terminal launchers can use the same preference. Preserve other entries,
    # exclusions and comments rather than replacing the whole list.
    for name in ('xdg-terminals.list','niri-xdg-terminals.list'):
        path=config/name
        if name.startswith('niri-') and not path.exists():continue
        lines=path.read_text().splitlines() if path.exists() else []
        lines=[line for line in lines if line.strip() not in (app_id,'+'+app_id,'-'+app_id)]
        write_atomic(path,app_id+'\n'+'\n'.join(lines)+('\n' if lines else ''))


def apply(changes):
    if not isinstance(changes,dict) or any(role not in ROLES for role in changes):raise ValueError('Unknown default application category.')
    gio,desktop=libraries();config,data=paths()
    config.joinpath('macshell').mkdir(parents=True,exist_ok=True)
    with (config/'macshell/default-apps.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        roles={role['id']:role for role in catalog()['roles']}
        entries={}
        for role,app_id in changes.items():
            if not isinstance(app_id,str) or app_id not in {app['id'] for app in roles[role]['apps']}:
                raise ValueError('Choose an installed application that supports this category.')
            app=desktop_entry(desktop,app_id)
            if not app:raise ValueError('The selected application is no longer installed.')
            entries[role]=app
        before={path:path.read_bytes() if path.is_file() else None for path in tracked_preferences(config,data)}
        modes={path:path.stat().st_mode & 0o777 for path,content in before.items() if content is not None}
        if any(path.is_symlink() for path in before):raise ValueError('Symlinked application preferences require manual editing.')
        try:
            for role,app in entries.items():
                if role=='terminal':terminal_preferences(config,app.get_id())
                else:
                    for mime in ROLES[role][1]:
                        if not app.set_as_default_for_type(mime):raise RuntimeError('The application association could not be saved.')
        except BaseException:
            for path in tracked_preferences(config,data)|set(before):
                content=before.get(path)
                if content is None:path.unlink(missing_ok=True)
                else:
                    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content);path.chmod(modes.get(path,0o600))
            raise
        for path,content in before.items():
            if content is None or not path.is_file() or path.read_bytes()==content:continue
            backup=path.with_name(path.name+'.before-macshell-defaults')
            if not backup.exists():
                backup.write_bytes(content);backup.chmod(modes.get(path,0o600))
    return catalog()


def command_for_terminal(app,arguments):
    # Desktop Exec field codes are placeholders, not shell syntax. Keep all
    # literal arguments (including Flatpak/env wrappers), never use a shell.
    tokens=shlex.split(app.get_commandline() or '')
    base=[]
    for token in tokens:
        if token in ('%f','%F','%u','%U','%i','%c','%k'):continue
        base.append(token.replace('%%','%'))
    if not base:raise ValueError('The selected terminal has no launch command.')
    if arguments and arguments[0]=='-e':
        command=arguments[1:]
        if not command:raise ValueError('Missing command after -e.')
        separator=app.get_string('X-TerminalArgExec')
        if separator is None:separator=app.get_string('TerminalArgExec')
        if separator is None:
            app_id=app.get_id().lower()
            separator='--' if any(v in app_id for v in ('gnome.terminal','gnome.console','ptyxis','foot')) else '-e'
        return base+shlex.split(separator)+command
    return base+arguments


def launch_terminal(arguments):
    explicit=None
    if arguments[:1]==['--app']:
        if len(arguments)<2:raise ValueError('Missing terminal application.')
        explicit=arguments[1];arguments=arguments[2:]
    config,_=paths()
    selected=explicit or saved_terminal(config)
    app=None
    try:
        _,desktop=libraries()
        selected=selected or terminal_id(config,desktop)
        app=desktop_entry(desktop,selected) if selected else None
    except ImportError:
        if selected and selected!='kitty.desktop':raise RuntimeError('Install Python GObject bindings to launch the selected terminal.')
    if app:
        if not is_terminal(app):raise ValueError('Selected desktop entry is not a terminal emulator.')
        command=command_for_terminal(app,arguments)
    else:
        if explicit or selected and selected!='kitty.desktop':raise ValueError('The selected terminal is no longer installed. Choose another in Default Applications.')
        binary=shutil.which('kitty')
        if not binary:raise ValueError('No terminal found. Choose one in Default Applications.')
        command=[binary,*arguments]
    product=Path('/sys/class/dmi/id/product_name')
    if product.exists() and 'virtualbox' in product.read_text().lower() and any(v in (selected or '') for v in ('kitty','ghostty')):
        os.environ.setdefault('LIBGL_ALWAYS_SOFTWARE','1')
        if 'ghostty' in (selected or ''):os.environ.setdefault('GSK_RENDERER','cairo')
    os.execvpe(command[0],command,os.environ)


if __name__=='__main__':
    try:
        if len(sys.argv)>1 and sys.argv[1]=='apply':result=apply(json.loads(sys.argv[2]))
        else:result=catalog()
        print(json.dumps(result))
    except (ImportError,ValueError,RuntimeError,OSError) as error:
        sys.exit(str(error))
