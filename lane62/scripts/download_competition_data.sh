#!/usr/bin/env bash
# Place the competition rasters into data/official/.
#
# THE BLOCKER, STATED PLAINLY.  The DrivenData data page requires a login:
# a fetch of https://www.drivendata.org/competitions/306/competition-doe-gems/data/
# on 2026-10-11 returned a redirect to /accounts/login/.  No credential exists in
# this sandbox and none is sought.  This script therefore does NOT log in; it
# accepts the files from wherever you obtained them and verifies the bytes.
#
# Two supported routes:
#   A) you are logged in and downloaded the files yourself -> put them in data/official/
#   B) you have an authorized URL or a directory of mirrors -> set SRC=...
#
# It never writes a file it has not hashed.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/data/official"
mkdir -p "$DEST"

# sha256 pins taken from the group's public manifest (60GEMSDOE data/restore_receipt.json)
# and re-verified in this checkout on 2026-10-11.  These authenticate the BYTES, not
# the file's origin from DrivenData (see IR-62-07).
declare -A PIN=(
  [sample_submission.tif]=2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc
  [existing_faults.tif]=7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093
  [labels.tif]=7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093
)

echo "Competition data placement"
echo "  destination: $DEST"
echo "  DrivenData data page: https://www.drivendata.org/competitions/306/competition-doe-gems/data/ (login required)"
echo

if [ -n "${SRC:-}" ]; then
  echo "  copying from SRC=$SRC"
  for f in sample_submission.tif existing_faults.tif labels.tif; do
    [ -f "$SRC/$f" ] && cp -n "$SRC/$f" "$DEST/$f" || true
  done
fi

missing=0
for f in sample_submission.tif existing_faults.tif labels.tif; do
  if [ ! -f "$DEST/$f" ]; then
    echo "  MISSING  $f"; missing=1; continue
  fi
  got=$(sha256sum "$DEST/$f" | cut -d' ' -f1)
  if [ "$got" = "${PIN[$f]}" ]; then
    echo "  OK       $f  sha256 ${got:0:16}…"
  else
    echo "  MISMATCH $f"; echo "           expected ${PIN[$f]}"; echo "           got      $got"; missing=1
  fi
done

# training_features.tif is large (418,912,844 B) and is NOT required by this lane,
# which works from the DEM plus the group's derived stacks.  Pin it if present.
if [ -f "$DEST/training_features.tif" ]; then
  got=$(sha256sum "$DEST/training_features.tif" | cut -d' ' -f1)
  want=4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5
  [ "$got" = "$want" ] && echo "  OK       training_features.tif" \
    || { echo "  MISMATCH training_features.tif"; missing=1; }
fi

echo
if [ "$missing" = "0" ]; then
  echo "All required rasters present and hash-matched. Next: python3 scripts/prepare_data.py"
else
  echo "Incomplete. Download the missing files through an authorized session into"
  echo "$DEST and re-run. This script will not fetch them for you."
  exit 1
fi
