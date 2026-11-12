# SPDX-FileCopyrightText: 2026 Yaroslav Halchenko <yaroslav.o.halchenko@dartmouth.edu>
# SPDX-License-Identifier: MIT
#
# Generated with Claude Code
"""The graph of CON's things, and how it meets other sites' graphs.

`content/graph/graph.json` is CON's graph, built here from the record store.
Every graph on the site is drawn from it by `theme/static/js/con-graph.js`,
which filters it by node type and by distance from a root.

Another site's graph is NOT part of that file.  When a reader asks for it,
the browser loads that site's own `graph.json` from that site -- so it is as
current as the site is -- and falls back to the copy under `content/graph/`
(refreshed by `scripts/fetch_graphs.py`) only when the site cannot be
reached.  What this module contributes to the join is the half we own: for
every CON node, the `keys` by which a node of another site is recognised as
the same thing.  The browser derives the other site's keys from its nodes
with the same rules and joins nodes of the same type that share one.

Node and edge selection follows `code/pool2graph.py` of www-from-model, the
producer of the `graph.json` behind psychoinformatics.de, so the graphs
describe the same kinds of things: the same eight record classes are nodes
and the same seven fields are edges.  That choice, and the shape of the
file another site publishes (`{nodes: [{id, label, type, size, url}],
edges: [{source, target}]}`), are what this module takes from it; none of
its code is here -- it reads a pool's JSON lines, this reads our YAML
records.  Two differences: an edge keeps the name of the field it came
from, and a thing nothing links to is left out.

Keys.  Every ORINOCO site names its own records `xyzrins:<class>/<slug>`,
one namespace shared by all of them; `xyzrins:.` is each site's own root.

* `pid:<pid>` -- a global pid is its own key (`pid:ror:02nv7yv05`), and an
  `exact_mappings` entry (`skos:exactMatch`) in one of our records is a key
  for the record it names (`pid:xyzrins:projects/a605574d-...`).  That is
  the curated way to say "same thing" when two stores minted different
  pids; see "The same thing in another store" in con-site-specific's
  docs/metadata-curation.md.  Every node of another site has `pid:<its
  pid>`.
* `path:<class>/<slug>` -- the local pid, when the source allows it
  (`match_local_paths`): the sites share people, projects and objectives
  and name them alike.  Never the root.
* `orcid:`, `doi:`, `ror:` -- identifiers a record carries.
* `title:<normalised>` -- for publications, since the upstream graph.json
  has no DOIs.

`merge()` is the same join in Python.  The site does not use its result; it
is what `render_graph.py --report` runs over the saved copy to show what the
browser will join, and what the tests pin the JavaScript against.
"""
import json
import re
import unicodedata

import render_projects
from conrecords import (HERE, RECORDS, TIERS, attrs, one, person_name,
                        preprint_of, publication_doi, publication_url, toc_hook,
                        yaml)

SOURCES_FILE = HERE / "content/graph-sources.yaml"
GRAPH_FILE = HERE / "content/graph/graph.json"
# saved copies of other sites' graphs, served as the fallback
CACHE_DIR = HERE / "content/graph"

LOCAL = "xyzrins:"
# IRI prefix -> CURIE prefix, for reading `exact_mappings`.  `xyzrins:` is
# one namespace shared by every store built on the demo schema.
IRI_PREFIXES = {
    "https://concepts.datalad.org/s/demo-research-information/ns/": LOCAL,
    "https://ror.org/": "ror:",
    "https://orcid.org/": "orcid:",
    "https://doi.org/": "doi:",
}
# class directory -> node type; the order is the order of the legend
NODE_CLASSES = {
    "XYZPerson": "person",
    "XYZProject": "project",
    "XYZPublication": "publication",
    "XYZInstrument": "instrument",
    "XYZDataset": "dataset",
    "XYZOrganization": "organization",
    "XYZObjective": "objective",
    "XYZTopic": "topic",
}
TYPES = list(NODE_CLASSES.values())
EDGE_FIELDS = ("associated_with", "attributed_to", "generated_by",
               "delegated_by", "influenced_by", "part_of", "about")
# plural used in "12 projects"; `person` is the irregular one
PLURAL = {"person": "people"}


def plural(kind, n):
    return kind if n == 1 else PLURAL.get(kind, kind + "s")


def norm_title(text):
    """A title reduced to what survives re-typing: letters and digits."""
    text = unicodedata.normalize("NFKD", text or "").lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def norm_doi(doi):
    doi = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:)", "", doi.strip(), flags=re.I)
    return doi.replace("\\", "").lower()


