#!/usr/bin/env python3
"""Render content/pages/publications.html from con-site-specific's records.

Every XYZPublication, in three lists -- papers and reports, posters, talks --
newest first.  Each entry names its authors (people with an entry on whoweare
link there), links its title to its own page or DOI, and names the projects
that produced it: the record's `generated_by`, the same relation the projects
page reads to list a project's publications.

A record names only the authors who have person records, unless it carries
the full `bibo:authorList`.  Without the full list the entry says "Authors
include", so a paper with thirty authors does not read as written by the two
the store knows.
"""
import argparse
import html
import sys

from conrecords import (
    RECORDS,
    TIERS,
    load_yaml,
    one,
    person_name,
    publication_date,
    publication_projects,
    publication_url,
    publications,
    toc_hook,
    write_page,
)
from render_whoweare import page_anchors

# the slides themselves, which this page's talks link into
TALKS_SITE = "https://datasets.datalad.org/centerforopenneuroscience/talks/"

# section -> the record kinds it holds; anything else is a paper
POSTERS = {"fabio:ConferencePoster"}
TALKS = {"bibo:Slideshow"}
SECTIONS = ["Papers and reports", "Posters", "Talks"]


def section_of(d):
    return ("Posters" if d.get("kind") in POSTERS
            else "Talks" if d.get("kind") in TALKS else "Papers and reports")


def people():
    """person pid -> (name, href or None), and name -> href for author lists."""
    by_pid, by_name = {}, {}
    for f in sorted((RECORDS / "XYZPerson").glob("*.yaml")):
        d = load_yaml(f)
        name = person_name(d)
        href = ("/whoweare#" + toc_hook(name)
                if one(d, "dlthings:tier") in TIERS else None)
        by_pid[d["pid"]] = (name, href)
        for n in {name, f'{d.get("given_name")} {d.get("family_name")}'}:
            by_name[n] = href
    return by_pid, by_name


def projects():
    """project pid -> (label, href or None)."""
    anchors, out = page_anchors(), {}
    for f in sorted((RECORDS / "XYZProject").glob("*.yaml")):
        d = load_yaml(f)
        label = d.get("short_name") or d.get("display_label") or d.get("title") or f.stem
        out[d["pid"]] = (label, anchors.get(d["pid"]) or one(d, "foaf:homepage"))
    return out


def link(label, href):
    label = html.escape(label)
    return f'<a href="{html.escape(href)}">{label}</a>' if href else label


def authors(d, by_pid, by_name):
    full = one(d, "bibo:authorList")
    if full:
        return [link(n.strip(), by_name.get(n.strip()))
                for n in full.split(";") if n.strip()]
    seen, out = set(), []
    for a in d.get("attributed_to") or []:
        who = a.get("object")
        if who in by_pid and who not in seen:
            seen.add(who)
            out.append(link(*by_pid[who]))
    return out


def entry(d, by_pid, by_name, projs):
    bits = [f'<span class="pub-title">{link(d["title"], publication_url(d))}</span>']
    names = ", ".join(authors(d, by_pid, by_name))
    if names and not one(d, "bibo:authorList"):
        names = "Authors include " + names
    meta = [names,
            html.escape(one(d, "bibo:presentedAt") or ""),
            (publication_date(d) or "")[:4]]
    extra = [link(label, one(d, pred)) for label, pred in
             (("PDF", "dcat:downloadURL"), ("video", "schema:video")) if one(d, pred)]
    meta = [m for m in meta if m] + extra
    if meta:
        bits.append(f'<span class="pub-meta">{" &#183; ".join(meta)}</span>')
    mine = sorted((projs[p] for p in publication_projects(d) if p in projs),
                  key=lambda r: r[0].lower())
    if mine:
        bits.append('<span class="pub-projects">Projects: '
                    + ", ".join(link(*p) for p in mine) + '</span>')
    return '\t\t<li>' + ' '.join(bits) + '</li>'


def render():
    by_pid, by_name = people()
    projs = projects()
    rows = publications()
    out = ['<html>', '', '<head>', '\t<title>Publications</title>',
           '\t<meta name="url" content="publications" />',
           '\t<meta name="save_as" content="publications.html" />',
           # in the menu where the external Talks link was
           '\t<meta name="show_in_top_menu" content="true" />',
           '\t<meta name="order" content="6" />',
           '\t<meta name="show_as_selected" content="publications" />',
           '\t<meta name="table_of_contents" content="true" />',
           '\t<meta name="description" content="Papers, posters and talks, '
           'and the projects behind them" />',
           '\t<meta name="author" content="CON" />',
           '\t<!-- GENERATED from con-site-specific by scripts/render_publications.py',
           '\t     Edit the records, not this file. -->',
           '</head>', '', '<body>', '  <section>', '  <div id="publications">']
    for sec in SECTIONS:
        mine = [d for d in rows if section_of(d) == sec]
        if not mine:
            continue
        out.append(f'\t<h1>{html.escape(sec)}</h1>')
        if sec == "Talks":
            out.append(f'\t<p>Slides of these and other talks are also collected '
                       f'on our <a href="{TALKS_SITE}">Talks site</a>.</p>')
        out.append('\t<ul class="publication-list">')
        out += [entry(d, by_pid, by_name, projs) for d in mine]
        out.append('\t</ul>')
    out += ['  </div>', '  </section>', '</body>', '', '</html>']
    return "\n".join(out) + "\n", []


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out")
    a = ap.parse_args()
    markup, skipped = render()
    return write_page(markup, a.out, skipped)


if __name__ == "__main__":
    sys.exit(main())
