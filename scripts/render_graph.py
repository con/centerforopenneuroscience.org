#!/usr/bin/env python3
"""Write content/graph/graph.json: the graph of CON's things.

It is built from the record store alone.  The graphs of the other sites in
content/graph-sources.yaml are loaded by the browser from those sites; this
file only names them and gives every CON node the keys by which their nodes
are recognised as the same thing (see scripts/congraph.py).

`--report` joins CON's graph with the saved copy of each other site's and
prints which nodes were unified, and why -- what a reader will see joined.
That list is the thing to review when a mapping is added or a copy
refreshed.
"""
import argparse
import collections
import pathlib
import sys

import congraph


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", help="file to write; default: standard output")
    ap.add_argument("--report", action="store_true",
                    help="list the cross-source joins instead of the graph")
    a = ap.parse_args()
    if a.report:
        graph, joins = congraph.joined()
        labels = {n["id"]: n for n in graph["nodes"]}
        for kept, other, why in sorted(joins, key=lambda j: (j[2].split(":")[0], j[0])):
            n = labels.get(kept)
            if n:
                print(f'{why.split(":")[0]:8s} {n["type"]:12s} {n["label"][:50]:50s} '
                      f'{kept}  ==  {other}')
        per = collections.Counter(tuple(n["sources"]) for n in graph["nodes"])
        for srcs, k in sorted(per.items()):
            print(f'{k:5d} nodes in {" + ".join(srcs)}', file=sys.stderr)
        return 0
    graph = congraph.build()
    text = congraph.dumps(graph)
    if a.out:
        pathlib.Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(a.out).write_text(text)
        print(f'wrote {a.out}  ({len(graph["nodes"])} nodes, '
              f'{len(graph["edges"])} edges)')
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
