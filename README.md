This repo can be considered as AI SLOP. If you care about that, then make a new repo.

The data in this repository is derived from [stein.world Wiki](https://wiki.stein.world/wiki/), licensed under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). This repository and its contents remain licensed under CC BY-SA 4.0.

## Updating

`update.py` downloads the item databases from the wiki (`Module:Database` and `Module:Legacy Database`), converts them to JSON with `convert.py`, fixes broken field names (hidden zero-width spaces, typos like `Selling valu`), and rebuilds the TEST databases (same items, every stat number scrambled, for testing tools that compare stats).

```
python3 update.py          # update the files
python3 update.py --check  # only report what changed on the wiki
```

A GitHub Action (`.github/workflows/update.yml`) runs it every day and commits only when the wiki changed. It can also be started by hand from the Actions tab. GitHub pauses scheduled runs after 60 days without any repo activity; it sends an email and one click re-enables it.
