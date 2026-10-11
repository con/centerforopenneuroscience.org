#!/usr/bin/env python3
"""Carry projects.html's own content into the records.

Same problem the people had: the page holds a marked-up description, a logo
with its layout attributes, an anchor and a section heading, and the records
held a one-line summary.  Rendering from records without these would strip
every in-text link from 30 descriptions.

`dlthings:section` records the h1 the entry sits under -- Software,
Initiatives, Meetings, Standards, Education, Infrastructure -- which is the
grouping the page already uses and the one the generated page keeps.
"""
import argparse
import re
import sys

from conrecords import HERE, RECORDS, yaml


def A(pred, val):
    return {"predicate": pred, "schema_type": "dlthings:AttributeSpecification",
            "value": val}


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def index():
    out = {}
    for cls in ("XYZProject", "XYZInstrument", "XYZOrganization"):
        for f in sorted((RECORDS / cls).glob("*.yaml")):
            d = yaml.safe_load(f.read_text())
            keys = {norm(f.stem), norm(d.get("short_name")), norm(d.get("title")),
                    norm(d.get("display_label"))} - {""}
            for k in keys:
                out.setdefault(k, (cls, f))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    idx = index()
    ALIAS = {"brainimagingdatastructurebids": "bids",
             "neurodatawithoutbordersneurophysiologynwbn": "nwb",
             "heudiconvreproin": "heudiconv",
             "singularityhubafterlife": "singularityhub",
             "repronimreproduciblebasics": "repronimreproduciblebasics"}

    touched, missing = 0, []
    for src in sorted((HERE / "content/projects").glob("*.yaml")):
        p = yaml.safe_load(src.read_text())
        if not p.get("body_html"):
            continue                       # logo-only whoweare entries
        key = norm(p.get("display_name") or p["project"])
        key = ALIAS.get(key, key)
        hit = idx.get(key) or idx.get(norm(p["project"]))
        if not hit:
            missing.append(p.get("display_name")); continue
        cls, f = hit
        d = yaml.safe_load(f.read_text())
        attrs = d.setdefault("attributes", [])
        have = {x.get("predicate") for x in attrs}

        body = re.sub(r"\s+", " ", p["body_html"]).strip()
        # Strip ONLY the first <figure>: it holds the project's own logo,
        # which the renderer re-emits from the record.  Stripping every
        # figure deletes genuine content -- EMBER's description carries a
        # second one for HEARTH.
        body = re.sub(r"<figure>.*?</figure>\s*", "", body, count=1,
                      flags=re.S | re.I).strip()
        if body and "dlthings:description_html" not in have:
            attrs.append(A("dlthings:description_html", body))
        if p.get("section") and "dlthings:section" not in have:
            attrs.append(A("dlthings:section", p["section"]))
        if p.get("anchor_id") and "dlthings:anchor" not in have:
            attrs.append(A("dlthings:anchor", p["anchor_id"]))
        logo = p.get("logo") or {}
        if logo.get("style") and "dlthings:logo_style" not in have:
            attrs.append(A("dlthings:logo_style", logo["style"]))
        if logo.get("href") and "foaf:homepage" not in have:
            attrs.insert(0, A("foaf:homepage", logo["href"]))

        if a.write:
            f.write_text(yaml.safe_dump(d, default_flow_style=False,
                                        sort_keys=True, width=84,
                                        allow_unicode=True))
        touched += 1

    print(f"{'enriched' if a.write else 'would enrich'}: {touched} records")
    if missing:
        print(f"NO RECORD for ({len(missing)}): {missing}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
