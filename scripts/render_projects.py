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
import re
import sys

from conrecords import (
    INTROS,
    RECORDS,
    STORE_ROOT,
    TIERS,
    one,
    person_name,
    role_labels,
    toc_hook,
    write_page,
    yaml,
)

SECTIONS = ["Software", "Archives", "Standards", "Initiatives", "Meetings",
            "Education", "Infrastructure"]
# projects that lead their section whatever their date says
LEAD = ["datalad", "dandi", "ember", "openneuro", "neurodebian", "pymvpa"]
# records whose section the page did not assign, or which move to Archives
SECTION_OVERRIDE = {"dandi": "Archives", "ember": "Archives",
                    "openneuro": "Archives"}


def instruments_by_project():
    """Instruments grouped by the project that generated them.

    DataLad's page entry hand-listed two extensions; ten exist. Rather than
    keep a prose list in step with the records, the components are rendered
    from them.
    """
    out = {}
    for f in sorted((RECORDS / "XYZInstrument").glob("*.yaml")):
        d = yaml.safe_load(f.read_text())
        for g in (d.get("generated_by") or []):
            proj = g.get("object")
            if not proj:
                continue
            # The instrument that IS the project (instruments/datalad under
            # projects/datalad) is the software itself, not a component.
            if proj.rsplit("/", 1)[-1] == f.stem:
                continue
            out.setdefault(proj, []).append((f.stem, d))
    return out


def people_of(d, parts):
    """[(name, href or None, [(role label, [component names])]), ...].

    The reverse of whoweare's "related projects": who is associated with
    this entry, and as what.  A project names its people in
    `associated_with`; an instrument, being an entity, in `attributed_to`.

    Its instruments' people count too.  DANDI's own record names three
    people and its components seven more -- Cody Baker, Isaac To and Austin
    Macdonald among them -- so the project alone would have hidden most of
    its team.  A role held only through components names them, since "Lead"
    of pydantic2linkml is not "Lead" of DANDI.  Sub-projects do NOT roll up:
    they have entries of their own, and STAMPED, being `part_of` five
    projects, would otherwise have repeated its whole team under each.

    Current people first, in whoweare's tier order, then by name.  A person
    with no tier has no entry on whoweare, so is named but not linked.
    """
    labels, found = role_labels(), {}

    def take(rec, via):
        for a in (rec.get("associated_with") or []) + (rec.get("attributed_to") or []):
            who = a.get("object") or ""
            if not who.startswith("xyzrins:persons/"):
                continue
            mine = found.setdefault(who, {})
            for r in (labels.get(x, x) for x in (a.get("roles") or [])):
                vias = mine.setdefault(r, [])
                # held directly ([] first) means held: drop the components
                if via is None:
                    vias.clear()
                    vias.append(None)
                elif None not in vias and via not in vias:
                    vias.append(via)

    take(d, None)
    for slug, pr in parts:
        take(pr, pr.get("short_name") or pr.get("name")
             or pr.get("display_label") or slug)
    out = []
    for who, mine in found.items():
        f = RECORDS / "XYZPerson" / (who.rsplit("/", 1)[-1] + ".yaml")
        if not f.exists():
            continue
        p = yaml.safe_load(f.read_text())
        tier, name = one(p, "dlthings:tier"), person_name(p)
        href = "/whoweare#" + toc_hook(name) if tier in TIERS else None
        # direct roles first, then those held through components
        roles = sorted(((r, sorted(v for v in vias if v))
                        for r, vias in mine.items()),
                       key=lambda rv: bool(rv[1]))
        out.append((TIERS.index(tier) if tier in TIERS else len(TIERS),
                    name, href, roles))
    return [row[1:] for row in sorted(out, key=lambda r: (r[0], r[1]))]


def by_recency(rows):
    """Flagships first in their listed order, then newest-first by date,
    then undated -- an unknown date is not a recent one.

    Passes rather than one clever key: a single key that negated the date
    per character compared elementwise, so "2020" sorted before
    "2020-01-15" -- ascending, for any pair where one date prefixes the
    other.  A function rather than four lines inside render(), so the test
    can exercise this sort instead of its own copy of it.
    """
    rows = sorted(rows, key=lambda r: (r["started"] is None,
                                       "" if r["started"] is None
                                       else r["started"]),
                  reverse=True)
    rows.sort(key=lambda r: r["started"] is None)
    rows.sort(key=lambda r: LEAD.index(r["slug"]) if r["slug"] in LEAD
              else len(LEAD))
    return rows