def norm_orcid(value):
    m = re.search(r"\d{4}-\d{4}-\d{4}-\d{3}[\dX]", value or "")
    return m.group(0) if m else None


# --- CON's own graph, from the record store ----------------------------

def _mapped(d):
    """The pids of other stores' records that `exact_mappings` names."""
    out = set()
    for iri in d.get("exact_mappings") or []:
        for prefix, curie in IRI_PREFIXES.items():
            if str(iri).startswith(prefix):
                out.add(curie + str(iri)[len(prefix):])
    return out


def _own_keys(pid, match_paths):
    """The keys a node has by its pid alone; the same rule for every site,
    and the one con-graph.js applies to another site's nodes."""
    if not pid.startswith(LOCAL):
        # a global pid is also the identifier it is made of: our record of
        # a person carries `orcid:0000-...`, theirs may be named by it
        return {"pid:" + pid, pid}
    if match_paths and pid != LOCAL + ".":
        return {"path:" + pid[len(LOCAL):]}
    return set()


def _label(kind, d, stem):
    if kind == "person":
        return person_name(d)
    return (d.get("short_name") or d.get("display_label") or d.get("name")
            or d.get("title") or stem)


def _keys(kind, d):
    """Global identifiers a record carries, as merge keys."""
    out = set()
    for ident in d.get("identifiers") or []:
        st, note = ident.get("schema_type", ""), str(ident.get("notation", ""))
        if st.endswith(":DOI"):
            out.add("doi:" + norm_doi(note))
        elif st.endswith(":ORCID") and norm_orcid(note):
            out.add("orcid:" + norm_orcid(note))
        elif st.endswith(":ROR"):
            out.add("ror:" + note.rsplit("/", 1)[-1])
    for v in attrs(d, "dlthings:orcid"):
        if norm_orcid(v):
            out.add("orcid:" + norm_orcid(v))
    for v in attrs(d, "dlthings:ror"):
        out.add("ror:" + v.rsplit("/", 1)[-1])
    if kind == "publication" and (d.get("title") or d.get("display_label")):
        out.add("title:" + norm_title(d.get("title") or d.get("display_label")))
    return out


def _links(kind, d, anchors):
    """Where a CON node leads: a place on this site first, the world second."""
    pid, out = d["pid"], []
    if pid == LOCAL + ".":
        return [{"k": "con", "href": "/"}]
    if kind == "person" and one(d, "dlthings:tier") in TIERS:
        out.append({"k": "con", "href": "/whoweare#" + toc_hook(person_name(d))})
    elif pid in anchors:
        out.append({"k": "con", "href": anchors[pid]})
    elif kind == "objective" and d.get("title"):
        out.append({"k": "con", "href": "/objectives#" + toc_hook(d["title"])})
    doi = next((k for k in sorted(_keys(kind, d)) if k.startswith("doi:")), None)
    if doi:
        out.append({"k": "doi", "href": "https://doi.org/" + doi[4:]})
    home = one(d, "foaf:homepage") or one(d, "dlthings:home_page")
    if home:
        out.append({"k": "web", "href": home})
    elif kind == "person" and not out:
        orcid = next((k for k in sorted(_keys(kind, d))
                      if k.startswith("orcid:")), None)
        if orcid:
            out.append({"k": "web", "href": "https://orcid.org/" + orcid[6:]})
    if pid.startswith("ror:") and not out:
        out.append({"k": "web", "href": "https://ror.org/" + pid[4:]})
    return out


def con_graph():
    """CON's graph in the neutral form `merge()` takes."""
    anchors = {r["d"]["pid"]:
               "/projects#" + toc_hook(r["d"].get("display_label")
                                       or r["d"].get("title") or r["slug"])
               for r in render_projects.load()[0]}
    nodes, edges, records = {}, [], {}
    for cls, kind in NODE_CLASSES.items():
        for f in sorted((RECORDS / cls).glob("*.yaml")):
            d = yaml.safe_load(f.read_text())
            pid = d["pid"]
            records[pid] = d
            nodes[pid] = {"id": pid, "label": _label(kind, d, f.stem),
                          "type": kind,
                          "keys": (_keys(kind, d)
                                   | {"pid:" + m for m in _mapped(d)}
                                   | _own_keys(pid, True)),
                          "links": _links(kind, d, anchors)}
            for field in EDGE_FIELDS:
                for rel in d.get(field) or []:
                    target = rel.get("object") if isinstance(rel, dict) else rel
                    if target:
                        edges.append((pid, target, field))
    root = nodes.get(LOCAL + ".")
    if root:
        root["label"] = "CON"
    edges = _fold_preprints(nodes, edges, records)
    return {"nodes": list(nodes.values()), "edges": edges}


