# SPDX-FileCopyrightText: 2026 Yaroslav Halchenko <yaroslav.o.halchenko@dartmouth.edu>
# SPDX-License-Identifier: MIT
#
# Generated with Claude Code
"""Pelican plugin: write the search box's index, `<output>/search.json`.

After Pelican has written the site, this reads the pages back and lists
everything a reader may look for -- one entry per thing, not per page:

* every stretch of a page under a heading that has an id (a person, a
  project, an objective...), leading to that heading; what a page says
  before its first such heading is an entry for the page itself;
* every publication, from publications.json, leading to the publication.
  On /publications they are 200-odd list items without anchors, so the list
  there is left out.

An entry says what kind of thing it is.  For a publication that is its type;
for a heading it is the type of the graph node that links there
(content/graph/graph.json), so no second list of who is a person has to be
kept.

theme/static/js/con-search.js fetches the file when the box is first opened
and searches it in the browser with MiniSearch.  Nothing here needs more
than the standard library.

The entries, as short keys because there are hundreds of them:
    u  address       t  title      k  kind
    p  the page it is on (not for a page itself or a publication)
    x  text
"""
import json
import pathlib
import re
import urllib.parse
from html.parser import HTMLParser

from pelican import signals

# vendored libraries ship demo pages
NOT_PAGES = {"theme"}

# Left out of the index, besides whatever base.html marks data-search-ignore.
# (tag, class) -- or (None, attribute) for an element carrying an attribute.
EXCLUDE = [
    # filled or drawn by the browser when opened
    ("details", "graph"), ("details", "publications"),
    # who-works-on-what lists, closed until asked for: with them every
    # query for a project also "found" each of its people, and the reverse
    ("details", "related"), ("details", "people"),
    # indexed one entry per publication instead, see publications()
    (None, "data-pub-app"),
    # a person's "E-Mail", "GitHub", "ORCID", a project's "home page",
    # "source"...: link labels, the same for all
    ("div", "contact"), ("span", "contact"),
]
# put where a block starts or ends; not something a page can contain
BREAK = "\x00"
NOT_TEXT = {"script", "style", "noscript", "template"}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "source", "track", "wbr"}
HEADING = re.compile(r"h[1-6]$")
# an element that ends a run of words: "DataLad</h2><div>Software" is two
BLOCK = {"address", "article", "aside", "blockquote", "br", "dd", "details",
         "div", "dl", "dt", "figcaption", "figure", "footer", "h1", "h2",
         "h3", "h4", "h5", "h6", "header", "hr", "li", "main", "nav", "ol",
         "p", "pre", "section", "summary", "table", "td", "th", "tr", "ul"}


def pages(out):
    """(file, address) for every page of the site, addressed as it is linked."""
    for path in sorted(out.rglob("*.html")):
        rel = path.relative_to(out)
        if rel.parts[0] in NOT_PAGES:
            continue
        if rel.name == "index.html":
            yield path, "/" + "".join(p + "/" for p in rel.parts[:-1])
        else:
            yield path, "/" + rel.with_suffix("").as_posix()


