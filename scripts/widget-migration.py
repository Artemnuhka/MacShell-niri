"""Migrate the original widget layout without modifying or deleting its source."""
import json
from pathlib import Path


def migrate(config):
    old = Path(config) / 'macwidgets/settings.json'
    new = Path(config) / 'macshell/widgets.json'
    if new.exists() or not old.is_file():
        return
    source = json.loads(old.read_text())
    widgets = []
    types = {'weather': 'weather', 'calendar': 'calendar', 'clock': 'clock', 'player': 'music'}
    for index, item in enumerate(source.get('widgets', [])):
        if not isinstance(item, dict) or item.get('type') not in types:
            continue
        widgets.append({'id': str(item.get('id', f'legacy-{index}')),
                        'type': types[item['type']],
                        'size': {'small': 's', 'medium': 'm', 'large': 'l'}.get(item.get('size'), 's'),
                        'style': 'glass' if item.get('style') == 'liquid' else 'opaque',
                        'x': max(8, float(item.get('x', 32))),
                        'y': max(36, float(item.get('y', 56))), 'screen': ''})
    new.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation protects an already-created new layout during an update.
    try:
        with new.open('x') as stream:
            json.dump({'enabled': True, 'style': 'glass', 'glassAmt': 0.5,
                       'blurAmt': 0.5, 'cityName': source.get('cityName', ''), 'widgets': widgets}, stream, indent=2)
    except FileExistsError:
        return
    print(f'Migrated widget layout: {old} -> {new}; original preserved.')
