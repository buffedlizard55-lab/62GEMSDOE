#!/usr/bin/env python3
"""List entries of a public GitHub repo tree; optional path substring filter."""
import json, sys, urllib.request

def api(url):
    req = urllib.request.Request(url, headers={"User-Agent": "repo-audit", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)

repo = sys.argv[1]
filt = sys.argv[2] if len(sys.argv) > 2 else ""
info = api(f"https://api.github.com/repos/{repo}")
br = info.get("default_branch", "main")
t = api(f"https://api.github.com/repos/{repo}/git/trees/{br}?recursive=1")
rows = [(e.get("size", 0), e["path"]) for e in t.get("tree", []) if e["type"] == "blob"]
rows = [(s, p) for s, p in rows if filt in p]
rows.sort()
print(f"### {repo}  matches={len(rows)} total_bytes={sum(s for s,_ in rows)/1e6:.2f}MB")
for s, p in rows:
    print(f"  {s/1e6:9.3f}MB  {p}")