class Sections(HTMLParser):
    """A page as [id or None, title, text]: the page itself, then every
    stretch under a heading that has an id."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.sections = [[None, "", []]]
        self.open = []            # the elements we are inside of
        self.ignored = None       # depth of the element being left out
        self.heading = None       # depth of the id'd heading being read
        self.in_title = False     # the first <title>; an <svg> may have one
        self.titled = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "title" and not self.titled:
            self.in_title = self.titled = True
        if tag not in VOID:
            self.open.append(tag)
        if self.ignored is not None:
            return
        if self.heading is not None and tag in BLOCK:
            self.sections[-1][1] += " "       # "Foo<br>Bar" is two words
        # a logo is the only mention of many a lab or partner
        if tag == "img" and attrs.get("alt"):
            self.handle_data(f" {attrs['alt']} ")
        classes = (attrs.get("class") or "").split()
        if (tag in NOT_TEXT or "data-search-ignore" in attrs
                or any((t is None and c in attrs) or (t == tag and c in classes)
                       for t, c in EXCLUDE)):
            if tag not in VOID:
                self.ignored = len(self.open)
            return
        if tag in BLOCK:
            self.sections[-1][2].append(BREAK)
        if HEADING.match(tag) and attrs.get("id"):
            self.sections.append([attrs["id"], "", []])
            self.heading = len(self.open)

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        # Pages are not all well-formed (a stray </br>, an unclosed <p>):
        # an end tag closes the nearest such element, or nothing -- and
        # inside what is left out, nothing outside of it, or a stray </p>
        # there would end the leaving out.
        inside = (self.open if self.ignored is None
                  else self.open[self.ignored - 1:])
        if tag not in inside:
            return
        while self.open.pop() != tag:
            pass
        if self.ignored is not None and len(self.open) < self.ignored:
            self.ignored = None
        if self.heading is not None and len(self.open) < self.heading:
            self.heading = None
        if tag in BLOCK and self.ignored is None:
            self.sections[-1][2].append(BREAK)

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        elif self.ignored is None:
            if self.heading is not None:
                self.sections[-1][1] += data
            else:
                self.sections[-1][2].append(data)


def tidy(text):
    """One line, its blocks set apart."""
    blocks = (" ".join(b.split()) for b in text.split(BREAK))
    return " · ".join(b for b in blocks if b)


def sections(page_html, url, kinds):
    """The entries of one page."""
    parser = Sections()
    parser.feed(page_html)
    parser.close()
    page = " ".join(parser.title.split())
    for anchor, title, text in parser.sections:
        text = tidy("".join(text))
        if anchor is None:
            yield {"u": url, "t": page, "k": "page", "x": text}
        else:
            address = f"{url}#{anchor}"
            yield {"u": address, "t": " ".join(title.split()), "p": page,
                   "k": kinds.get(address, "section"), "x": text}


def publications(data):
    """The entry of every publication in publications.json."""
    for pub in data.get("publications", []):
        if not pub.get("title"):
            continue
        authors = ", ".join(a[0] if a else "…"
                            for a in pub.get("authors") or [])
        about = [authors, pub.get("venue") or "", str(pub.get("year") or "")]
        yield {"u": pub.get("url")
               # one without an address of its own: the list, narrowed to it
               or "/publications?q=" + urllib.parse.quote(pub["title"]),
               "t": pub["title"],
               # as the site labels it: a paper not (yet) published is a preprint
               "k": "preprint" if pub.get("preprint") else pub.get("type") or "paper",
               "x": " · ".join(p for p in about if p)}


def node_kinds(graph):
    """Address on this site -> the type of the graph node that links there."""
    kinds = {}
    for node in graph.get("nodes", []):
        for link in node.get("links", []):
            href = link.get("href") or ""
            if link.get("k") == "con" and href.startswith("/"):
                kinds.setdefault(href, node["type"])
    return kinds


def build(out, pubs_json, graph_json):
    """Every entry of the site at `out`."""
    kinds = {}
    if graph_json.is_file():
        kinds = node_kinds(json.loads(graph_json.read_text(encoding="utf-8")))
    entries = []
    for path, url in pages(out):
        entries += sections(path.read_text(encoding="utf-8"), url, kinds)
    n_sections = len(entries)
    if pubs_json.is_file():
        entries += publications(json.loads(pubs_json.read_text(encoding="utf-8")))
    return entries, n_sections


def index_site(pelican):
    out = pathlib.Path(pelican.settings["OUTPUT_PATH"])
    theme = pathlib.Path(pelican.settings["THEME"])
    entries, n_sections = build(
        out, theme / "static" / "data" / "publications.json",
        pathlib.Path(pelican.settings["PATH"]) / "graph" / "graph.json")
    target = out / "search.json"
    target.write_text(
        json.dumps(entries, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8")
    print(f"Search index: {n_sections} sections of pages, "
          f"{len(entries) - n_sections} publications -> {target} "
          f"({target.stat().st_size // 1024} kB)")


def register():
    signals.finalized.connect(index_site)
