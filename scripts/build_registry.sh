#!/usr/bin/env bash
# Bounded, reproducible download of the group's PUBLIC prior-submission rasters,
# used only as the uniqueness comparison set for this lane's artefact.
#
# Scope is enumerated, not open-ended: every repository of the group that
# publishes raster artefacts under docs/downloads, docs/submissions, downloads
# or submission is fetched as a codeload tarball and its .tif files are
# extracted into $REG.  Repositories whose tarball exceeds MAX_MB are SKIPPED
# and the skip is recorded in the manifest so the coverage limit is explicit.
#
# Requires: github.com + codeload.github.com reachable.  No credentials.
set -euo pipefail
REG="${REG:-$HOME/.cache/gems62_registry}"
MAX_MB="${MAX_MB:-90}"
mkdir -p "$REG"; cd "$REG"

API=https://api.github.com/repos/buffedlizard55-lab
OWNER=buffedlizard55-lab

repos=$(curl -s "https://api.github.com/users/$OWNER/repos?per_page=100&sort=created" \
        | python3 -c 'import json,sys;print(" ".join(r["name"] for r in json.load(sys.stdin)))')

: > registry_manifest.tsv
printf 'repo\tstatus\tbytes_or_reason\n' >> registry_manifest.tsv

for r in $repos; do
  rm -f "$r.tar.gz"
  code=$(curl -s -L -o "$r.tar.gz" -w '%{http_code}' \
         "https://codeload.github.com/$OWNER/$r/tar.gz/refs/heads/main" || echo 000)
  if [ "$code" != "200" ]; then printf '%s\tHTTP_%s\t\n' "$r" "$code" >> registry_manifest.tsv; continue; fi
  mb=$(( $(stat -c%s "$r.tar.gz") / 1048576 ))
  if [ "$mb" -gt "$MAX_MB" ]; then
    printf '%s\tSKIPPED_TOO_BIG\t%s_MB\n' "$r" "$mb" >> registry_manifest.tsv; rm -f "$r.tar.gz"; continue
  fi
  mkdir -p "$r"
  tar xzf "$r.tar.gz" -C "$r" \
      --wildcards --no-anchored 'docs/downloads/*.tif' 'docs/submissions/*.tif' \
      'downloads/*.tif' 'submission/*.tif' 'evidence/*.tif' 'docs/*.tif' 2>/dev/null || true
  n=$(find "$r" -name '*.tif' | wc -l)
  printf '%s\tOK\t%s_tif_%s_MB\n' "$r" "$n" "$mb" >> registry_manifest.tsv
  rm -f "$r.tar.gz"
done
echo "registry at $REG"; grep -c OK registry_manifest.tsv
