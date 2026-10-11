#!/usr/bin/env python3
"""Rewrite sandbox-absolute paths in this lane's evidence JSONs to repo-relative form.

The lane was developed at the repository root (sandbox path /home/user/62GEMSDOE)
and later consolidated into lane62/ so that it does not collide with the sibling
lane that already occupies the repository root.  The receipts recorded absolute
paths; this script rewrites them to lane62-relative paths.  Only the 'file' /
'path' strings are touched -- no measured value, hash or byte count is altered.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # .../lane62
REPO = ROOT.parent
SUBS = [
    (str(REPO) + "/lane62/", ""),      # already-correct prefix, if any
    (str(REPO) + "/", "lane62/"),
    ("/home/user/62GEMSDOE/lane62/", ""),
    ("/home/user/62GEMSDOE/", "lane62/"),
]
PAT = re.compile("|".join(re.escape(p) for p, _ in SUBS))


def fix(s: str) -> str:
    for old, new in SUBS:
        s = s.replace(old, new)
    return s


def walk(o):
    if isinstance(o, dict):
        return {k: (fix(v) if isinstance(v, str) and PAT.search(v) else walk(v))
                for k, v in o.items()}
    if isinstance(o, list):
        return [walk(v) for v in o]
    return o


def main():
    n = 0
    for p in sorted(list((ROOT / "evidence").glob("*.json")) +
                    list((ROOT / "docs" / "downloads").glob("*.json")) +
                    list((ROOT / "docs" / "data").glob("*.json"))):
        obj = json.loads(p.read_text())
        new = walk(obj)
        if new != obj:
            p.write_text(json.dumps(new, indent=1) + "\n")
            n += 1
            print("rewrote", p.relative_to(REPO))
    print(f"{n} file(s) rewritten")


if __name__ == "__main__":
    sys.exit(main())
