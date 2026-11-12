#!/usr/bin/env python3
"""Write content/graph/graph.json: CON's things joined with other sites'.

The sources are listed in content/graph-sources.yaml.  CON's own graph comes
from the record store; every other one from its cached `graph.json` under
sourcedata/graphs/ (refreshed by scripts/fetch_graphs.py), so this script
never touches the network and renders the same file from the same inputs.

`--report` prints which nodes of different sources were joined, and why.
That list is the thing to review when a source is added or refreshed.
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
    graph, joins = congraph.build()
    if a.report:
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
