#!/usr/bin/env python3
"""Render content/pages/whoweare.html from con-site-specific's records.

Ordering, which is the point of the exercise: every tier is sorted by when
the person joined CON -- the `started` date on their association with the
site-root project, derived from this repo's own git history -- and Emeritus
by when they left.  Previously only Centroids had a deliberate order and the
rest were whatever the file happened to say.

People with no date sort last within their tier rather than first, because an
unknown date is not an early one.  YOH is the exception and is pinned to the
top of Centroids: he predates the website, so his association is deliberately
undated (see the curation evidence), and sorting him last would be absurd.
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
STORE = STORE_ROOT
RECORDS = STORE / "metadata/records"
INTROS = HERE / "content/section-intros.yaml"
TIERS = ["Centroids", "Collaborators", "Affiliated Faculty", "Emeritus"]
# contact predicate -> (css class, link text); order fixes the link order
CONTACTS = [
    ("vcard:hasEmail", "email", "E-Mail"),
    ("vcard:hasTelephone", "phone", None),
    ("foaf:homepage", "research", "Research Page"),
    ("dlthings:home_page", "home", "Home Page"),
    ("vcard:hasURL", "cv", "CV"),
    ("foaf:account", "account", None),
    ("dlthings:github", "github", "GitHub"),
    ("dlthings:orcid", "orcid", "ORCID"),
    ("foaf:weblog", "blog", "Blog"),
    ("dlthings:scholar", "scholar", "Google Scholar"),
]
ACCOUNT_CLASS = {"plus.google.com": ("googleplus", "Google+"),
                 "twitter.com": ("twitter", "Twitter"),
                 "x.com": ("twitter", "Twitter"),
                 "fosstodon.org": ("mastodon", "Mastodon"),
                 "mastodon": ("mastodon", "Mastodon"),
                 "facebook.com": ("facebook", "FaceBook"),
                 "linkedin.com": ("linkedin", "LinkedIn"),
                 "bsky.app": ("bluesky", "Bluesky")}


def attrs(d, pred):
    return [a["value"] for a in (d.get("attributes") or [])
            if a.get("predicate") == pred]


def one(d, pred):
    v = attrs(d, pred)
    return v[0] if v else None


def load_people():
    out = {}
    for f in sorted((RECORDS / "XYZPerson").glob("*.yaml")):
        d = yaml.safe_load(f.read_text())
        out[d["pid"]] = (f.stem, d)
    return out


def joined():
    """pid -> (started, ended) from the site-root associations."""
    d = yaml.safe_load((RECORDS / "XYZProject" / "site-root.yaml").read_text())
    return {a["object"]: ((a.get("started") or {}).get("at_time"),
                          (a.get("ended") or {}).get("at_time"))
            for a in d.get("associated_with", []) if a.get("object")}


def portrait(slug):
    """Theme path for a person's portrait.

    The file is `persons/<slug>/portrait.ext` in the record store and lands
    in the theme as `team/<slug>.ext` -- an earlier version returned
    `team/portrait.ext`, dropping the slug, which made every portrait point
    at the same non-existent file.
    """
    for p in sorted((STORE / "content/persons" / slug).glob("portrait.*")):
        return f"/theme/img/team/{slug}{p.suffix.lower()}"
    return None


def contact_links(d):
    out, seen_classes = [], set()
    for pred, cls, label in CONTACTS:
        for v in attrs(d, pred):
            c, text = cls, label
            if pred == "foaf:account":
                c, text = next(((k2, t) for host, (k2, t) in ACCOUNT_CLASS.items()
                                if host in v), ("web", "Web"))
            if pred == "vcard:hasTelephone":
                text = v.replace("tel:", "")
            # `research` and `home` both land on foaf:homepage, so the same
            # URL could be emitted twice with the same icon
            # A "research page" pointing at this very page is not a link.
            if v.rstrip("/").endswith("centerforopenneuroscience.org/whoweare"):
                continue
            # Dedupe by the rendered CLASS, not the URL.  `research`, `home`
            # and `web` all land on foaf:homepage and all render as the same
            # icon, so two different URLs still produce two identical-looking
            # icons side by side -- which is what YOH's entry showed.
            if c in seen_classes and c in ("research", "email", "github",
                                           "orcid", "cv", "phone", "scholar"):
                continue
            seen_classes.add(c)
            out.append(f'<a href="{html.escape(v)}" class="{c}">'
                       f'{html.escape(text or v)}</a>')
    return out


def render():
    people, dates = load_people(), joined()
    rows, skipped = [], []
    for pid, (slug, d) in people.items():
        tier = one(d, "dlthings:tier")
        if tier is None:
            continue                     # not a website person; fine
        if tier not in TIERS:
            # A typo in one field would otherwise delete a person from the
            # Center's website with exit code 0.
            skipped.append((slug, f"tier {tier!r} is not one of {TIERS}"))
            continue
        start, end = dates.get(pid, (None, None))
        rows.append({"pid": pid, "slug": slug, "d": d, "tier": tier,
                     "start": start, "end": end})

    out = ['<html>', '', '<head>', '\t<title>Who we are</title>',
           '\t<meta name="url" content="whoweare" />',
           '\t<meta name="save_as" content="whoweare.html" />',
           '\t<meta name="show_in_top_menu" content="true" />',
           '\t<meta name="order" content="2" />',
           '\t<meta name="top_menu_name" content="Who we are" />',
           '\t<meta name="show_as_selected" content="whoweare" />',
           '\t<meta name="table_of_contents" content="true" />',
           '\t<meta name="description" content="People of the center" />',
           '\t<meta name="author" content="CON" />',
           '\t<!-- GENERATED from con-site-specific by scripts/render_whoweare.py',
           '\t     Edit the records, not this file. -->',
           '</head>', '', '<body>', '  <section>', '  <div id="people">']

    for tier in TIERS:
        group = [r for r in rows if r["tier"] == tier]
        if not group:
            continue
        key = "end" if tier == "Emeritus" else "start"
        # undated sorts last; YOH predates the site and is pinned first
        group.sort(key=lambda r: (r["pid"] != "xyzrins:persons/yaroslav-halchenko"
                                  if tier == "Centroids" else 0,
                                  r[key] is None, r[key] or ""))
        out.append(f'\t<h2>{html.escape(tier)}</h2>')
        for r in group:
            d = r["d"]
            # the page's own spelling, parentheticals and all
            name = d.get("display_label") or one(d, "dlthings:formatted_name")
            out.append('\t  <div class="row">')
            out.append(f'\t\t<h3>{html.escape(name)}</h3>')
            pic = portrait(r["slug"])
            if pic:
                out.append(f'\t\t<figure><img src="{pic}" class="pull-left"/></figure>')
            for pos in attrs(d, "dlthings:position"):
                # a position may carry markup: Haxby's second one links to
                # his National Academy election.  Escaping it would print the
                # anchor instead of rendering it.
                body = pos if "<a " in pos else html.escape(pos)
                out.append(f'\t\t<div class="col-md-4 col-sm-4 position">'
                           f'{body}</div>')
            links = contact_links(d)
            if links:
                out.append('\t\t<div class="col-md-5 col-sm-5 contact">')
                out += [f'\t\t  {l}' for l in links]
                out.append('\t\t</div>')
            # 25 of 33 descriptions link to projects, handbooks and papers.
            # The plain-text `description` drops those, so the marked-up form
            # is preferred and only falls back when there is none.
            rich = one(d, "dlthings:description_html")
            desc = rich or d.get("description")
            if desc:
                out.append('\t\t<div class="col-md-9 col-sm-9 description">')
                out.append(f'\t\t  {desc if rich else html.escape(desc)}')
                out.append('\t\t</div>')
            out.append('\t  </div>')
    # --- the logo strips the records also drive -------------------------
    # Collaborating projects are the ones with no `part_of: xyzrins:.` -- the
    # discriminator the part_of refactor established.  Partners are
    # organizations rather than projects.
    projects, partners = [], []
    for f in sorted((RECORDS / "XYZProject").glob("*.yaml")):
        pr = yaml.safe_load(f.read_text())
        if "xyzrins:." in (pr.get("part_of") or []) or pr["pid"] == "xyzrins:.":
            continue
        logo = next((q for q in sorted((STORE / "content/projects" / f.stem)
                                       .glob("logo.*"))), None)
        # patsy and seaborn have no logo and appear on the live page as plain
        # text links, so a missing logo is not a reason to drop the entry.
        projects.append((pr, f.stem, logo.name if logo else None))
    for slug in ("incf", "nitrc"):
        f = RECORDS / "XYZOrganization" / f"{slug}.yaml"
        if f.exists():
            org = yaml.safe_load(f.read_text())
            logo = next((q for q in sorted((STORE / "content/organizations" / slug)
                                           .glob("logo.*"))), None)
            partners.append((org, slug, logo.name if logo else None))

    intros = (yaml.safe_load(INTROS.read_text()) or {}).get("whoweare", {}) \
        if INTROS.exists() else {}
    for title, items, sub, div_id in (
            ("Collaborating projects", projects, "projects",
             "collaborating-projects"),
            ("Partners", partners, "organizations", "partners")):
        if not items:
            continue
        out.append(f'\t<h2>{title}</h2>')
        # The id and the enclosing #people div both carry CSS: #people img
        # sizes and floats every logo, and #collaborating-projects img sets
        # the opacity and hover.  An earlier version closed #people first and
        # used class="logos", which has no rule anywhere, so 43 logos
        # rendered at natural size.
        out.append(f'\t  <div id="{div_id}" class="row">')
        if intros.get(title):
            out.append(f'\t\t{intros[title].strip()}')
        for rec, slug, logo in items:
            href = one(rec, "foaf:homepage") or "#"
            label = rec.get("short_name") or rec.get("display_label") or slug
            style = ' style="width:400px"' if sub == "organizations" else ""
            img = (f'<img src="/theme/img/{sub}/{slug}/{logo}" '
                   f'alt="{html.escape(label)}"{style}/>'
                   if logo else html.escape(label))
            out.append(f'\t\t<a href="{html.escape(href)}" '
                       f'title="{html.escape(label)}">{img}</a>')
        out.append('\t  </div>')

    out.append('  </div>')
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
        for tier in TIERS:
            g = [r for r in rows if r["tier"] == tier]
            key = "end" if tier == "Emeritus" else "start"
            g.sort(key=lambda r: (r["pid"] != "xyzrins:persons/yaroslav-halchenko"
                                  if tier == "Centroids" else 0,
                                  r[key] is None, r[key] or ""))
            print(f"\n{tier} ({len(g)}) by {key}:")
            for r in g:
                print(f"   {r[key] or '(undated)':12s} {r['slug']}")
        return 0
    try:
        ET.fromstring("<root>" + re.sub(r"<!DOCTYPE[^>]*>", "", markup) + "</root>")
    except ET.ParseError as exc:
        print(f"REFUSING TO WRITE: the generated page is not well-formed "
              f"XML, so the table-of-contents extension would silently drop "
              f"every anchor: {exc}", file=sys.stderr)
        return 2
    if a.out:
        pathlib.Path(a.out).write_text(markup)
        print(f"wrote {a.out}  ({len(markup.splitlines())} lines)")
    else:
        print(markup)
    return 2 if skipped else 0


if __name__ == "__main__":
    sys.exit(main())