def parents_first(group, children):
    """Reorder a section so a sub-project follows its parent.

    Sorting a section purely by date scatters a family: Standards ran
    STAMPED, BEP028, BIDS 2.0, BIDS, NWB, BEP032, BEP044, WG-16, WG-32,
    DICOM, NIDM -- with BIDS's four sub-projects in three different places
    and DICOM after both of its working groups.  Each parent keeps its
    sorted position; its children are pulled up to sit directly beneath it,
    in their own sorted order.
    """
    by_pid = {r["d"]["pid"]: r for r in group}
    kids_of = {}
    for r in group:
        for parent in (r["d"].get("part_of") or []):
            if parent in by_pid:
                kids_of.setdefault(parent, []).append(r)
    placed, out = set(), []

    def emit(r):
        if r["slug"] in placed:
            return
        placed.add(r["slug"])
        out.append(r)
        for kid in kids_of.get(r["d"]["pid"], []):
            emit(kid)

    for r in group:
        # a child is emitted by its parent, unless the parent sorts after it
        # and has not been reached yet -- then it leads its own family
        parents = [p for p in (r["d"].get("part_of") or []) if p in by_pid]
        if parents and any(p not in {q["d"]["pid"] for q in out} for p in parents):
            continue
        emit(r)
    for r in group:                      # anything orphaned by the above
        emit(r)
    return out


def subprojects_by_parent():
    """Projects grouped by the project they are `part_of`.

    Without this a sub-project is invisible unless it also claims a section
    of its own: EMBER's study template and the DICOM working groups had
    records and appeared nowhere.
    """
    out = {}
    for f in sorted((RECORDS / "XYZProject").glob("*.yaml")):
        d = yaml.safe_load(f.read_text())
        for parent in (d.get("part_of") or []):
            if parent == "xyzrins:.":
                continue          # "part of the Center" is not a sub-project
            out.setdefault(parent, []).append((f.stem, d))
    return out


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
            has_desc = bool(one(d, "dlthings:description_html")
                            or d.get("description"))
            # `dlthings:section` is what marks a record as a page entry.
            # Without one it is a collaborating project or an instrument's
            # parent, which belong on whoweare or nowhere -- not a skip
            # worth reporting.
            if sec is None:
                continue
            if not has_desc:
                skipped.append((f.stem, f"section {sec!r} but no description"))
                continue
            if sec not in SECTIONS:
                skipped.append((f.stem, f"section {sec!r} is not one of {SECTIONS}"))
                continue
            out.append({"slug": f.stem, "d": d, "section": sec,
                        "started": (d.get("started") or {}).get("at_time")})
    return out, skipped


def link_to(d, slug, on_page, tip=True):
    """A link to a related record: in-page if it has an entry, else out."""
    name = d.get("short_name") or d.get("name") or d.get("display_label") or slug
    desc = (d.get("description") or "") if tip else ""
    label = html.escape(name)
    if d.get("pid") in on_page:
        tipattr = f' title="{html.escape(desc)}"' if desc else ''
        return f'<a href="#{html.escape(on_page[d["pid"]])}"{tipattr}>{label}</a>'
    url = one(d, "foaf:homepage")
    tipattr = f' title="{html.escape(desc)}"' if desc else ''
    return f'<a href="{html.escape(url)}"{tipattr}>{label}</a>' if url else label


def meta_line(d, section, started):
    """A short labelled strip under the heading.

    This replaces an icon row borrowed from whoweare, which did not survive
    the move: there `.contact` sits beside a `col-md-9` description, so two
    floats share a row; here the description is a bare <p>, so a 353px float
    re-flowed the first two lines of all 36 entries.  It also never held
    more than one icon -- no record has a homepage AND a separate repository
    -- so the page reserved a third of its width, 36 times, for one glyph.

    The projects analogue of whoweare's one-line position field is a line of
    metadata, which cannot float anything and says more.
    """
    bits = []
    if section:
        bits.append(html.escape(section))
    if started:
        bits.append("since " + html.escape(started[:4]))
    line = " &#183; ".join(bits)
    # The same icons whoweare uses for a person's links, rather than the
    # words "Home page" and "Source".  Reusing its `.contact` classes means
    # reusing its background-image rules; only the box needs overriding,
    # because there they float and here they sit in a line of text.
    #
    # The label stays inside the anchor and is pushed off-screen by
    # text-indent, exactly as on whoweare -- a screen reader still reads
    # "Home page", and the title shows it on hover.
    icons = []
    for url, kind, label in links_of(d):
        icons.append(f'<a href="{html.escape(url)}" class="{kind}" '
                     f'title="{html.escape(label)}">{html.escape(label)}</a>')
    if icons:
        line += ' <span class="contact">' + "".join(icons) + "</span>"
    return line


