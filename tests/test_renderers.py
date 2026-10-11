# SPDX-FileCopyrightText: 2026 Yaroslav Halchenko <yaroslav.o.halchenko@dartmouth.edu>
# SPDX-License-Identifier: MIT
#
# Generated with Claude Code 2.1.295 / Claude Opus 5
"""Tests for the page generators.

These exist because every defect these scripts shipped was one a test would
have caught, and none was caught by running them and looking at the output:

* a silent skip removed a person from the site with exit code 0
* a regex without `count=1` stripped every <figure> from a description,
  deleting a logo that was not the one it meant to remove
* a descending sort negated dates per character, so "2020" sorted before
  "2020-01-15"
* a path builder used the file's name instead of the person's slug, pointing
  every portrait at the same missing file
* generated markup that is not well-formed makes the table-of-contents
  extension silently drop every anchor on the page

One test per scar.
"""
import pathlib
import re
import subprocess
import sys

import pytest
import yaml

HERE = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS = HERE / "scripts"
STORE = HERE / "sourcedata/con-site-specific"

sys.path.insert(0, str(SCRIPTS))


def run(script, *args, store=None, expect=0):
    env = None
    if store is not None:
        import os
        env = dict(os.environ, CON_RECORD_STORE=str(store))
    p = subprocess.run([sys.executable, str(SCRIPTS / script), *args],
                       capture_output=True, text=True, env=env)
    assert p.returncode == expect, (
        f"{script} exited {p.returncode}, expected {expect}\n"
        f"stdout: {p.stdout[-2000:]}\nstderr: {p.stderr[-2000:]}")
    return p


@pytest.fixture(scope="session")
def whoweare():
    return run("render_whoweare.py").stdout


@pytest.fixture(scope="session")
def projects():
    return run("render_projects.py").stdout


@pytest.fixture
def store_copy(tmp_path):
    """A throwaway copy of the record store, for perturbation."""
    import shutil
    dst = tmp_path / "store"
    shutil.copytree(STORE, dst, symlinks=True,
                    ignore=shutil.ignore_patterns(".git"))
    return dst


# --- well-formedness ------------------------------------------------------

@pytest.mark.ai_generated
@pytest.mark.parametrize("page", ["render_whoweare.py", "render_projects.py"])
def test_output_is_well_formed_xml(page):
    """The ToC extension parses with strict ElementTree and, on a parse
    error, returns the page UNCHANGED -- so one malformed tag silently drops
    every anchor while the build still succeeds."""
    import xml.etree.ElementTree as ET
    out = run(page).stdout
    ET.fromstring("<root>" + out + "</root>")


@pytest.mark.ai_generated
def test_malformed_record_is_refused(store_copy):
    """An unclosed tag in a record must stop the render, not produce a page
    with no anchors."""
    f = store_copy / "metadata/records/XYZProject/datalad.yaml"
    d = yaml.safe_load(f.read_text())
    for a in d["attributes"]:
        if a["predicate"] == "dlthings:description_html":
            a["value"] = "<p>broken <strong>unclosed</p>"
    f.write_text(yaml.safe_dump(d))
    p = run("render_projects.py", store=store_copy, expect=2)
    assert "not well-formed" in p.stderr


# --- silent skips ---------------------------------------------------------

@pytest.mark.ai_generated
def test_missing_tier_is_reported_not_silent(store_copy):
    """Removing a person's tier used to drop them from the site, quietly."""
    f = store_copy / "metadata/records/XYZPerson/joey-hess.yaml"
    d = yaml.safe_load(f.read_text())
    d["attributes"] = [a for a in d["attributes"]
                       if a["predicate"] != "dlthings:tier"]
    f.write_text(yaml.safe_dump(d))
    out = run("render_whoweare.py", store=store_copy).stdout
    assert "Joey Hess" not in out          # genuinely absent
    # ...but a person with a tier that is simply WRONG must be reported
    d["attributes"].append({"predicate": "dlthings:tier",
                            "schema_type": "dlthings:AttributeSpecification",
                            "value": "Centroid"})   # typo: no trailing s
    f.write_text(yaml.safe_dump(d))
    p = run("render_whoweare.py", store=store_copy, expect=2)
    assert "SKIPPED joey-hess" in p.stderr


@pytest.mark.ai_generated
def test_bad_section_is_reported_not_silent(store_copy):
    f = store_copy / "metadata/records/XYZProject/duecredit.yaml"
    d = yaml.safe_load(f.read_text())
    for a in d["attributes"]:
        if a["predicate"] == "dlthings:section":
            a["value"] = "software"        # lowercase typo
    f.write_text(yaml.safe_dump(d))
    p = run("render_projects.py", store=store_copy, expect=2)
    assert "SKIPPED duecredit" in p.stderr


