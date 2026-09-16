#!/usr/bin/env python3
"""Validate that content HTML files parse as valid XML.

Pelican's ToC extension (jinjaext/table_of_contents.py) wraps each page's
content in <root>…</root> and parses it with ElementTree.  If any page
contains invalid XML (e.g. bare & in a URL, mismatched tags) the parser
fails silently and the table of contents is suppressed for that page.

Run this script before building to catch such problems early and make CI
fail with a clear error message instead of a silent ToC regression.

Exit code: 0 if all files are valid, 1 if any file fails.
"""

import sys
from pathlib import Path
from xml.etree import ElementTree


def validate_file(path: Path) -> bool:
    content = path.read_text(encoding="utf-8")
    try:
        ElementTree.fromstring("<root>" + content + "</root>")
        return True
    except ElementTree.ParseError as e:
        print(f"ERROR: {path}: {e}")
        if e.position:
            lines = ("<root>" + content).splitlines()
            line_no, col_no = e.position
            if 0 < line_no <= len(lines):
                print(f"  line {line_no}, col {col_no}:")
                print(f"  {lines[line_no - 1]}")
                print(f"  {' ' * (col_no - 1)}^")
        return False


def main() -> None:
    content_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("content")
    html_files = sorted(content_dir.rglob("*.html"))
    if not html_files:
        print(f"No HTML files found under {content_dir}", file=sys.stderr)
        raise SystemExit(1)

    failed = [f for f in html_files if not validate_file(f)]
    if failed:
        print(f"\n{len(failed)} of {len(html_files)} file(s) failed XML validation.")
        raise SystemExit(1)
    print(f"All {len(html_files)} HTML file(s) passed XML validation.")


if __name__ == "__main__":
    main()
