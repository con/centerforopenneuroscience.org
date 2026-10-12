#!/usr/bin/env python3
"""`pelican.server` with a charset on the Content-Type it serves.

Python's SimpleHTTPRequestHandler sends `Content-Type: text/html` and no
charset, and `pelican.server` does not add one.  A browser falls back to the
document's own `<meta charset="utf-8">`, so the site looks right -- but a
tool that fetches over HTTP and believes the header decodes UTF-8 as
Latin-1, which is what turned "Software - since 2013" into "Software A-
since 2013" and an em dash into "a" throughout a site-diff report.  The
pages were never wrong; the header was incomplete.

Everything else, including the clean-URL handling that makes /projects work
without the .html, is pelican's.  Usage: devserver.py [PORT] [--path DIR]
"""
import argparse
import os
import sys

from pelican.server import ComplexHTTPRequestHandler, RootedHTTPServer

# Every text format this site serves is UTF-8, because that is what the
# generators write.  Binary types are left alone.
TEXTUAL = {"text/html", "text/plain", "text/css", "text/csv", "text/xml",
           "application/javascript", "application/json", "application/xml",
           "image/svg+xml"}


class UTF8Handler(ComplexHTTPRequestHandler):
    def guess_type(self, path):
        t = super().guess_type(path)
        return f"{t}; charset=utf-8" if t in TEXTUAL else t


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("port", nargs="?", default=8000, type=int)
    ap.add_argument("--path", default=os.curdir)
    ap.add_argument("--server", default="")
    a = ap.parse_args(argv)
    RootedHTTPServer.allow_reuse_address = True
    httpd = RootedHTTPServer(a.path, (a.server, a.port), UTF8Handler)
    print(f"serving {os.path.abspath(a.path)} on port {a.port} (utf-8)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.socket.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
