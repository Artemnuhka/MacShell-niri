#!/usr/bin/env python3
"""Conservative KDL edits: managed block and rootless Xwayland migration.

No compositor is started. Configurations are validated using `niri validate`.
Includes are rejected during migration rather than silently rewriting other files.
"""
import argparse
import datetime
import json
import re
import shutil
import subprocess
from pathlib import Path

BEGIN = '// BEGIN macshell-niri (managed)'
END = '// END macshell-niri (managed)'


def tokens(text):
    """Lex enough KDL to preserve comments, multiline strings and nested blocks."""
    result = []
    i = 0
    while i < len(text):
        start = i
        if text.startswith('//', i):
            end = text.find('\n', i)
            i = len(text) if end < 0 else end
        elif text.startswith('/*', i):
            depth = 1
            i += 2
            while depth and i < len(text):
                if text.startswith('/*', i):
                    depth += 1
                    i += 2
                elif text.startswith('*/', i):
                    depth -= 1
                    i += 2
                else:
                    i += 1
            if depth:
                raise ValueError('Unterminated KDL comment')
        elif text[i] in ' \t\r':
            i += 1
        elif text[i] in '{};=\n':
            i += 1
            result.append((text[start:i], start, i))
        elif text.startswith('/-', i):
            i += 2
            result.append(('/-', start, i))
        else:
            raw = re.match(r'r?(#+)"', text[i:])
            if raw:
                marker = '"' + raw[1]
                end = text.find(marker, i + raw.end())
                if end < 0:
                    raise ValueError('Unterminated raw string')
                i = end + len(marker)
            elif text[i] == '"':
                # Reject uncommon multiline strings rather than guessing boundaries.
                if text.startswith('"""', i):
                    raise ValueError('Multiline KDL strings require manual migration')
                i += 1
                while i < len(text):
                    if text[i] == '\\':
                        i += 2
                    elif text[i] == '"':
                        i += 1
                        break
                    else:
                        i += 1
                else:
                    raise ValueError('Unterminated KDL string')
            else:
                while i < len(text) and text[i] not in ' \t\r\n{};=':
                    i += 1
            result.append((text[start:i], start, i))
    return result


def nodes(text):
    ts = tokens(text)
    out = []
    i = 0
    while i < len(ts):
        if ts[i][0] in ('\n', ';'):
            i += 1
            continue
        begin = i
        depth = 0
        while i < len(ts):
            val = ts[i][0]
            if val == '{':
                depth += 1
            elif val == '}':
                depth -= 1
                if depth < 0:
                    raise ValueError('Unbalanced KDL block')
            if depth == 0 and val in ('\n', ';'):
                break
            i += 1
            if depth == 0 and val == '}':
                break
        if depth:
            raise ValueError('Unbalanced KDL block')
        part = ts[begin:i]
        out.append((part[0][0], part, part[0][1], part[-1][2]))
    return out


def managed(text):
    for begin, end in ((BEGIN, END), ('// BEGIN macshell-niri bindings', '// END macshell-niri bindings')):
        if begin in text or end in text:
            if text.count(begin) != 1 or text.count(end) != 1:
                raise ValueError('Malformed macshell-niri managed block')
            a, b = text.index(begin), text.index(end) + len(end)
            if a >= b:
                raise ValueError('Malformed macshell-niri managed block')
            text = text[:a] + text[b:]
    return text


def merge_keybinds(text, launcher, lock_launcher=None):
    example = (Path(__file__).resolve().parent.parent / 'config/niri.example.kdl').read_text()
    def children(part):
        opening = next(t for t in part if t[0] == '{')
        closing = next(t for t in reversed(part) if t[0] == '}')
        return opening[2], closing[1]
    desired = []
    for name, part, _, _ in nodes(example):
        if name == 'binds':
            a, b = children(part)
            desired = [(key, example[a:b][start:end]) for key, _, start, end in nodes(example[a:b])]
    existing = next((n for n in nodes(text) if n[0] == 'binds'), None)
    if existing:
        a, b = children(existing[1])
        inner = text[a:b]
        used = {name.lower() for name, _, _, _ in nodes(inner)}
    else:
        a = b = len(text)
        inner, used = '', set()
    additions = []
    for key, line in desired:
        if '"macshell-lock"' in line and lock_launcher is None:
            continue
        if key.lower() in used:
            print(f'Existing binding preserved: {key}')
            continue
        additions.append(line.replace('"macshell-niri"', json.dumps(str(launcher))).replace('"macshell-lock"', json.dumps(str(lock_launcher))))
    if not additions:
        return text
    block = ['// BEGIN macshell-niri bindings', *additions, '// END macshell-niri bindings']
    body = inner.rstrip() + '\n' + '\n'.join('    ' + line for line in block) + '\n'
    if existing:
        return text[:a] + body + text[b:]
    return text.rstrip() + '\n\nbinds {' + body + '}\n'


