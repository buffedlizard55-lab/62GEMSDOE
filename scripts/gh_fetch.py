#!/usr/bin/env python3
"""Fetch a single blob from a public GitHub repo through api.github.com/contents.

Only hosts reachable from this sandbox: github.com, codeload.github.com, api.github.com.
Usage: python3 scripts/gh_fetch.py <repo> <path-in-repo> <dest>
"""
from __future__ import annotations
import hashlib, pathlib, sys, urllib.request

OWNER = "buffedlizard55-lab"

def fetch(repo: str, path: str, dest: str) -> str:
    url = f"https://api.github.com/repos/{OWNER}/{repo}/contents/{path}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "62gemsdoe-fetch", "Accept": "application/vnd.github.raw"})
    with urllib.request.urlopen(req, timeout=900) as r:
        data = r.read()
    p = pathlib.Path(dest); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return hashlib.sha256(data).hexdigest()

if __name__ == "__main__":
    repo, path, dest = sys.argv[1], sys.argv[2], sys.argv[3]
    h = fetch(repo, path, dest)
    print(f"{pathlib.Path(dest).stat().st_size:>12d} B  sha256={h}  {dest}")
