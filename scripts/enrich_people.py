#!/usr/bin/env python3
"""Carry the per-person details from whoweare.html into the records.

Generating the page from records only works if the records hold what the page
shows.  They did not: con-site-specific had names, descriptions, a GitHub
handle and sometimes an email, while the page also carries a position line, a
portrait and up to nine contact links per person.

Contacts become `attributes` with a predicate per kind, so a renderer can ask
for "the ORCID" rather than parsing a label.  Portraits are synced as files
next to the record, the way logos were.  Positions are multivalued -- three
people have two.
"""
import argparse
import html
import os
import pathlib
import re
import shutil
import sys

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
RECORDS = STORE_ROOT / "metadata/records/XYZPerson"

# One predicate per contact kind.  vcard covers the person-to-person ones;
# the rest are accounts, which foaf:account models and which a renderer can
# tell apart by the URL it already has.
PREDICATE = {
    "email": "vcard:hasEmail",
    "phone": "vcard:hasTelephone",
    "research": "foaf:homepage",
    "cv": "vcard:hasURL",
    "orcid": "dlthings:orcid",
    "github": "dlthings:github",
    "twitter": "foaf:account",
    "mastodon": "foaf:account",
    "facebook": "foaf:account",
    "linkedin": "foaf:account",
    "bluesky": "foaf:account",
    "web": "foaf:homepage",
    "home": "dlthings:home_page",
    "blog": "foaf:weblog",
    "googleplus": "foaf:account",
    "google scholar": "dlthings:scholar",
}


def A(pred, val):
    return {"predicate": pred, "schema_type": "dlthings:AttributeSpecification",
            "value": val}


def slugify(name):
    name = re.sub(r"\s*\([^)]*\)\s*", " ", name or "")   # "Matthijs (Matt) van der Meer"
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    # map display name -> record, so the page's spelling can find it
    recs = {}
    for f in RECORDS.glob("*.yaml"):
        d = yaml.safe_load(f.read_text())
        for k in ("formatted_name", "display_label"):
            if d.get(k):
                recs.setdefault(slugify(d[k]), f)
        recs.setdefault(f.stem, f)

    touched, unmatched, portraits = 0, [], 0
    for src in sorted((HERE / "content/people").glob("*.yaml")):
        p = yaml.safe_load(src.read_text())
        key = slugify(p.get("display_name") or p["person"])
        f = recs.get(key) or recs.get(slugify(p["person"]))
        if not f:
            unmatched.append(p.get("display_name"))
            continue
        d = yaml.safe_load(f.read_text())
        attrs = d.setdefault("attributes", [])
        have = {(x.get("predicate"), x.get("value")) for x in attrs}

        for pos in (p.get("positions") or []):
            pair = ("dlthings:position", pos)
            if pair not in have:
                attrs.append(A(*pair)); have.add(pair)
        for c in (p.get("contacts") or []):
            # the page writes a few labels by hand, so "GitHub" and
            # "Google Scholar" arrive capitalised
            pred = PREDICATE.get((c.get("kind") or "").strip().lower())
            # the page stores hrefs HTML-escaped; keep the real URL
            href = html.unescape((c.get("href") or "").strip())
            if not pred or not href:
                continue
            if (pred, href) not in have:
                attrs.append(A(pred, href)); have.add((pred, href))
        # the website tier is a fact about the site, and the slide renders by it
        if p.get("tier") and ("dlthings:tier", p["tier"]) not in have:
            attrs.append(A("dlthings:tier", p["tier"]))

        if a.write:
            f.write_text(yaml.safe_dump(d, default_flow_style=False,
                                        sort_keys=True, width=84,
                                        allow_unicode=True))
        touched += 1

        # portrait, as a file beside the record
        por = (p.get("portrait") or "").lstrip("/")
        if por:
            s = HERE / "theme/static" / por.replace("theme/", "", 1)
            if s.exists():
                out = STORE_ROOT / "content/persons" / f.stem / f"portrait{s.suffix.lower()}"
                if not any(out.parent.glob("portrait.*")):
                    if a.write:
                        out.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(s, out)
                    portraits += 1

    print(f"{'enriched' if a.write else 'would enrich'}: {touched} person records")
    print(f"portraits {'copied' if a.write else 'to copy'}: {portraits}")
    if unmatched:
        print(f"NO RECORD for: {unmatched}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
