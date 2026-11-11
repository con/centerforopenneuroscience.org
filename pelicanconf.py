#!/usr/bin/env python3
# -*- coding: utf-8 -*- #

AUTHOR = 'CON team'
SITENAME = 'CON'
SITEURL = ''

TIMEZONE = 'America/New_York'

DEFAULT_LANG = 'en'

DIRECT_TEMPLATES = ['index']

STATIC_PATHS = [ 'img', 'CNAME' ]

THEME = 'theme'

MARKDOWN = {
    'extension_configs': {
        'markdown.extensions.codehilite': {'css_class': 'highlight'},
        # TODO(asmacdo) I assumed we had to declare fix_code_blocks here, but it doesn't make a change.
        # I also tried deleting the mdext code assuming it wasn't getting used,
        # but that led to the left bar of the /projects page to render incorrectly. I suppose we just leave it.
        # 'markdown.extensions.extra': 'mdext.fix_code_blocks',
    }
}

import hashlib, os, sys
sys.path.append(os.path.join(os.getcwd(), "jinjaext"))
from table_of_contents import TableOfContents as TOC

def publications_version():
    """A hash of the publications' JSON, for publications.js to cache them
    under: a browser keeps them for its session, and without a version a
    rebuilt list (corrected dates, new records) stayed unseen until the tab
    was closed.  A function, called on every render, so `make devserver`
    picks up a re-render without a restart."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "theme", "static", "data", "publications.json")
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:12]
    except OSError:
        return ""


JINJA_GLOBALS = {"publications_version": publications_version}
JINJA_FILTERS = {
    'extract_toc_info' : TOC.extractTableOfContentsInfo,
    'create_toc' : TOC.createTableOfContents,
    'add_toc_hooks' : TOC.addTableOfContentsHooks
}

# GOOGLE_ANALYTICS = "TODO"

PLUGINS = []

# Uncomment following line if you want document-relative URLs when developing
#RELATIVE_URLS = True
