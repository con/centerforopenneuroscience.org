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
import functools
import http.server
import os
import pathlib
import re
import shutil
import socketserver
import subprocess
import sys
import threading
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

import pytest
import yaml

HERE = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS = HERE / "scripts"
STORE = HERE / "sourcedata/con-site-specific"

sys.path.insert(0, str(SCRIPTS))

import render_projects  # noqa: E402 -- needs SCRIPTS on sys.path


def run(script, *args, store=None, expect=0):
    env = None
    if store is not None:
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
def test_a_person_named_only_by_given_and_family_name_renders(store_copy):
    """Records may leave out `display_label` and `formatted_name` when the
    given and family names compose the name; three new people did, and the
    render crashed on html.escape(None)."""
    f = store_copy / "metadata/records/XYZPerson/joey-hess.yaml"
    d = yaml.safe_load(f.read_text())
    d.pop("display_label", None)
    d.pop("formatted_name", None)
    d["attributes"] = [a for a in d["attributes"]
                       if a["predicate"] != "dlthings:formatted_name"]
    d["given_name"], d["family_name"] = "Joey", "Hess"
    f.write_text(yaml.safe_dump(d))
    out = run("render_whoweare.py", store=store_copy).stdout
    assert "<h3>Joey Hess</h3>" in out


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
@pytest.mark.parametrize("page,n", [("render_whoweare.py", 43),
                                    ("render_projects.py", 45)])
def test_expected_entry_count(page, n):
    """A guard against silent loss, so the number moves only on purpose.
    27 -> 36 when NIDM, DICOM + WG-16/32, BEP028/032/044, BIDS 2.0, ReproIn,
    the EMBER study template and the two advisory projects were added;
    36 -> 38 for ORINOCO Lite and the OHBM 2020 posters registry, and
    38 -> 41 when Quail, HyperTools and SuperEEG were restored -- they had
    been on the hand-written page, had no records, and vanished.  The
    DataLad Handbook arrived with them and is not counted: it is
    `part_of: datalad`, so it renders as one of DataLad's components rather
    than as a heading of its own.  35 -> 39 people with Dora Hermes,
    Oliver Rübel, Ryan Ly and Seyed (Yahya) Shirazi, and 43 -> 44 with
    BEP020 (Annotation Garden is a component, not a heading); 39 -> 40 and
    44 -> 45 with Russ Poldrack and svgtune; 40 -> 43 with Kitware's
    Jacob Nesbitt, Roni Choudhury and Mike Grauer."""
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
def test_relation_lists_need_more_than_one(projects):
    """A list of one is not a list: con/annextube's only instrument is
    con/annextube, and "Within it: STAMPED Principles" said nothing three
    times over."""
    for m in re.finditer(r'<ul class="component-list">(.*?)</ul>',
                         projects, re.S):
        assert len(re.findall(r"<li>", m.group(1))) != 1, \
            "component list with exactly one entry"
    # a component list must gloss its entries, not just name them
    lists = re.findall(r'<ul class="component-list">(.*?)</ul>', projects, re.S)
    assert lists, "no component lists rendered"
    for body in lists:
        items = re.findall(r"<li>(.*?)</li>", body, re.S)
        glossed = [i for i in items if ":" in re.sub(r"<[^>]+>", "", i)]
        assert glossed, "a component list with no glosses at all"


@pytest.mark.ai_generated
def test_subprojects_are_listed_under_their_parent(projects):
    """A sub-project with no section of its own was invisible: EMBER's study
    template and the DICOM working groups had records and appeared nowhere."""
    i = projects.index(">DICOM</h2>")
    block = projects[i:i + 4000]
    assert "DICOM WG-16" in block and "DICOM WG-32" in block
    assert "study-template" in projects