def _fold_preprints(nodes, edges, records):
    """One node for a paper and the preprint it was.

    The store keeps the two as two records, rightly, and the published one
    names the other (`influenced_by`, Preprint role).  Drawn as two dots
    they read as a duplicate: the same title twice, on the same authors.
    So the preprint's node goes, as its entry goes from the publications
    page, and the paper's node takes over

    * its links -- an author or a project recorded only on the preprint
      still reaches the paper;
    * its keys -- another site that holds only the preprint, or holds the
      paper under the title the two share, joins this one node;
    * a `preprints` entry, which the node's card lists and its mark shows.
    """
    into = {}
    for pid, d in records.items():
        was = preprint_of(d)
        if was in nodes and pid in nodes and was != pid:
            into[was] = pid
    for was, pid in into.items():
        gone, kept, d = nodes.pop(was), nodes[pid], records[was]
        kept["keys"] |= gone["keys"]
        doi = publication_doi(d)
        kept.setdefault("preprints", []).append({
            "label": ("doi:" + doi) if doi else gone["label"],
            "href": publication_url(d)})
    seen, out = set(), []
    for s, t, field in edges:
        s, t = into.get(s, s), into.get(t, t)
        if s != t and (s, t, field) not in seen:
            seen.add((s, t, field))
            out.append((s, t, field))
    return out


# --- another site's graph, in the form its graph.json has --------------

def external_graph(src, raw=None):
    """A site's `graph.json` (the saved copy unless `raw` is given) as
    nodes with keys.  con-graph.js does the same to the live file.

    Upstream nodes are `{id, label, type, size, url}` with `url` relative to
    that site.  `ids` is optional: global identifiers (`doi:...`,
    `orcid:...`) of the thing, which pool2graph.py does not emit yet.
    """
    if raw is None:
        raw = json.loads((CACHE_DIR / src["fallback"]).read_text())
    base = src["base_url"].rstrip("/")
    nodes = []
    for n in raw["nodes"]:
        # unlike ours, another site's node is always reachable by its pid:
        # that is what an exact_mappings entry of ours names
        keys = {"pid:" + n["id"]} | _own_keys(n["id"], src.get("match_local_paths"))
        for k in n.get("ids") or []:
            scheme, _, rest = k.partition(":")
            keys.add("doi:" + norm_doi(rest) if scheme == "doi" else k)
        if n["type"] == "publication" and n.get("label"):
            keys.add("title:" + norm_title(n["label"]))
        url = n.get("url")
        links = []
        if url:
            links.append({"k": src["id"],
                          "href": base + ("/" if url == "/." else url)})
        nodes.append({"id": n["id"], "label": n.get("label") or n["id"],
                      "type": n["type"], "keys": keys, "links": links})
    edges = [(e["source"], e["target"], e.get("type") or "")
             for e in raw["edges"]]
    if src.get("within"):
        # Only what lies this many links from the site's root: a pool holds
        # more than its site shows (Psychoinformatics' has 850 publications
        # of the whole institute; two links from the root are the group's
        # people and projects and what those made).
        near, frontier = {LOCAL + "."}, {LOCAL + "."}
        for _ in range(int(src["within"])):
            frontier = ({t for s, t, _k in edges if s in frontier}
                        | {s for s, t, _k in edges if t in frontier}) - near
            near |= frontier
        nodes = [n for n in nodes if n["id"] in near]
        edges = [e for e in edges if e[0] in near and e[1] in near]
    return {"nodes": nodes, "edges": edges}


# --- the join, as the browser makes it ---------------------------------

def load_sources():
    return yaml.safe_load(SOURCES_FILE.read_text())["sources"]


def _qualify(pid, source):
    return source + ":" + pid[len(LOCAL):] if pid.startswith(LOCAL) else pid


