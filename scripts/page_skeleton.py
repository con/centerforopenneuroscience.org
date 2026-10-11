#!/usr/bin/env python3
"""Split a page into an ordered list of segments, so regeneration is total.

The previous check compared only the window it knew how to rebuild -- 85.5%
of whoweare.html -- and reported "round-trip CLEAN" while 5577 bytes
containing 41 collaborating-project links sat outside the comparison, in no
record at all.  A gate that can be clean while content is missing is worse
than no gate: it reads as coverage.

So the page is modelled as a skeleton: an ordered list of segments, each
either

    {literal: "..."}        verbatim bytes, not yet structured
    {record: "people/x"}    rendered from a record

Concatenating the segments MUST reproduce the file byte for byte.  Coverage
is then a real number -- the share of bytes served by records rather than
literals -- that goes up as more of the page is structured, instead of a
binary that was never earned.
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent.parent


def build(page_path, spans):
    """spans: ordered [(start, end, record_id)] -- the rest becomes literals."""
    text = page_path.read_text()
    segs, pos = [], 0
    for start, end, rid in sorted(spans):
        if start > pos:
            segs.append({"literal": text[pos:start]})
        segs.append({"record": rid, "bytes": end - start})
        pos = end
    if pos < len(text):
        segs.append({"literal": text[pos:]})
    return segs


def coverage(segs):
    rec = sum(s.get("bytes", 0) for s in segs if "record" in s)
    lit = sum(len(s["literal"]) for s in segs if "literal" in s)
    return rec, lit, (100.0 * rec / (rec + lit) if rec + lit else 0.0)


def verify(page_path, segs, render):
    """render(record_id) -> str.  Returns (ok, first_difference_offset)."""
    out = []
    for s in segs:
        out.append(s["literal"] if "literal" in s else render(s["record"]))
    rebuilt = "".join(out)
    original = page_path.read_text()
    if rebuilt == original:
        return True, None
    for i, (a, b) in enumerate(zip(original, rebuilt)):
        if a != b:
            return False, i
    return False, min(len(original), len(rebuilt))


if __name__ == "__main__":
    print(__doc__)
    sys.exit(0)
