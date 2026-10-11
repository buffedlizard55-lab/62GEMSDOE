#!/usr/bin/env bash
# Obtain the three official competition rasters into $GEMS62_DATA (default: ./data).
#
# THERE ARE TWO ROUTES.  Route A is the organiser's and requires a DrivenData
# login.  Route B is the in-organisation git bridge used by this sandbox, where
# drivendata.org is not reachable at all.
#
# Official data tab (login required):
#   https://www.drivendata.org/competitions/306/competition-doe-gems/data/
#
# sha256 pins that BOTH routes must satisfy (published in
# buffedlizard55-lab/6GEMSDOE : data/bridge/manifest.json and re-verified here
# on 2026-10-11 -- see registry/data_manifest.json):
#
#   training_features.tif   418,912,844 B  4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5
#   labels.tif                  425,830 B  7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093
#   sample_submission.tif     1,599,597 B  2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc
#
# The file names on the data tab and the canonical names used by this repository
# differ; the bridge manifest records the mapping:
#   gems-geodawn-numerical-features.tif -> training_features.tif
#   existing_faults.tif                 -> labels.tif
#   example_submission.tif              -> sample_submission.tif
#
# 1m_DEM_links.csv (USGS 3DEP 1 m lidar index) is also on the data tab and is
# NOT available through the bridge.  Its absence is recorded as IR-62-DEM-01.

set -euo pipefail

DEST="${GEMS62_DATA:-$(cd "$(dirname "$0")/.." && pwd)/data}"
mkdir -p "$DEST"

PIN_FEATURES=4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5
PIN_LABELS=7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093
PIN_SAMPLE=2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc

sha() { sha256sum "$1" | cut -d' ' -f1; }

check() {  # check <file> <pin>
  if [[ ! -f "$1" ]]; then echo "MISSING  $1"; return 1; fi
  local got; got="$(sha "$1")"
  if [[ "$got" == "$2" ]]; then
    echo "VERIFIED $1  $(stat -c%s "$1" 2>/dev/null || stat -f%z "$1") bytes  $got"
    return 0
  fi
  echo "MISMATCH $1  expected $2  got $got"
  return 1
}

echo "== destination: $DEST"

ok=1
check "$DEST/training_features.tif" "$PIN_FEATURES" || ok=0
check "$DEST/labels.tif"            "$PIN_LABELS"    || ok=0
check "$DEST/sample_submission.tif" "$PIN_SAMPLE"    || ok=0
if [[ $ok -eq 1 ]]; then
  echo "== all three rasters already present and verified. Nothing to do."
  exit 0
fi

echo
echo "== ROUTE A: DrivenData data tab (needs your login cookie/session)"
echo "   https://www.drivendata.org/competitions/306/competition-doe-gems/data/"
echo "   Download these four files into $DEST and rename as shown:"
echo "     gems-geodawn-numerical-features.tif  -> training_features.tif"
echo "     existing_faults.tif                  -> labels.tif"
echo "     example_submission.tif               -> sample_submission.tif"
echo "     1m_DEM_links.csv                     -> 1m_DEM_links.csv   (no rename)"
echo "   Then re-run this script to verify the pins."
echo
if [[ -n "${GEMS62_BRIDGE_REPO:-}" ]]; then
  echo "== ROUTE B: in-organisation git bridge at $GEMS62_BRIDGE_REPO"
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' EXIT
  git clone --depth 1 "$GEMS62_BRIDGE_REPO" "$tmp/bridge"
  cat "$tmp/bridge"/data/bridge/gems-geodawn-numerical-features.tif.part-* \
      > "$DEST/training_features.tif"
  cp "$tmp/bridge/data/bridge/existing_faults.tif"  "$DEST/labels.tif"
  cp "$tmp/bridge/data/bridge/example_submission.tif" "$DEST/sample_submission.tif"
  echo "-- re-verifying after restore"
  check "$DEST/training_features.tif" "$PIN_FEATURES"
  check "$DEST/labels.tif"            "$PIN_LABELS"
  check "$DEST/sample_submission.tif" "$PIN_SAMPLE"
else
  echo "== ROUTE B: set GEMS62_BRIDGE_REPO to an in-organisation repo that carries"
  echo "   data/bridge/*.part-NNN to restore without a DrivenData login, e.g."
  echo "     export GEMS62_BRIDGE_REPO=https://github.com/buffedlizard55-lab/6GEMSDOE.git"
fi

echo
echo "== done. Run:  pytest tests -q   then   python scripts/run_lane.py"
