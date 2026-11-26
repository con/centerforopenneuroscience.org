# SPDX-FileCopyrightText: 2026 Yaroslav Halchenko <yaroslav.o.halchenko@dartmouth.edu>
# SPDX-License-Identifier: MIT
#
# Generated with Claude Code
"""Tests for the search box.

The index is written by a program that reports success whatever it found,
and the box is drawn by a script that is fetched only when it is opened --
so neither a page missing from the index nor a hit that leads nowhere shows
up in a build log.  These build the site and search it in a browser.
"""
import asyncio
import contextlib
import http.server
import json
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
    """Type a query into the open box; the hits as (text, href), in order."""
    pg.fill("#con-search input", query)
    # the count names the query once it is answered -- an earlier query's
    # hits are listed until then -- and each hit is a placeholder until its
    # part of the index has arrived
    pg.wait_for_function(
        """q => {
          const box = document.getElementById('con-search'),
                said = (box.querySelector('.pagefind-ui__message')
                        || {textContent: ''}).textContent;
          return said.includes(q)
              && !box.querySelector('.pagefind-ui__loading')
              && (said.startsWith('No results')
                  || box.querySelector('.pagefind-ui__result-link'));
        }""", arg=query)
    return pg.eval_on_selector_all(
        "#con-search .pagefind-ui__results a[href]",
        "els => els.map(a => [a.textContent.trim(), a.getAttribute('href')])")


def test_every_page_and_every_publication_is_indexed(site):
    """Pagefind skips a page it cannot read (one without an <html> element:
    all eight of ours, at first) and still exits 0."""
    pages = list(con_search.pages(site))
    assert "index.html" in pages and "explore/index.html" in pages
    assert not [p for p in pages if p.startswith(("theme/", "pagefind/"))], (
        "a vendored demo page or Pagefind's own output would be searched")
    pubs = json.loads((HERE / "theme/static/data/publications.json").read_text())
    entry = json.loads((site / "pagefind/pagefind-entry.json").read_text())
    assert list(entry["languages"]) == ["en"], "no lang= means no stemming"
    assert entry["languages"]["en"]["page_count"] == (
        len(pages) + len(pubs["publications"]))


def test_a_page_pagefind_skips_fails_the_build(site, tmp_path):
    """It skips a page without an <html> element and exits 0, and what it
    reports for a directory is the files it was given, not those it read:
    the check has to count what was written."""
    out = tmp_path / "site"
    shutil.copytree(site, out)
    (out / "bare.html").write_text("<head><title>x</title></head><p>bare</p>")
    with pytest.raises(SystemExit, match="233 expected"):
        asyncio.run(con_search.build(
            out, HERE / "theme/static/data/publications.json"))


def test_a_publication_without_an_address_leads_to_the_list_narrowed_to_it():
    (_, page), = con_search.publications({"publications": [
        {"title": 'A "B" & C', "url": None, "type": "paper", "year": 2020,
         "preprint": True, "authors": [["X Y", None], None]}]})
    assert 'href="/publications?q=A%20%22B%22%20%26%20C"' in page
    assert '<span data-pagefind-meta="type">preprint</span>' in page
    assert '<span data-pagefind-meta="year">2020</span>' in page
    assert "A &quot;B&quot; &amp; C</p>" in page


