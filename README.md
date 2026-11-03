This repo can be considered as AI SLOP. If you care about that, then make a new repo.

The data in this repository is derived from [stein.world Wiki](https://wiki.stein.world/wiki/), licensed under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). This repository and its contents remain licensed under CC BY-SA 4.0.

## Updating

`update.py` downloads the item databases from the wiki (`Module:Database` and `Module:Legacy Database`), converts them to JSON with `convert.py`, fixes broken field names (hidden zero-width spaces, typos like `Selling valu`), and rebuilds the TEST databases (same items, every stat number scrambled, for testing tools that compare stats).

```
python3 update.py          # update the files
python3 update.py --check  # only report what changed on the wiki
```

To publish an update, run it on your own computer, then commit and push:

```
python3 update.py
git add -A && git commit -m "Update from wiki" && git push
```

It has to run from a home connection: the wiki's Cloudflare protection blocks GitHub's servers ("Checking your connection" page), so a GitHub Action can't download it.
