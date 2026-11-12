# SPDX-FileCopyrightText: 2026 Yaroslav Halchenko <yaroslav.o.halchenko@dartmouth.edu>
# SPDX-License-Identifier: MIT
"""Tests for the graph: what is joined with what, and where a node leads.

The join across sites is the part a reader cannot check by looking -- a wrong
one silently makes two people one -- so each rule of `congraph.merge` has a
test that would fail if the rule were dropped.  The rest pin the graph to the
pages: a link from a node lands on a heading that exists, and the count in a
person's "Graph (...)" summary is the count the opened graph shows.
"""
import html
import json
import pathlib
import re
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / "scripts"))
sys.path.insert(0, str(HERE / "tests"))

import congraph  # noqa: E402 -- needs scripts/ on sys.path
from conrecords import toc_hook  # noqa: E402
from test_renderers import _browser, run, served_site  # noqa: E402,F401 -- fixture

pytestmark = pytest.mark.ai_generated

CON = {"id": "con", "match_local_paths": True}
PSY = {"id": "psyinf", "match_local_paths": True}


def node(pid, kind="person", label=None, keys=(), links=()):
    return {"id": pid, "label": label or pid, "type": kind,
            "keys": set(keys), "links": list(links)}


def graph(nodes, edges=()):
    return {"nodes": nodes, "edges": list(edges)}


def ids(merged):
    return {n["id"]: n for n in merged["nodes"]}


def test_same_local_path_is_one_thing():
    a = graph([node("xyzrins:persons/a", label="Ada Lovelace"),
               node("xyzrins:projects/p", "project")],
              [("xyzrins:projects/p", "xyzrins:persons/a", "associated_with")])
    b = graph([node("xyzrins:persons/a", label="A.Lovelace"),
               node("xyzrins:projects/q", "project")],
              [("xyzrins:projects/q", "xyzrins:persons/a", "associated_with")])
    merged, joins = congraph.merge([(CON, a), (PSY, b)])
    got = ids(merged)
    assert got["con:persons/a"]["sources"] == ["con", "psyinf"]
    # the first source's spelling wins
    assert got["con:persons/a"]["label"] == "Ada Lovelace"
    assert "psyinf:persons/a" not in got
    # both projects now hang off the one person
    assert {(e["s"], e["t"]) for e in merged["edges"]} == {
        ("con:projects/p", "con:persons/a"), ("psyinf:projects/q", "con:persons/a")}
    assert [j[2] for j in joins] == ["path:persons/a"]


def test_site_roots_are_never_joined():
    """`xyzrins:.` is each site's own root: CON is not Psychoinformatics."""
    a = graph([node("xyzrins:.", "project", "CON"), node("xyzrins:persons/a")],
              [("xyzrins:.", "xyzrins:persons/a", "associated_with")])
    b = graph([node("xyzrins:.", "project", "Psychoinformatics"),
               node("xyzrins:persons/a")],
              [("xyzrins:.", "xyzrins:persons/a", "associated_with")])
    got = ids(congraph.merge([(CON, a), (PSY, b)])[0])
    assert got["con:."]["sources"] == ["con"]
    assert got["psyinf:."]["sources"] == ["psyinf"]


def test_global_identifier_joins_differently_named_records():
    """One site's local record with an ORCID is another's `orcid:` pid."""
    a = graph([node("xyzrins:persons/yoh", keys={"orcid:0000-0003-3456-2493"}),
               node("xyzrins:projects/p", "project")],
              [("xyzrins:projects/p", "xyzrins:persons/yoh", "associated_with")])
    b = graph([node("orcid:0000-0003-3456-2493"),
               node("xyzrins:projects/q", "project")],
              [("xyzrins:projects/q", "orcid:0000-0003-3456-2493", "associated_with")])
    got = ids(congraph.merge([(CON, a), (PSY, b)])[0])
    assert got["con:persons/yoh"]["sources"] == ["con", "psyinf"]


def test_a_path_does_not_join_across_types_or_without_consent():
    a = graph([node("xyzrins:things/x", "project"), node("xyzrins:persons/a")],
              [("xyzrins:things/x", "xyzrins:persons/a", "associated_with")])
    b = graph([node("xyzrins:things/x", "instrument"), node("xyzrins:persons/a")],
              [("xyzrins:things/x", "xyzrins:persons/a", "attributed_to")])
    got = ids(congraph.merge([(CON, a), (PSY, b)])[0])
    assert "psyinf:things/x" in got, "a project was joined with an instrument"
    shy = dict(PSY, match_local_paths=False)
    got = ids(congraph.merge([(CON, a), (shy, b)])[0])
    assert "psyinf:persons/a" in got, "joined by path although the source declined"


def test_distinct_vetoes_and_same_as_forces():
    a = graph([node("xyzrins:persons/a"), node("xyzrins:persons/b"),
               node("xyzrins:projects/p", "project")],
              [("xyzrins:projects/p", "xyzrins:persons/a", "associated_with"),
               ("xyzrins:projects/p", "xyzrins:persons/b", "associated_with")])
    b = graph([node("xyzrins:persons/a"), node("xyzrins:persons/bee"),
               node("xyzrins:projects/q", "project")],
              [("xyzrins:projects/q", "xyzrins:persons/a", "associated_with"),
               ("xyzrins:projects/q", "xyzrins:persons/bee", "associated_with")])
    got = ids(congraph.merge(
        [(CON, a), (PSY, b)],
        same_as=[["con:persons/b", "psyinf:persons/bee"]],
        distinct=[["con:persons/a", "psyinf:persons/a"]])[0])
    assert "psyinf:persons/a" in got
    assert got["con:persons/b"]["sources"] == ["con", "psyinf"]


