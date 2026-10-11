#!/usr/bin/env python3
"""Harvest dated evidence for CON's associations with community projects.

Every row this emits is a *citation*, not a conclusion: a changelog trailer, a
commit, or the commit that first listed a project on this website.  Curation
into content/associations/*.yaml stays a human step -- this only assembles the
evidence a human needs to do it.

Sources, in decreasing order of strength:

  debian-changelog   pkg-exppsy checkouts -- an RFC-2822 trailer dates a first
                     upload precisely and names the uploader
  upstream-git       an upstream checkout -- first/last commit by us
  site-git-history   this repo -- the commit that first introduced a project's
                     <h2 id="..."> anchor, i.e. "listed on the CON site since"

Usage:  scripts/harvest_associations.py [--out reports/associations-evidence.json]
"""

import argparse
import json
import pathlib
import re
import subprocess
from email.utils import parsedate_to_datetime

PKG_EXPPSY = pathlib.Path("/home/yoh/deb/gits/pkg-exppsy")
SITE = pathlib.Path(__file__).resolve().parent.parent
US = re.compile(r"alchenko|Hanke", re.I)          # "us" for authorship purposes

CL_HEADER = re.compile(r"^(?P<src>[a-z0-9][a-z0-9+.-]*) \((?P<ver>[^)]+)\) (?P<dist>[^;]+);\s*urgency=(?P<urgency>\S+)")
CL_TRAILER = re.compile(r"^ -- (?P<who>.*\S)\s\s+(?P<when>\w{3},\s.*?)\s*$")


WARNINGS = []


def run(cmd, cwd=None):
    """Run a command, or record WHY it produced nothing.

    Returning "" on failure would make a broken checkout indistinguishable from
    "no commits found" -- a fabricated negative, which in a provenance system is
    as damaging as a fabricated positive (B2).
    """
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        WARNINGS.append({"cmd": " ".join(cmd[:4]) + " ...", "cwd": str(cwd),
                         "returncode": r.returncode, "stderr": r.stderr.strip()[:200]})
        return None
    return r.stdout


def changelog_entries(path):
    """Every (version, dist, uploader, date) in a debian/changelog, oldest first.

    An UNRELEASED entry is deliberately kept distinguishable: it is not evidence
    of an upload, which matters when the claim is "first upload".
    """
    out, cur = [], None
    for i, line in enumerate(path.read_text(errors="replace").split("\n"), 1):
        m = CL_HEADER.match(line)
        if m:
            cur = (m.group("src"), m.group("ver"), m.group("dist").strip(), i)
            continue
        m = CL_TRAILER.match(line)
        if m and cur:
            try:
                dt = parsedate_to_datetime(m.group("when"))
            except Exception as e:
                WARNINGS.append({"file": str(path), "line": i,
                                 "unparseable_trailer": line[:120], "error": str(e)})
                cur = None
                continue
            out.append({"source_package": cur[0], "version": cur[1], "dist": cur[2],
                        "released": cur[2].upper() != "UNRELEASED",
                        "line": cur[3], "uploader": m.group("who").strip(),
                        "date": dt.date().isoformat(),
                        # H4: a changelog's oldest entry is an UPPER bound on
                        # when packaging began -- packaging predating the repo
                        # conversion is invisible here, so the real date is at
                        # or BEFORE this one.  The old name and comment said
                        # "lower", which is the colloquial "at least this old"
                        # and the opposite of what the field means; see
                        # content/associations/SCHEMA.md rule 2.
                        "bound": "upper"})
            cur = None
        elif line.startswith(" -- ") and cur:
            WARNINGS.append({"file": str(path), "line": i,
                             "unmatched_trailer": line[:120]})
            cur = None
    out.sort(key=lambda e: e["date"])
    return out


def harvest_changelogs():
    rows = []
    for cl in sorted(PKG_EXPPSY.glob("*/debian/changelog")):
        es = changelog_entries(cl)
        if not es:
            continue
        ours = [e for e in es if US.search(e["uploader"])]
        rows.append({
            "kind": "debian-changelog",
            "checkout": cl.parts[-3],
            "source": f"pkg-exppsy:{cl.relative_to(PKG_EXPPSY)}",
            "first": es[0], "last": es[-1], "n_entries": len(es),
            "first_by_us": ours[0] if ours else None,
            "n_by_us": len(ours),
        })
    return rows


