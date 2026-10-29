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
