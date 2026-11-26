# SPDX-FileCopyrightText: 2026 Yaroslav Halchenko <yaroslav.o.halchenko@dartmouth.edu>
# SPDX-License-Identifier: MIT
#
# Generated with Claude Code
"""Tests for the search box.

The index is read back out of the built pages, and the box is filled by a
script that fetches it only when it is opened -- so neither a section
missing from the index nor a hit that leads nowhere shows up in a build
log.  These build the site, check what was indexed and search it in a
browser.
"""
import contextlib
import http.server
import json
import re
import pathlib
import shutil
import subprocess
import sys
import threading

import pytest

HERE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / "tests"))
sys.path.insert(0, str(HERE / "plugins"))

import con_search  # noqa: E402 -- needs plugins/ on sys.path
from test_renderers import _browser, _build  # noqa: E402

pytestmark = pytest.mark.ai_generated

PREVIEW = "/centerforopenneuroscience.org/pr-preview/pr-1"


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    """The built site, index included."""
    return _build(tmp_path_factory.mktemp("search"))


@contextlib.contextmanager
def serve(root):
    """`root` over HTTP; /projects is answered from projects.html, as in
    production and by `make serve`."""
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(root), **kw)

        def send_head(self):
            path = self.path.split("?", 1)[0].split("#", 1)[0]
            if (not path.endswith("/")
                    and not (root / path.lstrip("/")).exists()
                    and (root / (path.lstrip("/") + ".html")).is_file()):
                self.path = path + ".html"
            return super().send_head()

        def log_message(self, *args):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{srv.server_address[1]}"
    finally:
        srv.shutdown()


def search(pg, query):
    """Type a query into the open box; the hits as (kind, title, href)."""
    pg.fill("#con-search-input", query)
    # the search is synchronous once the index is there, and says so
    pg.wait_for_function(
        "document.getElementById('con-search-status').textContent !== ''")
    return pg.eval_on_selector_all(
        "#con-search-hits a", """els => els.map(a => [
            a.querySelector('.pub-type').textContent,
            a.querySelector('.con-search-title').textContent,
            a.getAttribute('href')])""")


def open_box(pg):
    pg.click("[data-con-search]")
    pg.wait_for_selector("#con-search-input", state="visible")
    pg.wait_for_function("!!window.MiniSearch")


@pytest.fixture(scope="module")
def entries(site):
    return json.loads((site / "search.json").read_text())


def test_every_heading_one_can_link_to_is_an_entry(site, entries):
    """...and every entry within the site leads to a heading that exists."""
    indexed = {e["u"] for e in entries}
    for path, url in con_search.pages(site):
        assert not path.is_relative_to(site / "theme"), (
            "a vendored demo page would be searched")
        assert url in indexed
        text = path.read_text()
        # the main column: the sidebar repeats the headings as links, and
        # the navbar and the footer have ids of their own
        ids = re.findall(r'<h[1-6][^>]*\bid="([^"]+)"', text)
        assert {f"{url}#{i}" for i in ids} <= indexed, url
    local = {e["u"] for e in entries if e["u"].startswith("/") and "#" in e["u"]}
    for u in local:
        page, anchor = u.split("#")
        html_ = (site / (page.strip("/") + ".html")).read_text()
        assert f'id="{anchor}"' in html_, u
    assert len(local) == sum("#" in e["u"] for e in entries
                             if e["u"].startswith("/")), "an anchor indexed twice"


def test_every_publication_is_an_entry(entries):
    pubs = json.loads((HERE / "theme/static/data/publications.json").read_text())
    titles = [e["t"] for e in entries
              if e["k"] in ("paper", "preprint", "talk", "poster", "dataset")]
    assert sorted(titles) == sorted(p["title"] for p in pubs["publications"])


def test_a_publication_without_an_address_leads_to_the_list_narrowed_to_it():
    entry, = con_search.publications({"publications": [
        {"title": 'A "B" & C', "url": None, "type": "paper", "year": 2020,
         "preprint": True, "authors": [["X Y", None], None]}]})
    assert entry == {"u": "/publications?q=A%20%22B%22%20%26%20C",
                     "t": 'A "B" & C', "k": "preprint",
                     "x": "X Y, \u2026 \u00b7 2020"}


