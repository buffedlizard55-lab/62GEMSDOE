#!/usr/bin/env python3
"""Scan public repos for path patterns; report matches. Uses `gh api` (authenticated)."""
import json, re, subprocess, sys

REPOS = sys.argv[1].split(",")
PAT = re.compile(sys.argv[2] if len(sys.argv) > 2 else r"dem|elev|shore|lahontan|isobase|srtm|3dep", re.I)

def gh(url):
    out = subprocess.run(["gh", "api", url], capture_output=True, text=True, timeout=120)
    if out.returncode != 0:
        return None
    return json.loads(out.stdout)

for repo in REPOS:
    info = gh(f"repos/{repo}")
    if not info:
        print(f"### {repo}: FAIL"); continue
    br = info.get("default_branch", "main")
    t = gh(f"repos/{repo}/git/trees/{br}?recursive=1")
    rows = [(e.get("size", 0), e["path"]) for e in t.get("tree", []) if e["type"] == "blob"]
    hits = sorted((s, p) for s, p in rows if PAT.search(p))
    print(f"### {repo}  blobs={len(rows)} hits={len(hits)} truncated={t.get('truncated')}")
    for s, p in hits[:60]:
        print(f"   {s/1e6:8.3f}MB {p}")
    if len(hits) > 60:
        print(f"   ... {len(hits)-60} more")
