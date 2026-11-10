#!/usr/bin/env python3
"""Render content/pages/support.html from con-site-specific's records.

The page used to show one logo per funder, each linking to a single award.
The store knows every grant, its funder (the `marcrel:fnd` attribution), its
period and the projects it funds (the projects' `influenced_by` with the
`FRAPO:Funding` role), so each funder now gets the list of its grants.

The Center for Cognitive Neuroscience is institutional support, not a grant,
and has no record; its block is section copy in content/section-intros.yaml.
"""
import argparse
import html
import sys

from conrecords import INTROS, RECORDS, load_yaml, one, write_page
from render_whoweare import page_anchors

FUNDER = "marcrel:fnd"
FUNDING = "FRAPO:Funding"
# the funders' logos already in the theme; a funder without one gets its name
LOGOS = {"ror:01cwqze88": "/theme/img/3rd/nih-logo.png",
         "ror:021nxhr62": "/theme/img/3rd/nsf-logo.gif"}
# an award page that the identifier alone determines
AWARD_URL = {"ror:021nxhr62": "https://www.nsf.gov/awardsearch/showAward?AWD_ID={}"}


def funded_projects(anchors):
    """grant pid -> [(label, href or None), ...]."""
    out = {}
    for f in sorted((RECORDS / "XYZProject").glob("*.yaml")):
        d = load_yaml(f)
        label = d.get("short_name") or d.get("display_label") or d.get("title") or f.stem
        href = anchors.get(d["pid"]) or one(d, "foaf:homepage")
        for inf in d.get("influenced_by") or []:
            if FUNDING in (inf.get("roles") or []):
                out.setdefault(inf["object"], []).append((label, href))
    return {k: sorted(v, key=lambda r: r[0].lower()) for k, v in out.items()}


def period(g):
    start = ((g.get("generated_by") or {}).get("at_time") or "")[:4]
    end = ((g.get("invalidated_by") or {}).get("at_time") or "")[:4]
    return f"{start}&#8211;{end}" if start and end else start


def link(label, href):
    label = html.escape(label)
    return f'<a href="{html.escape(href)}">{label}</a>' if href else label


def link_html(inner, href):
    """Like link(), for markup that is already escaped."""
    return f'<a href="{html.escape(href)}">{inner}</a>' if href else inner


def render():
    funders = {}
    for f in sorted((RECORDS / "XYZOrganization").glob("*.yaml")):
        d = load_yaml(f)
        funders[d["pid"]] = d
    grants, skipped = {}, []
    for f in sorted((RECORDS / "XYZGrant").glob("*.yaml")):
        g = load_yaml(f)
        who = [a["object"] for a in g.get("attributed_to") or []
               if FUNDER in (a.get("roles") or [])]
        if not who or who[0] not in funders:
            skipped.append((f.stem, f"no known funder ({who})"))
            continue
        grants.setdefault(who[0], []).append(g)
    funds = funded_projects(page_anchors())
    intros = (load_yaml(INTROS) if INTROS.exists() else {}).get("support", {})

    out = ['<html>', '', '<head>', '    <title>Support</title>',
           '    <meta name="url" content="support" />',
           '    <meta name="save_as" content="support.html" />',
           '    <meta name="show_in_top_menu" content="true" />',
           '    <meta name="order" content="5" />',
           '    <meta name="top_menu_name" content="Support" />',
           '    <meta name="show_as_selected" content="support" />',
           '    <meta name="table_of_contents" content="false" />',
           '    <meta name="description" content="Our supporters" />',
           '    <meta name="author" content="CON" />',
           '    <!-- GENERATED from con-site-specific by scripts/render_support.py',
           '         Edit the records, not this file. -->',
           '</head>', '', '<body>', '  <section>',
           '\t<p>Support for the center and its projects is provided by</p>']
    if intros.get("Institutional"):
        out.append(intros["Institutional"].rstrip())
    # the funder with the most grants first
    for pid in sorted(grants, key=lambda p: (-len(grants[p]), p)):
        d = funders[pid]
        name = d.get("name") or d.get("display_label")
        logo = LOGOS.get(pid)
        head = (f'<img src="{logo}" alt="{html.escape(name)}" />' if logo
                else html.escape(d.get("display_label") or name))
        out += ['\t<div class="funder">',
                f'\t  <h2>{link_html(head, one(d, "foaf:homepage"))}</h2>',
                '\t  <ul class="grants">']
        # newest first; an undated grant last
        for g in sorted(grants[pid], key=lambda g: ((g.get("generated_by") or {})
                                                    .get("at_time") or ""), reverse=True):
            ident = next((i["notation"] for i in g.get("identifiers") or []), None)
            url = one(g, "foaf:homepage") or (
                AWARD_URL[pid].format(ident) if ident and pid in AWARD_URL else None)
            bits = [f'<span class="grant-title">{link(g["title"], url)}</span>']
            meta = ", ".join(x for x in (html.escape(ident) if ident else None,
                                         period(g)) if x)
            if meta:
                bits.append(f'<span class="grant-meta">{meta}</span>')
            if funds.get(g["pid"]):
                bits.append('<span class="grant-projects">Funds: '
                            + ", ".join(link(*p) for p in funds[g["pid"]]) + '</span>')
            out.append('\t\t<li>' + ' '.join(bits) + '</li>')
        out += ['\t  </ul>', '\t</div>']
    out += ['  </section>', '</body>', '', '</html>']
    return "\n".join(out) + "\n", skipped


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out")
    a = ap.parse_args()
    markup, skipped = render()
    for slug, why in skipped:
        print(f"SKIPPED {slug}: {why}", file=sys.stderr)
    return write_page(markup, a.out, skipped)


if __name__ == "__main__":
    sys.exit(main())