def test_an_entry_is_the_kind_of_thing_the_graph_says(entries):
    by = {e["u"]: e for e in entries}
    assert by["/whoweare#yaroslav_o_halchenko_"]["k"] == "person"
    assert by["/projects#datalad_"]["k"] == "project"
    assert by["/projects#datalad_"]["p"] == "Projects"
    assert by["/projects"]["k"] == "page"
    assert by["/projects#software_"]["k"] == "section"
    kinds = {e["k"] for e in entries}
    assert {"person", "project", "objective"} <= kinds, kinds


def test_what_is_not_content_is_not_indexed(entries):
    """The navbar, sidebar and footer are on every page; the folded lists
    under a person name every project, and under a project every person."""
    text = " ".join(e["x"] for e in entries)
    for chrome in ("Maynard Street", "Toggle navigation", "Back to Top",
                   "Stay in touch", "not directly affiliated"):
        assert chrome not in text, chrome
    datalad = next(e for e in entries if e["u"] == "/projects#datalad_")
    assert "DataLad is" in datalad["x"]
    assert "John Wodder" not in datalad["x"], "the folded list of its people"
    assert "home page" not in datalad["x"], "the labels of its links"
    # a lab that is only a logo is found by the logo's name
    labs = next(e for e in entries
                if e["u"] == "/whoweare#collaborating_labs__groups_")
    assert labs["x"], "the logos' alt texts"
    # blocks are set apart, not run together: "...Developer" + "Works on..."
    wodder = next(e for e in entries if e["u"] == "/whoweare#john_wodder_")
    assert wodder["x"].startswith("Software Developer \u00b7 Works on")


def test_sections_survive_markup_that_is_not_well_formed():
    """Our pages have a stray </br> and unclosed <p>s; a parser that
    believed every end tag would stop ignoring, or never stop."""
    page = """<html><head><title> A   page </title><style>p{}</style></head>
      <body><div data-search-ignore><p>menu</br><img src=x></div>
      <p>intro<h2 id="a_">First <a href="#a_">one</a></h2><p>alpha<br>beta
      <details class="people"><summary>2 people</summary><ul><li>X</ul></details>
      <h2>no anchor</h2><p>gamma</p>
      <h3 id="b_">Second</h3><div data-pub-app=""><li>a paper</div>delta
      </body></html>"""
    got = list(con_search.sections(page, "/p", {"/p#b_": "person"}))
    # a stray end tag inside what is left out does not end the leaving out
    stray = "<html><body><p>in<div data-search-ignore><b>x</b></p>y</div>out"
    assert [e["x"] for e in con_search.sections(stray, "/p", {})] == [
        "in \u00b7 out"]
    assert got == [
        {"u": "/p", "t": "A page", "k": "page", "x": "intro"},
        {"u": "/p#a_", "t": "First one", "p": "A page", "k": "section",
         "x": "alpha \u00b7 beta \u00b7 no anchor \u00b7 gamma"},
        {"u": "/p#b_", "t": "Second", "p": "A page", "k": "person",
         "x": "delta"},
    ]


def test_a_search_finds_the_section_the_person_and_the_publication(site):
    pw = pytest.importorskip("playwright.sync_api")
    with serve(site) as url, pw.sync_playwright() as p:
        browser = _browser(p)
        pg = browser.new_page(viewport={"width": 1280, "height": 900})
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        fetched = []
        pg.on("request", lambda r: fetched.append(r.url))
        pg.goto(f"{url}/engage")
        assert not [u for u in fetched if "search.json" in u or "minisearch" in u], (
            "the index is fetched before anyone searches")

        open_box(pg)
        assert pg.evaluate("document.activeElement.id") == "con-search-input"

        # a project before the talks about it
        hits = search(pg, "datalad")
        assert hits[0] == ["project", "DataLad", "/projects#datalad_"], hits[:3]
        assert pg.inner_text("#con-search-hits li:first-child mark") == "DataLad"
        # a person, by a name being typed
        assert search(pg, "wodd")[0] == [
            "person", "John Wodder", "/whoweare#john_wodder_"]
        # a publication leads to the publication; every word has to match
        hits = search(pg, "neurobagel international network")
        assert len(hits) == 1 and hits[0][0] == "preprint", hits
        assert hits[0][2].startswith("https://doi.org/")
        # a letter off still finds it
        assert search(pg, "heudicnov")[0][2] == "/projects#heudiconv___reproin_"
        # a letter typed without its mark finds the one with it
        assert "Oliver R\u00fcbel" in [t for _, t, _ in search(pg, "rubel")]
        # what is only in the navbar, the sidebar or the footer is not a hit
        assert search(pg, "maynard") == []
        assert "Nothing found" in pg.inner_text("#con-search-status")

        # the keyboard: down into the hits, up back to the field, Enter opens
        search(pg, "datalad")
        pg.keyboard.press("ArrowDown")
        pg.keyboard.press("ArrowDown")
        assert pg.evaluate("document.activeElement.getAttribute('href')") == (
            "/projects#dataladregistry_")
        pg.keyboard.press("ArrowUp")
        pg.keyboard.press("ArrowUp")
        assert pg.evaluate("document.activeElement.id") == "con-search-input"
        pg.keyboard.press("Escape")
        pg.wait_for_selector("#con-search", state="hidden")
        # the focus is back on what opened the box
        assert pg.evaluate("document.activeElement.hasAttribute('data-con-search')")
        # a keydown without a key (Chrome's autofill sends one) is not ours
        pg.evaluate("document.dispatchEvent(new Event('keydown', {bubbles: true}))")
        pg.keyboard.press("/")
        pg.wait_for_selector("#con-search-input", state="visible")
        search(pg, "datalad")
        with pg.expect_navigation():
            pg.keyboard.press("Enter")
        assert pg.url.endswith("/projects#datalad_")
        assert not errors, errors
        browser.close()