@pytest.mark.ai_generated
def test_subprojects_follow_their_parent(projects):
    """Sorting a section by date alone scattered a family: BIDS's four
    sub-projects landed in three different places and DICOM came after both
    its working groups."""
    i = projects.index(">Standards</h1>")
    j = projects.find("<h1", i + 1)
    names = [re.sub(r"<[^>]+>", "", m).strip()
             for m in re.findall(r"<h2[^>]*>(.*?)</h2>", projects[i:j], re.S)]
    bids = names.index("Brain Imaging Data Structure (BIDS)")
    for kid in ("BEP020", "BEP028", "BEP032", "BEP044", "BIDS 2.0"):
        assert names.index(kid) > bids, f"{kid} should follow BIDS"
    dicom = names.index("DICOM")
    for kid in ("DICOM WG-16", "DICOM WG-32"):
        assert names.index(kid) > dicom, f"{kid} should follow DICOM"
    # and contiguously -- nothing unrelated wedged between a parent and its
    # children
    assert names[bids + 1:bids + 6] == ["BEP028", "BIDS 2.0", "BEP020",
                                        "BEP032", "BEP044"]


@pytest.mark.ai_generated
def test_one_list_per_project_not_two(projects):
    """`part_of` and `generated_by` are two slots in the records but one
    question for a reader -- what is inside this project.  Rendering them as
    "Components:" and "Within it:" meant BIDS's four BEPs looked like a
    different kind of thing from DataLad's extensions, for no reason visible
    on the page."""
    assert "Within it" not in projects
    assert 'class="subprojects"' not in projects
    m = re.search(r"<h2[^>]*>Brain Imaging Data Structure \(BIDS\)</h2>"
                  r"(.*?)(?=<h2 )", projects, re.S)
    body = m.group(1)
    assert body.count('<ul class="component-list">') == 1
    listed = re.findall(r'<li><a href="([^"]+)"[^>]*>(.*?)</a>',
                        body.split("component-list")[-1])
    names = {n for _, n in listed}
    assert {"BEP028", "BEP032", "BEP044", "BIDS 2.0"} <= names, names
    # and each links to its own entry on this page, not off-site
    for href, name in listed:
        if name in ("BEP028", "BEP032", "BEP044", "BIDS 2.0"):
            assert href.startswith("#"), f"{name} leaves the page: {href}"


@pytest.mark.ai_generated
def test_a_gloss_is_not_also_a_tooltip(projects):
    """The tooltip repeated the gloss printed beside it, word for word: a
    second copy of every description in the HTML and in the accessibility
    tree."""
    for body in re.findall(r'<ul class="component-list">(.*?)</ul>',
                           projects, re.S):
        for item in re.findall(r"<li>(.*?)</li>", body, re.S):
            tip = re.search(r'title="([^"]*)"', item)
            text = re.sub(r"<[^>]+>", "", item)
            if tip and ":" in text:
                assert tip.group(1) not in text, \
                    "tooltip duplicates the visible gloss"


@pytest.mark.ai_generated
def test_components_do_not_repeat_the_description(projects):
    """DataLad's prose bullets gloss datalad-container and datalad-fuse
    better than a generated line can; listing them again is strictly worse."""
    m = re.search(r"<h2[^>]*>DataLad</h2>(.*?)(?=<h2 )", projects, re.S)
    body = m.group(1).split("component-list")[-1]
    listed = {re.sub(r"<[^>]+>", "", i).split(":")[0].strip()
              for i in re.findall(r"<li>(.*?)</li>", body, re.S)}
    assert "datalad-container" not in listed
    assert "datalad-fuse" not in listed
    assert "datalad-crawler" in listed       # the rest still show


# --- ordering -------------------------------------------------------------

@pytest.mark.ai_generated
def test_dates_sort_descending_even_when_one_prefixes_another():
    """A key that negated each character compared elementwise, so "2020"
    sorted before "2020-01-15"."""
    rows = [{"slug": s, "started": d, "section": "Software", "d": {}}
            for s, d in [("a", "2020"), ("b", "2020-01-15"), ("c", "2021"),
                         ("d", "2019-12"), ("e", None)]]
    # the renderer's own sort, not a copy of it in the test
    assert [r["slug"] for r in render_projects.by_recency(rows)] \
        == ["c", "b", "a", "d", "e"]
    # flagships jump the queue whatever their date
    rows.append({"slug": "pymvpa", "started": "2008", "section": "Software",
                 "d": {}})
    assert render_projects.by_recency(rows)[0]["slug"] == "pymvpa"


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



