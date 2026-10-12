#!/usr/bin/env python3
"""Fetch the registry raster masks needed to rebuild the S* truth surrogate.

Transports each (repo, path) named in datum62/evidence/measured_artifacts_56.json
through the git protocol (sparse, blob-filtered clone), NOT the REST contents API,
because the API secondary rate limit rejects large raw downloads. GitHub's git
protocol is on the sandbox allow-list (github.com).

Usage:  .venv/bin/python scripts/fetch_registry_masks.py [--dest build/registry]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
OWNER = "buffedlizard55-lab"


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, **kw)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default="build/registry")
    ap.add_argument("--rows", default="datum62/evidence/measured_artifacts_56.json")
    args = ap.parse_args()
    dest = (ROOT / args.dest).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    rows = json.loads((ROOT / args.rows).read_text())
    mirrors = ROOT / "build" / "mirrors"
    mirrors.mkdir(parents=True, exist_ok=True)
    ok = miss = 0
    for row in rows:
        repo, path = row["repo"], row["path"]
        base = pathlib.Path(path).name
        out = dest / base
        if out.exists() and out.stat().st_size > 1000:
            ok += 1
            continue
        mdir = mirrors / repo
        if not (mdir / ".git").exists():
            run(["git", "clone", "--depth", "1", "--filter=blob:none", "--no-checkout",
                 f"https://github.com/{OWNER}/{repo}.git", str(mdir)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # sparse-checkout the single file (non-cone mode)
        run(["git", "-C", str(mdir), "sparse-checkout", "init", "--no-cone"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        run(["git", "-C", str(mdir), "sparse-checkout", "set", path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        run(["git", "-C", str(mdir), "checkout"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        src = mdir / path
        if src.exists():
            shutil.copy2(src, out)
            ok += 1
            print(f"ok   {repo}/{base}  {out.stat().st_size:,} B", flush=True)
        else:
            miss += 1
            print(f"MISS {repo}/{path}", file=sys.stderr, flush=True)
    print(f"done ok={ok} miss={miss} -> {dest}")
    return 0 if miss == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
