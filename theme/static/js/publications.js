/* Publications: search and filter con-site-specific's publication records.
 *
 * scripts/render_publications.py --json writes every record, newest first,
 * to /theme/data/publications.json.  This fetches it once per browser
 * session and answers filters over it:
 *
 *   CONPublications.filter(data, {q, type, year, project, person})
 *
 * where q is free text (every word must occur in the title, authors, venue,
 * year or project names, or "preprint"; case and accents ignored), type is
 * paper, poster, talk or dataset, year is 2020, 2015-2020, 2015- or -2005,
 * and project, person and objective are the slugs of their records
 * (datalad, yaroslav-halchenko, open-science).  A publication serves the objectives it names and those of
 * the projects behind it.
 *
 * render(el, f, {group: ["type", "year"]}) puts the matches under headings,
 * one level per key, and returns those groups -- what sidebar() turns into
 * the same left-hand menu the projects page gets from its headings.
 *
 * Two uses on the site, both wired up on page load:
 *   - <div data-pub-app> becomes the whole searchable listing, grouped by
 *     type and then year with the sidebar to match, its filters kept in the
 *     address (/publications?project=datalad&type=talk) so a filtered view
 *     can be linked to;
 *   - <details data-pub-filter="project=datalad"> fills its .pub-slot with
 *     the matching entries the first time it is opened, so a page with many
 *     such lists fetches nothing until someone asks for one.
 * Without JavaScript the page keeps whatever static markup it carries.
 */
