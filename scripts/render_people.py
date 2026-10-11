#!/usr/bin/env python3
"""Render content/people/*.yaml back into the whoweare markup, and diff.

The point is the diff, not the output.  A generator may only take over the
live page once it can reproduce it exactly; until `--check` is clean, the
records are known to be lossy and nothing should be generated from them.

  scripts/render_people.py --check     compare against content/pages/whoweare.html
  scripts/render_people.py --out FILE  write the rendered markup
"""
import argparse
import difflib
import pathlib
import re
import sys

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required")

HERE = pathlib.Path(__file__).resolve().parent.parent
PAGE = HERE / "content/pages/whoweare.html"
PEOPLE = HERE / "content/people"
TIER_ORDER = ["Centroids", "Collaborators", "Affiliated Faculty", "Emeritus"]


def load():
    recs = [yaml.safe_load(f.read_text()) for f in sorted(PEOPLE.glob("*.yaml"))]
    return sorted(recs, key=lambda r: r["order"])


def render_person(p):
    h3 = f'<h3 id="{p["anchor_id"]}">' if p.get("anchor_id") else "<h3>"
    out = [f'{h3}{p["display_name"]}</h3>']
    if p.get("portrait"):
        out.append(f'<figure><img src="{p["portrait"]}"'
                   f'{p.get("portrait_attrs") or "/"}></figure>')
    for pos in (p.get("positions") or []):
        out.append(f'<div class="col-md-4 col-sm-4 position">{pos}</div>')
    if p.get("contacts"):
        out.append('<div class="col-md-5 col-sm-5 contact">')
        for c in p["contacts"]:
            out.append(f'<a href="{c["href"]}" class="{c["kind"]}">{c["label"]}</a>')
        out.append("</div>")
    if p.get("description_html"):
        out.append(f'<div class="col-md-9 col-sm-9 description">{p["description_html"]}</div>')
    return out


def render():
    lines = []
    people = load()
    for tier in TIER_ORDER:
        lines.append(f"<h2>{tier}</h2>")
        for p in [x for x in people if x["tier"] == tier]:
            lines.append('<div class="row">')
            lines += render_person(p)
            lines.append("</div>")
    return "\n".join(lines) + "\n"


def normalise(html):
    """Collapse indentation, and NOTHING else that a browser can see.

    The previous version stripped comments and collapsed `>\\s+<` to `><`.
    Both made the gate dishonest: a renderer that dropped every comment, or
    that welded every inline sibling together (joining "</a><a>" where the
    page has "</a> <a>"), passed clean.  Verified -- a no-separator render
    of the people region passed.  Comments are content; inter-element
    whitespace is content wherever elements are inline.
    """
    return re.sub(r"[ \t]*\n[ \t]*", "\n", html).strip()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--out")
    a = ap.parse_args()

    out = render()
    if a.out:
        pathlib.Path(a.out).write_text(out)
        print(f"wrote {a.out}")
    if not a.check:
        return 0

    page = PAGE.read_text()
    # the people region runs from the first tier heading to the end of Emeritus
    start = page.index("<h2>Centroids</h2>")
    end = page.index("<h2>Collaborating projects</h2>")
    live = normalise(page[start:end])
    mine = normalise(out)
    if live == mine:
        print(f"round-trip CLEAN: {len(load())} records reproduce the people region")
        return 0
    sm = difflib.SequenceMatcher(a=live, b=mine, autojunk=False)
    print(f"round-trip DIFFERS (similarity {sm.ratio():.4f})")
    shown = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal" or shown >= 12:
            continue
        shown += 1
        print(f"  {tag:<7} live[{i1}:{i2}] {live[i1:i2][:90]!r}")
        print(f"          mine        {mine[j1:j2][:90]!r}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
