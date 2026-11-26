/* SPDX-License-Identifier: MIT
 *
 * The search box: the magnifier in the navbar (any [data-con-search]), or
 * "/" or Ctrl/Cmd+K, opens #con-search (base.html) with Pagefind's UI in it.
 *
 * Nothing is fetched until it is first opened.  Then Pagefind's UI and, as
 * someone types, the chunks of the index a query needs are loaded from
 * pagefind/, which plugins/con_search.py writes when the site is built.
 * The search runs here, in the browser; no query leaves it.
 */
(function () {
  "use strict";

  // Where the site lives, from where this file was loaded: a PR preview is
  // served from /centerforopenneuroscience.org/pr-preview/pr-N/, where
  // "/pagefind/" is a 404 -- only href= and src= attributes are rewritten
  // for it (scripts/rewrite_preview_paths.py).
  var script = document.currentScript;
  var ROOT = new URL((script && script.src || "/theme/js/con-search.js")
                     .replace(/theme\/js\/con-search\.js.*$/, ""),
                     window.location.href);
  var $modal = $("#con-search"), box = document.getElementById("con-search-box");
  var loading = null, styles = null, opener = null;

  function add(tag, attrs) {
    return new Promise(function (resolve, reject) {
      var el = document.createElement(tag);
      for (var k in attrs) el[k] = attrs[k];
      el.onload = resolve;
      el.onerror = function () { reject(new Error("could not load " + (attrs.src || attrs.href))); };
      document.head.appendChild(el);
    });
  }

  // Pagefind names a page by its file (/projects.html, /explore/); the site
  // links them without the suffix.  A publication's record is a page that
  // exists only in the index and says where it leads in its `href`.
  function address(url, meta) {
    if (meta && meta.href) {
      return /^[a-z]+:/i.test(meta.href) ? meta.href
           : ROOT.pathname + meta.href.replace(/^\//, "");
    }
    return url.replace(/\.html(?=$|[?#])/, "");
  }

  function load() {
    styles = styles || Promise.all([
      add("link", { rel: "stylesheet", href: ROOT + "pagefind/pagefind-ui.css" }),
      add("link", { rel: "stylesheet", href: ROOT + "theme/css/con-search.css" })
    ]).catch(function () { /* unstyled is still usable */ });
    loading = loading || Promise.all([
      add("script", { src: ROOT + "pagefind/pagefind-ui.js" }), styles
    ]).then(function () {
      box.textContent = "";                 // the message of a failed attempt
      new window.PagefindUI({
        element: box,
        bundlePath: ROOT.pathname + "pagefind/",
        baseUrl: ROOT.pathname,
        showImages: false,
        showSubResults: true,
        pageSize: 8,
        // A page here is long and holds many things; a publication's record
        // is one line.  Scored as Pagefind does by default, a word in a
        // short record outweighs a page that is about it.
        ranking: { pageLength: 0, termSaturation: 2 },
        translations: { placeholder: "Search people, projects, publications…" },
        processResult: function (result) {
          result.url = address(result.url, result.meta);
          (result.sub_results || []).forEach(function (sub) {
            sub.url = address(sub.url, result.meta);
          });
          // the UI lists whatever else a record carries under the hit
          delete result.meta.href;
          return result;
        }
      });
    }).catch(function (err) {
      loading = null;                       // may be retried on the next opening
      box.textContent = "The search could not be loaded (" + err.message + ").";
    });
    return loading;
  }

  function input() { return box.querySelector("input"); }

  function open() {
    if (!$modal.hasClass("in")) opener = document.activeElement;
    $modal.modal("show");
    load().then(function () { if (input()) input().focus(); });
  }

  $(document).on("click", "[data-con-search]", function (e) {
    e.preventDefault();
    // the collapsed (phone) menu would stay open behind the box
    $(".navbar-collapse.in").collapse("hide");
    open();
  });
  $modal.on("shown.bs.modal", function () { if (input()) input().focus(); });
  // back to where the reader was: Bootstrap 3 only does this for boxes
  // opened by data-toggle
  $modal.on("hidden.bs.modal", function () {
    if (opener && opener.focus && document.contains(opener)) opener.focus();
    opener = null;
  });

  $(document).on("keydown", function (e) {
    var t = e.target, typing = t && (t.isContentEditable ||
        /^(input|textarea|select)$/i.test(t.tagName));
    // a keydown may come without a key: Chrome sends one when an autofill
    // entry is chosen, as in the filter of /publications
    var key = e.key || "";
    if ((key === "/" && !typing && !e.ctrlKey && !e.metaKey && !e.altKey) ||
        (key.toLowerCase() === "k" && (e.ctrlKey || e.metaKey) && !e.altKey)) {
      e.preventDefault();
      open();
    }
  });

  // Escape closes the box.  Bootstrap would, but only while the focus is
  // inside it, and Pagefind's field answers Escape by clearing itself and
  // letting go of the focus -- after which nothing was listening.
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && $modal.hasClass("in")) $modal.modal("hide");
  }, true);

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