@pytest.mark.ai_generated
def test_past_people_close_the_page(whoweare):
    """Former people come after every logo strip, and those who worked with
    CON rather than within it have a tier of their own."""
    assert re.findall(r"<h2>([^<]*)</h2>", whoweare) == [
        "Centroids", "Collaborators", "Affiliated Faculty",
        "Collaborating labs &amp; groups", "Partners",
        "Collaborating projects", "Emeritus", "Emeritus Collaborators"]
    past = whoweare[whoweare.index("<h2>Emeritus Collaborators</h2>"):]
    assert "<h3>Mike Grauer</h3>" in past
    assert "<h3>John Wodder</h3>" not in past

# --- navigation ---------------------------------------------------------

def _build(tmp):
    """Build the site and return the built pages."""
    out = tmp / "site"
    r = subprocess.run([sys.executable, "-m", "pelican", "content", "-o", str(out),
                        "-s", "pelicanconf.py"], cwd=HERE, capture_output=True,
                       text=True)
    assert r.returncode == 0, r.stderr[-2000:]
    return out


@pytest.mark.ai_generated
def test_sidebar_nests_sections_inside_their_own_item(tmp_path):
    """Each section's <ul> must be a CHILD of that section's <li>.

    The CSS that reveals a section's entries is
    `.bs-docs-sidebar .nav > .active > ul`, so a <ul> that is merely a
    SIBLING of the <li> never shows -- which is what shipped: clicking
    Archives highlighted it and revealed nothing.

    An earlier version of this test counted <ul> nesting depth over the raw
    string, and a sibling <ul> increments that too, so it passed on the
    broken markup.  This one walks parents.
    """
    out = _build(tmp_path)
    for name, want in (("projects", 7), ("whoweare", 8)):
        t = (out / f"{name}.html").read_text()
        i = t.index('id="full-toc"'); j = t.index("</div>", i)

        class P(HTMLParser):
            def __init__(s):
                super().__init__()
                s.stack = []          # open elements
                s.sections = []       # (text, has_child_ul)
                s.cur = None
                s.bad = []
            def handle_starttag(s, tag, attrs):
                if tag in ("ul", "li"):
                    if tag == "ul" and s.stack and s.stack[-1][0] == "ul":
                        s.bad.append("ul directly inside ul")
                    # a <ul> whose parent is an <li> is that item's children
                    if tag == "ul" and len(s.stack) == 2 and s.stack[-1][0] == "li":
                        s.sections[-1] = (s.sections[-1][0], True)
                    s.stack.append((tag, len(s.stack)))
                elif tag == "a" and dict(attrs).get("href", "").startswith("#"):
                    s.cur = len(s.stack)
            def handle_data(s, d):
                if s.cur is not None and d.strip():
                    if s.cur == 2:    # ul > li > a  == a top-level section
                        s.sections.append((d.strip(), False))
                    s.cur = None
            def handle_endtag(s, tag):
                if tag in ("ul", "li"):
                    if s.stack and s.stack[-1][0] == tag:
                        s.stack.pop()
                    else:
                        s.bad.append(f"mismatched </{tag}>")

        p = P(); p.feed(t[t.index("<ul", i):j])
        assert not p.bad, f"{name}: malformed sidebar: {p.bad}"
        assert len(p.sections) == want, \
            f"{name}: {len(p.sections)} sections, expected {want}: {p.sections}"
        childless = [s for s, has in p.sections if not has]
        # the three logo strips on whoweare genuinely have no sub-entries
        allowed = {"Collaborating projects", "Collaborating labs & groups",
                   "Partners"}
        assert not (set(childless) - allowed), \
            f"{name}: sections with no nested list of their own: {childless}"


@pytest.mark.ai_generated
def test_cross_page_links_land_on_a_real_heading(tmp_path):
    """whoweare's "Related projects" links INTO the projects page, so the
    anchors have to be the ones the ToC extension will actually produce
    there -- a different page's ids, which the same-page check above cannot
    see."""
    out = _build(tmp_path)
    ids = set(re.findall(r'id="([^"]+)"',
                         (out / "projects.html").read_text()))
    who = (out / "whoweare.html").read_text()
    links = set(re.findall(r'href="/projects#([^"]+)"', who))
    assert links, "whoweare links to no project at all"
    assert not links - ids, f"dead cross-page anchors: {sorted(links - ids)}"


