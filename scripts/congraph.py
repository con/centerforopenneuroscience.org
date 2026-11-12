# SPDX-FileCopyrightText: 2026 Yaroslav Halchenko <yaroslav.o.halchenko@dartmouth.edu>
# SPDX-License-Identifier: MIT
"""The graph of CON's things, alone and joined with other sites' graphs.

One file, `content/graph/graph.json`, feeds every graph on the site.  The
front end (`theme/static/js/con-graph.js`) only filters it: by source, by
node type and by distance from a root.  Everything that needs judgement --
which records are nodes, where a node links to, which node of another site
is the same thing -- is decided here, at build time, where it can be tested
and reviewed in a diff.

Node and edge selection follows `code/pool2graph.py` of www-from-model, the
producer of the `graph.json` behind dev.centerforopenneuroscience.org/explore
and psychoinformatics.de, so the three graphs describe the same kinds of
things.  Two differences: an edge keeps the name of the field it came from,
and a thing nothing links to is left out, because a lone dot explains nothing.

Identity across sites.  Every ORINOCO site names its own records
`xyzrins:<class>/<slug>`: the prefix means "this site", so the same pid on
two sites is two claims, and `xyzrins:.` is each site's own root.  Local pids
are therefore rewritten to `<source>:<class>/<slug>`, and two nodes of the
same type are joined when they share

* a global identifier: the pid itself (`orcid:`, `ror:`, `doi:`) or one the
  record carries (ORCID, DOI, ROR);
* the local path, when the source allows it (`match_local_paths`): the sites
  share people, projects and objectives and name them alike -- CON's seven
  objectives carry the very UUIDs they have at psychoinformatics.de.  The
  root is never matched this way;
* the title, for publications, since the upstream `graph.json` has no DOIs;
* an `exact_mappings` entry (`skos:exactMatch`) in one of our records that
  names the other site's record -- the curated way to say "same thing" when
  the two stores minted different pids (see "The same thing in another
  store" in con-site-specific's docs/metadata-curation.md);
* an explicit `same_as` pair in `content/graph-sources.yaml`, for a join
  that is about the graph rather than a fact worth a record.

`distinct` in that file vetoes a wrong join.  `render_graph.py --report`
lists every join made, with the key that made it.
"""
import json
import re
import unicodedata

import render_projects
from conrecords import HERE, RECORDS, TIERS, attrs, one, person_name, toc_hook, yaml

SOURCES_FILE = HERE / "content/graph-sources.yaml"
GRAPH_FILE = HERE / "content/graph/graph.json"
CACHE_DIR = HERE / "sourcedata/graphs"

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
    nodes, edges = {}, []
    for cls, kind in NODE_CLASSES.items():
        for f in sorted((RECORDS / cls).glob("*.yaml")):
            d = yaml.safe_load(f.read_text())
            pid = d["pid"]
            nodes[pid] = {"id": pid, "label": _label(kind, d, f.stem),
                          "type": kind, "keys": _keys(kind, d),
                          "maps": _mapped(d),
                          "links": _links(kind, d, anchors)}
            for field in EDGE_FIELDS:
                for rel in d.get(field) or []:
                    target = rel.get("object") if isinstance(rel, dict) else rel
                    if target:
                        edges.append((pid, target, field))
    root = nodes.get(LOCAL + ".")
    if root:
        root["label"] = "CON"
    return {"nodes": list(nodes.values()), "edges": edges}


# --- other sites' graphs, from their cached graph.json -----------------

def external_graph(src):
    """A cached upstream `graph.json` in the neutral form.

    Upstream nodes are `{id, label, type, size, url}` with `url` relative to
    that site.  `ids` is optional: global identifiers (`doi:...`,
    `orcid:...`) of the thing, which pool2graph.py does not emit yet.
    """
    raw = json.loads((CACHE_DIR / src["cache"]).read_text())
    base = src["base_url"].rstrip("/")
    nodes = []
    for n in raw["nodes"]:
        keys = set()
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


# --- joining them ------------------------------------------------------

def load_sources():
    cfg = yaml.safe_load(SOURCES_FILE.read_text())
    return cfg["sources"], cfg.get("same_as") or [], cfg.get("distinct") or []


def _qualify(pid, source):
    return source + ":" + pid[len(LOCAL):] if pid.startswith(LOCAL) else pid


