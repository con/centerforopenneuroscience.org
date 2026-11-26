# SPDX-License-Identifier: MIT
"""Pelican plugin: index the built site for the search box (Pagefind).

After Pelican has written the site, this writes `<output>/pagefind/`: the
index, in chunks the browser fetches as it needs them, and Pagefind's own
UI, which theme/static/js/con-search.js opens from the navbar.  Nothing is
sent anywhere: the search runs in the reader's browser against those files.

What is indexed:

* every page Pelican wrote.  Pagefind splits a page at its headings that
  have an id, so a hit lands on a person or a project;
* every publication, as a record of its own leading to the publication.
  On /publications they are 200-odd list items without anchors, which
  could only ever be found as "somewhere on that page", so the list there
  is left out (EXCLUDE) and each entry of publications.json is indexed as
  a small page that exists only for the indexer.  Where the hit leads is
  carried as its `href` metadata, which con-search.js makes the link.

  (Pagefind has an API for such records, `add_custom_record`, but its
  Python wrapper waits 0.1s for every answer: 224 publications took 24s
  of each build.  A directory is one call.)

Needs the `pagefind` binary: `pip install 'pagefind[bin]'`.
"""
import asyncio
import html
import json
import pathlib
import shutil
import tempfile

from pelican import signals

# Left out of the index.  The navbar, sidebar and footer are marked in
# base.html (data-pagefind-ignore); these are in the generated pages.
EXCLUDE = [
    # filled or drawn by the browser when opened
    "details.graph", "details.publications",
    # who-works-on-what lists, closed until asked for: with them every
    # query for a project also "found" each of its people, and the reverse
    "details.related", "details.people",
    # indexed one record per publication instead, see publications()
    "[data-pub-app]",
]
# vendored libraries ship demo pages; pagefind/ is our own output
NOT_PAGES = {"theme", "pagefind"}
# where the publications' records appear to live; nothing is served from it
PUBLICATIONS = "publication"


def pages(out):
    """Every page of the site, relative to the output directory."""
    for path in sorted(out.rglob("*.html")):
        rel = path.relative_to(out)
        if rel.parts[0] not in NOT_PAGES:
            yield rel.as_posix()


def publications(data):
    """(file name, page) for every publication in publications.json."""
    kinds = data.get("types", {})
    for n, pub in enumerate(data.get("publications", [])):
        title = pub.get("title")
        if not title:
            continue
        authors = ", ".join(a[0] for a in pub.get("authors") or [] if a)
        about = [kinds.get(pub.get("type"), pub.get("type") or ""),
                 authors, pub.get("venue") or "", str(pub.get("year") or "")]
        about = html.escape(" \u00b7 ".join(p for p in about if p))
        href = html.escape(pub.get("url") or "/publications", quote=True)
        yield f"{n:04d}.html", (
            # the title is not a heading: Pagefind weighs an <h1> sevenfold,
            # and a query for "datalad" then listed eight talks before the
            # project
            '<html lang="en"><body data-pagefind-weight="0.3">'
            f'<p data-pagefind-meta="title">{html.escape(title)}</p>'
            f'<p>{about}</p><a data-pagefind-meta="href[href]" href="{href}">'
            "</a></body></html>")


async def build(out, pubs_json):
    try:
        from pagefind.index import IndexConfig, PagefindIndex
    except ImportError as exc:
        raise SystemExit(
            "The search index needs Pagefind: pip install 'pagefind[bin]'"
        ) from exc

    target = out / "pagefind"
    # Pagefind names its chunks by content and does not clear old ones
    shutil.rmtree(target, ignore_errors=True)
    config = IndexConfig(output_path=str(target), exclude_selectors=EXCLUDE)
    with tempfile.TemporaryDirectory() as tmp:
        records = pathlib.Path(tmp) / PUBLICATIONS
        records.mkdir()
        if pubs_json.is_file():
            data = json.loads(pubs_json.read_text(encoding="utf-8"))
            for name, page in publications(data):
                (records / name).write_text(page, encoding="utf-8")
        async with PagefindIndex(config=config) as index:
            site = await index.add_directory(
                str(out), glob="{" + ",".join(pages(out)) + "}")
            pubs = await index.add_directory(tmp)
    print(f"Search index: {site['page_count']} pages, "
          f"{pubs['page_count']} publications -> {target}")
    # a page Pagefind cannot read (no <html> element, say) is skipped
    # without an error, and would simply never be found
    if site["page_count"] != len(list(pages(out))):
        raise SystemExit(f"Search index: only {site['page_count']} of "
                         f"{len(list(pages(out)))} pages were indexed")


def index_site(pelican):
    out = pathlib.Path(pelican.settings["OUTPUT_PATH"])
    pubs = (pathlib.Path(pelican.settings["THEME"])
            / "static" / "data" / "publications.json")
    asyncio.run(build(out, pubs))


def register():
    signals.finalized.connect(index_site)