@pytest.mark.ai_generated
def test_a_person_who_leads_a_group_says_so(whoweare):
    """The fact lives on the ORGANIZATION record -- `influenced_by` plus a
    lead role -- so nothing in the person's own record shows it, and the
    page said nothing for years."""
    def block(name):
        i = whoweare.index(f"<h3>{name}</h3>")
        j = whoweare.find("<h3>", i + 1)
        return whoweare[i:j if j > 0 else len(whoweare)]
    for who, group in (("Michael Hanke", "Psychoinformatics"),
                       ("Jean-Baptiste Poline", "ORIGAMI Lab"),
                       ("James V. Haxby", "Haxby Lab")):
        b = block(who)
        assert 'class="col-md-9 col-sm-9 leads"' in b, f"{who}: no Leads line"
        assert group in b.split('class="col-md-9 col-sm-9 leads"')[1][:300], \
            f"{who} should be shown leading {group}"


@pytest.mark.ai_generated
def test_related_projects_are_linked_and_roled(whoweare):
    """A "Related projects" entry with no link is a dead end, and one with
    no role does not say why the person is in the list.  Restricting the
    list to projects with a heading on /projects dropped Joey Hess's only
    entry (git-annex is a collaborating project), so off-page links are
    expected and must be real URLs."""
    bodies = re.findall(r'<ul class="related-list">(.*?)</ul>', whoweare, re.S)
    assert len(bodies) > 5, f"only {len(bodies)} people have a related list"
    seen_offpage, linked, bare = False, 0, 0
    for body in bodies:
        for item in re.findall(r"<li>(.*?)</li>", body, re.S):
            assert "&#8212;" in item, f"related entry with no role: {item}"
            href = re.search(r'href="([^"]*)"', item)
            if not href:
                # HRF models and Hyperalignment infrastructure are advisory
                # efforts with no site and no heading of their own; naming
                # them unlinked beats inventing a destination
                bare += 1
                continue
            linked += 1
            assert href.group(1) != "#", f"placeholder link: {item}"
            seen_offpage |= href.group(1).startswith("http")
    assert seen_offpage, "no off-page project link survived"
    assert linked > 10 * bare, f"{bare} of {linked + bare} entries go nowhere"


@pytest.mark.ai_generated
def test_the_collaborating_strip_holds_no_sub_projects(whoweare):
    """A BEP is `part_of: bids` rather than `part_of: xyzrins:.`, so testing
    only for the latter put the four BEPs, the two DICOM working groups and
    ember's study-template in the strip as independent collaborations --
    next to the parent they belong to."""
    i = whoweare.index('id="collaborating-projects"')
    j = whoweare.index("<h2>", i)
    strip = whoweare[i:j]
    for name in ("BEP028", "BEP032", "BEP044", "BIDS 2.0",
                 "DICOM WG-16", "DICOM WG-32", "study-template", "TR&amp;D3"):
        assert f'title="{name}"' not in strip, f"{name} is not a collaboration"
    # and the parents it does hold are still there
    for name in ("BIDS", "DICOM", "git-annex"):
        assert f'title="{name}"' in strip, f"{name} went missing"


def test_no_broken_in_page_links(tmp_path):
    """A component linking to a sibling entry must land on it.  The ToC
    extension rewrites every id to a hook derived from the heading text, so
    an anchor built from a record slug does not survive the build."""
    out = _build(tmp_path)
    for name in ("projects", "whoweare"):
        t = (out / f"{name}.html").read_text()
        ids = set(re.findall(r'id="([^"]+)"', t))
        links = {l for l in re.findall(r'href="#([^"]+)"', t) if l}
        assert not links - ids, f"{name}: broken anchors {sorted(links - ids)}"


# --- assets ---------------------------------------------------------------

@pytest.mark.ai_generated
@pytest.mark.parametrize("page", ["render_whoweare.py", "render_projects.py"])
def test_every_image_resolves_on_disk(page):
    out = run(page).stdout
    missing = [s for s in set(re.findall(r'src="(/theme/[^"]+)"', out))
               if not (HERE / "theme/static" / s.replace("/theme/", "", 1)).exists()]
    assert not missing, f"{page} references images that do not exist: {missing}"


