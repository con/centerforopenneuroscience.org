#!/usr/bin/env python3
"""Render content/pages/projects.html from con-site-specific's records.

Keeps the page's own six sections -- Software, Initiatives, Meetings,
Standards, Education, Infrastructure -- because that grouping already tells
infrastructure from standards, and adds Archives, because DANDI, EMBER and
OpenNeuro are archives rather than software and the page had nowhere to say
so.

Within a section, order is newest-first by the project's `started` date,
except that a few flagship projects lead their section regardless: a strictly
chronological Software list would open with con/tinuous and bury DataLad.
"""
import argparse
import html
import os
import pathlib
import re
import sys
import xml.etree.ElementTree as ET

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required")

HERE = pathlib.Path(__file__).resolve().parent.parent

# The record store.  It is a submodule of this repo, so the default needs no
# configuration; CON_RECORD_STORE overrides it for working against another
# checkout.  An absolute path baked into a script is not reproducible and not
# portable -- see STAMPED.
STORE_ROOT = pathlib.Path(os.environ.get("CON_RECORD_STORE",
                                         HERE / "sourcedata/con-site-specific"))
INTROS = HERE / "content/section-intros.yaml"
STORE = STORE_ROOT
RECORDS = STORE / "metadata/records"

SECTIONS = ["Software", "Archives", "Standards", "Initiatives", "Meetings",
            "Education", "Infrastructure"]
# projects that lead their section whatever their date says
LEAD = ["datalad", "dandi", "ember", "openneuro", "neurodebian", "pymvpa"]
# records whose section the page did not assign, or which move to Archives
SECTION_OVERRIDE = {"dandi": "Archives", "ember": "Archives",
                    "openneuro": "Archives"}


def attrs(d, pred):
    return [a["value"] for a in (d.get("attributes") or [])
            if a.get("predicate") == pred]


def one(d, pred):
    v = attrs(d, pred)
    return v[0] if v else None


def load():
    """Entries to render, and anything skipped for a reason worth hearing.

    A silent skip here deletes a project from the Center's website: a typo in
    `dlthings:section`, or a missing description, and the entry just is not
    there, with exit code 0.  Skips are therefore collected and reported, and
    a skip that looks like a mistake makes the run fail.
    """
    out, skipped = [], []
    for cls in ("XYZProject", "XYZInstrument", "XYZOrganization"):
        for f in sorted((RECORDS / cls).glob("*.yaml")):
            d = yaml.safe_load(f.read_text())
            sec = SECTION_OVERRIDE.get(f.stem) or one(d, "dlthings:section")
            has_desc = bool(one(d, "dlthings:description_html"))
            if sec is None and not has_desc:
                continue                 # not a page entry at all; fine
            if not has_desc:
                skipped.append((f.stem, f"section {sec!r} but no description"))
                continue
            if sec not in SECTIONS:
                skipped.append((f.stem, f"section {sec!r} is not one of {SECTIONS}"))
                continue
            out.append({"slug": f.stem, "d": d, "section": sec,
                        "started": (d.get("started") or {}).get("at_time")})
    return out, skipped


def logo_for(slug):
    for sub in ("projects", "instruments", "organizations"):
        p = STORE / "content" / sub / slug
        for q in sorted(p.glob("logo.*")):
            return f"/theme/img/{sub}/{slug}/{q.name}"
    return None


