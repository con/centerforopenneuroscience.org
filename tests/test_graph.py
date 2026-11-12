# SPDX-FileCopyrightText: 2026 Yaroslav Halchenko <yaroslav.o.halchenko@dartmouth.edu>
# SPDX-License-Identifier: MIT
#
# Generated with Claude Code
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
PSY = {"id": "psyinf", "match_local_paths": True, "base_url": "https://psy.example"}


def node(pid, kind="person", label=None, keys=(), links=(), paths=True):
    """A node as con_graph() or external_graph() hands it to merge()."""
    return {"id": pid, "label": label or pid, "type": kind,
            "keys": set(keys) | congraph._own_keys(pid, paths),
            "links": list(links)}


def theirs(pid, kind="person", label=None, keys=(), paths=True):
    """Another site's node: also reachable by its pid."""
    return node(pid, kind, label, set(keys) | {"pid:" + pid}, paths=paths)


def graph(nodes, edges=()):
    return {"nodes": nodes, "edges": list(edges)}


def ids(merged):
    return {n["id"]: n for n in merged["nodes"]}


def test_same_local_path_is_one_thing():
    a = graph([node("xyzrins:persons/a", label="Ada Lovelace"),
               node("xyzrins:projects/p", "project")],
              [("xyzrins:projects/p", "xyzrins:persons/a", "associated_with")])
    b = graph([theirs("xyzrins:persons/a", label="A.Lovelace"),
               theirs("xyzrins:projects/q", "project")],
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
    assert joins == [("con:persons/a", "psyinf:persons/a", "path:persons/a")]


def test_site_roots_are_never_joined():
    """`xyzrins:.` is each site's own root: CON is not Psychoinformatics."""
    a = graph([node("xyzrins:.", "project", "CON"), node("xyzrins:persons/a")],
              [("xyzrins:.", "xyzrins:persons/a", "associated_with")])
    b = graph([node("xyzrins:.", "project", "Psychoinformatics"),
               theirs("xyzrins:persons/a")],
              [("xyzrins:.", "xyzrins:persons/a", "associated_with")])
    got = ids(congraph.merge([(CON, a), (PSY, b)])[0])
    assert got["con:."]["sources"] == ["con"]
    assert got["psyinf:."]["sources"] == ["psyinf"]


def test_global_identifier_joins_differently_named_records():
    """One site's local record with an ORCID is another's `orcid:` pid."""
    a = graph([node("xyzrins:persons/yoh", keys={"orcid:0000-0003-3456-2493"}),
               node("xyzrins:projects/p", "project")],
              [("xyzrins:projects/p", "xyzrins:persons/yoh", "associated_with")])
    b = graph([theirs("orcid:0000-0003-3456-2493"),
               theirs("xyzrins:projects/q", "project")],
              [("xyzrins:projects/q", "orcid:0000-0003-3456-2493", "associated_with")])
    got = ids(congraph.merge([(CON, a), (PSY, b)])[0])
    assert got["con:persons/yoh"]["sources"] == ["con", "psyinf"]


def test_a_path_does_not_join_across_types_or_without_consent():
    a = graph([node("xyzrins:things/x", "project"), node("xyzrins:persons/a")],
              [("xyzrins:things/x", "xyzrins:persons/a", "associated_with")])
    b = graph([theirs("xyzrins:things/x", "instrument"), theirs("xyzrins:persons/a")],
              [("xyzrins:things/x", "xyzrins:persons/a", "attributed_to")])
    got = ids(congraph.merge([(CON, a), (PSY, b)])[0])
    assert "psyinf:things/x" in got, "a project was joined with an instrument"
    shy = graph([theirs("xyzrins:things/x", "instrument", paths=False),
                 theirs("xyzrins:persons/a", paths=False)], b["edges"])
    got = ids(congraph.merge([(CON, a), (PSY, shy)])[0])
    assert "psyinf:persons/a" in got, "joined by path although the source declined"


def test_exact_mappings_join_differently_named_records():
    """Our slug, their UUID: the record says they are one thing."""
    a = graph([node("xyzrins:projects/distribits", "project",
                    keys={"pid:xyzrins:projects/a605"}),
               node("xyzrins:persons/a")],
              [("xyzrins:projects/distribits", "xyzrins:persons/a", "associated_with")])
    b = graph([theirs("xyzrins:projects/a605", "project"), theirs("xyzrins:persons/b")],
              [("xyzrins:projects/a605", "xyzrins:persons/b", "associated_with")])
    merged, joins = congraph.merge([(CON, a), (PSY, b)])
    got = ids(merged)
    assert got["con:projects/distribits"]["sources"] == ["con", "psyinf"]
    assert "psyinf:projects/a605" not in got
    assert ("con:projects/distribits", "psyinf:projects/a605",
            "pid:xyzrins:projects/a605") in joins


def test_exact_mappings_are_read_from_the_iri():
    ns = "https://concepts.datalad.org/s/demo-research-information/ns/"
    assert congraph._mapped({"exact_mappings": [
        ns + "organizations/fzj", "https://ror.org/02nv7yv05",
        "http://purl.obolibrary.org/obo/OMRSE_00000087"]}) == {
            "xyzrins:organizations/fzj", "ror:02nv7yv05"}


def test_a_sites_own_records_are_never_joined_with_each_other():
    """A preprint and its article share a title and are two records; the
    same talk was given in four places.  Fusing them lost publications."""
    t = {"title:one title"}
    a = graph([node("xyzrins:publications/preprint", "publication", keys=t),
               node("xyzrins:publications/article", "publication", keys=t),
               node("xyzrins:persons/a")],
              [("xyzrins:publications/preprint", "xyzrins:persons/a", "attributed_to"),
               ("xyzrins:publications/article", "xyzrins:persons/a", "attributed_to")])
    got = ids(congraph.merge([(CON, a)])[0])
    assert {"con:publications/preprint", "con:publications/article"} <= set(got)
    # ... and a title that names two of ours cannot say which one theirs is
    b = graph([theirs("xyzrins:publications/uuid", "publication", keys=t),
               theirs("xyzrins:persons/b")],
              [("xyzrins:publications/uuid", "xyzrins:persons/b", "attributed_to")])
    merged, joins = congraph.merge([(CON, a), (PSY, b)])
    assert "psyinf:publications/uuid" in ids(merged) and not joins


def test_a_thing_nothing_links_to_is_left_out_unless_asked():
    a = graph([node("xyzrins:persons/a"), node("xyzrins:persons/lonely"),
               node("xyzrins:projects/p", "project")],
              [("xyzrins:projects/p", "xyzrins:persons/a", "associated_with"),
               ("xyzrins:projects/p", "xyzrins:persons/nobody", "associated_with")])
    assert set(ids(congraph.merge([(CON, a)])[0])) == {
        "con:persons/a", "con:projects/p"}
    # graph.json keeps it: another site's node may be joined with it
    assert "con:persons/lonely" in ids(congraph.merge([(CON, a)], prune=False)[0])


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


def test_a_source_can_be_limited_to_what_is_near_its_root():
    raw = {"nodes": [{"id": "xyzrins:.", "type": "project", "label": "Lab", "url": "/."},
                     {"id": "xyzrins:persons/a", "type": "person", "label": "A", "url": "/persons/a"},
                     {"id": "xyzrins:publications/p", "type": "publication", "label": "P", "url": None},
                     {"id": "xyzrins:persons/far", "type": "person", "label": "Far", "url": None}],
           "edges": [{"source": "xyzrins:.", "target": "xyzrins:persons/a"},
                     {"source": "xyzrins:publications/p", "target": "xyzrins:persons/a"},
                     {"source": "xyzrins:publications/p", "target": "xyzrins:persons/far"}]}
    assert len(congraph.external_graph(PSY, raw)["nodes"]) == 4
    near = congraph.external_graph(dict(PSY, within=2), raw)
    assert {n["id"] for n in near["nodes"]} == {
        "xyzrins:.", "xyzrins:persons/a", "xyzrins:publications/p"}
    assert near["nodes"][0]["links"] == [{"k": "psyinf", "href": "https://psy.example/"}]
    assert "pid:xyzrins:persons/a" in near["nodes"][1]["keys"]


# --- the graph this repo actually ships --------------------------------

@pytest.fixture(scope="module")
def shipped():
    return json.loads(run("render_graph.py").stdout)


def test_committed_graph_is_what_the_store_renders():
    assert run("render_graph.py").stdout == congraph.GRAPH_FILE.read_text(), (
        "content/graph/graph.json is stale: run `make project`")


def test_the_graph_is_ours_alone_closed_and_typed(shipped):
    """Nothing of another site is built into graph.json: the browser loads
    theirs from them.  The file names where, and where the saved copy is."""
    known = {n["id"] for n in shipped["nodes"]}
    assert len(known) == len(shipped["nodes"]), "duplicate node ids"
    for n in shipped["nodes"]:
        assert n["type"] in shipped["types"]
        assert n["sources"] == ["con"]
    for e in shipped["edges"]:
        assert e["s"] in known and e["t"] in known and e["sources"] == ["con"]
    others = shipped["sources"][1:]
    assert others, "no other site to join with"
    for src in others:
        assert src["graph_url"].startswith("https://")
        saved = congraph.CACHE_DIR / src["fallback"]
        assert saved.is_file(), f"no saved copy of {src['id']}'s graph"
        assert "xyzrins:." in {n["id"] for n in json.loads(saved.read_text())["nodes"]}


def test_the_sites_meet():
    """The point of the joint view: the people and projects we share."""
    got = {n["id"]: n["sources"] for n in congraph.joined()[0]["nodes"]}
    for pid in ("con:persons/yaroslav-halchenko", "con:persons/michael-hanke",
                "con:projects/datalad",
                # by exact_mappings in the record: a slug here, a UUID there
                "con:projects/distribits", "con:instruments/datalad-container",
                # ... and a ROR here, a local record there
                "ror:02nv7yv05"):
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


@pytest.mark.parametrize("page,least", [("whoweare", 20), ("projects", 20)])
def test_people_and_projects_each_offer_a_graph(shipped, page, least):
    text = (HERE / f"content/pages/{page}.html").read_text()
    known = {n["id"] for n in shipped["nodes"]}
    roots = re.findall(r'data-root="([^"]+)"', text)
    assert len(roots) > least
    assert len(set(roots)) == len(roots), "the same graph offered twice"
    assert set(roots) <= known, set(roots) - known
    assert re.search(r"<summary>Graph \(\d+ (people|person|projects?), ", text), (
        "no 'Graph (N ..., M ...)' summary")


def test_opened_graph_shows_what_its_summary_counted(served_site):  # noqa: F811
    """The summary is counted in Python, the graph filtered in JavaScript."""
    pw = pytest.importorskip("playwright.sync_api")
    with pw.sync_playwright() as p:
        browser = _browser(p)
        pg = browser.new_page(viewport={"width": 1400, "height": 900})
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        for page in ("whoweare", "projects"):
            pg.goto(f"{served_site}/{page}")
            fold = pg.locator("details.graph").first
            promised = sum(int(x) for x in re.findall(
                r"\d+", fold.locator("summary").inner_text()))
            fold.locator("summary").click()
            pg.wait_for_selector("details.graph .cg-count")
            shown = int(re.match(r"\d+", fold.locator(".cg-count").inner_text())[0])
            # the root itself is drawn but is not one of the things linked to it
            assert shown == promised + 1, page
        assert not errors, errors
        browser.close()


def test_the_browser_joins_another_site_as_python_does(served_site):  # noqa: F811
    """con-graph.js loads the other site's graph and joins it itself; the
    rules live twice, here and in congraph.merge().  With the site out of
    reach it must fall back to the saved copy, say so, and join exactly the
    nodes Python joins from that copy."""
    pw = pytest.importorskip("playwright.sync_api")
    want = sorted(n["id"] for n in congraph.joined()[0]["nodes"]
                  if len(n["sources"]) > 1)
    assert len(want) > 20
    with pw.sync_playwright() as p:
        browser = _browser(p)
        pg = browser.new_page(viewport={"width": 1400, "height": 900})
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        # never the real site from a test: unreachable is the case to check
        pg.route(re.compile(r"^https?://(?!127\.0\.0\.1)"), lambda r: r.abort())
        pg.goto(f"{served_site}/explore/#sources=con,psyinf&root=con:projects/datalad")
        pg.wait_for_selector(".cg-rings")
        got = pg.evaluate("""async () => {
            const d = await CONGraph.load();
            return {how: d.loaded.psyinf,
                    shared: d.nodes.filter(n => n.sources.length > 1)
                                   .map(n => n.id).sort()};
        }""")
        assert got["how"] == "saved"
        assert "saved copy" in pg.locator(".cg-note").inner_text()
        assert got["shared"] == want
        assert not errors, errors
        browser.close()


def test_every_type_has_its_mark():
    """con-graph.js draws theme/img/graph/<type>.svg on a node's dot; a
    missing file is a blank dot in the browser, not an error anywhere."""
    js = (HERE / "theme/static/js/con-graph.js").read_text()
    assert '"theme/img/graph/" + type + ".svg"' in js
    for kind in congraph.TYPES:
        mark = HERE / "theme/static/img/graph" / f"{kind}.svg"
        assert mark.is_file(), f"no mark for {kind}"
        text = mark.read_text()
        assert "<title>" in text and 'fill="#ffffff"' in text


def test_a_paper_and_its_preprint_are_one_node(shipped):
    """The store keeps a preprint and its article as two records; drawn as
    two dots of one title they read as a duplicate.  The article's node
    stands for both, lists the preprint, and can be joined by either."""
    got = {n["id"]: n for n in shipped["nodes"]}
    article = got["con:publications/doi-10-1162-imag-a-00074"]
    assert "con:publications/doi-10-1101-2023-08-16-552472" not in got
    assert article["preprints"] == [{
        "label": "doi:10.1101/2023.08.16.552472",
        "href": "https://doi.org/10.1101/2023.08.16.552472"}]
    assert {"doi:10.1101/2023.08.16.552472", "doi:10.1162/imag_a_00074"} <= set(article["keys"])
    # nobody the preprint named is lost
    authors = {e["t"] for e in shipped["edges"] if e["s"] == article["id"]}
    assert "con:persons/austin-macdonald" in authors
    assert (HERE / "theme/static/img/graph/publication-preprint.svg").is_file()


def test_folding_keeps_the_preprints_links_and_drops_the_pair():
    nodes = {"A": {"id": "A", "label": "Paper", "type": "publication", "keys": {"doi:a"}, "links": []},
             "P": {"id": "P", "label": "Paper", "type": "publication", "keys": {"doi:p"}, "links": []},
             "X": {"id": "X", "label": "X", "type": "person", "keys": set(), "links": []}}
    records = {"A": {"pid": "A", "influenced_by": [
                   {"object": "P", "roles": ["xyzrins:entity-roles/296e863e-7361-47ee-b337-e51a7e6bfe8d"]}]},
               "P": {"pid": "P", "identifiers": [{"schema_type": "dlthings:DOI", "notation": "10.1/p"}]},
               "X": {"pid": "X"}}
    edges = congraph._fold_preprints(
        nodes, [("A", "P", "influenced_by"), ("P", "X", "attributed_to"),
                ("A", "X", "attributed_to")], records)
    assert set(nodes) == {"A", "X"}
    assert edges == [("A", "X", "attributed_to")]
    assert nodes["A"]["keys"] == {"doi:a", "doi:p"}
    assert nodes["A"]["preprints"] == [{"label": "doi:10.1/p", "href": "https://doi.org/10.1/p"}]
