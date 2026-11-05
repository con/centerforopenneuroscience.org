#!/usr/bin/env python3
"""Check that the committed pages are what the pinned record store renders.

whoweare.html and projects.html are generated from sourcedata/con-site-specific
(`make run-project`), and the theme holds copies of the store's logos and
portraits.  Advancing the store without re-running the projection leaves the
site describing an older store, with nothing to notice it.  This renders both
pages into a temporary directory, compares them byte for byte with the
committed ones, and asks sync_assets_to_theme.py, in its dry-run mode, whether
any asset would be copied or removed.  It writes nothing.

It needs the store's annexed media present, to compare asset sizes.

Run it as `tox -e projection`.  Exit status is non-zero on any difference.
"""
import difflib
import os
import pathlib
import re
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS = HERE / "scripts"
STORE = pathlib.Path(os.environ.get("CON_RECORD_STORE",
                                    HERE / "sourcedata/con-site-specific"))
PAGES = ("whoweare", "projects")


def run(script, *args):
    p = subprocess.run([sys.executable, str(SCRIPTS / script), *args],
                       capture_output=True, text=True, cwd=HERE)
    if p.returncode:
        sys.exit(f"{script} exited {p.returncode}:\n{p.stdout}{p.stderr}")
    return p.stdout


def main():
    problems = []

    sync = run("sync_assets_to_theme.py").strip().splitlines()
    summary = sync[-1] if sync else ""
    m = re.search(r"would copy: (\d+);.*orphans removed: (\d+)", summary)
    if not m:
        problems.append(f"sync_assets_to_theme.py said nothing parseable: {summary!r}")
    elif m.groups() != ("0", "0"):
        problems.append("theme assets differ from the store's:\n  "
                        + "\n  ".join(sync))

    with tempfile.TemporaryDirectory() as tmp:
        for page in PAGES:
            out = pathlib.Path(tmp) / f"{page}.html"
            run(f"render_{page}.py", "--out", str(out))
            committed = HERE / "content/pages" / f"{page}.html"
            want, have = out.read_text(), committed.read_text()
            if want != have:
                diff = difflib.unified_diff(
                    have.splitlines(True), want.splitlines(True),
                    fromfile=f"{committed.relative_to(HERE)} (committed)",
                    tofile=f"{page}.html (rendered from the store)")
                problems.append("".join(diff))

    rev = subprocess.run(["git", "-C", str(STORE), "rev-parse", "--short", "HEAD"],
                         capture_output=True, text=True).stdout.strip()
    if problems:
        print("\n".join(problems))
        print(f"\nThe pages do not match {STORE.name} at {rev or '?'}: "
              f"re-render with `make run-project`.", file=sys.stderr)
        return 1
    print(f"pages and theme assets match {STORE.name} at {rev or '?'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
