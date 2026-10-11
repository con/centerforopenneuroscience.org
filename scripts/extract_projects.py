#!/usr/bin/env python3
"""Extract content/pages/projects.html (and the Partners block of
whoweare.html) into per-project records.

Unlike the people entries, project bodies are free prose: paragraphs with
inline citations, nested <ul>s, per-project logo styling.  Trying to
decompose that into fields would lose content, so the body is kept verbatim
and the *structured* parts are derived alongside it:

    body_html          verbatim, so the page regenerates byte-identically
    logo               parsed out, for the slide and for ORINOCO-Lite
    people_referenced  anchors this project links to on /whoweare

INCF and NITRC live in whoweare.html's Partners block rather than
projects.html, and are parked inside HTML comments there -- they are
projects, not people, and are picked up here.
"""
import pathlib
import re
import sys

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required")

HERE = pathlib.Path(__file__).resolve().parent.parent
PROJECTS = HERE / "content/pages/projects.html"
WHOWEARE = HERE / "content/pages/whoweare.html"
OUT = HERE / "content/projects"


def slug(name):
    kept = "".join(c if (c.isalnum() or c.isspace()) else " " for c in name.lower())
    return "-".join(kept.split())


def balanced_row(html, pos):
    """The <div class="row"> enclosing `pos`, to its MATCHING </div>.

    Project bodies contain nested divs, so taking the last </div> before the
    next heading silently truncates or over-runs the row.  This walks the
    div tags keeping a depth count instead.
    """
    start = html.rfind('<div class="row">', 0, pos)
    if start < 0:
        return None, None
    depth, i = 0, start
    for m in re.finditer(r"<div\b[^>]*>|</div>", html[start:]):
        i = start + m.end()
        depth += 1 if m.group(0).startswith("<div") else -1
        if depth == 0:
            return start, i
    return start, None


def parse_logo(body):
    m = re.search(r'<figure>\s*(?:<a href="([^"]+)">\s*)?<img ([^>]*?)/?>\s*(?:</a>)?\s*</figure>',
                  body, re.S)
    if not m:
        return None
    attrs = dict(re.findall(r'(\w[\w-]*)="([^"]*)"', m.group(2)))
    return {"href": m.group(1), "src": attrs.get("src"), "alt": attrs.get("alt"),
            "class": attrs.get("class"), "style": attrs.get("style")}


