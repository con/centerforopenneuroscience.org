#!/usr/bin/env python3
"""Derive when each person appeared on, and left, the whoweare page.

The acknowledgement slide wants its tiers ordered by when people joined CON
(and for Emeritus, when they left), and nothing in the records says.  The
site's own git history does: whoweare.html has 126 commits back to
2015-07-21, so the commit that first mentions a person bounds their arrival,
and the commit that first files them under Emeritus bounds their departure.

Both are UPPER bounds in the sense SCHEMA/CURATION defines: an edit to a
website follows the fact it records, so the real date is at or earlier.  And
this repo only starts 2015-07-21, so anyone present in the first commit is
bounded by the repo rather than by their arrival -- reported separately,
because treating those as 2015 arrivals would be wrong.
"""
import argparse
import json
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent.parent
PAGE = "content/pages/whoweare.html"


def git(*args):
    return subprocess.run(["git", "-C", str(HERE), *args],
                          capture_output=True, text=True).stdout


def commits():
    out = git("log", "--follow", "--format=%H\t%ad", "--date=short", "--", PAGE)
    rows = [l.split("\t") for l in out.strip().split("\n") if "\t" in l]
    return list(reversed(rows))          # oldest first


def tiers(html):
    """{slug-ish name: tier} for every person mentioned, by section."""
    out = {}
    tier = None
    for m in re.finditer(r'<h2[^>]*>(.*?)</h2>|<h3[^>]*>(.*?)</h3>', html, re.S):
        pass
    # sections are h2, people are h3 inside them
    parts = re.split(r'<h2[^>]*>(.*?)</h2>', html, flags=re.S)
    for i in range(1, len(parts), 2):
        tier = re.sub(r"<[^>]+>", "", parts[i]).strip()
        body = parts[i + 1] if i + 1 < len(parts) else ""
        for h3 in re.findall(r'<h3[^>]*>(.*?)</h3>', body, re.S):
            name = re.sub(r"<[^>]+>", "", h3)
            name = re.sub(r"\s+", " ", name).strip()
            if name:
                out[name] = tier
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", help="write the result here")
    a = ap.parse_args()

    rows = commits()
    first_seen, first_emeritus, last_seen = {}, {}, {}
    repo_start = rows[0][1]
    for sha, date in rows:
        html = git("show", f"{sha}:{PAGE}")
        if not html:
            continue
        for name, tier in tiers(html).items():
            first_seen.setdefault(name, (date, sha))
            last_seen[name] = (date, sha)
            if "emerit" in (tier or "").lower():
                first_emeritus.setdefault(name, (date, sha))

    result = {}
    for name, (date, sha) in sorted(first_seen.items(), key=lambda x: x[1][0]):
        rec = {"first_seen": date, "first_seen_commit": sha[:9],
               "bounded_by_repo": date == repo_start}
        if name in first_emeritus:
            rec["first_emeritus"] = first_emeritus[name][0]
            rec["first_emeritus_commit"] = first_emeritus[name][1][:9]
        result[name] = rec

    present_at_start = [n for n, r in result.items() if r["bounded_by_repo"]]
    print(f"{len(rows)} commits to {PAGE}, {rows[0][1]} .. {rows[-1][1]}")
    print(f"{len(result)} people seen; {len(present_at_start)} already present "
          f"in the first commit (bounded by the repo, not by their arrival)\n")
    print(f"{'person':40s} {'first seen':12s} {'emeritus since':14s}")
    for name, r in sorted(result.items(), key=lambda x: x[1]["first_seen"]):
        tag = " (repo start)" if r["bounded_by_repo"] else ""
        print(f"  {name[:38]:38s} {r['first_seen']:12s} "
              f"{r.get('first_emeritus', ''):14s}{tag}")
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(result, indent=1))
        print(f"\nwrote {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