@pytest.mark.ai_generated
def test_every_section_expands_when_clicked(tmp_path):
    """Clicking a section in the sidebar must make it current AND reveal its
    entries -- in a browser, which is the only place this is decidable.

    Three separate things conspired to break this, none visible in the
    markup: the bs-docs sidebar reveals a section only while its <li> has
    `.active`, which scrollspy moves; a 70px `scroll-margin-top` left the
    jump 0.4px short of the section's own scrollspy offset, so the PREVIOUS
    section stayed open; and the page could not scroll far enough for the
    last two sections to ever become current.
    """
    pw = pytest.importorskip("playwright.sync_api")
    out = _build(tmp_path)

    srv = socketserver.TCPServer(("127.0.0.1", 0), functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(out)))
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        with pw.sync_playwright() as p:
            try:
                browser = p.chromium.launch()
            except Exception as exc:                       # no browser installed
                pytest.skip(f"chromium unavailable: {exc}")
            pg = browser.new_page(viewport={"width": 1500, "height": 1000})
            errors = []
            pg.on("pageerror", lambda e: errors.append(str(e)))
            for page in ("projects", "whoweare"):
                pg.goto(f"http://127.0.0.1:{port}/{page}.html")
                pg.wait_for_timeout(1200)
                # only sections that HAVE entries can show any; whoweare's
                # "Collaborating projects" is a leaf
                names = pg.eval_on_selector_all(
                    "#full-toc > ul > li:has(> ul) > a",
                    "els => els.map(e => e.textContent)")
                assert len(names) > 3, f"{page}: only {names} in the sidebar"
                for name in names:
                    pg.eval_on_selector(
                        f"#full-toc a:text-is({name!r})", "el => el.click()")
                    # wait for the condition, not for a fixed 600ms: four
                    # browser launches in one run made that too short under
                    # load and the test failed in the suite while passing
                    # alone
                    try:
                        pg.wait_for_function(
                            "n => [...document.querySelectorAll("
                            "'#full-toc li.active > a')].some("
                            "a => a.textContent === n)", arg=name, timeout=5000)
                    except Exception:
                        pass            # let the assertion below report it
                    active = pg.eval_on_selector_all(
                        "#full-toc li.active > a", "els => els.map(e => e.textContent)")
                    shown = pg.eval_on_selector_all(
                        "#full-toc li.active > ul.nav:visible li > a",
                        "els => els.map(e => e.textContent)")
                    assert name in active, \
                        f"{page}: clicking {name!r} made {active} current"
                    assert shown, f"{page}: {name!r} is current but shows no entries"
            assert not errors, errors
            browser.close()
    finally:
        srv.shutdown()


@pytest.mark.ai_generated
def test_top_menu_order(tmp_path):
    """Engage sat before Projects because the two pages shared
    `order: 3` and the menu sort is stable -- so the order was decided by
    which filename Pelican happened to read first, not by anything anyone
    wrote. Distinct numbers, and a test that says what they are for."""
    out = _build(tmp_path)
    t = (out / "projects.html").read_text()
    i = t.index("navbar-collapse")
    j = t.index("</ul>", i)
    # tags stripped: the off-site items end in icon <span>s
    labels = [re.sub(r"<[^>]+>", "", m).strip() for m in
              re.findall(r"<a [^>]*>(.*?)</a>", t[i:j], re.S)]
    menu = [l for l in labels if l != "Center for Open Neuroscience"]
    assert menu == ["Who we are", "Projects", "Engage", "Support",
                    "Talks", "Hub", "CONTube"], menu


@pytest.mark.ai_generated
def test_no_escaped_entities_in_plain_text_fields(whoweare, projects):
    """A record value that is NOT description_html is plain text, and the
    renderer escapes what it is given -- so an `&amp;` left in one by the
    extraction printed literally.  Vadim Melnik had two position attributes
    saying the same thing, one of them escaped, and the page showed both."""
    for page in (whoweare, projects):
        for m in re.finditer(r'class="[^"]*position[^"]*">(.*?)</div>', page):
            assert "&amp;amp;" not in m.group(1), m.group(1)
    # and the duplicate itself
    assert whoweare.count("Software Engineer &amp; Consultant") == 1


