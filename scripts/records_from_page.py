#!/usr/bin/env python3
"""Mint XYZProject records for page entries that have none.

45 of the 71 projects on the live pages -- including ReproNim, INCF,
scikit-learn, HCP and git-annex -- had no record in con-site-specific, so
regenerating the pages from records alone would have silently dropped them.
This mints the missing ones from what the pages already say.

It does NOT invent content.  39 of the 45 are logo-only entries on
`whoweare` with no prose anywhere, so their records carry a title, a short
name and a homepage and nothing else.  A description is written only where
the page actually has one.

Logos are deliberately NOT modelled here.  The house pattern is a separate
XYZDepiction record whose `distributions` point at annexed files, and the
assets currently live in con.org's `theme/static/img/3rd/`, not in the
record repo.  Minting depictions that point into another repo's theme would
be worse than leaving the generator to map record to logo by pid, which is
what it does until the assets move.
"""
import argparse
import html
import re
import sys

from conrecords import HERE, RECORDS, yaml


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


# A shared forge host identifies nobody: github.com/con/duct and
# github.com/neurodroid/stimfit are not the same project.  Matching on host
# alone silently declared Freenect and Stimfit already covered, and they were
# not -- so generic hosts fall back to the full path.
GENERIC_HOSTS = {
    "github.com", "gitlab.com", "sourceforge.net", "readthedocs.io",
    "github.io", "bitbucket.org", "codeberg.org", "foss.heptapod.net",
}


def host(u):
    m = re.match(r"https?://(?:www\.)?([^/]+)(/[^?#]*)?", (u or "").strip())
    if not m:
        return None
    h = m.group(1).lower()
    if h in GENERIC_HOSTS or any(h.endswith("." + g) for g in GENERIC_HOSTS):
        path = (m.group(2) or "/").rstrip("/").lower()
        # owner/repo is enough to tell two forge projects apart
        return h + "/" + "/".join(path.strip("/").split("/")[:2])
    return h


def prose(body_html):
    """First paragraph of the page entry, as plain text, or None."""
    if not body_html:
        return None
    m = re.search(r"<p>(.*?)</p>", body_html, re.S)
    if not m:
        return None
    txt = re.sub(r"<[^>]+>", "", m.group(1))
    txt = html.unescape(re.sub(r"\s+", " ", txt)).strip()
    return txt or None


# Listed on the pages among the projects, but modelled as organizations:
# INCF is the coordinating facility that backed the NIDM and BIDS
# standardization work, NITRC is a resource registry.  Neither is a project
# of ours, and minting XYZProject records for them was the original mistake.
AS_ORGANIZATION = {"incf", "nitrc"}

# Page entries whose record is spelled differently.  "HeuDiConv / ReproIn" on
# the page is `heudiconv` in the store; minting it by its page name produced
# two records for one project, which only showed up in a summary of the graph.
SPELLED_AS = {"heudiconvreproin": "heudiconv"}


def existing():
    out = []
    for f in sorted((RECORDS / "XYZProject").glob("*.yaml")):
        d = yaml.safe_load(f.read_text())
        hp = next((a["value"] for a in (d.get("attributes") or [])
                   if a.get("predicate") == "foaf:homepage"), None)
        out.append({
            "pid": d["pid"],
            "keys": {norm(d.get("short_name")), norm(d.get("title")),
                     norm(f.stem), norm((d.get("pid") or "").split("/")[-1])} - {""},
            "host": host(hp)})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true", help="actually write the records")
    a = ap.parse_args()

    recs = existing()
    made, skipped = [], []
    for f in sorted((HERE / "content/projects").glob("*.yaml")):
        d = yaml.safe_load(f.read_text())
        name = d.get("display_name") or d["project"]
        logo = d.get("logo") or {}
        hp = logo.get("href") or d.get("homepage")
        keys = {norm(name), norm(d["project"])} - {""}
        keys |= {SPELLED_AS[k] for k in keys if k in SPELLED_AS}
        if norm(d["project"]) in AS_ORGANIZATION:
            skipped.append(f"{name} (modelled as an organization)")
            continue
        h = host(hp)
        if any((keys & r["keys"]) or (h and r["host"] and h == r["host"]) for r in recs):
            skipped.append(name)
            continue

        slug = re.sub(r"[^a-z0-9]+", "-", d["project"].lower()).strip("-")
        rec = {
            "pid": f"xyzrins:projects/{slug}",
            "schema_type": "xyzri:XYZProject",
            "title": name,
            "short_name": name,
            "display_label": name,
        }
        attrs = [{"predicate": "skos:prefLabel",
                  "schema_type": "dlthings:AttributeSpecification", "value": name},
                 {"predicate": "dlthings:title",
                  "schema_type": "dlthings:AttributeSpecification", "value": name},
                 {"predicate": "dlthings:short_name",
                  "schema_type": "dlthings:AttributeSpecification", "value": name}]
        if hp:
            attrs.insert(0, {"predicate": "foaf:homepage",
                             "schema_type": "dlthings:AttributeSpecification",
                             "value": hp})
        desc = prose(d.get("body_html"))
        if desc:
            rec["description"] = desc
            attrs.insert(1, {"predicate": "dcterms:description",
                             "schema_type": "dlthings:AttributeSpecification",
                             "value": desc})
        rec["attributes"] = attrs

        path = RECORDS / "XYZProject" / f"{slug}.yaml"
        made.append((path, rec, bool(desc)))
        if a.write:
            # allow_unicode: an em-dash lifted from the page should stay an
            # em-dash, not become "\u2014" in a file people are meant to read.
            path.write_text(yaml.safe_dump(rec, default_flow_style=False,
                                           sort_keys=True, width=84,
                                           allow_unicode=True))

    print(f"already covered: {len(skipped)}")
    print(f"{'wrote' if a.write else 'would write'}: {len(made)} "
          f"({sum(1 for _, _, h in made if h)} with a description from the page)")
    for path, rec, has in made:
        print(f"  {'+' if has else ' '} {path.name:34s} {rec['pid']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