def main():
    html = PROJECTS.read_text()
    sections = [(m.start(), re.sub(r"<[^>]+>", "", m.group(1)).strip(), m.group(0))
                for m in re.finditer(r"<h1[^>]*>(.*?)</h1>", html, re.S)]

    def section_at(pos):
        cur = None
        for start, label, raw in sections:
            if start < pos:
                cur = (label, raw)
        return cur or (None, None)

    # prose can sit directly under an <h1>, outside any row -- the Meetings
    # section opens with a paragraph about CON's annual exhibits
    intros = {}
    for idx, (start, label, raw) in enumerate(sections):
        after = start + len(raw)
        nxt = html.find('<div class="row">', after)
        nxt_h1 = sections[idx + 1][0] if idx + 1 < len(sections) else len(html)
        stop = min(x for x in (nxt if nxt >= 0 else len(html), nxt_h1))
        intro = html[after:stop]
        intros[label] = intro if intro.strip() else None

    OUT.mkdir(parents=True, exist_ok=True)
    recs, order, seen_anchor = [], 0, {}
    heads = list(re.finditer(r"<h2([^>]*)>(.*?)</h2>", html, re.S))
    for i, m in enumerate(heads):
        attrs, name = m.group(1), re.sub(r"<[^>]+>", "", m.group(2)).strip()
        anchor = (re.search(r'id="([^"]+)"', attrs) or [None, None])[1]
        rs, re_ = balanced_row(html, m.start())
        row_html = html[rs:re_] if rs is not None and re_ else None
        body = html[m.end():re_ - len("</div>")] if re_ else ""
        order += 1
        if anchor:
            seen_anchor[anchor] = seen_anchor.get(anchor, 0) + 1
        recs.append({
            "project": slug(name),
            "display_name": name,
            "anchor_id": anchor,
            "anchor_duplicated": None,     # filled in below
            "section": section_at(m.start())[0],
            "section_html": section_at(m.start())[1],
            "section_intro_html": intros.get(section_at(m.start())[0]),
            "order": order,
            "source_page": "projects",
            "logo": parse_logo(body),
            "people_referenced": sorted(set(re.findall(r'href="/whoweare#([^"]+)"', body))),
            "body_html": body,
            "row_html": row_html,     # verbatim, for lossless regeneration
        })
    for r in recs:
        if r["anchor_id"]:
            r["anchor_duplicated"] = seen_anchor[r["anchor_id"]] > 1

    # Partners: projects parked in whoweare.html, headings inside comments
    w = WHOWEARE.read_text()
    pm = re.search(r"<h2>Partners</h2>(.*?)</div>", w, re.S)
    if pm:
        blk = pm.group(1)
        names = re.findall(r"<!--\s*<h3>(.*?)</h3>\s*-->", blk)
        links = re.findall(r'<a href="([^"]+)"><img src="([^"]+)"([^>]*?)/?></a>', blk)
        for n, (href, src, rest) in zip(names, links):
            order += 1
            attrs = dict(re.findall(r'(\w[\w-]*)="([^"]*)"', rest))
            recs.append({
                "project": slug(n), "display_name": n.strip(), "anchor_id": None,
                "anchor_duplicated": False, "section": "Partners", "order": order,
                "source_page": "whoweare",
                "logo": {"href": href, "src": src, "alt": attrs.get("alt"),
                         "class": attrs.get("class"), "style": attrs.get("style")},
                "people_referenced": [], "body_html": None, "row_html": None,
            })

    # The "Collaborating projects" block of whoweare.html: 38 logo links plus
    # two deliberately icon-less text links.  This is the richest source of
    # collaborating-project data on the site and was previously extracted by
    # nothing at all -- it sits outside both round-trip windows.
    cp = re.search(r'<h2>Collaborating projects</h2>(.*?)(?=<div id="people">)', w, re.S)
    if cp:
        blk = cp.group(1)
        for m2 in re.finditer(
                r'<a href="([^"]+)">(?:<img ([^>]*?)/?>)?([^<]*)</a>', blk):
            href, imgattrs, text = m2.group(1), m2.group(2), (m2.group(3) or "").strip()
            attrs = dict(re.findall(r'(\w[\w-]*)="([^"]*)"', imgattrs or ""))
            name = attrs.get("alt") or text
            if not name:
                continue
            order += 1
            recs.append({
                "project": slug(name), "display_name": name, "anchor_id": None,
                "anchor_duplicated": False, "section": "Collaborating projects",
                "order": order, "source_page": "whoweare",
                "logo": {"href": href, "src": attrs.get("src"),
                         "alt": attrs.get("alt"),
                         # title differs from alt for OpenSesame and Psychtoolbox
                         "title": attrs.get("title"),
                         "class": attrs.get("class"), "style": attrs.get("style")},
                "icon_less": not imgattrs,   # patsy and seaborn, per the page's
                                             # own "if no icon could be found"
                "people_referenced": [], "body_html": None, "row_html": None,
            })

    for r in recs:
        (OUT / f"{r['project']}.yaml").write_text(
            yaml.safe_dump(r, sort_keys=False, allow_unicode=True, width=100))
    by_section = {}
    for r in recs:
        by_section[r["section"]] = by_section.get(r["section"], 0) + 1
    print(f"{len(recs)} projects -> {OUT.relative_to(HERE)}/")
    for s, n in by_section.items():
        print(f"  {s}: {n}")
    dup = sorted({r["anchor_id"] for r in recs if r["anchor_duplicated"]})
    if dup:
        print(f"  duplicate anchors (page bug, flagged not fixed): {dup}")
    noanchor = [r["display_name"] for r in recs
                if not r["anchor_id"] and r["source_page"] == "projects"]
    if noanchor:
        print(f"  no id attribute ({len(noanchor)}): {noanchor}")


if __name__ == "__main__":
    main()