def merge(graphs, prune=True):
    """Join `[(source, graph), ...]` into one graph; the first source wins.

    A node joins the node of an EARLIER source that has its type and shares
    a key with it, and otherwise is added under `<source>:<path>` (or its
    global pid).  Two nodes of one source are never joined: a site's own
    records are distinct by definition, and ours do share keys -- a preprint
    and its article have one title, as does a talk given in four places.
    For the same reason a key that several nodes of a source share points
    at none of them: a title cannot tell which of the two is meant.

    "Wins" is about presentation -- id, label, link order -- so the site's
    own source goes first.  Returns `(graph, joins)`; `joins` records which
    nodes were unified and by which key.  With `prune`, a node no edge
    reaches is left out.
    """
    by_key, nodes, joins, edges = {}, {}, [], {}
    for src, g in graphs:
        sid, local, mine = src["id"], {}, {}
        for n in g["nodes"]:
            hit = next(((k, by_key[(n["type"], k)]) for k in sorted(n["keys"])
                        if by_key.get((n["type"], k))), None)
            if hit:
                node = nodes[hit[1]]
                joins.append((node["id"], _qualify(n["id"], sid), hit[0]))
            else:
                node = {"id": _qualify(n["id"], sid), "label": n["label"],
                        "type": n["type"], "sources": [], "links": []}
                if n.get("preprints"):
                    node["preprints"] = n["preprints"]
                nodes[node["id"]] = node
            if sid not in node["sources"]:
                node["sources"].append(sid)
            node["links"] += [x for x in n["links"] if x not in node["links"]]
            for k in n["keys"]:
                # None marks a key two of this source's nodes share
                seen = mine.setdefault((n["type"], k), node["id"])
                if seen != node["id"]:
                    mine[(n["type"], k)] = None
            local[n["id"]] = node["id"]
        # only now do this source's keys become visible, to later sources
        for k, target in mine.items():
            if k not in by_key:
                by_key[k] = target
        for s, t, kind in g["edges"]:
            s, t = local.get(s), local.get(t)
            if not s or not t or s == t:
                continue            # the target is not a node: as upstream
            e = edges.setdefault((s, t), {"s": s, "t": t, "type": kind,
                                          "sources": []})
            if sid not in e["sources"]:
                e["sources"].append(sid)
    linked = {x for e in edges.values() for x in (e["s"], e["t"])}
    return ({"nodes": [n for n in nodes.values()
                       if not prune or n["id"] in linked],
             "edges": list(edges.values())}, joins)


SOURCE_FIELDS = ("id", "label", "base_url", "graph_url", "fallback",
                 "within", "match_local_paths")


def build():
    """CON's graph as it is written to graph.json."""
    sources = load_sources()
    home = con_graph()
    # Unpruned: a record nothing of ours links to may be the one another
    # site's node is joined with (FZJ is: none of our people is recorded as
    # working there, Psychoinformatics' are).  The browser leaves out what
    # is still unlinked in the view it draws.
    graph, _ = merge([(sources[0], home)], prune=False)
    keys = {_qualify(n["id"], sources[0]["id"]): sorted(n["keys"])
            for n in home["nodes"]}
    for n in graph["nodes"]:
        n["keys"] = keys[n["id"]]
    return {"sources": [{k: s[k] for k in SOURCE_FIELDS if k in s}
                        for s in sources],
            "types": TYPES, **graph}


def joined():
    """CON's graph joined with the saved copy of every other source: what
    the browser shows when none of the sites can be reached."""
    sources = load_sources()
    return merge([(sources[0], con_graph())]
                 + [(s, external_graph(s)) for s in sources[1:]])


def dumps(graph):
    """One node or edge per line: a store change is a readable diff."""
    def rows(items):
        return ",\n".join("  " + json.dumps(i, ensure_ascii=False,
                                            separators=(",", ":"))
                          for i in items)
    return ("{\n"
            f' "sources": {json.dumps(graph["sources"], ensure_ascii=False)},\n'
            f' "types": {json.dumps(graph["types"])},\n'
            f' "nodes": [\n{rows(graph["nodes"])}\n ],\n'
            f' "edges": [\n{rows(graph["edges"])}\n ]\n'
            "}\n")


# --- reading it back, the way the front end does -----------------------

def neighbourhood(graph, root, source=None):
    """Type -> count of the things directly linked to `root`.

    Mirrors `filterGraph()` in con-graph.js for depth 1, so the count in a
    "Graph (...)" summary is the count the opened graph shows.
    """
    types = {n["id"]: n["type"] for n in graph["nodes"]
             if source is None or source in n["sources"]}
    if root not in types:
        return {}
    near = set()
    for e in graph["edges"]:
        if source is not None and source not in e["sources"]:
            continue
        if e["s"] == root and e["t"] in types:
            near.add(e["t"])
        elif e["t"] == root and e["s"] in types:
            near.add(e["s"])
    counts = {}
    for n in near:
        counts[types[n]] = counts.get(types[n], 0) + 1
    return {t: counts[t] for t in TYPES if t in counts}


def summary(counts):
    """`{"project": 12, "person": 1}` -> "12 projects, 1 person"."""
    return ", ".join(f"{n} {plural(t, n)}" for t, n in counts.items())