(function (root) {
  "use strict";

  // the data's version, a hash pelicanconf.py puts on the <script> tag: the
  // cache key and the URL change whenever the publications do
  var VERSION = (root.document && root.document.currentScript
                 && root.document.currentScript.getAttribute("data-version")) || "";
  var SRC = "/theme/data/publications.json" + (VERSION ? "?v=" + VERSION : "");
  var FIELDS = ["q", "type", "year", "project", "person", "objective"];
  var loading = {};

  /* -- data ------------------------------------------------------------ */

  function load(src) {
    src = src || SRC;
    if (!loading[src]) {
      loading[src] = fromSession(src).then(function (cached) {
        return cached || root.fetch(src).then(function (r) {
          if (!r.ok) throw new Error(src + ": HTTP " + r.status);
          return r.text();
        }).then(function (text) {
          try { root.sessionStorage.setItem(src, text); } catch (e) { /* full or blocked */ }
          return JSON.parse(text);
        });
      });
      // a failed fetch may be retried on the next call
      loading[src].catch(function () { delete loading[src]; });
    }
    return loading[src];
  }

  function fromSession(src) {
    var text = null;
    try { text = root.sessionStorage.getItem(src); } catch (e) { /* blocked */ }
    try { return Promise.resolve(text && JSON.parse(text)); }
    catch (e) { return Promise.resolve(null); }
  }

  /* -- filtering ------------------------------------------------------- */

  function fold(s) {
    return String(s || "").normalize("NFKD").replace(/[̀-ͯ]/g, "")
      .toLowerCase();
  }

  function haystack(e, data) {
    if (e._hay === undefined) {
      var bits = [e.title, e.venue, e.year, (data.types || {})[e.type]];
      if (e.preprint) bits.push("preprint");
      (e.authors || []).forEach(function (a) { if (a) bits.push(a[0]); });
      (e.projects || []).forEach(function (p) {
        bits.push(p, (data.projects[p] || [])[0]);
      });
      Object.defineProperty(e, "_hay", {value: fold(bits.join(" "))});
    }
    return e._hay;
  }

  function inYears(year, spec) {
    var m = /^\s*(\d{4})?\s*(-)?\s*(\d{4})?\s*$/.exec(spec || "");
    if (!m || !(m[1] || m[3])) return true;
    if (!year) return false;
    var lo = m[1] || "0000", hi = m[2] ? (m[3] || "9999") : lo;
    return year >= lo && year <= hi;
  }

  function filter(data, f) {
    f = f || {};
    var words = fold(f.q).split(/\s+/).filter(Boolean);
    return data.publications.filter(function (e) {
      if (f.type && e.type !== f.type) return false;
      if (f.project && e.projects.indexOf(f.project) < 0) return false;
      if (f.person && e.people.indexOf(f.person) < 0) return false;
      if (f.objective && (e.objectives || []).indexOf(f.objective) < 0) return false;
      if (f.year && !inYears(e.year, f.year)) return false;
      if (words.length) {
        var hay = haystack(e, data);
        for (var i = 0; i < words.length; i++) {
          if (hay.indexOf(words[i]) < 0) return false;
        }
      }
      return true;
    });
  }

  function parse(query) {
    var f = {};
    String(query || "").replace(/^\?/, "").split("&").forEach(function (kv) {
      var i = kv.indexOf("="), k = decodeURIComponent(kv.slice(0, i < 0 ? kv.length : i));
      if (FIELDS.indexOf(k) >= 0 && i >= 0) {
        f[k] = decodeURIComponent(kv.slice(i + 1).replace(/\+/g, " "));
      }
    });
    return f;
  }

  function query(f) {
    return FIELDS.filter(function (k) { return f[k]; }).map(function (k) {
      return k + "=" + encodeURIComponent(f[k]);
    }).join("&");
  }

  /* -- grouping -------------------------------------------------------- */

  /* key -> what an entry's value is, how it is labelled, how values sort */
  var GROUPS = {
    type: {of: function (e) { return e.type; },
           label: function (v, data) { return data.types[v]; },
           order: function (vs, data) {
             var o = Object.keys(data.types);
             return vs.sort(function (a, b) { return o.indexOf(a) - o.indexOf(b); });
           }},
    // newest first; undated last
    year: {of: function (e) { return e.year || ""; },
           label: function (v) { return v || "Undated"; },
           order: function (vs) { return vs.sort().reverse(); }}
  };

  /* rows split by the first key, each part by the rest:
     [{label, id, rows, children}, ...], or null for no keys */
  function group(rows, data, keys, prefix) {
    if (!keys || !keys.length) return null;
    var g = GROUPS[keys[0]], parts = Object.create(null), values = [];
    rows.forEach(function (e) {
      var v = g.of(e);
      if (!parts[v]) { parts[v] = []; values.push(v); }
      parts[v].push(e);
    });
    return g.order(values, data).map(function (v) {
      var id = (prefix || "pub") + "-" + (v || "undated");
      return {label: g.label(v, data), id: id, rows: parts[v],
              children: group(parts[v], data, keys.slice(1), id)};
    });
  }

  /* the theme's sidebar markup, as jinjaext/table_of_contents.py writes it:
     the first level, and under each the second, which the theme's CSS
     shows for the section in view */
  function sidebar(groups) {
    return "<ul class='nav bs-docs-sidenav'>" + groups.map(function (g, i) {
      return "<li" + (i ? "" : " class='active'") + "><a href='#" + esc(g.id) + "'>"
        + esc(g.label) + "</a>" + (g.children ? "<ul class='nav'>"
        + g.children.map(function (c) {
          return "<li><a href='#" + esc(c.id) + "'>" + esc(c.label) + "</a></li>";
        }).join("") + "</ul>" : "") + "</li>";
    }).join("") + "</ul>";
  }

  /* -- markup ---------------------------------------------------------- */

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c];
    });
  }

  function link(label, href) {
    return href ? '<a href="' + esc(href) + '">' + esc(label) + "</a>" : esc(label);
  }

  /* what it is -- paper, poster, talk -- where no heading says so */
  function badge(e) {
    return '<span class="pub-type pub-type-' + esc(e.type) + '">' + esc(e.type) + "</span> ";
  }

  /* a paper not (yet) peer reviewed */
  function preprint(e) {
    return e.preprint ? ' <span class="pub-preprint">preprint</span>' : "";
  }

  /* "(PDF) (📺 CONTube)" after the title, as the Talks site has them, and
     "[PREPRINT] [DATASET]" as YOH's CV has them */
  function alts(e) {
    var out = [];
    if (e.pdf) out.push(["PDF", e.pdf]);
    if (e.video) out.push([(/contube/i.test(e.video) ? "\uD83D\uDCFA CONTube" : "\uD83D\uDCFA video"), e.video]);
    var tags = e.preprint_url ? [["PREPRINT", e.preprint_url]] : [];
    (e.dataset_urls || []).forEach(function (u) { tags.push(["DATASET", u]); });
    return out.map(function (a) {
      return ' (<a class="pub-alt" href="' + esc(a[1]) + '">' + esc(a[0]) + "</a>)";
    }).join("") + tags.map(function (a) {
      return ' <a class="pub-tag" href="' + esc(a[1]) + '">[' + a[0] + "]</a>";
    }).join("");
  }

  /* the same markup as render_publications.py's static list */
  function entry(e, data, typed) {
    var bits = [(typed ? badge(e) : "")
                + '<span class="pub-title">' + link(e.title, e.url) + preprint(e)
                + alts(e) + "</span>"];
    var names = e.authors.map(function (a) {
      return a === null ? "&#8230;" : link(a[0], a[1]);
    }).join(", ");
    if (names && !e.authors_complete) names = "Authors include " + names;
    else if (e.authors.indexOf(null) >= 0) names += " (" + e.authors_count + " authors)";
    var meta = [names, e.venue ? esc(e.venue) : "", e.year].filter(Boolean);
    if (meta.length) bits.push('<span class="pub-meta">' + meta.join(" &#183; ") + "</span>");
    if (e.projects.length) {
      bits.push('<span class="pub-projects">Projects: ' + e.projects.map(function (p) {
        return link(data.projects[p][0], data.projects[p][1]);
      }).join(", ") + "</span>");
    }
    return "<li>" + bits.join(" ") + "</li>";
  }

  /* one line each, for the lists under a project or a person */
  function brief(e, data, typed) {
    return "<li>" + (typed ? badge(e) : "") + link(e.title, e.url) + preprint(e) + alts(e)
      + (e.year ? " <small>(" + esc(e.year) + ")</small>" : "") + "</li>";
  }

  /* opts.group: the keys to put headings for, outermost first (h2, h3, ...);
     opts.brief: one line per entry */
  function list(rows, data, opts) {
    opts = opts || {};
    var keys = opts.group || [], typed = keys.indexOf("type") < 0;
    function ul(rs) {
      return '<ul class="publication-list">' + rs.map(function (e) {
        return (opts.brief ? brief : entry)(e, data, typed);
      }).join("") + "</ul>";
    }
    function walk(groups, level) {
      var h = "h" + Math.min(level, 6);
      return groups.map(function (g) {
        // a link to itself, as the build makes every sidebar heading
        return "<" + h + ' id="' + esc(g.id) + '"><a class="heading-link" href="#'
          + esc(g.id) + '">' + esc(g.label) + "</a> <small>"
          + g.rows.length + "</small></" + h + ">"
          + (g.children ? walk(g.children, level + 1) : ul(g.rows));
      }).join("");
    }
    return keys.length ? walk(group(rows, data, keys), 2) : ul(rows);
  }

  /* Fill el with the entries matching f; resolves to how many there were. */
  function render(el, f, opts) {
    el.innerHTML = '<p class="pub-status">Loading&#8230;</p>';
    return load(opts && opts.src).then(function (data) {
      var rows = filter(data, f);
      el.innerHTML = rows.length ? list(rows, data, opts)
        : '<p class="pub-status">None found.</p>';
      return rows.length;
    }, function (err) {
      el.innerHTML = '<p class="pub-status">Could not load the publications ('
        + esc(err.message) + ").</p>";
      throw err;
    });
  }

  /* -- the searchable listing ------------------------------------------ */

  function options(all, pairs, current) {
    return '<option value="">' + esc(all) + "</option>" + pairs.map(function (p) {
      return '<option value="' + esc(p[0]) + '"' + (p[0] === current ? " selected" : "")
        + ">" + esc(p[1]) + "</option>";
    }).join("");
  }

  /* "3 publications (1 paper, 2 talks)", in the types' own order */
  function summary(rows, data, of) {
    var n = {}, parts = [];
    rows.forEach(function (e) { n[e.type] = (n[e.type] || 0) + 1; });
    Object.keys(data.types).forEach(function (t) {
      if (n[t]) parts.push(n[t] + " " + t + (n[t] === 1 ? "" : "s"));
    });
    var total = of && of !== rows.length ? rows.length + " of " + of : String(rows.length);
    return total + (of === 1 || (!of && rows.length === 1) ? " publication" : " publications")
      + (parts.length ? " (" + parts.join(", ") + ")" : "");
  }

  function counted(data, key, label) {
    var n = {};
    data.publications.forEach(function (e) {
      (e[key] || []).forEach(function (k) { n[k] = (n[k] || 0) + 1; });
    });
    return Object.keys(n).map(function (k) {
      return [k, label(k) + " (" + n[k] + ")"];
    }).sort(function (a, b) { return fold(a[1]) < fold(b[1]) ? -1 : 1; });
  }

  /* The theme's left column holds the sidebar; a page whose headings are
     rendered here has none from the build, so make one.  Scrollspy marks
     the section in view and affix pins it, as on the projects page. */
  function sidebarHost(doc) {
    var col = doc.querySelector(".bs-docs-container .col-md-3");
    if (!col) return null;
    var toc = doc.getElementById("full-toc");
    if (!toc) {
      toc = doc.createElement("div");
      toc.id = "full-toc";
      toc.className = "bs-docs-sidebar hidden-print affix-top hidden-xs hidden-sm";
      toc.setAttribute("role", "complementary");
      col.appendChild(toc);
      if (root.jQuery && root.jQuery.fn.affix) root.jQuery(toc).affix();
    }
    return toc;
  }

  function mount(el, opts) {
    var f = parse(root.location.search);
    var keys = (opts && opts.group) || ["type", "year"];
    var toc = sidebarHost(root.document);
    return load(el.getAttribute("data-pub-src")).then(function (data) {
      var years = [];
      data.publications.forEach(function (e) {
        if (e.year && years.indexOf(e.year) < 0) years.push(e.year);
      });
      years.sort().reverse();
      // a range given in the address (?year=2015-2020) is kept as an option
      if (f.year && years.indexOf(f.year) < 0) years.unshift(f.year);
      el.innerHTML =
        '<form class="pub-filters" role="search">'
        + '<input type="search" name="q" placeholder="Search titles, authors, venues" aria-label="Search" value="' + esc(f.q || "") + '" />'
        + '<select name="type" aria-label="Type">' + options("All types",
            Object.keys(data.types).map(function (t) { return [t, data.types[t]]; }), f.type) + "</select>"
        + '<select name="year" aria-label="Year">' + options("All years",
            years.map(function (y) { return [y, y]; }), f.year) + "</select>"
        + '<select name="project" aria-label="Project">' + options("All projects",
            counted(data, "projects", function (k) { return data.projects[k][0]; }), f.project) + "</select>"
        + '<select name="person" aria-label="Person">' + options("All people",
            counted(data, "people", function (k) { return data.people[k][0]; }), f.person) + "</select>"
        // in the site's own order of objectives, not alphabetical
        + '<select name="objective" aria-label="Objective">' + options("All objectives",
            Object.keys(data.objectives || {}).map(function (k) {
              var n = data.publications.filter(function (e) {
                return (e.objectives || []).indexOf(k) >= 0; }).length;
              return [k, data.objectives[k][0] + " (" + n + ")"];
            }).filter(function (o) { return !/ \(0\)$/.test(o[1]); }), f.objective) + "</select>"
        + '<button type="reset" class="btn btn-default btn-sm">Clear</button>'
        + "</form>"
        + '<p class="pub-count" aria-live="polite"></p><div class="pub-results"></div>';
      var form = el.querySelector("form"), timer;
      var count = el.querySelector(".pub-count"), results = el.querySelector(".pub-results");

      function update() {
        FIELDS.forEach(function (k) { f[k] = form.elements[k].value.trim(); });
        var q = query(f), rows = filter(data, f);
        root.history.replaceState(null, "", root.location.pathname + (q ? "?" + q : ""));
        count.textContent = summary(rows, data, data.publications.length);
        results.innerHTML = rows.length ? list(rows, data, {group: keys})
          : '<p class="pub-status">None match.</p>';
        if (toc) {
          toc.innerHTML = rows.length ? sidebar(group(rows, data, keys)) : "";
          if (root.jQuery && root.jQuery.fn.scrollspy) {
            root.jQuery(root.document.body).scrollspy("refresh");
          }
          // the page changed length under a sidebar placed for the old one:
          // let affix and base.html's footer check look again
          if (root.jQuery) root.jQuery(root).trigger("scroll");
        }
      }
      form.addEventListener("input", function () {
        root.clearTimeout(timer);
        timer = root.setTimeout(update, 120);
      });
      form.addEventListener("change", update);
      form.addEventListener("submit", function (ev) { ev.preventDefault(); update(); });
      // reset clears the fields after this event; select's "selected" would
      // otherwise restore the values the page was opened with
      form.addEventListener("reset", function (ev) {
        ev.preventDefault();
        FIELDS.forEach(function (k) { form.elements[k].value = ""; });
        update();
      });
      update();
      // the headings did not exist when the page tried to land on one
      var target = root.location.hash && root.document.getElementById(root.location.hash.slice(1));
      if (target) root.scrollTo(0, target.getBoundingClientRect().top + root.pageYOffset - 65);
    }, function (err) {
      // keep the static lists; say why there is no search
      el.insertAdjacentHTML("afterbegin", '<p class="pub-status">Search is unavailable: '
        + esc(err.message) + "</p>");
    });
  }

  /* -- wiring ---------------------------------------------------------- */

  function init(doc) {
    Array.prototype.forEach.call(doc.querySelectorAll("[data-pub-app]"), mount);
    Array.prototype.forEach.call(doc.querySelectorAll("details[data-pub-filter]"), function (d) {
      d.addEventListener("toggle", function () {
        if (!d.open || d.getAttribute("data-pub-loaded")) return;
        d.setAttribute("data-pub-loaded", "1");
        render(d.querySelector(".pub-slot"), parse(d.getAttribute("data-pub-filter")),
               {brief: true}).catch(function () { d.removeAttribute("data-pub-loaded"); });
      });
    });
  }

  var api = {load: load, filter: filter, group: group, sidebar: sidebar, summary: summary, parse: parse,
             query: query, render: render, mount: mount, init: init};
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    root.CONPublications = api;
    if (root.document.readyState === "loading") {
      root.document.addEventListener("DOMContentLoaded", function () { init(root.document); });
    } else {
      init(root.document);
    }
  }
})(typeof window !== "undefined" ? window : globalThis);
