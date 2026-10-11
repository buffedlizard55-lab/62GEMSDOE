"""Fetch the prior-artifact registry used for the lane-drift check.

Sources are the public `buffedlizard55-lab` GitHub repositories listed in
`registry/registry_sources.json`.  Each fetched byte sequence is SHA-256 hashed and
written into `registry/registry_manifest.json` so a reviewer can re-derive the
comparison without trusting this checkout.

Usage:
    python scripts/fetch_registry.py [--out /tmp/gems/registry]
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gems62.validate import sha256_file  # noqa: E402

HERE = Path(__file__).resolve().parents[1]
SOURCES = HERE / "registry" / "registry_sources.json"
API = "https://api.github.com/repos/buffedlizard55-lab/{repo}/contents/{path}"


def fetch(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github.raw",
        "User-Agent": "gems62-registry-fetch",
    })
    with urllib.request.urlopen(req, timeout=180) as r:
        data = r.read()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/tmp/gems/registry")
    args = ap.parse_args()

    out = Path(args.out)
    src = json.loads(SOURCES.read_text())
    manifest = {"note": src["note"], "source_host": src["source_host"], "entries": []}

    ok = fail = skip = 0
    for e in src["entries"]:
        if e.get("skip"):
            skip += 1
            continue
        dest = out / f"{e['alias']}.tif"
        try:
            if not dest.exists() or dest.stat().st_size == 0:
                fetch(API.format(repo=e["repo"], path=e["path"]), dest)
            digest = sha256_file(dest)
            note = None
            if e.get("sha256") and digest != e["sha256"]:
                note = f"SHA-256 differs from the pinned value in registry_sources.json ({e['sha256']})"
            manifest["entries"].append({
                "alias": e["alias"],
                "repo": e["repo"],
                "path": e["path"],
                "local": str(dest),
                "bytes": dest.stat().st_size,
                "sha256": digest,
                "owner_reported_score": e.get("owner_reported_score"),
                "note": note,
            })
            ok += 1
            print(f"  ok   {e['alias']}  {dest.stat().st_size:>9d} B  {digest[:12]}")
        except Exception as exc:  # noqa: BLE001
            fail += 1
            print(f"  FAIL {e['alias']}: {exc}")
            manifest["entries"].append({
                "alias": e["alias"], "repo": e["repo"], "path": e["path"],
                "status": "missing", "error": str(exc),
            })

    (HERE / "registry" / "registry_manifest.json").write_text(json.dumps(manifest, indent=1))
    print(f"\nfetched {ok}, failed {fail}, skipped {skip}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
