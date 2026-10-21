#!/usr/bin/env python3
"""Render content/pages/whoweare.html from con-site-specific's records.

Ordering, which is the point of the exercise: every tier is sorted by when
the person joined CON -- the `started` date on their association with the
site-root project, derived from this repo's own git history -- and the two
Emeritus tiers by when they left.  Previously only Centroids had a deliberate
order and the rest were whatever the file happened to say.

People with no date sort last within their tier rather than first, because an
unknown date is not an early one.  YOH is the exception and is pinned to the
top of Centroids: he predates the website, so his association is deliberately
undated (see the curation evidence), and sorting him last would be absurd.
"""
import argparse
import html
import re
import sys

import render_projects  # for the projects page's own anchors
from conrecords import (
    INTROS,
    RECORDS,
    STORE_ROOT,
    attrs,
    one,
    toc_hook,
    write_page,
    yaml,
)

TIERS = ["Centroids", "Collaborators", "Affiliated Faculty", "Emeritus",
         "Emeritus Collaborators"]
# Past people close the page, after the logo strips, and sort by when they
# left.  "Emeritus" is for former centroids; "Emeritus Collaborators" for
# those who worked with CON without ever working within it.
PAST_TIERS = ("Emeritus", "Emeritus Collaborators")
# the logo strips at the foot of the page, in order.  `dlthings:tier` is the
# same predicate that groups the people above -- "which block of whoweare
# does this belong to" -- rather than `dlthings:section`, which already means
# "which heading on the PROJECTS page" and would send an organization there.
ORG_TIERS = ["Collaborating labs & groups", "Partners"]
# a person who leads one of these is shown as leading it
LEAD_ROLES = {"marcrel:ldr", "marcrel:led"}
# Accounts on services that no longer exist.  The record keeps the fact --
# it was true -- but the page should not hand a reader a dead link.  Google+
# shut down in April 2019 and two entries still linked to it.
DEFUNCT_ACCOUNTS = ("plus.google.com",)
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
ACCOUNT_CLASS = {"twitter.com": ("twitter", "Twitter"),
                 "x.com": ("twitter", "Twitter"),
                 "fosstodon.org": ("mastodon", "Mastodon"),
                 "mastodon": ("mastodon", "Mastodon"),
                 "facebook.com": ("facebook", "FaceBook"),
                 "linkedin.com": ("linkedin", "LinkedIn"),
                 "bsky.app": ("bluesky", "Bluesky")}


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


def role_labels():
    """role pid -> printable label, from the XYZAgentRole records.

    The alternative was a map in this file, which would go stale silently;
    the records already carry `display_label` for all eighteen.
    """
    out = {}
    for f in sorted((RECORDS / "XYZAgentRole").glob("*.yaml")):
        d = yaml.safe_load(f.read_text())
        if d.get("display_label"):
            out[d["pid"]] = d["display_label"]
    return out


def led_organizations():
    """person pid -> [(label, homepage), ...] for the groups they lead.

    Hanke leads Psychoinformatics, Poline ORIGAMI, Wager CANlab: facts the
    records hold on the ORGANIZATION (`influenced_by` plus a lead role) and
    the page never showed.  The link goes to the group's own site rather than
    to the strip at the foot of this page -- a logo in a strip is not an
    entry to land on, and the site is what a reader following "Leads" wants.
    """
    out = {}
    for f in sorted((RECORDS / "XYZOrganization").glob("*.yaml")):
        d = yaml.safe_load(f.read_text())
        for inf in (d.get("influenced_by") or []):
            if set(inf.get("roles") or []) & LEAD_ROLES:
                out.setdefault(inf["object"], []).append(
                    (d.get("short_name") or d.get("display_label") or f.stem,
                     one(d, "foaf:homepage")))
    return out


def page_anchors():
    """project pid -> "/projects#hook" for everything with an entry there.

    `render_projects.load()` owns which records earn a heading and `toc_hook`
    owns what the table-of-contents extension will call it, so a link built
    here cannot drift from the page it points at.
    """
    return {r["d"]["pid"]:
            "/projects#" + toc_hook(r["d"].get("display_label")
                                    or r["d"].get("title") or r["slug"])
            for r in render_projects.load()[0]}


