#!/usr/bin/env bash
# Restore the competition grid inputs this lane needs into ./data/.
#
# Three of the four files are byte-identical to the official competition files
# published on the DrivenData data tab (login-walled), mirrored through the public
# GitHub repositories of this project.  Each is SHA-256 pinned below and verified
# after download; a mismatch aborts.
#
# The fourth file (the 100 m DEM) is NOT on the competition data tab, is not
# organizer-authenticated, and has no per-file upstream receipt -- it is an
# owner-supplied mirror.  It is included because the lane cannot run without it and
# because it sits exactly on the competition grid.  See IR-62-001.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p data

API="https://api.github.com/repos/buffedlizard55-lab"
RAW_ACCEPT='Accept: application/vnd.github.raw'

fetch () {  # fetch <repo> <path> <dest> <sha256>
  local repo="$1" path="$2" dest="$3" sha="$4"
  if [ -f "$dest" ] && [ "$(sha256sum "$dest" | cut -d' ' -f1)" = "$sha" ]; then
    echo "  have  $dest"
    return 0
  fi
  echo "  get   $dest"
  curl -sSL --retry 3 --max-time 600 -H "$RAW_ACCEPT" \
    "$API/$repo/contents/$path" -o "$dest.part"
  local got; got="$(sha256sum "$dest.part" | cut -d' ' -f1)"
  if [ "$got" != "$sha" ]; then
    echo "  FAIL  $dest sha256 $got != $sha" >&2; rm -f "$dest.part"; return 1
  fi
  mv "$dest.part" "$dest"
}

echo "core competition files (owner mirrors of the DrivenData data tab):"
fetch GEMSDOE51 data/labels.tif            data/labels.tif            7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093
fetch GEMSDOE51 data/sample_submission.tif data/sample_submission.tif 2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc
fetch GEMSDOE51 data/existing_faults.tif   data/existing_faults.tif   7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093

echo "19-band feature stack (418,912,844 B, ~17 s):"
mkdir -p data/tmp_stack
for i in 000 001 002 003 004; do
  curl -sSL --retry 3 --max-time 900 -H "$RAW_ACCEPT" \
    "$API/GEMSDOE/contents/data/bridge/gems-geodawn-numerical-features.tif.part-$i" \
    -o "data/tmp_stack/part-$i"
done
cat data/tmp_stack/part-* > data/training_features.tif
rm -rf data/tmp_stack
got="$(sha256sum data/training_features.tif | cut -d' ' -f1)"
exp="4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5"
[ "$got" = "$exp" ] || { echo "  FAIL  training_features.tif sha256 $got != $exp" >&2; exit 1; }

echo "100 m DEM on the competition grid (owner mirror; see IR-62-001):"
fetch 60GEMSDOE data/geodawn_dem_a2_100m.tif data/geodawn_dem_a2_100m.tif \
  "$(python3 -c "import json;print(json.load(open('registry/data_pins.json'))['geodawn_dem_a2_100m.tif']['sha256'])" 2>/dev/null || echo '')" \
  || echo "  NOTE: DEM sha256 not pinned yet; compute it and record it in registry/data_pins.json"

echo "done."
