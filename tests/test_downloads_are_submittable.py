"""Nothing the repository offers for submission may be portal-illegal.

This is the guard the owner's portal error ("Predicted values must be in range [0, 1]") asked
for.  It was written for one lane, and the merge with ``main`` changed what it can demand: this
repository deliberately keeps **NaN-encoded twins** of some fields next to their ``-zeros``
siblings, so that the two encodings of one dot set stay comparable, and ``docs/downloads/*.tif``
therefore contains rasters that are *not* strictly legal by this lane's convention (see
IR-62-20's neighbourhood and ``docs/irregularities.md``).

So the invariant is stated where it actually matters rather than as a blanket rule:

* **anything the repository tells a reader is OK to submit must be 14/14 legal** — checked by
  joining the hand-authored claims in ``verdicts.json`` with the audit's own measured checks;
* **a file that is not legal must be labelled on the pages that link it**, and must never be
  presented with the words "OK to submit" or as the hero download;
* **the NaN mechanism must stay explained**, because it is the diagnosis of the error the owner
  actually hit.

The audit (``scripts/audit_downloads.py --write``) produces the manifest and the per-file
sidecars this module reads; ``tests/test_download_manifest.py`` owns the manifest's own
reproducibility.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
from pathlib import PurePosixPath

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

DL = ROOT / "docs" / "downloads"
DL_REL = PurePosixPath("docs/downloads")
MANIFEST = DL / "manifest.json"


def _site_rows() -> list[dict]:
    """Only the rasters at the site root: a lane directory is not offered for download."""
    return [r for r in _rows() if PurePosixPath(r["path"]).parent == DL_REL]


def _manifest() -> dict:
    assert MANIFEST.exists(), ("docs/downloads/manifest.json is missing; run "
                               "`python scripts/audit_downloads.py --write`")
    return json.loads(MANIFEST.read_text())


def _claims() -> dict:
    return json.loads((DL / "verdicts.json").read_text())


def _rows() -> list[dict]:
    return _manifest()["files"]


def _name(row: dict) -> str:
    return pathlib.Path(row["path"]).name


def test_the_repository_has_no_unlabelled_raster():
    """Every *.tif in the download directory is in the manifest the site renders from."""
    man = _manifest()
    listed = {_name(r) for r in _site_rows()}
    on_disk = {p.name for p in DL.glob("*.tif")}
    assert on_disk == listed, f"unlisted: {sorted(on_disk - listed)} / stale: {sorted(listed - on_disk)}"
    assert man.get("problems") == [], man["problems"]


@pytest.mark.parametrize("row", [r for r in json.loads(
    (pathlib.Path(__file__).resolve().parents[1] / "docs" / "downloads" / "manifest.json").read_text()
)["files"] if PurePosixPath(r["path"]).parent
    == PurePosixPath("docs/downloads")],
    ids=lambda r: pathlib.Path(r["path"]).name)
def test_a_file_is_legal_exactly_when_its_verdict_says_it_is(row):
    """The claim and the measurement must agree, in both directions.

    ``ok_to_submit`` is the repository's promise to the owner, so a raster whose bytes cannot
    satisfy ``0 <= v <= 1`` must never carry it, and a raster that does carry it must pass all
    14 checks.  The audit recomputes the checks from the bytes on every run.
    """
    name = _name(row)
    claim = _claims().get(name)
    assert claim is not None, f"{name} has no hand-authored verdict in verdicts.json"
    ok = claim.get("ok_to_submit")
    checks = f"{row.get('checks_passed')}/{row.get('checks_total')}"
    if ok:
        assert row["format_legal"] is True, (
            f"{name} is offered as OK to submit but the audit finds {checks} checks passing: "
            f"{row['fails']}")
        assert row["fails"] == [], row["fails"]
        assert row["nan_count"] == 0 and row["n_outside_0_1"] == 0
        assert row["nodata"] is None, "a nodata tag is a portal range risk"
    else:
        # the opposite direction: a file that is flagged is not silently offered
        assert row["format_legal"] in (True, False)


def test_every_offered_file_is_at_least_labelled_on_the_pages():
    """A reader must be able to tell, on the page, which files are not strictly legal.

    Scoped to the page that links the file rather than to index.html alone: a lane's twin may be
    linked only from the lane's own page, and demanding the landing page carry every row is how a
    well-meaning guard turns into a stale claim of its own.
    """
    pages = {p: p.read_text() for p in sorted((ROOT / "docs").glob("**/*.html"))}
    for row in _site_rows():
        name = _name(row)
        linking = [p for p, text in pages.items() if name in text]
        assert linking, f"{name} carries a verdict but no page mentions it at all"
        if row["format_legal"]:
            continue
        for page in linking:
            text = pages[page]
            for m in re.finditer(r"<tr[^>]*>.*?</tr>", text, re.S):
                row_html = m.group(0)
                # only rows that OFFER the file (a download link) are download rows; the
                # irregularities register legitimately names the file without offering it
                if f'href="downloads/{name}"' not in row_html:
                    continue
                assert "not legal" in row_html, (
                    f"{page.name} has a download row for {name} that does not say it is not legal")
                for flag in row["fails"]:
                    assert flag in row_html, (
                        f"{page.name}: {name}'s download row does not name the failing check {flag}")


def test_no_page_offers_an_illegal_file_as_ok_to_submit():
    """The specific failure the owner hit: clicking a download and being rejected by the portal.

    Two structural guards, no fragile phrase windows:

    * an approval block (the "OK to Download and Submit?" table, or any block whose text approves
      downloading) may not contain a link to a raster that fails the format contract, because that
      is the shape of a reader being sent to a file the portal will reject;
    * no download *button* anywhere may target such a raster -- a button beside a working download
      is how the NaN twin got submitted by mistake in the first place.
    """
    man = _manifest()
    illegal = {_name(r) for r in _site_rows() if not r["format_legal"]}
    assert illegal, "no illegal rasters -- then this test has nothing to protect; revisit it"
    for page in ("docs/index.html", "docs/executive-summary.html"):
        text = (ROOT / page).read_text()
        # The approval block is identified by its heading, not by phrase proximity: this
        # repository's verdict strings legitimately mention downloading while labelling a file
        # NEGATIVE, and a phrase window cannot tell a verdict from an offer (it caught both).
        for m in re.finditer(r"OK to Download and Submit\?", text, re.I):
            tail = text[m.end():]
            table = re.search(r"<table[^>]*>.*?</table>", tail, re.S)
            if not table:
                continue
            for href in re.findall(r'href="downloads/([^"]+)"', table.group(0)):
                assert pathlib.Path(href).name not in illegal, (
                    f"{page}: the approval block links the illegal raster {href}")
        for m in re.finditer(r'class="btn[^"]*" href="downloads/([^"]+)"', text):
            name = pathlib.Path(m.group(1)).name
            assert name not in illegal, f"{page} puts an illegal raster on a button: {name}"


def test_the_nan_mechanism_is_still_documented():
    """The diagnosis of the portal error must survive; removing it would hide the defect."""
    text = (ROOT / "docs" / "index.html").read_text()
    assert "Predicted values must be in range [0, 1]" in text
    assert "7,111,787" in text, "the measured NaN cell count is no longer on the landing page"


def test_the_primary_download_is_strictly_legal():
    """The most prominent button on the landing page must be a zero-encoded, legal raster."""
    text = (ROOT / "docs" / "index.html").read_text()
    m = re.search(r'class="btn" href="downloads/([^"]+\.tif)"', text)
    assert m, "the landing page has no primary download button"
    row = next((r for r in _site_rows() if _name(r) == pathlib.Path(m.group(1)).name), None)
    assert row is not None, f"{m.group(1)} is not audited at all"
    assert row["format_legal"] is True, f"the primary download {m.group(1)} fails {row['fails']}"
