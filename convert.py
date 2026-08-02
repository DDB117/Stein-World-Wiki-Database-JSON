#!/usr/bin/env python3
"""
Convert a stein.world SteinDB Lua module (the wiki's item database) into JSON.

The Lua source is extremely regular:
  - top-level is `return { ... }`
  - each item is `["Item Name"]={ ... },`
  - each field is `["Key"] = "Value",`  (last field ends `"},`)
  - all keys and values are double-quoted; no escaped quotes, no single
    quotes, no unquoted numbers, no multi-line values, comments start with --

So a stateful line parser is enough and needs no dependencies.

Usage:
    python3 convert.py input.lua output.json
    python3 convert.py input.lua            # -> input.json next to it
"""

import json
import re
import sys
from pathlib import Path

# ["Item Name"]={     (an item block header: ends in an opening brace)
HEADER_RE = re.compile(r'^\["(?P<name>.*?)"\]\s*=\s*\{$')
# ["Key"] = "Value"   (a field line, after we've stripped its trailing , or },)
FIELD_RE = re.compile(r'^\["(?P<key>.*?)"\]\s*=\s*"(?P<value>.*)"$')


def convert(lua_text: str):
    items = {}
    current_name = None
    current = None
    duplicates = []

    for lineno, raw in enumerate(lua_text.splitlines(), start=1):
        line = raw.strip()

        # Skip blank lines, comments, and the outer `return {` / final `}`
        if not line or line.startswith("--") or line in ("return {", "}", "{"):
            continue

        # Item header?
        m = HEADER_RE.match(line)
        if m:
            current_name = m.group("name")
            if current_name in items:
                duplicates.append(current_name)
            current = {}
            items[current_name] = current
            continue

        # Otherwise it's a field line. Figure out whether it closes the block.
        closes_block = line.endswith("},")
        if closes_block:
            core = line[:-2]          # strip the closing "},"
        elif line.endswith(","):
            core = line[:-1]          # strip the trailing ","
        else:
            core = line

        m = FIELD_RE.match(core)
        if not m:
            raise ValueError(f"Unparseable line {lineno}: {raw!r}")
        if current is None:
            raise ValueError(f"Field outside any item at line {lineno}: {raw!r}")

        current[m.group("key")] = m.group("value")

        if closes_block:
            current_name = None
            current = None

    return items, duplicates


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: python3 convert.py input.lua [output.json]")

    src = Path(sys.argv[1])
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else src.with_suffix(".json")

    text = src.read_text(encoding="utf-8")
    items, duplicates = convert(text)

    dst.write_text(
        json.dumps(items, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"Parsed {len(items)} items -> {dst}")
    if duplicates:
        print(f"WARNING: {len(duplicates)} duplicate name(s) (last one wins): "
              f"{', '.join(sorted(set(duplicates)))}")


if __name__ == "__main__":
    main()