def links_of(d):
    """(url, icon class, label) for a project's own links, in order.

    The icon follows the URL's host, not the slot it came from: forty
    records put a GitHub URL in `foaf:homepage`, and five of those also
    carry a `code_repository`, so keying on the slot drew a house over a
    link to GitHub.  A GitHub URL is a repository wherever it is written
    down.

    At most one GitHub link.  ORINOCO Lite's homepage is its organization
    and its repository is the engine inside it; two GitHub marks in a row,
    one of them labelled "source" and not being one, says less than one.

    Labels carry the project's name because they are the accessible name of
    an icon with no visible text -- thirty-five links all called "Home page"
    is a links list that cannot be used.
    """
    name = (d.get("short_name") or d.get("display_label") or d.get("title")
            or "")
    home = one(d, "foaf:homepage")
    repo = one(d, "dlthings:code_repository")
    out = []
    if home and "github.com" not in home:
        out.append((home, "home", f"{name} home page".strip()))
    src = repo or (home if home and "github.com" in home else None)
    if src and not any(src == u for u, _k, _l in out):
        out.append((src, "github" if "github.com" in src else "home",
                    f"{name} source".strip()))
    return out


def logo_for(slug):
    for sub in ("projects", "instruments", "organizations"):
        p = STORE_ROOT / "content" / sub / slug
        for q in sorted(p.glob("logo.*")):
            return f"/theme/img/{sub}/{slug}/{q.name}"
    return None


def anchor_of(d, slug):
    return one(d, "dlthings:anchor") or slug