# --- content preservation -------------------------------------------------

@pytest.mark.ai_generated
def test_second_figure_in_a_description_survives(projects):
    """EMBER's description carries a HEARTH logo in a second <figure>.  The
    renderer strips the project's own logo figure; stripping every figure
    deleted this one."""
    assert "hearth_logo.svg" in projects


@pytest.mark.ai_generated
def test_every_person_renders_a_portrait_at_its_own_path(whoweare):
    srcs = re.findall(r'src="(/theme/img/team/[^"]+)"', whoweare)
    assert len(srcs) == len(set(srcs)), "two people share a portrait path"
    assert "/theme/img/team/portrait.jpg" not in srcs


@pytest.mark.ai_generated
@pytest.mark.parametrize("page,n", [("render_whoweare.py", 33),
                                    ("render_projects.py", 35)])
def test_expected_entry_count(page, n):
    """A guard against silent loss, so the number moves only on purpose.
    27 -> 35 when NIDM, DICOM + WG-16/32, BEP028/032/044, BIDS 2.0, ReproIn,
    the EMBER study template and the two advisory projects were added."""
    out = run(page).stdout
    tag = "h3" if "whoweare" in page else "h2"
    assert len(re.findall(rf"<{tag}[^>]*>", out)) == n


@pytest.mark.ai_generated
def test_section_intros_are_present(whoweare, projects):
    """Both belong to a section rather than an entity, so nothing in the
    records holds them and they were dropped the first time."""
    assert "For over a decade" in projects
    assert "push/pull relationship" in whoweare


@pytest.mark.ai_generated
def test_components_line_needs_more_than_one(projects):
    """A list of one is not a list: con/annextube's only instrument is
    con/annextube, so the line said nothing."""
    import re
    for m in re.finditer(r'<p class="components">(.*?)</p>', projects, re.S):
        assert len(re.findall(r"<a ", m.group(1))) > 1


@pytest.mark.ai_generated
def test_subprojects_are_listed_under_their_parent(projects):
    """A sub-project with no section of its own was invisible: EMBER's study
    template and the DICOM working groups had records and appeared nowhere."""
    import re
    i = projects.index(">DICOM</h2>")
    block = projects[i:i + 4000]
    assert "DICOM WG-16" in block and "DICOM WG-32" in block
    assert "study-template" in projects


# --- ordering -------------------------------------------------------------

@pytest.mark.ai_generated
def test_dates_sort_descending_even_when_one_prefixes_another():
    """A key that negated each character compared elementwise, so "2020"
    sorted before "2020-01-15"."""
    import render_projects
    rows = [{"slug": s, "started": d, "section": "Software", "d": {}}
            for s, d in [("a", "2020"), ("b", "2020-01-15"), ("c", "2021"),
                         ("d", "2019-12"), ("e", None)]]
    rows.sort(key=lambda r: (r["started"] is None,
                             "" if r["started"] is None else r["started"]),
              reverse=True)
    rows.sort(key=lambda r: r["started"] is None)
    assert [r["slug"] for r in rows] == ["c", "b", "a", "d", "e"]


@pytest.mark.ai_generated
def test_emeritus_sorts_by_departure_and_others_by_arrival(whoweare):
    def tier_block(name):
        i = whoweare.index(f"<h2>{name}</h2>")
        j = whoweare.find("<h2>", i + 1)
        return whoweare[i:j if j > 0 else len(whoweare)]
    # the founding director leads the Centroids despite having no date
    assert tier_block("Centroids").index("Yaroslav") < \
        tier_block("Centroids").index("Austin")
    # Hanke leads Collaborators -- CON's founding, earliest of that tier
    assert tier_block("Collaborators").index("Michael Hanke") < \
        tier_block("Collaborators").index("Adina Wagner")


# --- assets ---------------------------------------------------------------

@pytest.mark.ai_generated
@pytest.mark.parametrize("page", ["render_whoweare.py", "render_projects.py"])
def test_every_image_resolves_on_disk(page):
    out = run(page).stdout
    missing = [s for s in set(re.findall(r'src="(/theme/[^"]+)"', out))
               if not (HERE / "theme/static" / s.replace("/theme/", "", 1)).exists()]
    assert not missing, f"{page} references images that do not exist: {missing}"
