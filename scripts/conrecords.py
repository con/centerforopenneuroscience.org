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


def attrs(d, pred):
    return [a["value"] for a in (d.get("attributes") or [])
            if a.get("predicate") == pred]


def one(d, pred):
    v = attrs(d, pred)
    return v[0] if v else None


def load_yaml(path):
    with open(path) as fh:
        return yaml.safe_load(fh) or {}


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
