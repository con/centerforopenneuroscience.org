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

With --json, theme/static/data/publications.json: the same entries, and the
projects and people they name, for theme/static/js/publications.js to search
and filter in the browser -- the whole publications page, and the lists that
open under a project on the projects page and a person on whoweare.  The
HTML page keeps the plain lists as what a reader without JavaScript gets.
"""
import argparse
import html
import json
import pathlib
import sys

from conrecords import (
    RECORDS,
    TIERS,
    load_yaml,
    one,
    person_name,
    project_objectives,
    publication_date,
    publication_objectives,
    publication_projects,
    publication_type,
    publication_url,
    publications,
    toc_hook,
    write_page,
)
from render_objectives import objectives as current_objectives
from render_whoweare import page_anchors

# the slides themselves, which this page's talks link into
TALKS_SITE = "https://datasets.datalad.org/centerforopenneuroscience/talks/"

SECTIONS = ["Papers and reports", "Posters", "Talks"]
# section -> the `type` a filter takes, publication_type()'s
TYPE = {"Papers and reports": "paper", "Posters": "poster", "Talks": "talk"}


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


def slug(pid):
    """`xyzrins:persons/jane-doe` -> `jane-doe`: what a filter is given."""
    return pid.rsplit("/", 1)[-1]


def authors(d, by_pid, by_name):
    """[(name, href or None), ...], and whether that is the full list."""
    full = one(d, "bibo:authorList")
    if full:
        return [(n.strip(), by_name.get(n.strip()))
                for n in full.split(";") if n.strip()], True
    seen, out = set(), []
    for a in d.get("attributed_to") or []:
        who = a.get("object")
        if who in by_pid and who not in seen:
            seen.add(who)
            out.append(by_pid[who])
    return out, False


def model():
    """Everything both outputs show: the entries, newest first, and the
    projects and people they name, keyed by the slugs a filter takes."""
    by_pid, by_name = people()
    projs = projects()
    by_project = project_objectives()
    # the objectives the site shows, in its order, linked to their sections
    objs = {d["pid"]: (d["title"], "/objectives#" + toc_hook(d["title"]))
            for d in current_objectives()[0]}
    entries, used_projects, used_people = [], {}, {}
    for d in publications():
        names, complete = authors(d, by_pid, by_name)
        mine = sorted((p for p in publication_projects(d) if p in projs),
                      key=lambda p: projs[p][0].lower())
        who = []
        for a in d.get("attributed_to") or []:
            pid = a.get("object")
            if pid in by_pid and slug(pid) not in who:
                who.append(slug(pid))
                used_people[slug(pid)] = by_pid[pid]
        for p in mine:
            used_projects[slug(p)] = projs[p]
        date = publication_date(d) or ""
        entries.append({
            "title": d["title"], "url": publication_url(d),
            "date": date, "year": date[:4], "type": publication_type(d),
            "venue": one(d, "bibo:presentedAt"),
            "authors": names, "authors_complete": complete,
            "projects": [slug(p) for p in mine], "people": who,
            "objectives": [slug(o) for o in publication_objectives(d, by_project)
                           if o in objs],
            "pdf": one(d, "dcat:downloadURL"), "video": one(d, "schema:video")})
    return {"types": {TYPE[s]: s for s in SECTIONS},
            "projects": dict(sorted(used_projects.items())),
            "people": dict(sorted(used_people.items())),
            "objectives": {slug(o): v for o, v in objs.items()},
            "publications": entries}


def alts(e):
    """"(PDF) (📺 CONTube)" after the title, as the Talks site has them."""
    out = []
    if e["pdf"]:
        out.append(("PDF", e["pdf"]))
    if e["video"]:
        out.append(("\U0001F4FA " + ("CONTube" if "contube" in e["video"].lower()
                                       else "video"), e["video"]))
    return "".join(f' (<a class="pub-alt" href="{html.escape(h)}">{html.escape(t)}</a>)'
                   for t, h in out)


def entry(e, projs):
    bits = [f'<span class="pub-title">{link(e["title"], e["url"])}{alts(e)}</span>']
    names = ", ".join(link(*a) for a in e["authors"])
    if names and not e["authors_complete"]:
        names = "Authors include " + names
    meta = [m for m in (names, html.escape(e["venue"] or ""), e["year"]) if m]
    if meta:
        bits.append(f'<span class="pub-meta">{" &#183; ".join(meta)}</span>')
    if e["projects"]:
        bits.append('<span class="pub-projects">Projects: '
                    + ", ".join(link(*projs[p]) for p in e["projects"]) + '</span>')
    return '\t\t<li>' + ' '.join(bits) + '</li>'


def render():
    m = model()
    out = ['<html>', '', '<head>', '\t<title>Publications</title>',
           '\t<meta name="url" content="publications" />',
           '\t<meta name="save_as" content="publications.html" />',
           # in the menu where the external Talks link was
           '\t<meta name="show_in_top_menu" content="true" />',
           '\t<meta name="order" content="6" />',
           '\t<meta name="show_as_selected" content="publications" />',
           # the filters replace the sidebar: a type filter is its sections
           '\t<meta name="table_of_contents" content="false" />',
           '\t<meta name="description" content="Papers, posters and talks, '
           'and the projects behind them" />',
           '\t<meta name="author" content="CON" />',
           '\t<!-- GENERATED from con-site-specific by scripts/render_publications.py',
           '\t     Edit the records, not this file. -->',
           '</head>', '', '<body>', '  <section>',
           f'\t<p class="pub-intro">Slides of our talks are also collected on our '
           f'<a href="{TALKS_SITE}">Talks site</a>.  For '
           f'<a href="/whoweare#{toc_hook("Affiliated Faculty")}">affiliated faculty</a> and '
           'collaborators, only their works joint with CON members are listed.</p>',
           # publications.js replaces the lists below with the filterable
           # view of the same records; without JavaScript they are the page
           '  <div id="publications" data-pub-app="">']
    for sec in SECTIONS:
        mine = [e for e in m["publications"] if e["type"] == TYPE[sec]]
        if not mine:
            continue
        out += [f'\t<h2>{html.escape(sec)}</h2>', '\t<ul class="publication-list">']
        out += [entry(e, m["projects"]) for e in mine]
        out.append('\t</ul>')
    out += ['  </div>', '  </section>', '</body>', '', '</html>']
    return "\n".join(out) + "\n", []


def render_json():
    """The records publications.js filters, fetched once per browser session."""
    return json.dumps(model(), indent=1, ensure_ascii=False) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out")
    ap.add_argument("--json", action="store_true",
                    help="write the records as JSON for publications.js instead")
    a = ap.parse_args()
    if a.json:
        text = render_json()
        if a.out:
            pathlib.Path(a.out).write_text(text)
            print(f"wrote {a.out}")
        else:
            print(text, end="")
        return 0
    markup, skipped = render()
    return write_page(markup, a.out, skipped)


if __name__ == "__main__":
    sys.exit(main())
