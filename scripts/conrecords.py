# SPDX-FileCopyrightText: 2026 Yaroslav Halchenko <yaroslav.o.halchenko@dartmouth.edu>
# SPDX-License-Identifier: MIT
#
# Generated with Claude Code 2.1.295 / Claude Opus 5
"""Plumbing shared by the scripts that read the record store.

Every script here had its own copy of the store-location preamble and of
`attrs`/`one`, and the two renderers had their own copy of the
well-formedness guard.  Copies drift: `render_projects.py --show-order`
re-derived the sort order and silently disagreed with the page once the
renderer learned to group children under their parent, and the same shape of
bug was sitting in `render_whoweare.py`.  One copy, imported.
"""
import os
import pathlib
import re
import string
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
RECORDS = STORE_ROOT / "metadata/records"
INTROS = HERE / "content/section-intros.yaml"

# whoweare's blocks of people, in page order.  Here rather than in
# render_whoweare.py because the projects page lists people too, and
# render_whoweare already imports render_projects.
TIERS = ["Centroids", "Collaborators", "Affiliated Faculty", "Emeritus",
         "Emeritus Collaborators"]


def attrs(d, pred):
    return [a["value"] for a in (d.get("attributes") or [])
            if a.get("predicate") == pred]


def one(d, pred):
    v = attrs(d, pred)
    return v[0] if v else None


def person_name(d):
    """The page's own spelling of a person, parentheticals and all.

    A record whose given and family names already compose the name carries
    neither `display_label` nor `formatted_name` (the store's AGENTS.md says
    to leave them out).
    """
    return (d.get("display_label") or one(d, "dlthings:formatted_name")
            or f'{d["given_name"]} {d["family_name"]}')


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


def load_yaml(path):
    with open(path) as fh:
        return yaml.safe_load(fh) or {}


def toc_hook(text):
    """The anchor the table-of-contents extension will actually produce.

    It OVERWRITES every explicit id= with a hook derived from the heading
    text, so an in-page link built from a record slug would point at an id
    that does not survive the build.  This mirrors
    jinjaext/table_of_contents.py: parse_hook_from_text + the trailing "_"
    that produce_new_hook appends.
    """
    h = text.strip().replace(" ", "_").lower()
    h = h.replace("/:", ":").replace("/", ":").replace(":", "_")
    for tok in string.punctuation.replace("_", ""):
        h = h.replace(tok, "")
    return h.strip("_") + "_"



def publications():
    """Every publication record, newest first; an undated one last.

    Here rather than in render_publications.py because the projects page
    lists each project's publications too, and render_publications imports
    render_projects for its anchors.
    """
    out = [load_yaml(f) for f in sorted((RECORDS / "XYZPublication").glob("*.yaml"))]
    return sorted(out, key=lambda d: (publication_date(d) or "", d["title"]),
                  reverse=True)


def publication_date(d):
    """When it was given (a talk, a poster) or else issued, as YYYY[-MM[-DD]]."""
    gen = [g["at_time"] for g in d.get("generated_by") or [] if g.get("at_time")]
    when = str(gen[0] if gen else one(d, "dcterms:issued") or "")
    # Zotero's dates come as 2022, 2022-03, 2022/03/01, 2009-5-12 and 12/2022
    parts = [x for x in re.split(r"[-/]", when[:10]) if x]
    if len(parts) == 2 and len(parts[1]) == 4:
        parts.reverse()                                  # MM/YYYY
    if not parts or len(parts[0]) != 4:
        return when or None
    return "-".join([parts[0]] + [x.zfill(2) for x in parts[1:3]])


def publication_url(d):
    """Its own page, else its DOI, else the first web address it carries --
    and for a talk with none of those, its slides or else its recording."""
    ids = d.get("identifiers") or []
    doi = next((i["notation"] for i in ids if i.get("schema_type") == "dlthings:DOI"), None)
    return (one(d, "foaf:homepage")
            or (f"https://doi.org/{doi}" if doi else None)
            or next((i["notation"] for i in ids
                     if str(i.get("notation", "")).startswith("http")), None)
            or one(d, "dcat:downloadURL")
            or one(d, "schema:video"))


# a publication's kind -> what a reader is told it is; anything else is a paper
PUBLICATION_TYPES = {"fabio:ConferencePoster": "poster", "bibo:Slideshow": "talk"}
# in the order a summary lists them
TYPE_ORDER = ["paper", "poster", "talk"]


def publication_type(d):
    return PUBLICATION_TYPES.get(d.get("kind"), "paper")


def publications_summary(types):
    """["paper", "talk", "talk"] -> "3 publications (1 paper, 2 talks)"."""
    n = len(types)
    parts = [f"{types.count(t)} {t}{'' if types.count(t) == 1 else 's'}"
             for t in TYPE_ORDER if t in types]
    return (f"{n} {'publication' if n == 1 else 'publications'}"
            + (f" ({', '.join(parts)})" if parts else ""))


def publication_projects(d):
    """The projects that produced it: its `generated_by`, less CON itself."""
    return [g["object"] for g in d.get("generated_by") or []
            if str(g.get("object", "")).startswith("xyzrins:projects/")]


def publications_details(key, pid, types, indent, cls="publications"):
    """A closed "N publications (...)" list that publications.js fills when
    opened.

    key is the filter (project, person), pid the record it names and types
    the publication_type() of each of its publications.  The counts are
    known here; the entries are fetched only once someone opens it.  The
    link inside, above the entries, works without JavaScript too: to the
    publications page, filtered the same way.
    """
    slug = pid.rsplit("/", 1)[-1]
    return [f'{indent}<details class="{cls}" data-pub-filter="{key}={slug}">',
            f'{indent}  <summary>{publications_summary(types)}</summary>',
            # first, so that a long list need not be scrolled past to reach it
            f'{indent}  <p class="pub-more"><a href="/publications?{key}={slug}">'
            'Search and filter them on the publications page</a></p>',
            f'{indent}  <div class="pub-slot"></div>',
            f'{indent}</details>']


def write_page(markup, out, skipped):
    """Write a generated page, or refuse to.

    The table-of-contents extension parses the page with strict ElementTree
    and, on a parse error, returns the content UNCHANGED -- so one malformed
    tag in one record silently strips every anchor from the page while
    Pelican still exits 0.  Catch it here instead.
    """
    try:
        ET.fromstring("<root>"
                      + re.sub(r"<!DOCTYPE[^>]*>", "", markup)
                      + "</root>")
    except ET.ParseError as exc:
        print(f"REFUSING TO WRITE: the generated page is not well-formed "
              f"XML, which means the table-of-contents extension will "
              f"silently drop every anchor: {exc}", file=sys.stderr)
        return 2
    if out:
        pathlib.Path(out).write_text(markup)
        print(f"wrote {out}  ({len(markup.splitlines())} lines)")
    else:
        print(markup)
    return 2 if skipped else 0
