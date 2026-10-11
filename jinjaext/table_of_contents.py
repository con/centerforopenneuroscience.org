from xml.etree import ElementTree
from string import punctuation

class TableOfContents:

    hooks_taken = []

    @staticmethod
    def parse_hook_from_text(text):

        hook = text.strip().replace(" ", "_").lower()
        hook = hook.replace("/:", ":").replace("/", ":")
        hook = hook.replace(":", "_")

        for token in punctuation.replace("_", ""):
            hook = hook.replace(token, "")

        if ( hook.startswith("_") ):
            hook = hook[1:]
        if ( hook.endswith("_") ):
            hook = hook[:-1]

        return hook

    @staticmethod
    def produce_new_hook(text):

        hook_base = TableOfContents.parse_hook_from_text(text)
        hook = hook_base + "_"
        hook_id = 2
        while (hook in TableOfContents.hooks_taken):

            hook = hook_base + "_" + str(hook_id)
            hook_id += 1

        TableOfContents.hooks_taken.append(hook)
        return hook

    @staticmethod
    def consume_existing_hook(text):

        hook = TableOfContents.parse_hook_from_text(text)
        hook += "_"
        stub_hooks = list(map(lambda x: x[:x.rfind("_")], TableOfContents.hooks_taken))

        if hook[:hook.rfind("_")] in stub_hooks:

            hook_at = stub_hooks.index(hook[:hook.rfind("_")])
            hook = TableOfContents.hooks_taken[hook_at]

        TableOfContents.hooks_taken.remove(hook)
        return hook

    @staticmethod
    def extractTableOfContentsInfo(content, active_page):

        hooks_taken = []

        try:
            root = ElementTree.fromstring("<root>"+content+"</root>")
        except ElementTree.ParseError as e:
            print("Error while extracting ToC from content")
            print("Could not parse page: %s" % active_page)
            print("The problem: " + str(e))
            if e.position:
                lines = ("<root>" + content).splitlines()
                line_no, col_no = e.position
                if 0 < line_no <= len(lines):
                    bad_line = lines[line_no - 1]
                    print("  Offending line %d, col %d:" % (line_no, col_no))
                    print("  " + bad_line)
                    print("  " + " " * (col_no - 1) + "^")
            return None
        except Exception as e:
            print("Error while extracting ToC from content")
            print("Something unexpected happened while parsing page: %s" % active_page)
            print("The problem: " + str(e))
            return None

        toc_info = []

        def process(element):

            if ( ( element.tag == 'h1'
              or element.tag == 'h2'
                          or element.tag == 'h3' )
                          and element.attrib.get("data-hidden-from-toc", "false") != "true" ):
                toc_info.append({
                    'tag' : element.tag,
                    'text' : element.text,
                    'hook' : TableOfContents.produce_new_hook(element.text)
                })

            for child in element:
                process(child)

        process(root)
        return toc_info

    @staticmethod
    def createTableOfContents(toc_info):
        """Build the sidebar as a properly nested list.

        The previous version closed each h1's <li> at the bottom of the loop,
        so the <ul> opened by the following h2 landed OUTSIDE that <li> -- a
        sibling of the section rather than its children.  With one h1 the
        page looked fine; with seven, only the first section had browsing
        items and every later section's entries appeared at the wrong depth.
        It also emitted </ul> before </li> when a section ended, which is not
        well-formed.

        Written as an explicit depth stack instead, so the nesting cannot
        drift out of step with the closers.
        """
        if toc_info is None:
            return ""
        if not toc_info:
            return ""

        LEVEL = {"h1": 1, "h2": 2, "h3": 3}
        # Depth is RELATIVE to the shallowest heading on the page, because
        # not every page starts at h1: projects.html uses h1 sections with h2
        # entries, whoweare.html uses h2 tiers with h3 people.  Treating the
        # tag as an absolute depth put a <ul> directly inside a <ul> on any
        # page that did not start at h1.
        base = min(LEVEL.get(it["tag"], 2) for it in toc_info)
        out = ["<ul class='nav bs-docs-sidenav'>"]
        open_li = 0          # how many <li> are currently open
        depth = 0            # how many <ul> are currently open, beyond the first
        first = True

        for item in toc_info:
            want = LEVEL.get(item["tag"], 2) - base
            while depth > want:
                out.append("</li>")
                out.append("</ul>")
                depth -= 1
                open_li -= 1
            if depth < want:
                # a heading deeper than its predecessor opens a nested list
                # INSIDE the still-open <li>, which is the whole point
                while depth < want:
                    out.append("<ul class='nav'>")
                    depth += 1
            elif not first:
                out.append("</li>")
                open_li -= 1
            cls = " class='active'" if first else ""
            out.append("<li%s>" % cls)
            open_li += 1
            out.append("<a href='#%s' data-scroll data-url>%s</a>"
                       % (item["hook"], item["text"]))
            first = False

        while depth > 0:
            out.append("</li>")
            out.append("</ul>")
            depth -= 1
            open_li -= 1
        if open_li > 0:
            out.append("</li>")
        out.append("</ul>")
        return "".join(out)

    @staticmethod
    def addTableOfContentsHooks(content, toc_info, active_page):

        if ( toc_info == None ):
            return content

        try:
            root = ElementTree.fromstring("<root>"+content+"</root>")
        except ElementTree.ParseError as e:
            print("Error while adding ToC hooks to content")
            print("Could not parse page: %s" % active_page)
            print("The problem: " + str(e))
            return content
        except Exception as e:
            print("Error while adding ToC hooks to content")
            print("Something unexpected happened while parsing page: %s" % active_page)
            print("The problem: " + str(e))
            return content

        def process(element):

            if ( ( element.tag == 'h1'
              or element.tag == 'h2'
                          or element.tag == 'h3' )
                          and element.attrib.get("data-hidden-from-toc", "false") != "true" ):
                element.attrib["id"] = TableOfContents.consume_existing_hook(element.text)

            for child in element:
                process(child)

        process(root)

        content = ElementTree.tostring(root, method="html", encoding="unicode")
        content = content.replace("<root>", "").replace("</root>", "")
        return content
