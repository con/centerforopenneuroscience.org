#!/usr/bin/env python3
"""Render the project rows of the Acknowledgements slide from records.

Takes a named selection from content/selections/ and emits the markup for the
deck's generated block.  Reads the record store, like the other two
generators -- it used to read content/projects/, the one-time extraction of
the hand-written page, which is gone.

Logo sizing is the whole problem here.  The site's logos are hand-tuned for a
one-column web row -- `width:255px`, `margin-top:-2em`, `pull-right` -- which
means nothing on a slide, and their intrinsic shapes run from 206x75
(scikit-learn, a wordmark) to 1024x1024 (DANDI, a square mark).  Scaling them
all to one height makes the wordmarks enormous and the square marks tiny, so
height is chosen per aspect ratio instead.
"""
import argparse
import pathlib
import subprocess
import sys

import render_projects
from conrecords import RECORDS, one, yaml

HERE = pathlib.Path(__file__).resolve().parent.parent
SITE = "https://centerforopenneuroscience.org"


def intrinsic(src, deck=None):
    """(w, h) of a logo asset, or None -- SVGs often carry no raster size.

    `src` is normally a site asset; an override names a path inside the deck
    instead, which is why `deck` has to be consulted first.
    """
    p = None
    if deck and not src.startswith("theme/"):
        cand = pathlib.Path(deck) / src
        if cand.exists():
            p = cand
    if p is None:
        p = HERE / "theme/static" / src.lstrip("/").replace("theme/", "", 1)
    if not p.exists():
        return None
    try:
        out = subprocess.run(["identify", "-format", "%w %h", str(p)],
                             capture_output=True, text=True, timeout=20)
        w, h = out.stdout.split()[:2]
        return int(w), int(h)
    except Exception:
        return None


def slide_height(dims, band):
    """Pick an optical height from the aspect ratio.

    A 13:1 wordmark and a 1:1 mark cannot share a height and look like one
    row; wide marks get shorter so their *area* stays comparable.
    """
    base = 58 if band == "funded" else 46
    if not dims:
        return base
    w, h = dims
    ar = w / h
    if ar >= 4.0:        # wide wordmark (nwb 5.5:1, incf 6.5:1)
        return round(base * 0.52)
    if ar >= 2.0:        # wordmark (scikit-learn, psychopy, hcp ~2.7:1)
        return round(base * 0.72)
    if ar <= 0.9:        # tall or square mark (dandi 1:1, ember 0.8:1)
        return round(base * 1.0)
    return round(base * 0.85)


def render(selection, deck=None):
    sel = yaml.safe_load((HERE / "content/selections" / f"{selection}.yaml").read_text())
    overrides = sel.get("logo_overrides") or {}
    recs = {}
    for f in sorted((RECORDS / "XYZProject").glob("*.yaml")):
        recs[f.stem] = yaml.safe_load(f.read_text())

    out, missing = [], []
    for band in sel["bands"]:
        items = []
        for slug in band["projects"]:
            r = recs.get(slug)
            if not r:
                missing.append(slug)
                continue
            over = overrides.get(slug) or {}
            src = over.get("src") or render_projects.logo_for(slug)
            if not src:
                missing.append(f"{slug} (no logo)")
                continue
            href = one(r, "foaf:homepage") or f"{SITE}/projects"
            title = (r.get("display_label") or r.get("title")
                     or r.get("short_name") or slug)
            # An override already names a deck-relative path; a site asset has
            # to be addressed in the copy the deck keeps.  The store calls
            # every logo `logo.<ext>`, so the deck-side name is built from the
            # slug -- which is what the deck's assets are already called.
            dsrc = (over["src"] if over.get("src")
                    else f"pics/con-projects/{slug}_logo{pathlib.Path(src).suffix}")
            # Measure the file the DECK will render, not the site's copy of
            # it.  They can differ: the deck's ReproNim mark is 280x341 and
            # the store's is a 600x120 wordmark, and the two land in
            # different branches of slide_height -- so sizing from the site
            # asset squashed the image actually on the slide.
            h = slide_height(intrinsic(dsrc, deck) or intrinsic(src, deck),
                             band["id"])
            items.append(
                f'\t  <a class="cww-proj" href="{href}" target="_blank" '
                f'title="{title}"><img style="height:{h}px" '
                f'data-src="{dsrc}"/></a>')
        if not items:
            continue
        out.append(f'  <div class="cww-tier"><span class="cww-label">{band["label"]}</span>')
        out.append('\t<div class="cww-faces" style="align-items:center;">')
        out += items
        if band is sel["bands"][-1]:
            more = sel["more"]
            out.append(f'\t  <a class="cww-proj cww-more" href="{more["href"]}" '
                       f'target="_blank" title="{more["note"]}">{more["label"]}</a>')
        out.append("\t</div>")
        out.append("  </div>")
    return "\n".join(out) + "\n", missing


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selection", default="acknowledgement")
    ap.add_argument("--out")
    ap.add_argument("--deck", default="../talks",
                    help="deck root, for resolving logo_overrides paths")
    a = ap.parse_args()
    markup, missing = render(a.selection, a.deck)
    if a.out:
        pathlib.Path(a.out).write_text(markup)
        print(f"wrote {a.out}")
    else:
        print(markup)
    if missing:
        print(f"NOT RENDERED ({len(missing)}): {missing}", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
