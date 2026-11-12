#!/usr/bin/env python3
"""Refresh the cached graphs of other sites under sourcedata/graphs/.

Each source in content/graph-sources.yaml with a `graph_url` is downloaded
to its `cache` file.  The build reads only the cache, so the site renders
without the network and a refresh shows up as a diff to review -- run
`scripts/render_graph.py --report` afterwards to see what it joined.

`--from-hugo-content DIR` is for a site whose graph.json cannot be reached:
it rebuilds an equivalent graph from a checkout of that site's Hugo sources
(the `content/` tree of a www-from-model site), which carry the same pids
and links, and DOIs and ORCIDs besides.  It needs `--source`.
"""
import argparse
import json
import pathlib
import sys
import urllib.request

import congraph
from conrecords import yaml

SECTIONS = {"persons": "person", "projects": "project",
            "publications": "publication", "instruments": "instrument",
            "datasets": "dataset", "objectives": "objective",
            "topics": "topic", "organizations": "organization"}


def check(graph, name):
    if not (isinstance(graph, dict) and isinstance(graph.get("nodes"), list)
            and isinstance(graph.get("edges"), list)):
        sys.exit(f"{name}: not a graph: expected an object with node and edge arrays")
    for n in graph["nodes"]:
        if not {"id", "type"} <= set(n):
            sys.exit(f"{name}: a node lacks id or type: {n!r}")
    return graph


def front_matter(path):
    text = path.read_text()
    if not text.startswith("---"):
        return {}
    return yaml.safe_load(text.split("\n---", 1)[0][3:]) or {}


def from_hugo_content(root):
    """A pool2graph-shaped graph from generated Hugo pages."""
    root = pathlib.Path(root)
    nodes, edges, names = {}, [], {}

    def pid_of(section, item):
        item = str(item)
        return item if ":" in item else f"xyzrins:{section}/{item}"

    pages = [(root / "_index.md", "project", "xyzrins:.", "/.")]
    for section, kind in SECTIONS.items():
        for f in sorted((root / section).glob("*/_index.md")):
            pages.append((f, kind, f"xyzrins:{section}/{f.parent.name}",
                          f"/{section}/{f.parent.name}"))
    for f, kind, pid, url in pages:
        if not f.exists():
            continue
        fm = front_matter(f)
        params = fm.get("params") or {}
        pid = params.get("graphRootNodePID") or params.get("pid") or pid
        ids = []
        if params.get("doi"):
            ids.append("doi:" + congraph.norm_doi(str(params["doi"])))
        for ident in params.get("identifiers") or []:
            if str(ident.get("schema_type", "")).endswith(":ORCID"):
                ids.append("orcid:" + str(ident["notation"]))
        node = {"id": pid, "label": str(fm.get("title") or pid), "type": kind,
                "size": 1, "url": ("/" + fm["url"].strip("/")) if fm.get("url") else url}
        if ids:
            node["ids"] = ids
        nodes[pid] = node
        for section in SECTIONS:
            for item in fm.get(section) or []:
                edges.append((pid, pid_of(section, item), SECTIONS[section]))
        for who in params.get("author") or []:
            if who.get("pid") and who.get("family_name"):
                names[who["pid"]] = (f'{who.get("given_name", "")} '
                                     f'{who["family_name"]}').strip()
    # People who are named but have no page of their own on that site
    # (pool2graph gives them a node and no url).
    for _, target, kind in edges:
        if target not in nodes and target in names:
            nodes[target] = {"id": target, "label": names[target],
                             "type": kind, "size": 1, "url": None}
    kept, seen = [], set()
    for s, t, _ in edges:
        if t in nodes and s != t and (s, t) not in seen and (t, s) not in seen:
            seen.add((s, t))
            nodes[t]["size"] += 1
            kept.append({"id": f"e{len(kept)}", "source": s, "target": t})
    return {"nodes": list(nodes.values()), "edges": kept}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", help="only this source id")
    ap.add_argument("--from-hugo-content", metavar="DIR")
    a = ap.parse_args()
    if a.from_hugo_content and not a.source:
        ap.error("--from-hugo-content needs --source")
    sources, _, _ = congraph.load_sources()
    done = 0
    for src in sources:
        if "cache" not in src or (a.source and src["id"] != a.source):
            continue
        if a.from_hugo_content:
            graph = from_hugo_content(a.from_hugo_content)
        else:
            req = urllib.request.Request(src["graph_url"],
                                         headers={"User-Agent": "con-graph-fetch"})
            with urllib.request.urlopen(req, timeout=60) as r:
                graph = json.load(r)
        check(graph, src["id"])
        out = congraph.CACHE_DIR / src["cache"]
        out.parent.mkdir(parents=True, exist_ok=True)
        # one node or edge per line, sorted: a refresh is a readable diff
        rows = lambda items: ",\n".join(  # noqa: E731
            "  " + json.dumps(i, ensure_ascii=False, sort_keys=True) for i in items)
        out.write_text('{\n "nodes": [\n'
                       + rows(sorted(graph["nodes"], key=lambda n: n["id"]))
                       + '\n ],\n "edges": [\n'
                       + rows(sorted(graph["edges"],
                                     key=lambda e: (e["source"], e["target"])))
                       + "\n ]\n}\n")
        print(f'wrote {out.relative_to(congraph.HERE)}  '
              f'({len(graph["nodes"])} nodes, {len(graph["edges"])} edges)')
        done += 1
    if not done:
        sys.exit("no source to fetch")
    return 0


if __name__ == "__main__":
    sys.exit(main())