def test_rebuilding_leaves_one_index(site, tmp_path):
    """Pagefind names its files by content and removes none: without a
    clean-up every rebuild of output/ would add another index to upload."""
    out = tmp_path / "site"
    shutil.copytree(site, out)
    (out / "pagefind/fragment/stale.pf_fragment").write_text("old")
    asyncio.run(con_search.build(
        out, HERE / "theme/static/data/publications.json"))
    assert not (out / "pagefind/fragment/stale.pf_fragment").exists()
    assert len(list((out / "pagefind").glob("*.pf_meta"))) == 1


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
        assert not [u for u in fetched if "/pagefind/" in u], (
            "the index is fetched before anyone searches")

        pg.click("[data-con-search]")
        pg.wait_for_selector("#con-search input")
        assert pg.evaluate("document.activeElement.tagName") == "INPUT"

        # a project: the page first, and under it the section about it
        hits = search(pg, "datalad")
        assert hits[0] == ["Projects", "/projects"], hits[:3]
        assert ["DataLad", "/projects#datalad_"] in hits[:4], hits[:4]
        # a person
        assert ["John Wodder", "/whoweare#john_wodder_"] in search(pg, "wodder")
        # a publication leads to the publication, not to a page of the index
        hits = search(pg, "neurobagel international network")
        assert hits and hits[0][1].startswith("https://doi.org/"), hits
        assert "Href:" not in pg.inner_text("#con-search")
        # What is only in the navbar, the sidebar or the footer is not a
        # hit.  (Not "no hits": finding nothing, Pagefind tries the word
        # shortened, and "may" is on several pages.)
        search(pg, "maynard")
        assert "maynard" not in pg.inner_text(
            "#con-search .pagefind-ui__results").lower()

        # two talks of one title are told apart by what is under them
        search(pg, "neurobagel international network")
        assert "preprint" in pg.inner_text("#con-search .pagefind-ui__results").lower()

        pg.keyboard.press("Escape")
        pg.wait_for_selector("#con-search", state="hidden")
        # the focus is back on what opened the box
        assert pg.evaluate("document.activeElement.hasAttribute('data-con-search')")
        # a keydown without a key (Chrome's autofill sends one) is not ours
        pg.evaluate("document.dispatchEvent(new Event('keydown', {bubbles: true}))")
        pg.keyboard.press("/")
        pg.wait_for_selector("#con-search input", state="visible")
        assert not errors, errors
        browser.close()


def test_a_hit_on_the_page_being_read_closes_the_box_and_lands_on_it(site):
    """Such a hit loads nothing, so nothing closed the box; and the heading
    has to end up below the fixed navbar, not under it."""
    pw = pytest.importorskip("playwright.sync_api")
    with serve(site) as url, pw.sync_playwright() as p:
        browser = _browser(p)
        pg = browser.new_page(viewport={"width": 1280, "height": 900})
        pg.goto(f"{url}/projects")
        pg.click("[data-con-search]")
        pg.wait_for_selector("#con-search input")
        search(pg, "heudiconv")
        pg.click("#con-search a[href$='#heudiconv___reproin_']")
        pg.wait_for_selector("#con-search", state="hidden")
        assert pg.url.endswith("/projects#heudiconv___reproin_")
        top = pg.evaluate("document.getElementById('heudiconv___reproin_')"
                          ".getBoundingClientRect().top")
        assert 50 <= top <= 90, f"the heading is {top}px from the top"
        browser.close()


def test_the_search_works_in_a_pull_request_preview(site, tmp_path):
    """A preview is served from a subpath, where /pagefind/ and /projects
    are someone else's: only href= and src= are rewritten for it."""
    pw = pytest.importorskip("playwright.sync_api")
    shutil.copytree(site, tmp_path / PREVIEW.lstrip("/"))
    subprocess.run([sys.executable, str(HERE / "scripts/rewrite_preview_paths.py"),
                    str(tmp_path / PREVIEW.lstrip("/")), PREVIEW], check=True)
    with serve(tmp_path) as url, pw.sync_playwright() as p:
        browser = _browser(p)
        pg = browser.new_page(viewport={"width": 1280, "height": 900})
        pg.goto(f"{url}{PREVIEW}/")
        pg.click("[data-con-search]")
        pg.wait_for_selector("#con-search input")
        assert ["DataLad", f"{PREVIEW}/projects#datalad_"] in search(pg, "datalad")
        hits = search(pg, "neurobagel international network")
        assert hits[0][1].startswith("https://doi.org/"), hits
        search(pg, "datalad")
        pg.click("#con-search a[href$='/projects#datalad_']")
        pg.wait_for_url(f"**{PREVIEW}/projects#datalad_")
        browser.close()
