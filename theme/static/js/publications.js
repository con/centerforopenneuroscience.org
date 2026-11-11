/* Publications: search and filter con-site-specific's publication records.
 *
 * scripts/render_publications.py --json writes every record, newest first,
 * to /theme/data/publications.json.  This fetches it once per browser
 * session and answers filters over it:
 *
 *   CONPublications.filter(data, {q, type, year, project, person})
 *
 * where q is free text (every word must occur in the title, authors, venue,
 * year or project names; case and accents ignored), type is paper, poster
 * or talk, year is 2020, 2015-2020, 2015- or -2005, and project and person
 * are the slugs of their records (datalad, yaroslav-halchenko).
 *
 * Two uses on the site, both wired up on page load:
 *   - <div data-pub-app> becomes the whole searchable listing, its filters
 *     kept in the address (/publications?project=datalad&type=talk) so a
 *     filtered view can be linked to;
 *   - <details data-pub-filter="project=datalad"> fills its .pub-slot with
 *     the matching entries the first time it is opened, so a page with many
 *     such lists fetches nothing until someone asks for one.
 * Without JavaScript the page keeps whatever static markup it carries.
 */
(function (root) {
  "use strict";

  var SRC = "/theme/data/publications.json";
  var FIELDS = ["q", "type", "year", "project", "person"];
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
      (e.authors || []).forEach(function (a) { bits.push(a[0]); });
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

  /* -- markup ---------------------------------------------------------- */

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c];
    });
  }

  function link(label, href) {
    return href ? '<a href="' + esc(href) + '">' + esc(label) + "</a>" : esc(label);
  }

  /* the same markup as render_publications.py's static list */
  function entry(e, data) {
    var bits = ['<span class="pub-title">' + link(e.title, e.url) + "</span>"];
    var names = e.authors.map(function (a) { return link(a[0], a[1]); }).join(", ");
    if (names && !e.authors_complete) names = "Authors include " + names;
    var meta = [names, e.venue ? esc(e.venue) : "", e.year].filter(Boolean);
    if (e.pdf) meta.push(link("PDF", e.pdf));
    if (e.video) meta.push(link("video", e.video));
    if (meta.length) bits.push('<span class="pub-meta">' + meta.join(" &#183; ") + "</span>");
    if (e.projects.length) {
      bits.push('<span class="pub-projects">Projects: ' + e.projects.map(function (p) {
        return link(data.projects[p][0], data.projects[p][1]);
      }).join(", ") + "</span>");
    }
    return "<li>" + bits.join(" ") + "</li>";
  }

  /* one line each, for the lists under a project or a person */
  function brief(e, data) {
    var note = [e.year, e.type === "paper" ? "" : e.type].filter(Boolean).join(", ");
    return "<li>" + link(e.title, e.url)
      + (note ? " <small>(" + esc(note) + ")</small>" : "") + "</li>";
  }

  function list(rows, data, opts) {
    opts = opts || {};
    var one = opts.brief ? brief : entry;
    if (!opts.grouped) {
      return '<ul class="publication-list">'
        + rows.map(function (e) { return one(e, data); }).join("") + "</ul>";
    }
    return Object.keys(data.types).map(function (t) {
      var mine = rows.filter(function (e) { return e.type === t; });
      return mine.length ? "<h2>" + esc(data.types[t]) + " <small>" + mine.length
        + "</small></h2>" + list(mine, data, {brief: opts.brief}) : "";
    }).join("");
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

  function counted(data, key, label) {
    var n = {};
    data.publications.forEach(function (e) {
      (e[key] || []).forEach(function (k) { n[k] = (n[k] || 0) + 1; });
    });
    return Object.keys(n).map(function (k) {
      return [k, label(k) + " (" + n[k] + ")"];
    }).sort(function (a, b) { return fold(a[1]) < fold(b[1]) ? -1 : 1; });
  }

  function mount(el) {
    var f = parse(root.location.search);
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
        + '<button type="reset" class="btn btn-default btn-sm">Clear</button>'
        + "</form>"
        + '<p class="pub-count" aria-live="polite"></p><div class="pub-results"></div>';
      var form = el.querySelector("form"), timer;
      var count = el.querySelector(".pub-count"), results = el.querySelector(".pub-results");

      function update() {
        FIELDS.forEach(function (k) { f[k] = form.elements[k].value.trim(); });
        var q = query(f), rows = filter(data, f);
        root.history.replaceState(null, "", root.location.pathname + (q ? "?" + q : ""));
        count.textContent = rows.length === data.publications.length
          ? rows.length + " publications"
          : rows.length + " of " + data.publications.length + " publications";
        results.innerHTML = rows.length ? list(rows, data, {grouped: !f.type})
          : '<p class="pub-status">None match.</p>';
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

  var api = {load: load, filter: filter, parse: parse, query: query, render: render,
             mount: mount, init: init};
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