def render():
    rows, skipped = load()
    intros = (yaml.safe_load(INTROS.read_text()) or {}).get("projects", {}) \
        if INTROS.exists() else {}
    out = ['<html>', '', '<head>', '\t<title>Projects</title>',
           '\t<meta name="url" content="projects" />',
           '\t<meta name="save_as" content="projects.html" />',
           '\t<meta name="show_in_top_menu" content="true" />',
           '\t<meta name="order" content="3" />',
           '\t<meta name="top_menu_name" content="Projects" />',
           '\t<meta name="show_as_selected" content="projects" />',
           '\t<meta name="table_of_contents" content="true" />',
           '\t<meta name="description" content="Projects of the center" />',
           '\t<meta name="author" content="CON" />',
           '\t<!-- GENERATED from con-site-specific by scripts/render_projects.py',
           '\t     Edit the records, not this file. -->',
           '</head>', '', '<body>', '  <section>']

    for sec in SECTIONS:
        group = [r for r in rows if r["section"] == sec]
        if not group:
            continue
        # flagships first in their listed order, then newest-first by date,
        # then undated (an unknown date is not a recent one)
        # Two passes rather than one clever key: sort newest-first, then
        # stable-sort the flagships to the front.  A single key that negated
        # the date per character compared elementwise, so "2020" sorted
        # before "2020-01-15" -- ascending, for any pair where one date
        # prefixes the other.
        group.sort(key=lambda r: (r["started"] is None, r["started"] or ""),
                   reverse=False)
        group.sort(key=lambda r: (r["started"] is None,
                                  "" if r["started"] is None else r["started"]),
                   reverse=True)
        group.sort(key=lambda r: r["started"] is None)
        group.sort(key=lambda r: LEAD.index(r["slug"]) if r["slug"] in LEAD
                   else len(LEAD))
        out.append(f'\t<h1>{html.escape(sec)}</h1>')
        if intros.get(sec):
            out.append(f'\t  {intros[sec].strip()}')
        for r in group:
            d = r["d"]
            name = d.get("display_label") or d.get("title") or r["slug"]
            anchor = one(d, "dlthings:anchor") or r["slug"]
            home = one(d, "foaf:homepage")
            out.append('\t  <div class="row">')
            out.append(f'\t\t<h2 id="{html.escape(anchor)}">{html.escape(name)}</h2>')
            logo = logo_for(r["slug"])
            if logo:
                style = one(d, "dlthings:logo_style") or \
                    "width:255px;padding-left:5px;margin-top:-2em;"
                a_open = f'<a href="{html.escape(home)}">' if home else ""
                a_close = "</a>" if home else ""
                out.append('\t\t<figure>')
                out.append(f'\t\t  {a_open}<img src="{logo}" '
                           f'alt="{html.escape(name)}" class="pull-right" '
                           f'style="{html.escape(style)}" />{a_close}')
                out.append('\t\t</figure>')
            out.append(f'\t\t{one(d, "dlthings:description_html")}')
            out.append('\t  </div>')
    out += ['  </section>', '</body>', '', '</html>', '']
    return "\n".join(out), rows, skipped


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out")
    ap.add_argument("--show-order", action="store_true")
    a = ap.parse_args()
    markup, rows, skipped = render()
    for slug, why in skipped:
        print(f"SKIPPED {slug}: {why}", file=sys.stderr)
    if a.show_order:
        for sec in SECTIONS:
            g = [r for r in rows if r["section"] == sec]
            if not g:
                continue
            g.sort(key=lambda r: (r["started"] is None,
                                  "" if r["started"] is None else r["started"]),
                   reverse=True)
            g.sort(key=lambda r: r["started"] is None)
            g.sort(key=lambda r: LEAD.index(r["slug"]) if r["slug"] in LEAD
                   else len(LEAD))
            print(f"\n{sec} ({len(g)}):")
            for r in g:
                lead = " *" if r["slug"] in LEAD else "  "
                print(f"  {lead} {r['started'] or '(undated)':12s} {r['slug']}")
        return 0
    # The ToC extension parses the page with strict ElementTree and, on a
    # parse error, returns the content UNCHANGED -- so one malformed tag in
    # one record silently strips every anchor from the page while Pelican
    # still exits 0.  Catch it here instead.
    try:
        ET.fromstring("<root>" + re.sub(r"<!DOCTYPE[^>]*>", "", markup) + "</root>")
    except ET.ParseError as exc:
        print(f"REFUSING TO WRITE: the generated page is not well-formed "
              f"XML, which means the table-of-contents extension will "
              f"silently drop every anchor: {exc}", file=sys.stderr)
        return 2
    if a.out:
        pathlib.Path(a.out).write_text(markup)
        print(f"wrote {a.out}  ({len(markup.splitlines())} lines)")
    else:
        print(markup)
    return 2 if skipped else 0


if __name__ == "__main__":
    sys.exit(main())