@pytest.mark.ai_generated
def test_phone_is_readable_and_still_dialable(whoweare):
    """`tel:` URIs allow only `-` and `.` as visual separators (RFC 3966),
    so the canonical value is `tel:+1(603)6469834` -- stripping the scheme
    for the label gave "+1(603)6469834" where the page had always shown
    the spaced form."""
    m = re.search(r'<a href="(tel:[^"]+)" class="phone">([^<]+)</a>', whoweare)
    assert m, "no phone link"
    assert m.group(2) == "+1 (603) 646-9834", m.group(2)
    assert "(" in m.group(1)          # href is still the canonical URI


@pytest.mark.ai_generated
def test_no_links_to_services_that_closed(whoweare):
    """Google+ shut down in April 2019 and two entries still linked to it.
    The records keep the account -- it was true -- but the page should not
    hand a reader a dead link."""
    assert "plus.google.com" not in whoweare
    assert "googleplus" not in whoweare


@pytest.mark.ai_generated
def test_every_icon_class_has_a_rule(whoweare, projects):
    """`.contact a` sets a DEFAULT background-image -- the Twitter bird --
    so a class with no rule of its own does not render as nothing, it
    renders as Twitter.  Three classes shipped that way once."""
    css = (HERE / "theme/static/css/site.css").read_text()
    for page, name in ((whoweare, "whoweare"), (projects, "projects")):
        for block in re.findall(r'<(?:div|span) class="[^"]*contact[^"]*">(.*?)'
                                r'</(?:div|span)>', page, re.S):
            for cls in re.findall(r'<a [^>]*class="([a-z0-9-]+)"', block):
                assert f".contact .{cls} {{" in css, \
                    f"{name}: .{cls} has no icon rule, so it renders as Twitter"


@pytest.mark.ai_generated
def test_project_links_are_icons_not_words(projects):
    """The metadata strip said "Home page" and "Source" in words while the
    person pages next to it used icons for the same links."""
    metas = re.findall(r'<p class="project-meta"><small>(.*?)</small>', projects)
    assert len(metas) > 30, f"only {len(metas)} metadata strips"
    linked = [m for m in metas if "<a " in m]
    assert len(linked) == len(metas), "a project with no link at all"
    for m in linked:
        assert 'class="contact"' in m, f"links not rendered as icons: {m[:90]}"
        # the label survives for a screen reader, and as a tooltip
        for a in re.findall(r"<a [^>]*>(.*?)</a>", m):
            assert a.strip(), "an icon with no accessible label"
        assert m.count("title=") == m.count("<a ")


@pytest.mark.ai_generated
def test_no_role_renders_as_a_bare_pid(whoweare):
    """Role labels come from the XYZAgentRole records and fall back to the
    pid, so a role used in an association but never defined prints as
    "Haxby 2001 -- marcrel:dtm"."""
    for body in re.findall(r'<ul class="related-list">(.*?)</ul>', whoweare, re.S):
        for item in re.findall(r"<li>(.*?)</li>", body, re.S):
            text = re.sub(r"<[^>]+>", "", item)
            assert not re.search(r"\b(marcrel|obo|xyzrins):", text), text.strip()


@pytest.mark.ai_generated
def test_typed_orcid_contact_link():
    """Typed ORCIDs render as links and take priority over legacy attributes."""
    from render_whoweare import contact_links

    person = {"identifiers": [{"schema_type": "xyzri:ORCID",
                               "notation": "0000-0002-1500-2143"}]}
    expected = ['<a href="https://orcid.org/0000-0002-1500-2143" '
                'class="orcid">ORCID</a>']
    assert contact_links(person) == expected
    person["attributes"] = [{"predicate": "dlthings:orcid",
                             "value": "https://orcid.org/0000-0001-6755-0259"}]
    assert contact_links(person) == expected
    del person["identifiers"]
    assert contact_links(person) == [
        '<a href="https://orcid.org/0000-0001-6755-0259" class="orcid">ORCID</a>']
