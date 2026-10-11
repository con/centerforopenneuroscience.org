#!/usr/bin/env python3
"""Extract content/pages/whoweare.html into per-person records, losslessly.

Step one of moving the site onto records: before anything can be *generated*
from records, the records have to be able to reproduce what is on the page
today, byte for byte.  This script only reads; scripts/render_people.py turns
the records back into HTML and the two are diffed.  Until that round-trip is
clean, no generator should touch the live page.

Prose is kept as raw HTML on purpose.  The descriptions carry links, <b>, and
project cross-references; normalising them into plain text would quietly throw
away content the page depends on.
"""
import pathlib
import re
import sys

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required")

HERE = pathlib.Path(__file__).resolve().parent.parent
PAGE = HERE / "content/pages/whoweare.html"
OUT = HERE / "content/people"

ROW = re.compile(r'<div class="row">(.*?)</div>\s*(?=<div class="row">|<h2|</div>)', re.S)


def slug(name):
    kept = "".join(c if (c.isalnum() or c.isspace()) else "" for c in name.lower())
    return "-".join(kept.split())


def grab_all(block, cls):
    """Every <div class="...cls..."> in order -- three people carry two
    `position` divs (Pestilli, Hanke, Haxby) and a single-valued field drops
    one of them without a word."""
    return [m.group(1) for m in
            re.finditer(r'<div class="[^"]*\b%s\b[^"]*">(.*?)</div>' % cls,
                        block, re.S)]


def grab(block, cls, strip=True):
    """Inner HTML of a <div class="...cls...">.

    `strip=False` keeps surrounding whitespace verbatim.  The descriptions on
    the live page are padded inside their div, and silently dropping that is
    the difference between a lossless record and one that merely looks right.
    """
    m = re.search(r'<div class="[^"]*\b%s\b[^"]*">(.*?)</div>' % cls, block, re.S)
    if not m:
        return None
    return m.group(1).strip() if strip else m.group(1)


def main():
    raw = PAGE.read_text()
    # blank out commented-out regions, keeping offsets, so headings parked in
    # comments (the Partners block has <!-- <h3>INCF</h3> -->) are not mistaken
    # for live entries
    html = re.sub(r"<!--.*?-->", lambda m: " " * len(m.group(0)), raw, flags=re.S)
    # tier headings partition the page
    tiers = [(m.start(), re.sub(r"<[^>]+>", "", m.group(1)).strip())
             for m in re.finditer(r"<h2[^>]*>(.*?)</h2>", html, re.S)]

    def tier_at(pos):
        cur = None
        for start, label in tiers:
            if start < pos:
                cur = label
        return cur

    OUT.mkdir(parents=True, exist_ok=True)
    people, order = [], 0
    for m in re.finditer(r"<h3([^>]*)>(.*?)</h3>", html, re.S):
        attrs, name = m.group(1), re.sub(r"<[^>]+>", "", m.group(2)).strip()
        if not name:
            continue
        explicit_id = re.search(r'id="([^"]+)"', attrs)
        # the block for this person runs to the next <h3> or <h2>
        nxt = re.search(r"<h[23][^>]*>", html[m.end():])
        block = html[m.end(): m.end() + (nxt.start() if nxt else len(html))]
        img = re.search(r'<figure>\s*<img src="([^"]+)"([^>]*)/?>\s*</figure>', block)
        contacts = []
        cm = re.search(r'<div class="[^"]*\bcontact\b[^"]*">(.*?)</div>', block, re.S)
        if cm:
            for a in re.finditer(r'<a href="([^"]+)"[^>]*class="([^"]+)"[^>]*>(.*?)</a>',
                                 cm.group(1), re.S):
                contacts.append({"kind": a.group(2).strip(), "href": a.group(1),
                                 "label": re.sub(r"<[^>]+>", "", a.group(3)).strip()})
        order += 1
        people.append({
            "person": slug(name),
            "display_name": name,
            "anchor_id": explicit_id.group(1) if explicit_id else None,
            "tier": tier_at(m.start()),
            "order": order,
            "positions": [x.strip() for x in grab_all(block, "position")],
            "portrait": img.group(1) if img else None,
            # verbatim: the tail differs per entry ("/" vs ' class="pull-left"/')
            "portrait_attrs": img.group(2) if img else None,
            "contacts": contacts,
            "description_html": grab(block, "description", strip=False),
        })

    for p in people:
        (OUT / f"{p['person']}.yaml").write_text(
            yaml.safe_dump(p, sort_keys=False, allow_unicode=True, width=100))
    tiers_seen = {}
    for p in people:
        tiers_seen[p["tier"]] = tiers_seen.get(p["tier"], 0) + 1
    print(f"{len(people)} people -> {OUT.relative_to(HERE)}/")
    for t, n in tiers_seen.items():
        print(f"  {t}: {n}")
    missing = [p["display_name"] for p in people if not p["description_html"]]
    if missing:
        print(f"  no description: {missing}")


if __name__ == "__main__":
    main()
