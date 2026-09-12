#!/usr/bin/env python3
"""Rewrite site-root-absolute links in built HTML for a GitHub Pages preview.

The site's templates and content pages hard-code links and asset paths as
absolute from the domain root (e.g. ``href="/theme/css/site.css"``,
``href="/whoweare#..."``). That assumption holds in production, where the
site is served at ``https://centerforopenneuroscience.org/``, but breaks
under a GitHub Pages preview, which is served from a subpath such as
``/centerforopenneuroscience.org/pr-preview/pr-12/``.

This script rewrites every ``href="/..."`` and ``src="/..."`` (excluding
protocol-relative ``//...`` URLs) in the built ``output/`` directory to be
prefixed with the preview's base path, so the preview renders with working
CSS/JS/images and internal links. It is only used for preview builds --
the production build (`make html` / `make publish`) is untouched.
"""

import re
import sys
from pathlib import Path

ATTR_RE = re.compile(r'(href|src)="(/(?!/)[^"]*)"')


def rewrite(html: str, base_path: str) -> str:
    def replace(match: "re.Match[str]") -> str:
        attr, path = match.group(1), match.group(2)
        return f'{attr}="{base_path}{path}"'

    return ATTR_RE.sub(replace, html)


def main() -> None:
    if len(sys.argv) != 3:
        print(f"usage: {sys.argv[0]} <output-dir> <base-path>", file=sys.stderr)
        raise SystemExit(1)

    output_dir = Path(sys.argv[1])
    base_path = sys.argv[2].rstrip("/")

    for html_file in output_dir.rglob("*.html"):
        original = html_file.read_text(encoding="utf-8")
        rewritten = rewrite(original, base_path)
        if rewritten != original:
            html_file.write_text(rewritten, encoding="utf-8")


if __name__ == "__main__":
    main()
