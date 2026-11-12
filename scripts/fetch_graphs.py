#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Yaroslav Halchenko <yaroslav.o.halchenko@dartmouth.edu>
# SPDX-License-Identifier: MIT
#
# Generated with Claude Code
"""Refresh the saved copies of other sites' graphs under content/graph/.

The browser loads another site's graph from that site (`graph_url` in
content/graph-sources.yaml).  The copy saved here is served with ours and
used only when that site cannot be reached, so the joint view degrades to
"as of the last refresh" instead of to nothing.  It is the site's file,
byte for byte; nothing is derived from it at build time.

Run `scripts/render_graph.py --report` afterwards to see what joins.
"""
import argparse
import json
import sys
import urllib.request

import congraph


def check(graph, name):
    if not (isinstance(graph, dict) and isinstance(graph.get("nodes"), list)
            and isinstance(graph.get("edges"), list)):
        sys.exit(f"{name}: not a graph: expected an object with node and edge arrays")
    for n in graph["nodes"]:
        if not {"id", "type"} <= set(n):
            sys.exit(f"{name}: a node lacks id or type: {n!r}")
    known = {n["id"] for n in graph["nodes"]}
    if "xyzrins:." not in known:
        sys.exit(f"{name}: no root node (xyzrins:.)")
    return graph


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", help="only this source id")
    a = ap.parse_args()
    done = 0
    for src in congraph.load_sources():
        if "graph_url" not in src or (a.source and src["id"] != a.source):
            continue
        req = urllib.request.Request(src["graph_url"],
                                     headers={
            "User-Agent": "con-graph-fetch",
            # as a browser on our site asks: the CORS header is only sent
            # in answer to an Origin
            "Origin": congraph.load_sources()[0]["base_url"]})
        with urllib.request.urlopen(req, timeout=60) as r:
            body = r.read()
            cors = r.headers.get("Access-Control-Allow-Origin")
        graph = check(json.loads(body), src["id"])
        out = congraph.CACHE_DIR / src["fallback"]
        out.write_bytes(body)
        print(f'wrote {out.relative_to(congraph.HERE)}  '
              f'({len(graph["nodes"])} nodes, {len(graph["edges"])} edges)')
        if cors != "*":
            print(f'WARNING: {src["graph_url"]} is served with '
                  f'Access-Control-Allow-Origin: {cors!r}; a browser on our '
                  f'site cannot load it and will always use the saved copy',
                  file=sys.stderr)
        done += 1
    if not done:
        sys.exit("no source to fetch")
    return 0


if __name__ == "__main__":
    sys.exit(main())
