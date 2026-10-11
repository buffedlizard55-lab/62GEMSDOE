#!/usr/bin/env python3
"""List a public GitHub repo's tree via the API (no auth needed for public repos)."""
import json, sys, urllib.request

def api(url):
    req = urllib.request.Request(url, headers={"User-Agent": "repo-audit", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)

def tree(repo, branch="HEAD"):
    info = api(f"https://api.github.com/repos/{repo}")
    br = info.get("default_branch", "main")
    t = api(f"https://api.github.com/repos/{repo}/git/trees/{br}?recursive=1")
    return info, t

if __name__ == "__main__":
    for repo in sys.argv[1:]:
        try:
            info, t = tree(repo)
        except Exception as e:
            print(f"### {repo}: ERROR {e}"); continue
        print(f"### {repo}  default_branch={info.get('default_branch')} size={info.get('size')}KB truncated={t.get('truncated')} entries={len(t.get('tree',[]))}")
        rows = []
        for e in t.get("tree", []):
            rows.append((e["type"], e.get("size", 0), e["path"]))
        # print dirs summary + biggest files
        dirs = sorted({p.rsplit("/", 1)[0] for ty, s, p in rows if "/" in p and ty == "blob"})
        for d in dirs[:40]:
            n = sum(1 for ty, s, p in rows if ty == "blob" and p.startswith(d + "/"))
            sz = sum(s for ty, s, p in rows if ty == "blob" and p.startswith(d + "/"))
            print(f"   dir {d}/  files={n} bytes={sz/1e6:.2f}MB")
        files = sorted([(s, p) for ty, s, p in rows if ty == "blob" and "/" not in p], reverse=True)
        for s, p in files[:15]:
            print(f"   file {p}  {s/1e6:.2f}MB")