def merge(graphs, same_as=(), distinct=()):
    """Join `[(source, graph), ...]` into one graph; the first source wins.

    "Wins" is about presentation only -- label, id, link order -- so the
    site's own source goes first.  Returns `(graph, joins)`; `joins` records
    which nodes were unified and by which key.
    """
    parent, order = {}, []

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    veto = {frozenset(p) for p in distinct}
    members = {}                    # union root -> [qualified ids]
    by_key, info, joins = {}, {}, []
    match_paths = {s["id"]: s.get("match_local_paths", False)
                   for s, _ in graphs}

    def union(a, b, why):
        ra, rb = find(a), find(b)
        if ra == rb:
            return
        if any(frozenset((x, y)) in veto
               for x in members[ra] for y in members[rb]):
            return
        if info[ra]["type"] != info[rb]["type"]:
            return
        # keep the earlier one as the representative
        if order.index(ra) > order.index(rb):
            ra, rb = rb, ra
        parent[rb] = ra
        members[ra] += members.pop(rb)
        joins.append((ra, rb, why))

    for src, g in graphs:
        sid = src["id"]
        for n in g["nodes"]:
            qid = _qualify(n["id"], sid)
            if qid in parent:       # a global pid seen in an earlier source
                info[qid]["sources"].append(sid)
                info[qid]["links"] += n["links"]
                info[qid]["keys"] |= n["keys"]
                joins.append((qid, qid, "pid"))
            else:
                parent[qid] = qid
                order.append(qid)
                members[qid] = [qid]
                info[qid] = dict(n, id=qid, sources=[sid],
                                 links=list(n["links"]), keys=set(n["keys"]))
            keys = set(n["keys"])
            if not n["id"].startswith(LOCAL):
                keys.add(n["id"])
            elif match_paths[sid] is not False and n["id"] != LOCAL + ".":
                keys.add("path:" + n["id"][len(LOCAL):])
            for k in sorted(keys):
                # a path only joins nodes of sources that both allow it
                if k.startswith("path:") and not match_paths[sid]:
                    continue
                if k in by_key:
                    union(by_key[k], qid, k)
                else:
                    by_key[k] = qid
    # what a record says is the same thing in another store
    for src, g in graphs:
        for n in g["nodes"]:
            for other in sorted(n.get("maps") or ()):
                for target_src, _ in graphs:
                    target = _qualify(other, target_src["id"])
                    if target in parent:
                        union(_qualify(n["id"], src["id"]), target,
                              "exact_mappings")
    for a, b in same_as:
        if a in parent and b in parent:
            union(a, b, "same_as")

    out_nodes = {}
    for qid in order:
        r = find(qid)
        if r not in out_nodes:
            i = info[r]
            out_nodes[r] = {"id": r, "label": i["label"], "type": i["type"],
                            "sources": [], "links": []}
        node, i = out_nodes[r], info[qid]
        node["sources"] += [s for s in i["sources"] if s not in node["sources"]]
        node["links"] += [x for x in i["links"] if x not in node["links"]]

    out_edges = {}
    for src, g in graphs:
        sid = src["id"]
        for s, t, kind in g["edges"]:
            s, t = _qualify(s, sid), _qualify(t, sid)
            if s not in parent or t not in parent:
                continue            # the target is not a node: as upstream
            s, t = find(s), find(t)
            if s == t:
                continue
            e = out_edges.setdefault((s, t), {"s": s, "t": t, "type": kind,
                                              "sources": []})
            if sid not in e["sources"]:
                e["sources"].append(sid)

    linked = {x for e in out_edges.values() for x in (e["s"], e["t"])}
    nodes = [n for n in out_nodes.values() if n["id"] in linked]
    return {"nodes": nodes, "edges": list(out_edges.values())}, joins


def build():
    """The joined graph as it is written to graph.json, and its joins."""
    sources, same_as, distinct = load_sources()
    graphs = []
    for src in sources:
        graphs.append((src, con_graph() if src.get("records")
                       else external_graph(src)))
    graph, joins = merge(graphs, same_as, distinct)
    graph = {
        "sources": [{k: s[k] for k in ("id", "label", "base_url") if k in s}
                    for s in sources],
        "types": TYPES,
        **graph,
    }
    return graph, joins


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