def test_a_thing_nothing_links_to_is_left_out():
    a = graph([node("xyzrins:persons/a"), node("xyzrins:persons/lonely"),
               node("xyzrins:projects/p", "project")],
              [("xyzrins:projects/p", "xyzrins:persons/a", "associated_with"),
               ("xyzrins:projects/p", "xyzrins:persons/nobody", "associated_with")])
    got = ids(congraph.merge([(CON, a)])[0])
    assert set(got) == {"con:persons/a", "con:projects/p"}


def test_neighbourhood_counts_one_source():
    merged = {"nodes": [{"id": "r", "type": "person", "sources": ["con"]},
                        {"id": "p", "type": "project", "sources": ["con", "psyinf"]},
                        {"id": "q", "type": "project", "sources": ["psyinf"]},
                        {"id": "w", "type": "publication", "sources": ["con"]}],
              "edges": [{"s": "p", "t": "r", "sources": ["con"]},
                        {"s": "q", "t": "r", "sources": ["psyinf"]},
                        {"s": "w", "t": "r", "sources": ["con"]},
                        {"s": "w", "t": "p", "sources": ["con"]}]}
    assert congraph.neighbourhood(merged, "r", "con") == {"project": 1, "publication": 1}
    assert congraph.neighbourhood(merged, "r") == {"project": 2, "publication": 1}
    assert congraph.summary({"project": 1, "person": 2}) == "1 project, 2 people"


# --- the graph this repo actually ships --------------------------------

@pytest.fixture(scope="module")
def shipped():
    return json.loads(run("render_graph.py").stdout)


def test_committed_graph_is_what_the_store_renders():
    assert run("render_graph.py").stdout == congraph.GRAPH_FILE.read_text(), (
        "content/graph/graph.json is stale: run `make project`")


def test_the_graph_is_closed_and_typed(shipped):
    known = {n["id"] for n in shipped["nodes"]}
    sources = {s["id"] for s in shipped["sources"]}
    assert len(known) == len(shipped["nodes"]), "duplicate node ids"
    for n in shipped["nodes"]:
        assert n["type"] in shipped["types"]
        assert n["sources"] and set(n["sources"]) <= sources
    for e in shipped["edges"]:
        assert e["s"] in known and e["t"] in known


def test_the_sites_meet(shipped):
    """The point of the joint view: the people and projects we share."""
    got = {n["id"]: n["sources"] for n in shipped["nodes"]}
    for pid in ("con:persons/yaroslav-halchenko", "con:persons/michael-hanke",
                "con:projects/datalad"):
        assert got[pid] == ["con", "psyinf"], f"{pid} is not shared"
    assert got["con:."] == ["con"]


def test_links_into_this_site_land_on_a_heading(shipped):
    """A node's "On this site" link is an anchor the built page really has."""
    hooks = {}
    for page, tag in (("whoweare", "h3"), ("projects", "h[12]"),
                      ("objectives", "h2")):
        text = (HERE / f"content/pages/{page}.html").read_text()
        hooks[page] = {toc_hook(html.unescape(re.sub(r"<[^>]+>", "", m)))
                       for m in re.findall(rf"<{tag}[^>]*>(.*?)</{tag[:1]}\d>", text)}
    bad = []
    for n in shipped["nodes"]:
        for link in n["links"]:
            if link["k"] != "con" or "#" not in link["href"]:
                continue
            page, hook = link["href"].lstrip("/").split("#")
            if hook not in hooks[page]:
                bad.append((n["id"], link["href"]))
    assert not bad, bad


def test_whoweare_offers_a_graph_per_person(shipped):
    page = (HERE / "content/pages/whoweare.html").read_text()
    known = {n["id"] for n in shipped["nodes"]}
    roots = re.findall(r'data-root="([^"]+)"', page)
    assert len(roots) > 20
    assert set(roots) <= known, set(roots) - known
    m = re.search(r"<summary>Graph \((\d+) projects?, (\d+) publications?", page)
    assert m, "no 'Graph (N projects, M publications, ...)' summary"


def test_opened_graph_shows_what_its_summary_counted(served_site):  # noqa: F811
    """The summary is counted in Python, the graph filtered in JavaScript."""
    pw = pytest.importorskip("playwright.sync_api")
    with pw.sync_playwright() as p:
        browser = _browser(p)
        pg = browser.new_page(viewport={"width": 1400, "height": 900})
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(f"{served_site}/whoweare")
        fold = pg.locator("details.graph").first
        promised = sum(int(x) for x in re.findall(r"\d+", fold.locator("summary").inner_text()))
        fold.locator("summary").click()
        pg.wait_for_selector("details.graph .cg-count")
        shown = int(re.match(r"\d+", fold.locator(".cg-count").inner_text())[0])
        # the root itself is drawn but is not one of the things linked to it
        assert shown == promised + 1
        pg.goto(f"{served_site}/explore/#sources=con,psyinf&root=con:projects/datalad")
        pg.wait_for_selector(".cg-count")
        assert pg.locator(".cg-rings").count() == 1
        assert not errors, errors
        browser.close()