def related_projects():
    """person pid -> [(label, href, [role labels]), ...].

    Every project the person is associated with, not only the ones with an
    entry on the projects page: YOH leads Fail2Ban and Joey Hess wrote
    git-annex, and both are collaborating projects that live in the logo
    strip rather than under a heading.  Restricting the list to page entries
    dropped 15 of YOH's associations and all of Joey's.

    So the link follows the same rule the projects page uses for its own
    components -- in-page when there is an entry to land on, the project's
    own site otherwise.

    `site-root` is CON itself.  Every person here is associated with it by
    definition; that is what the tier heading above them already says.

    Instruments and datasets count too, and they say it differently: both
    are entities, so their people hang off `attributed_to` as Attributions
    rather than off `associated_with` as Associations.  Walking only the
    projects lost Isaac To's work on dandi-schema -- a component with 52
    siblings -- and then, when datasets were left out of the same fix,
    Haxby's authorship of the data PyMVPA's tutorials are built on.
    """
    labels, anchors = role_labels(), page_anchors()
    out = {}
    for cls, slot in (("XYZProject", "associated_with"),
                      ("XYZInstrument", "attributed_to"),
                      ("XYZDataset", "attributed_to")):
        for f in sorted((RECORDS / cls).glob("*.yaml")):
            d = yaml.safe_load(f.read_text())
            if d["pid"] == "xyzrins:.":
                continue
            name = (d.get("short_name") or d.get("display_label")
                    or d.get("title") or f.stem)
            # an instrument or dataset has no heading of its own, so it
            # links to wherever it lives
            href = anchors.get(d["pid"]) or one(d, "foaf:homepage")
            for a in (d.get(slot) or []):
                who = a.get("object") or ""
                if not who.startswith("xyzrins:persons/"):
                    continue
                roles = [labels.get(x, x) for x in (a.get("roles") or [])]
                out.setdefault(who, []).append((name, href, roles))
    # one entry per project: a person may hold several associations with the
    # same project over time (Adina was an intern here, then a contributor)
    for who, rows in out.items():
        merged = {}
        for name, href, roles in rows:
            seen = merged.setdefault(name, (href, []))[1]
            seen += [r for r in roles if r not in seen]
        out[who] = sorted((n, h, r) for n, (h, r) in merged.items())
    return out


def org_strips():
    """tier -> [(record, slug, logo filename or None), ...]."""
    out = {}
    for f in sorted((RECORDS / "XYZOrganization").glob("*.yaml")):
        d = yaml.safe_load(f.read_text())
        tier = one(d, "dlthings:tier")
        if tier not in ORG_TIERS:
            continue
        logo = next((q for q in sorted((STORE_ROOT / "content/organizations"
                                        / f.stem).glob("logo.*"))), None)
        out.setdefault(tier, []).append((d, f.stem, logo.name if logo else None))
    return out


def portrait(slug):
    """Theme path for a person's portrait.

    The file is `persons/<slug>/portrait.ext` in the record store and lands
    in the theme as `team/<slug>.ext` -- an earlier version returned
    `team/portrait.ext`, dropping the slug, which made every portrait point
    at the same non-existent file.
    """
    for p in sorted((STORE_ROOT / "content/persons" / slug).glob("portrait.*")):
        return f"/theme/img/team/{slug}{p.suffix.lower()}"
    return None


def phone_text(uri):
    """A readable label for a `tel:` URI.

    RFC 3966 allows only `-` and `.` as visual separators, so the canonical
    form in the record is `tel:+1(603)6469834` and stripping the scheme gave
    "+1(603)6469834" where the page had always shown "+1 (603) 646-9834".
    The URI stays the href; only the label is spaced out, and only for the
    one shape that appears here -- anything else is printed as stored.
    """
    v = uri.replace("tel:", "")
    m = re.fullmatch(r"(\+1)\((\d{3})\)(\d{3})(\d{4})", v)
    return f"{m[1]} ({m[2]}) {m[3]}-{m[4]}" if m else v


