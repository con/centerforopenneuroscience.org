/* SPDX-License-Identifier: MIT
 *
 * The search box: the magnifier in the navbar (any [data-con-search]), or
 * "/" or Ctrl/Cmd+K, opens #con-search (base.html).
 *
 * Nothing is fetched until it is first opened.  Then MiniSearch
 * (theme/vendor/minisearch/) and search.json are: every heading of the site
 * that can be linked to and every publication, one entry each, written by
 * plugins/con_search.py when the site is built (the entries' keys are
 * explained there).  The search runs here, in the browser, on every
 * keystroke; no query leaves it.
 */
(function () {
  "use strict";

  // Where the site lives, from where this file was loaded: a PR preview is
  // served from /centerforopenneuroscience.org/pr-preview/pr-N/, where
  // "/search.json" is a 404 -- only href= and src= attributes are rewritten
  // for it (scripts/rewrite_preview_paths.py).
  var script = document.currentScript;
  var ROOT = new URL((script && script.src || "/theme/js/con-search.js")
                     .replace(/theme\/js\/con-search\.js.*$/, ""),
                     window.location.href);
  var SHOWN = 30;                 // hits listed; the rest are counted
  var AROUND = 90;                // characters of text either side of a match
  // what an entry is called; a publication's kinds are styled by site.css
  // (.pub-type-*) as on the rest of the site
  var KIND = { page: "page", section: "section", person: "person",
               project: "project", instrument: "software",
               organization: "group", objective: "objective",
               paper: "paper", preprint: "preprint", talk: "talk",
               poster: "poster", dataset: "dataset" };

  var $modal = $("#con-search"),
      input = document.getElementById("con-search-input"),
      status = document.getElementById("con-search-status"),
      list = document.getElementById("con-search-hits");
  var entries = null, index = null, loading = null;

  function loadScript(src) {
    return new Promise(function (resolve, reject) {
      var el = document.createElement("script");
      el.src = src;
      el.onload = resolve;
      el.onerror = function () { reject(new Error("could not load " + src)); };
      document.head.appendChild(el);
    });
  }

  function load() {
    loading = loading || Promise.all([
      loadScript(ROOT + "theme/vendor/minisearch/minisearch.js"),
      fetch(ROOT + "search.json").then(function (r) {
        if (!r.ok) throw new Error("search.json: " + r.status);
        return r.json();
      })
    ]).then(function (got) {
      entries = got[1];
      index = new window.MiniSearch({
        idField: "i",
        fields: ["t", "x"],
        searchOptions: {
          // every word has to be there; the last may still be being typed,
          // and a longer one may be a letter off
          combineWith: "AND",
          prefix: true,
          fuzzy: function (term) { return term.length > 4 ? 0.2 : 0; },
          boost: { t: 3 },
          // The site's own people and projects before what they wrote: a
          // publication is one line, which scores a word in it highly.
          boostDocument: function (id) {
            var k = entries[id].k;
            return k === "page" || k === "section" ? 1.5
                 : k === "person" || k === "project" || k === "objective" ? 2
                 : 1;
          }
        }
      });
      index.addAll(entries.map(function (e, i) {
        return { i: i, t: e.t, x: e.x };
      }));
    }).catch(function (err) {
      loading = null;                       // may be retried on the next opening
      status.textContent = "The search could not be loaded (" + err.message + ").";
      throw err;
    });
    return loading;
  }

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text) e.textContent = text;
    return e;
  }

  // `text` into `parent` with every word that was matched marked.  `terms`
  // are the words of the entry that matched, not the ones typed: "repro"
  // finds "reproducible", and that is what gets marked.
  function marked(parent, text, terms) {
    var at = 0, m, re = terms.length && new RegExp(
        "(?:^|[^\\p{L}\\p{N}])(" + terms.map(function (t) {
          return t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
        }).join("|") + ")(?![\\p{L}\\p{N}])", "giu");
    while (re && (m = re.exec(text))) {
      var start = m.index + m[0].length - m[1].length;
      parent.appendChild(document.createTextNode(text.slice(at, start)));
      parent.appendChild(el("mark", "", m[1]));
      at = start + m[1].length;
      re.lastIndex = at;
    }
    parent.appendChild(document.createTextNode(text.slice(at)));
    return at > 0;
  }

  // the part of a text around its first match, cut at word boundaries
  function excerpt(text, terms) {
    var lower = text.toLowerCase(), first = -1;
    terms.forEach(function (t) {
      var i = lower.search(new RegExp(
          "(?:^|[^\\p{L}\\p{N}])" + t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "u"));
      if (i >= 0 && (first < 0 || i < first)) first = i;
    });
    if (text.length <= 2 * AROUND) return text;
    var from = Math.max(0, first - AROUND), to = Math.min(text.length, from + 2 * AROUND);
    if (from > 0) from = text.indexOf(" ", from) + 1;
    if (to < text.length) to = text.lastIndexOf(" ", to);
    return (from > 0 ? "… " : "") + text.slice(from, to) +
           (to < text.length ? " …" : "");
  }

  function address(u) {
    return /^[a-z]+:/i.test(u) ? u : ROOT.pathname + u.replace(/^\//, "");
  }

  function hit(found) {
    var e = entries[found.id], li = el("li"),
        a = el("a", "con-search-hit");
    a.href = address(e.u);
    a.appendChild(el("span", "pub-type pub-type-" + e.k, KIND[e.k] || e.k));
    a.appendChild(document.createTextNode(" "));
    marked(a.appendChild(el("span", "con-search-title")), e.t, found.terms);
    if (e.p) a.appendChild(el("span", "con-search-page", e.p));
    if (e.x) {
      marked(a.appendChild(el("span", "con-search-text")),
             excerpt(e.x, found.terms), found.terms);
    }
    li.appendChild(a);
    return li;
  }

  function search() {
    var q = input.value.trim();
    list.textContent = "";
    if (!index || !q) {
      status.textContent = "";
      return;
    }
    var found = index.search(q);
    status.textContent = !found.length ? "Nothing found for “" + q + "”."
        : found.length === 1 ? "1 result"
        : found.length > SHOWN ? "The first " + SHOWN + " of " + found.length + " results"
        : found.length + " results";
    found.slice(0, SHOWN).forEach(function (f) { list.appendChild(hit(f)); });
    list.scrollTop = 0;
  }

  function open() {
    $modal.modal("show");
    input.focus();
    load().then(search, function () {});
  }

  $(document).on("click", "[data-con-search]", function (e) {
    e.preventDefault();
    // the collapsed (phone) menu would stay open behind the box
    $(".navbar-collapse.in").collapse("hide");
    open();
  });
  $modal.on("shown.bs.modal", function () { input.focus(); input.select(); });
  // or the hidden field keeps the focus for a moment, and a "/" pressed
  // right after Escape counts as typed into it
  $modal.on("hide.bs.modal", function () { input.blur(); });
  input.addEventListener("input", search);

  $(document).on("keydown", function (e) {
    var t = e.target, typing = t && (t.isContentEditable ||
        /^(input|textarea|select)$/i.test(t.tagName));
    if ((e.key === "/" && !typing && !e.ctrlKey && !e.metaKey && !e.altKey) ||
        (e.key.toLowerCase() === "k" && (e.ctrlKey || e.metaKey) && !e.altKey)) {
      e.preventDefault();
      open();
    }
  });

  // Down and Up walk the hits from the field and back; Enter in the field
  // opens the first.
  $modal.on("keydown", function (e) {
    var hits = Array.prototype.slice.call(list.querySelectorAll("a")),
        at = hits.indexOf(document.activeElement);
    if (e.key === "ArrowDown" && hits.length) {
      e.preventDefault();
      hits[Math.min(at + 1, hits.length - 1)].focus();
    } else if (e.key === "ArrowUp" && at >= 0) {
      e.preventDefault();
      (at ? hits[at - 1] : input).focus();
    } else if (e.key === "Enter" && e.target === input && hits.length) {
      e.preventDefault();
      hits[0].click();
    }
  });

  // A hit on the page being read does not load anything, so nothing would
  // close the box; and the jump has to clear the fixed navbar the way every
  // other in-page jump does (scroll_if_anchor, base.html).
  $modal.on("click", "a[href]", function (e) {
    var to = new URL(this.href, window.location.href);
    var same = to.origin === window.location.origin && to.hash &&
        to.pathname.replace(/\.html$/, "") ===
        window.location.pathname.replace(/\.html$/, "");
    if (e.ctrlKey || e.metaKey || e.shiftKey || e.which === 2) return;
    $modal.modal("hide");
    if (same && window.scroll_if_anchor) {
      e.preventDefault();
      window.scroll_if_anchor(to.hash);
    }
  });
})();
