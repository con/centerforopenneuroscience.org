#!/usr/bin/env python3
"""Populate con-site-specific's content/ tree with the logos the site uses.

con-site-specific keeps assets per entity -- content/projects/<slug>/logo.png,
content/instruments/<slug>/logo.png, content/persons/<slug>/portrait.png --
and had 20 of them.  The live pages reference 61.  This copies the rest out
of con.org's theme/static/img/ so the record repo can be the single source
for both the website and the slides.

The extension is kept from the source: logo.svg stays vector, logo.webp stays
webp.  Nothing is converted, because a logo re-encoded by a sync script is a
logo nobody can trace back.
"""
import argparse
import pathlib
import re
import shutil
import sys

from conrecords import HERE, STORE_ROOT, yaml

THEME = HERE / "theme/static/img"


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    # where a record lives decides where its logo goes
    kinds = {}
    for cls, sub in (("XYZProject", "projects"), ("XYZInstrument", "instruments"),
                     ("XYZOrganization", "organizations")):
        for f in (STORE_ROOT / "metadata/records" / cls).glob("*.yaml"):
            kinds[f.stem] = sub

    # The page's slug and the record's slug are not always the same word:
    # projects.html spells out "Brain Imaging Data Structure (BIDS)" where the
    # record is `bids`.  These are the cases, listed rather than guessed at.
    ALIAS = {
        "brain-imaging-data-structure-bids": "bids",
        "neurodata-without-borders-neurophysiology-nwb-n": "nwb",
        "repronim-containers": "repronim",
    }

    copied, already, no_record, no_file = [], [], [], []
    for f in sorted((HERE / "content/projects").glob("*.yaml")):
        d = yaml.safe_load(f.read_text())
        src_rel = (d.get("logo") or {}).get("src")
        if not src_rel:
            continue
        s = ALIAS.get(slug(d["project"]), slug(d["project"]))
        sub = kinds.get(s)
        if sub is None:
            no_record.append((s, src_rel))
            continue
        src = THEME / src_rel.split("/img/")[-1]
        if not src.exists():
            no_file.append((s, src_rel))
            continue
        out = STORE_ROOT / "content" / sub / s / f"logo{src.suffix.lower()}"
        if any(out.parent.glob("logo.*")):
            already.append(s)
            continue
        if a.write:
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, out)
        copied.append((s, sub, src.name))

    print(f"{'copied' if a.write else 'would copy'}: {len(copied)}")
    for s, sub, name in copied:
        print(f"    content/{sub}/{s}/logo{pathlib.Path(name).suffix}  <- {name}")
    print(f"already present: {len(already)}")
    if no_record:
        print(f"NO RECORD, logo not placed: {len(no_record)}")
        for s, src in no_record:
            print(f"    {s:34s} {src}")
    if no_file:
        print(f"LOGO FILE MISSING in theme: {len(no_file)}")
        for s, src in no_file:
            print(f"    {s:34s} {src}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
