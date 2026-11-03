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

Only uses the Python standard library. Run it from a home connection: the wiki's
Cloudflare protection blocks datacenter IPs such as GitHub Actions.
"""

import hashlib
import json
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from convert import convert

HERE = Path(__file__).resolve().parent
WIKI_RAW = 'https://wiki.stein.world/w/index.php?title={}&action=raw'
WIKI_API = 'https://wiki.stein.world/w/api.php?'
# Miraheze (the wiki host) blocks requests without a descriptive User-Agent that has contact info.
USER_AGENT = 'SteinWikiDatabaseJSON/1.1 (https://github.com/DDB117/Stein-World-Wiki-Database-JSON) python-urllib'

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


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as res:
        return res.read().decode('utf-8')


def from_raw(module):
    return fetch(WIKI_RAW.format(module))


def from_api(module):
    query = urllib.parse.urlencode({
        'action': 'query', 'prop': 'revisions', 'titles': module, 'rvprop': 'content',
        'rvslots': 'main', 'format': 'json', 'formatversion': '2',
    })
    data = json.loads(fetch(WIKI_API + query))
    return data['query']['pages'][0]['revisions'][0]['slots']['main']['content']


def download(module):
    """Try the raw page, then the API, a few times each. Explain the failure if all fail."""
    errors = []
    for attempt in range(3):
        for source in (from_raw, from_api):
            try:
                text = source(module)
            except urllib.error.HTTPError as e:
                body = e.read(300).decode('utf-8', 'replace').replace('\n', ' ')
                errors.append(f'{source.__name__}: HTTP {e.code} (server: {e.headers.get("Server")}) {body!r}')
                continue
            except (urllib.error.URLError, TimeoutError, KeyError, IndexError, ValueError) as e:
                errors.append(f'{source.__name__}: {e!r}')
                continue
            if text.lstrip().startswith('return {'):
                return text.rstrip('\n') + '\n'
            errors.append(f'{source.__name__}: unexpected content (starts with {text[:40]!r})')
        time.sleep(10 * (attempt + 1))
    raise SystemExit(f'{module}: could not download from the wiki:\n  ' + '\n  '.join(errors))


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
