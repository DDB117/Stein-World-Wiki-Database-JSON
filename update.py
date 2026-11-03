#!/usr/bin/env python3
"""
Update this repo from the stein.world wiki in one go:

  1. download the wiki's item databases (Lua modules)
  2. convert them to JSON (with convert.py), cleaning up broken field names
  3. rebuild the TEST databases (same items, every stat number scrambled)
  4. print what changed

Usage:
    python3 update.py            # update the files in this folder
    python3 update.py --check    # only report whether the wiki changed (exit 1 if it did)

Only uses the Python standard library. Run by the GitHub Action in
.github/workflows/update.yml, but works the same on your own computer.
"""

import hashlib
import json
import random
import re
import sys
import urllib.request
from pathlib import Path

from convert import convert

HERE = Path(__file__).resolve().parent
WIKI_RAW = 'https://wiki.stein.world/w/index.php?title={}&action=raw'

# wiki module -> (lua file, json file, test json file)
DATABASES = {
    'Module:Database': ('SteinDB.lua', 'SteinDB.json', 'SteinTestDB.json'),
    'Module:Legacy_Database': ('SteinLegacyDB.lua', 'SteinLegacyDB.json', 'SteinTestLegacyDB.json'),
}

# Refuse an update that loses more than this share of items (wiki outage or vandalism).
MAX_ITEM_LOSS = 0.10

# Field names that are broken on the wiki, and what they should be.
FIELD_FIXES = {'Selling valu': 'Selling value', 'Energy Usage': 'Energy usage'}

# Fields whose numbers get scrambled in the TEST databases.
SCRAMBLE = {
    'Armor', 'Casttime', 'Cooldown', 'Cooldown Reduction Rating', 'Critical Bonus Rating',
    'Critical Chance Rating', 'Death Damage', 'Earth Damage', 'Effect', 'Energy Regeneration',
    'Energy usage', 'Fire Damage', 'Function', 'Heal', 'Holy Damage', 'Life', 'Life Regeneration',
    'Magic Damage', 'Mana', 'Mana Regeneration', 'Mana usage', 'Physical Damage', 'Selling value',
    'Soul Damage', 'Threat', 'Water Damage',
}
NUMBER = re.compile(r'\d+(?:\.\d+)?')


def download(module):
    req = urllib.request.Request(WIKI_RAW.format(module), headers={'User-Agent': 'Stein-World-Wiki-Database-JSON updater'})
    with urllib.request.urlopen(req, timeout=60) as res:
        text = res.read().decode('utf-8')
    if not text.lstrip().startswith('return {'):
        raise SystemExit(f'{module}: unexpected content from the wiki (starts with {text[:40]!r})')
    return text.rstrip('\n') + '\n'


def clean_field(name):
    name = name.replace('​', '').strip()
    return FIELD_FIXES.get(name, name)


def clean(items):
    """Fix field names like 'Critical Bonus Rating\\u200b' so tools can find them."""
    fixed = 0
    out = {}
    for key, item in items.items():
        new = {}
        for field, value in item.items():
            name = clean_field(field)
            fixed += name != field
            new.setdefault(name, value)
        out[key] = new
    return out, fixed


def scramble(items, seed):
    """Same items, but every number in a stat field replaced by a random one."""
    rng = random.Random(seed)

    def fake(match):
        text = match.group(0)
        top = max(10.0, float(text) * 10)
        return f'{rng.uniform(0, top):.1f}' if '.' in text else str(rng.randint(0, int(top)))

    return {
        key: {f: NUMBER.sub(fake, v) if f in SCRAMBLE else v for f, v in item.items()}
        for key, item in items.items()
    }


def to_json(items):
    return json.dumps(items, ensure_ascii=False, indent=2, sort_keys=True) + '\n'


def describe(old, new):
    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    changed = sorted(k for k in set(old) & set(new) if old[k] != new[k])
    parts = [f'{len(new)} items']
    for label, keys in (('added', added), ('removed', removed), ('changed', changed)):
        if keys:
            preview = ', '.join(keys[:5]) + (f' (+{len(keys) - 5} more)' if len(keys) > 5 else '')
            parts.append(f'{len(keys)} {label}: {preview}')
    return '; '.join(parts)


def main():
    check_only = '--check' in sys.argv
    any_change = False

    for module, (lua_name, json_name, test_name) in DATABASES.items():
        lua_text = download(module)
        items, duplicates = convert(lua_text)
        items, fixed = clean(items)

        json_path = HERE / json_name
        old = json.loads(json_path.read_text(encoding='utf-8')) if json_path.exists() else {}
        if old and len(items) < len(old) * (1 - MAX_ITEM_LOSS):
            raise SystemExit(f'{module}: only {len(items)} items (had {len(old)}). Refusing to update; check the wiki.')

        new_json = to_json(items)
        lua_changed = (HERE / lua_name).read_text(encoding='utf-8') != lua_text if (HERE / lua_name).exists() else True
        json_changed = not json_path.exists() or json_path.read_text(encoding='utf-8') != new_json
        if not (lua_changed or json_changed):
            print(f'{json_name}: no changes ({len(items)} items)')
            continue

        any_change = True
        print(f'{json_name}: {describe(old, items)}')
        if fixed:
            print(f'  cleaned {fixed} broken field name(s)')
        if duplicates:
            print(f'  warning: duplicate item names on the wiki: {", ".join(sorted(set(duplicates)))}')
        if check_only:
            continue

        (HERE / lua_name).write_text(lua_text, encoding='utf-8')
        json_path.write_text(new_json, encoding='utf-8')
        # Seeded by the data, so the TEST file only changes when the real data does.
        seed = hashlib.sha256(new_json.encode('utf-8')).hexdigest()
        (HERE / test_name).write_text(to_json(scramble(items, seed)), encoding='utf-8')

    if check_only:
        sys.exit(1 if any_change else 0)
    if not any_change:
        print('Everything is up to date.')


if __name__ == '__main__':
    main()
