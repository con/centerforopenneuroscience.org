#!/usr/bin/env python3
"""Copy the records' own assets into the theme, so Pelican can serve them.

The generated pages reference /theme/img/<kind>/<slug>/logo.* and
/theme/img/team/<file>, because that is where the asset lives in
con-site-specific -- one directory per entity, beside its record.  The theme
previously kept everything flat under img/3rd/ with hand-chosen filenames.

This copies rather than symlinks: Pelican's static handling follows the tree
it is given, and a symlink into a submodule breaks as soon as the submodule
is checked out elsewhere.  Re-running is cheap and idempotent.
"""
import argparse
import os
import pathlib
import shutil
import sys

HERE = pathlib.Path(__file__).resolve().parent.parent

# The record store.  It is a submodule of this repo, so the default needs no
# configuration; CON_RECORD_STORE overrides it for working against another
# checkout.  An absolute path baked into a script is not reproducible and not
# portable -- see STAMPED.
STORE_ROOT = pathlib.Path(os.environ.get("CON_RECORD_STORE",
                                         HERE / "sourcedata/con-site-specific"))
STORE = STORE_ROOT / "content"
THEME = HERE / "theme/static/img"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    n, same, gone = 0, 0, 0
    # An entity whose record is deleted leaves its logo behind: the copy was
    # one-way and never removed anything, so quail, hypertools and supereeg
    # sat in the theme for a day after their records went, pointing at
    # nothing.  A directory here that has no counterpart in the store is an
    # orphan by definition -- the whole tree is a copy of the store.
    for sub in ("projects", "instruments", "organizations"):
        for d in sorted((THEME / sub).glob("*/")):
            if not (STORE / sub / d.name).exists():
                print(f"{'removing' if a.write else 'would remove'} orphan: "
                      f"{sub}/{d.name}")
                if a.write:
                    shutil.rmtree(d)
                gone += 1
                continue
            # ...and so is a logo the store no longer has under that name:
            # nipype's went from logo.png to logo.svg, and the png stayed.
            for f in sorted(d.glob("logo.*")):
                if not (STORE / sub / d.name / f.name).exists():
                    print(f"{'removing' if a.write else 'would remove'} orphan: "
                          f"{sub}/{d.name}/{f.name}")
                    if a.write:
                        f.unlink()
                    gone += 1
    for sub in ("projects", "instruments", "organizations"):
        for logo in sorted((STORE / sub).glob("*/logo.*")):
            out = THEME / sub / logo.parent.name / logo.name
            if out.exists() and out.stat().st_size == logo.stat().st_size:
                same += 1
                continue
            if a.write:
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(logo, out)
            n += 1
    # portraits keep the flat team/ layout the page already uses
    for por in sorted((STORE / "persons").glob("*/portrait.*")):
        out = THEME / "team" / f"{por.parent.name}{por.suffix}"
        if out.exists() and out.stat().st_size == por.stat().st_size:
            same += 1
            continue
        if a.write:
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(por, out)
        n += 1
    print(f"{'copied' if a.write else 'would copy'}: {n};  "
          f"already current: {same};  orphans removed: {gone}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