def render():
    rows, skipped = load()
    order = []                 # the order render() actually used, for --show-order
    # A component or sub-project that has its OWN entry on this page should
    # link to it, not off-site: clicking a BEP under BIDS used to leave the
    # page for a spec that may not exist yet.
    # old-style anchor (the record slug, or the page's own id) -> real hook
    legacy = {}
    for r in rows:
        hook = toc_hook(r["d"].get("display_label") or r["d"].get("title")
                        or r["slug"])
        for k in {r["slug"], anchor_of(r["d"], r["slug"]),
                  (r["d"]["pid"].rsplit("/", 1)[-1])}:
            legacy[k] = hook
    on_page = {r["d"]["pid"]:
               toc_hook(r["d"].get("display_label") or r["d"].get("title")
                        or r["slug"])
               for r in rows}
    components = instruments_by_project()
    children = subprojects_by_parent()
    intros = (yaml.safe_load(INTROS.read_text()) or {}).get("projects", {}) \
        if INTROS.exists() else {}
    out = ['<html>', '', '<head>', '\t<title>Projects</title>',
           '\t<meta name="url" content="projects" />',
           '\t<meta name="save_as" content="projects.html" />',
           '\t<meta name="show_in_top_menu" content="true" />',
           # 3 puts Projects before Engage.  The two shared order 3 and the
           # menu sort is stable, so engage.html's filename decided the menu.
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
        group = by_recency(group)
        group = parents_first(group, children)
        order.append((sec, [r["slug"] for r in group],
                      [r["started"] for r in group]))
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
            meta = meta_line(d, r["section"], r["started"])
            if meta:
                out.append(f'\t\t<p class="project-meta"><small>{meta}</small></p>')
            logo = logo_for(r["slug"])
            if logo:
                # The per-record `style` carried hard pixel widths up to
                # 460px and `margin-top:-2em`, which lifted logos into the
                # headings and, below ~1280px, painted them over the first
                # line of their own description.  Sizing belongs in CSS.
                a_open = f'<a href="{html.escape(home)}">' if home else ""
                a_close = "</a>" if home else ""
                out.append('\t\t<figure>')
                out.append(f'\t\t  {a_open}<img src="{logo}" '
                           f'alt="{html.escape(name)}" class="pull-right" '
                           f'/>{a_close}')
                out.append('\t\t</figure>')
            # A record imported from the old page carries marked-up HTML and
            # is emitted raw; one written by hand carries plain text and is
            # escaped.  Requiring the former skipped every hand-written
            # record -- loudly, which is how this was found.
            rich = one(d, "dlthings:description_html")
            if rich:
                # Descriptions carried over from the hand-written page link
                # to old-style anchors (#datalad, #bids) that the
                # table-of-contents extension no longer produces -- it
                # rewrites every id to a hook derived from the heading text.
                # Repoint them rather than ship dead links.
                rich = re.sub(r'href="#([A-Za-z0-9_-]+)"',
                              lambda m: 'href="#%s"' % legacy.get(m.group(1),
                                                                  m.group(1)),
                              rich)
                out.append(f'\t\t{rich}')
            else:
                out.append(f'\t\t<p>{html.escape(d.get("description") or "")}</p>')
            # One list, whatever the record calls the relationship.
            # `part_of` gives a sub-project, `generated_by` an instrument;
            # both are "things within this project" to a reader, and
            # splitting them meant BIDS's four BEPs rendered as a different
            # kind of list from DataLad's extensions.
            parts = ((children.get(d["pid"]) or [])
                     + (components.get(d["pid"]) or []))
            # A list of one is not a list.  con/annextube's only instrument
            # IS con/annextube, so "Components: con/annextube" said nothing.
            if len(parts) > 1:
                # A bare comma list of 13 repository names, at body weight,
                # taught the reader nothing without hovering each one.  The
                # page already has the right pattern for "a named thing plus
                # a gloss" -- the <ul> inside DataLad's own description --
                # so use it, and collapse the long ones.
                # Skip components the description already introduces with a
                # gloss of its own -- DataLad's prose bullets cover
                # datalad-container and datalad-fuse better than a generated
                # line can.
                # A regex over the anchor shape was too clever and matched
                # nothing; ask the simple question instead -- does the
                # description link this name and then gloss it?
                def already_glossed(nm):
                    i = (rich or "").find(">%s</a>" % nm)
                    return i >= 0 and ":" in (rich or "")[i:i + len(nm) + 16]
                parts = [(s, pr) for s, pr in parts
                         if not already_glossed(pr.get("name") or s)]
            # Re-checked after the dedupe: DataLad's prose can gloss all but
            # one, and a list of one is still not a list.  (This used to fall
            # back to the un-deduped instrument list, which both undid the
            # dedupe and, once sub-projects joined the list, dropped them.)
            if len(parts) > 1:
                rows_ = []
                for slug, pr in sorted(parts, key=lambda x: x[1].get("name") or x[0]):
                    gloss = pr.get("description") or ""
                    anchor = link_to(pr, slug, on_page, tip=not gloss)
                    rows_.append(f'\t\t    <li>{anchor}'
                                 + (f': {html.escape(gloss)}' if gloss else '')
                                 + '</li>')
                body = ['\t\t  <ul class="component-list">'] + rows_ + ['\t\t  </ul>']
                if len(parts) > 5:
                    # `open`: the content is the useful part.  Collapsed, a
                    # reader saw "9 components" and no way to know whether
                    # that mattered.  The disclosure stays, so a long list
                    # can still be folded away.
                    out.append('\t\t<details class="components" open="open">')
                    out.append(f'\t\t  <summary>{len(parts)} components</summary>')
                    out += body
                    out.append('\t\t</details>')
                else:
                    out.append('\t\t<p class="components">'
                               '<strong>Components:</strong></p>')
                    out += body
            # Closed, unlike a long component list: the description is the
            # content here, and the people are an index into whoweare.
            ppl = people_of(d, components.get(d["pid"]) or [])
            if ppl:
                out.append('\t\t<details class="people">')
                out.append(f'\t\t  <summary>{len(ppl)} '
                           f'{"person" if len(ppl) == 1 else "people"}</summary>')
                out.append('\t\t  <ul class="people-list">')
                for name, href, roles in ppl:
                    label = (f'<a href="{html.escape(href)}">{html.escape(name)}</a>'
                             if href else html.escape(name))
                    role = ", ".join(
                        html.escape(r) + (f' <small>({html.escape(", ".join(v))})'
                                          '</small>' if v else "")
                        for r, v in roles)
                    out.append(f'\t\t    <li>{label}'
                               + (f' &#8212; {role}' if role else '') + '</li>')
                out.append('\t\t  </ul>')
                out.append('\t\t</details>')
            out.append('\t  </div>')
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
        # printed from the order render() actually used -- an earlier
        # version re-derived it here and silently disagreed once the
        # renderer learned to group children under their parent
        for sec, slugs, starts in order:
            print(f"\n{sec} ({len(slugs)}):")
            for slug, started in zip(slugs, starts):
                print(f"   {started or '(undated)':12s} {slug}")
        return 0
    return write_page(markup, a.out, skipped)

if __name__ == "__main__":
    sys.exit(main())