def harvest_upstream_git(name, path):
    """First/last commit by us in an upstream checkout, plus any commit that
    mentions us -- upstream saying our name is stronger evidence than our own
    commits are."""
    if not (path / ".git").exists():
        return None
    fmt = "%ad\t%h\t%an\t%s"
    ours = run(["git", "log", "--reverse", "--author=alchenko",
                f"--format={fmt}", "--date=short"], cwd=path).strip().split("\n")
    ours = [l for l in ours if l]
    mentions = run(["git", "log", "--reverse", "--format=" + fmt, "--date=short",
                    "--grep=Yaro", "--grep=Halchenko", "--regexp-ignore-case"],
                   cwd=path).strip().split("\n")
    mentions = [l for l in mentions if l]

    def parse(line):
        d, h, a, s = (line.split("\t") + ["", "", "", ""])[:4]
        return {"date": d, "commit": h, "author": a, "subject": s}

    return {
        "kind": "upstream-git", "project": name, "source": str(path),
        "first_by_us": parse(ours[0]) if ours else None,
        "last_by_us": parse(ours[-1]) if ours else None,
        "n_by_us": len(ours),
        "mentions_us": [parse(m) for m in mentions[:5]],
    }


def harvest_site_anchors():
    """When each project first showed up on this website.

    Two different numbers, and conflating them would be a mistake:

      anchor_since   the commit that introduced <h2 id="..."> in projects.html.
                     Weak -- a page reorganisation resets it (most anchors date
                     to the 2021-06-16 rewrite, which says nothing about when
                     the association began).
      mention_since  the first commit anywhere under content/ containing the
                     project's display name.  Still only a LOWER BOUND: the
                     repo itself starts 2011-04-14, so anything older than that
                     is invisible here and needs another source.

    Neither is an association start date.  Both are "listed at least since".
    """
    page = "content/pages/projects.html"
    html = (SITE / page).read_text()
    # match EVERY <h2>, not only those carrying an id -- 11 of the 30 have
    # none (distribits, DueCredit, ReproMan, con/tributors, con/duct, Open
    # Brain Consent, SingularityHub ...) and silently dropping them reads as
    # "those projects have no history"
    pairs = [(m.group(1) or "", m.group(2))
             for m in re.finditer(r'<h2(?:[^>]*?\sid="([^"]+)")?[^>]*>(.*?)</h2>',
                                  html, re.S)]
    seen = {}
    for anchor, _ in pairs:
        if anchor:
            seen[anchor] = seen.get(anchor, 0) + 1
    for a, n in seen.items():
        if n > 1:
            WARNINGS.append({"file": page, "duplicate_anchor": a, "count": n,
                             "note": "id is not unique; records key off the "
                                     "generated slug instead"})
    repo_start = (run(["git", "log", "--reverse", "--format=%ad",
                       "--date=short"], cwd=SITE) or "").strip().split("\n")[0]
    rows = []
    for anchor, label in pairs:
        label = re.sub(r"<[^>]+>", "", label).strip()
        row = {"kind": "site-git-history", "anchor": anchor or None,
               "anchor_missing": not anchor, "label": label,
               "source": f"{page}#{anchor}" if anchor else page,
               "repo_starts": repo_start, "bound": "upper"}
        if not anchor:
            WARNINGS.append({"file": page, "heading_without_id": label})
        # --follow: projects.html was renamed from features.html on 2015-07-21,
        # so without it no anchor can ever be reported as older than that
        if anchor:
          log = (run(["git", "log", "--reverse", "--follow", "-S", f'id="{anchor}"',
                    "--format=%ad\t%h\t%s", "--date=short", "--", page],
                     cwd=SITE) or "").strip().split("\n")
          hit = [l for l in log if l]
          if hit:
            d, h, sub = (hit[0].split("\t") + ["", "", ""])[:3]
            row.update(anchor_since=d, anchor_commit=h, anchor_subject=sub)
        log = (run(["git", "log", "--reverse", "-S", label,
                    "--format=%ad\t%h\t%s", "--date=short", "--", "content/"],
                   cwd=SITE) or "").strip().split("\n")
        hit = [l for l in log if l]
        if hit:
            d, h, sub = (hit[0].split("\t") + ["", "", ""])[:3]
            row.update(mention_since=d, mention_commit=h, mention_subject=sub)
        rows.append(row)
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="reports/associations-evidence.json")
    args = ap.parse_args()

    ev = {"debian_changelogs": harvest_changelogs(),
          "site_anchors": harvest_site_anchors(),
          "upstream_git": []}
    for name, sub in (("psychopy", "psychopy"), ("nipy", "nipy")):
        got = harvest_upstream_git(name, PKG_EXPPSY / sub)
        if got:
            ev["upstream_git"].append(got)

    out = SITE / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    ev["parse_warnings"] = WARNINGS
    out.write_text(json.dumps(ev, indent=1) + "\n")
    print(f"{len(ev['debian_changelogs'])} changelogs, "
          f"{len(ev['site_anchors'])} site anchors, "
          f"{len(ev['upstream_git'])} upstream checkouts -> {args.out}")
    if WARNINGS:
        print(f"{len(WARNINGS)} warning(s) recorded in the output; first few:")
        for w in WARNINGS[:5]:
            print("  ", {k: v for k, v in w.items() if k != "note"})


if __name__ == "__main__":
    main()