def test_a_failed_load_is_said_and_tried_again(site):
    """The first keystroke used to wipe the message, leaving a field that
    answered nothing; and only reopening the box tried again."""
    pw = pytest.importorskip("playwright.sync_api")
    with serve(site) as url, pw.sync_playwright() as p:
        browser = _browser(p)
        pg = browser.new_page(viewport={"width": 1280, "height": 900})
        pg.goto(f"{url}/engage")
        pg.route("**/search.json", lambda route: route.abort())
        pg.click("[data-con-search]")
        pg.wait_for_function("document.getElementById('con-search-status')"
                             ".textContent.includes('could not be loaded')")
        # a keystroke tries again, and says so again
        pg.keyboard.type("d")
        pg.wait_for_function("document.getElementById('con-search-status')"
                             ".textContent.includes('could not be loaded')")
        assert pg.inner_text("#con-search-hits") == ""
        pg.unroute("**/search.json")
        pg.keyboard.type("atalad")
        pg.wait_for_selector("#con-search-hits a")
        assert "results" in pg.inner_text("#con-search-status")
        browser.close()


def test_a_hit_on_the_page_being_read_closes_the_box_and_lands_on_it(site):
    """Such a hit loads nothing, so nothing closed the box; and the heading
    has to end up below the fixed navbar, not under it."""
    pw = pytest.importorskip("playwright.sync_api")
    with serve(site) as url, pw.sync_playwright() as p:
        browser = _browser(p)
        pg = browser.new_page(viewport={"width": 1280, "height": 900})
        pg.goto(f"{url}/projects")
        open_box(pg)
        search(pg, "heudiconv")
        pg.click("#con-search a[href$='#heudiconv___reproin_']")
        pg.wait_for_selector("#con-search", state="hidden")
        assert pg.url.endswith("/projects#heudiconv___reproin_")
        top = pg.evaluate("document.getElementById('heudiconv___reproin_')"
                          ".getBoundingClientRect().top")
        assert 50 <= top <= 90, f"the heading is {top}px from the top"
        browser.close()


def test_the_search_works_in_a_pull_request_preview(site, tmp_path):
    """A preview is served from a subpath, where /search.json and /projects
    are someone else's: only href= and src= are rewritten for it."""
    pw = pytest.importorskip("playwright.sync_api")
    shutil.copytree(site, tmp_path / PREVIEW.lstrip("/"))
    subprocess.run([sys.executable, str(HERE / "scripts/rewrite_preview_paths.py"),
                    str(tmp_path / PREVIEW.lstrip("/")), PREVIEW], check=True)
    with serve(tmp_path) as url, pw.sync_playwright() as p:
        browser = _browser(p)
        pg = browser.new_page(viewport={"width": 1280, "height": 900})
        pg.goto(f"{url}{PREVIEW}/")
        open_box(pg)
        assert search(pg, "datalad")[0][2] == f"{PREVIEW}/projects#datalad_"
        hits = search(pg, "neurobagel international network")
        assert hits[0][2].startswith("https://doi.org/"), hits
        search(pg, "datalad")
        pg.click("#con-search a[href$='/projects#datalad_']")
        pg.wait_for_url(f"**{PREVIEW}/projects#datalad_")
        browser.close()