def contact_links(d):
    out, seen_classes = [], set()
    for pred, cls, label in CONTACTS:
        for v in attrs(d, pred):
            c, text = cls, label
            if pred == "foaf:account":
                c, text = next(((k2, t) for host, (k2, t) in ACCOUNT_CLASS.items()
                                if host in v), ("web", "Web"))
            if pred == "foaf:account" and any(h in v for h in DEFUNCT_ACCOUNTS):
                continue
            if pred == "vcard:hasTelephone":
                text = phone_text(v)
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
    leads, related = led_organizations(), related_projects()
    rows, skipped = [], []
    # the order render() actually used, for --show-order
    order = []
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

    def people(tier):
        group = [r for r in rows if r["tier"] == tier]
        if not group:
            return
        key = "end" if tier in PAST_TIERS else "start"
        # undated sorts last; YOH predates the site and is pinned first
        group.sort(key=lambda r: (r["pid"] != "xyzrins:persons/yaroslav-halchenko"
                                  if tier == "Centroids" else 0,
                                  r[key] is None, r[key] or ""))
        order.append((tier, key, group))
        out.append(f'\t<h2>{html.escape(tier)}</h2>')
        for r in group:
            d = r["d"]
            # the page's own spelling, parentheticals and all; a record whose
            # given and family names already compose the name carries
            # neither (the store's AGENTS.md says to leave them out)
            name = (d.get("display_label") or one(d, "dlthings:formatted_name")
                    or f'{d["given_name"]} {d["family_name"]}')
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
                out.extend(f'\t\t  {l}' for l in links)
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
            groups = leads.get(r["pid"]) or []
            if groups:
                bits = ", ".join(
                    f'<a href="{html.escape(h)}">{html.escape(n)}</a>' if h
                    else html.escape(n) for n, h in sorted(groups))
                out.append(f'\t\t<div class="col-md-9 col-sm-9 leads">'
                           f'<strong>Leads</strong> {bits}</div>')
            mine = related.get(r["pid"]) or []
            if mine:
                # closed by default: this is an index, and 38 open lines
                # under YOH would bury the next person.  The projects page
                # opens its component lists because they ARE the content
                # there; here the description is.
                out.append('\t\t<details class="col-md-9 col-sm-9 related">')
                out.append(f'\t\t  <summary>{len(mine)} related project'
                           f'{"" if len(mine) == 1 else "s"}</summary>')
                out.append('\t\t  <ul class="related-list">')
                for name, href, roles in mine:
                    role = (" &#8212; " + html.escape(", ".join(roles))
                            if roles else "")
                    # a record with neither a page entry nor a homepage still
                    # names the project; it just cannot be linked
                    label = (f'<a href="{html.escape(href)}">'
                             f'{html.escape(name)}</a>' if href
                             else html.escape(name))
                    out.append(f'\t\t    <li>{label}{role}</li>')
                out.append('\t\t  </ul>')
                out.append('\t\t</details>')
            out.append('\t  </div>')

    for tier in TIERS:
        if tier not in PAST_TIERS:
            people(tier)
    # --- the logo strips the records also drive -------------------------
    # Collaborating projects are the ones with no `part_of: xyzrins:.` -- the
    # discriminator the part_of refactor established.  The organization
    # strips below are driven by `dlthings:tier` instead of a tuple of slugs
    # in this file, so adding a lab is a record, not a code change.
    # ...and nothing that belongs to another project.  Testing only for
    # `part_of: xyzrins:.` stopped being enough once the standards gained
    # structure: a BEP is `part_of: bids` and the DICOM working groups are
    # `part_of: dicom`, so all seven landed in this strip as though they
    # were independent collaborations, alongside the parent they belong to.
    #
    # A record with no homepage is also dropped: the strip renders every
    # entry as a link, and HRF models and Hyperalignment infrastructure --
    # advisory efforts with no site of their own -- rendered as `href="#"`.
    projects = []
    for f in sorted((RECORDS / "XYZProject").glob("*.yaml")):
        pr = yaml.safe_load(f.read_text())
        if pr.get("part_of") or pr["pid"] == "xyzrins:.":
            continue
        if not one(pr, "foaf:homepage"):
            continue
        logo = next((q for q in sorted((STORE_ROOT / "content/projects" / f.stem)
                                       .glob("logo.*"))), None)
        # patsy and seaborn have no logo and appear on the live page as plain
        # text links, so a missing logo is not a reason to drop the entry.
        projects.append((pr, f.stem, logo.name if logo else None))

    intros = (yaml.safe_load(INTROS.read_text()) or {}).get("whoweare", {}) \
        if INTROS.exists() else {}
    strips = []
    for tier in ORG_TIERS:
        items = org_strips().get(tier) or []
        if items:
            strips.append((tier, items, "organizations",
                           toc_hook(tier).strip("_")))
    # the projects strip is the longest, so it goes after the labs
    strips.append(("Collaborating projects", projects, "projects",
                   "collaborating-projects"))
    for title, items, sub, div_id in strips:
        if not items:
            continue
        out.append(f'\t<h2>{html.escape(title)}</h2>')
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
            # A name with no logo needs its own spacing: the strip is a run
            # of floated images, so nine consecutive text links ran together
            # into "Haxby Lab ORIGAMI Lab Psychoinformatics" with nothing to
            # separate them.  `class="name"` is what the CSS keys on.
            cls = "" if logo else ' class="name"'
            out.append(f'\t\t<a href="{html.escape(href)}" '
                       f'title="{html.escape(label)}"{cls}>{img}</a>')
        out.append('\t  </div>')

    for tier in PAST_TIERS:
        people(tier)
    out.append('  </div>')
    out += ['  </section>', '</body>', '', '</html>', '']
    return "\n".join(out), order, skipped


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out")
    ap.add_argument("--show-order", action="store_true")
    a = ap.parse_args()
    markup, order, skipped = render()
    for slug, why in skipped:
        print(f"SKIPPED {slug}: {why}", file=sys.stderr)
    if a.show_order:
        # printed from the order render() actually used.  Re-deriving the
        # sort here is how the projects renderer came to report an order its
        # own page did not have.
        for tier, key, group in order:
            print(f"\n{tier} ({len(group)}) by {key}:")
            for r in group:
                print(f"   {r[key] or '(undated)':12s} {r['slug']}")
        return 0
    return write_page(markup, a.out, skipped)

if __name__ == "__main__":
    sys.exit(main())