def migrate(text):
    edits = []
    for name, ts, start, end in nodes(text):
        if name == 'include':
            raise ValueError('Config contains includes: migrate Xwayland in included files manually; see README.md')
        body = text[start:end]
        if name == 'xwayland-satellite':
            edits.append((start, end, ''))
        elif name in ('spawn-at-startup', 'spawn-sh-at-startup'):
            # Only disable commands that launch the server directly. Other actions
            # containing these words are left alone and reported to the user.
            args = []
            for token, _, _ in ts[1:]:
                if token in ('\n', ';'):
                    continue
                try:
                    args.append(json.loads(token) if token.startswith('"') else token)
                except ValueError:
                    raise ValueError('Complex startup string requires manual Xwayland migration')
            simple = args and Path(args[0]).name in ('Xwayland', 'xwayland-satellite')
            command = args[0] if name == 'spawn-sh-at-startup' and args else ''
            if len(args) >= 3 and Path(args[0]).name in ('sh', 'bash') and args[1] == '-c':
                command = args[2]
            if command and re.search(r'\b(?:Xwayland|xwayland-satellite)\b', command):
                if re.match(r'^\s*(?:exec\s+)?(?:/[^\s]+/)?(?:Xwayland|xwayland-satellite)(?:\s|$)', command) and not re.search(r'[;&|`$\n]', command):
                    simple = True
                else:
                    raise ValueError('Complex Xwayland startup command needs manual migration: ' + body.strip())
            if simple:
                print(f'Disable legacy Xwayland startup: {body.strip()}')
                edits.append((start, end, '// Disabled by macshell-niri: niri manages rootless Xwayland.'))
        elif name == 'environment':
            opening = next(t for t in ts if t[0] == '{')
            closing = next(t for t in reversed(ts) if t[0] == '}')
            inner = text[opening[2]:closing[1]]
            for child, _, a, b in nodes(inner):
                if child.strip('"') == 'DISPLAY':
                    print('Remove fixed DISPLAY from niri environment; niri sets it automatically.')
                    edits.append((opening[2] + a, opening[2] + b, ''))
    for a, b, replacement in sorted(edits, reverse=True):
        text = text[:a] + replacement + text[b:]
    return text


def configure(path, launcher, fix_xwayland=True, remove=False, validator="niri", lock_launcher=None):
    path = Path(path)
    if path.is_symlink():
        raise ValueError('Refusing to replace a symlinked niri config; edit the target explicitly')
    existed = path.exists()
    original = path.read_text() if existed else (Path(__file__).resolve().parent.parent / 'config/niri.base.kdl').read_text()
    if not existed:
        original = original.replace('spawn "macshell-niri"', 'spawn ' + json.dumps(str(launcher)))
    text = managed(original)
    anchor = '// MACSHELL_INTERNAL_INSERTION_POINT'
    if not remove and BEGIN in original:
        # Keep our block in place: moving it past theme/cursor blocks on each
        # reinstall otherwise produces unnecessary configuration backups.
        if anchor in original:
            raise ValueError('Reserved installer insertion marker in configuration')
        a, b = original.index(BEGIN), original.index(END) + len(END)
        text = managed(original[:a] + anchor + original[b:])
    if remove:
        text = text.replace('Mod+Return { spawn ' + json.dumps(str(launcher.parent / 'macshell-terminal')) + '; }',
                            'Mod+Return { spawn "kitty"; }')
    if not remove:
        if fix_xwayland:
            text = migrate(text)
        text = merge_keybinds(text, launcher, lock_launcher)
        # Only migrate our exact starter shortcut; preserve custom terminal commands.
        text = text.replace('Mod+Return { spawn \"kitty\"; }',
                            'Mod+Return { spawn ' + json.dumps(str(launcher.parent / 'macshell-terminal')) + '; }')
        block = [BEGIN, 'spawn-at-startup ' + json.dumps(str(launcher)),
                 'window-rule {', '    match title="^(macshell Settings|Clock)$"', '    open-floating true', '}']
        if fix_xwayland:
            block += ['xwayland-satellite {', '    path "xwayland-satellite"', '}']
        block += ['// Ask the compositor to blur windows as well as wallpaper. Exact shapes come from BackgroundEffect.',
                  'layer-rule {',
                  '    match namespace="^(macbar|macdock|macspot|macswitch|macwall)$"',
                  '    background-effect { xray false; }',
                  '}']
        block += [END]
        if anchor in text:
            text = text.replace(anchor, '\n'.join(block))
        else:
            text = text.rstrip() + '\n\n' + '\n'.join(block) + '\n'
    if text == original:
        return
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backup = path.with_name(path.name + '.macshell-backup-' + stamp)
    path.parent.mkdir(parents=True, exist_ok=True)
    if existed:
        shutil.copy2(path, backup)
    candidate = path.with_name('.macshell-candidate-' + stamp + '.kdl')
    try:
        candidate.write_text(text)
        result = subprocess.run([str(validator), 'validate', '--config', str(candidate)], check=False)
        if result.returncode:
            raise ValueError('niri rejected the candidate; original config has not been changed')
        candidate.chmod((path.stat().st_mode & 0o777) if existed else 0o600)
        candidate.replace(path)
    finally:
        candidate.unlink(missing_ok=True)
    print(f'Config updated. Backup: {backup}' if existed else f'Created niri config: {path}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('config', type=Path)
    parser.add_argument('launcher', type=Path)
    parser.add_argument('--keep-xwayland-config', action='store_true')
    parser.add_argument('--remove', action='store_true')
    args = parser.parse_args()
    try:
        configure(args.config, args.launcher, not args.keep_xwayland_config, args.remove)
    except (OSError, ValueError) as exc:
        parser.exit(1, f'{exc}\n')
