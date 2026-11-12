/* SPDX-License-Identifier: MIT
 *
 * One renderer for every graph on the site.
 *
 * All of them draw from graph/graph.json, CON's graph, written by
 * scripts/render_graph.py.  Another site's graph (Psychoinformatics') is not
 * in that file: when a reader ticks it, its own graph.json is loaded from
 * that site and joined with ours here, so it is as current as that site.
 * A saved copy beside ours (graph/<site>.json) is used only when the site
 * cannot be reached.
 *
 * A graph on a page is that data seen through a filter -- which sources,
 * how far from which root -- declared in the markup:
 *
 *   <div data-con-graph                       the whole graph, all controls
 *        data-sources="con"                   sources shown at first
 *        data-root="con:persons/x"            only this node's neighbourhood
 *        data-depth="1"                       ... this many links away
 *        data-controls="compact"></div>       the small toolbar
 *
 * A graph inside a closed <details> is drawn when the reader opens it, so
 * forty collapsed graphs on a page cost nothing; the libraries and the data
 * are fetched once, on first use.  From script: CONGraph.render(el, options).
 *
 * Which node of another site is the same thing as one of ours is decided
 * by keys: ours are computed at build time (scripts/congraph.py, which
 * documents the rules and has the same join in Python for the tests and
 * for `render_graph.py --report`); theirs are derived in join() below.
 */
(function () {
  "use strict";

  var script = document.currentScript;
  // The site root, from where this file was loaded: the site is also served
  // from a sub-path (the pull-request previews), where "/graph/..." is wrong.
  // window.CON_GRAPH_BASE overrides it, for a page that inlines this file.
  var BASE = window.CON_GRAPH_BASE || (script && script.src || "/theme/js/con-graph.js")
    .replace(/theme\/js\/con-graph\.js.*$/, "");

  // Fixed type -> colour: a type keeps its colour whatever else is shown.
  var TYPE_COLOR = {
    person: "#2a78d6",
    project: "#eb6834",
    publication: "#1baf7a",
    instrument: "#eda100",
    dataset: "#e87ba4",
    organization: "#6250d6",
    objective: "#008300",
    topic: "#e34948"
  };
  var TYPE_LABEL = {
    person: "People", project: "Projects", publication: "Publications",
    instrument: "Software & instruments", dataset: "Datasets",
    organization: "Organizations", objective: "Objectives", topic: "Topics"
  };
  var PLURAL = { person: "people" };
  // which way sigma's camera angle turns the drawing, so it follows the hand
  var ROTATE_SIGN = 1;
  var FADED = "#e4e3df";
  var EDGE = "#d9d8d2";
  var INK = "#1a1a19";
  // The ring says where a node comes from, when more than one source shows.
  var RING = {
    home: { color: "#ffffff", size: 0.12 },   // this site only
    other: { color: "#77766f", size: 0.24 },   // another site only
    shared: { color: INK, size: 0.3 }        // both
  };

  function plural(type, n) {
    return n === 1 ? type : (PLURAL[type] || type + "s");
  }

  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === "text") node.textContent = attrs[k];
      else if (k.slice(0, 2) === "on") node.addEventListener(k.slice(2), attrs[k]);
      else if (attrs[k] !== null && attrs[k] !== false) node.setAttribute(k, attrs[k]);
    });
    (children || []).forEach(function (c) { if (c) node.appendChild(c); });
    return node;
  }

  // --- loading: once per page, on first use ------------------------------

  var loading = null;

  function loadScript(src) {
    return new Promise(function (resolve, reject) {
      var s = el("script", { src: src });
      s.onload = resolve;
      s.onerror = function () { reject(new Error("could not load " + src)); };
      document.head.appendChild(s);
    });
  }

  function load() {
    if (loading) return loading;
    if (!document.querySelector("[data-con-graph-css]")) {
      document.head.appendChild(el("link", {
        rel: "stylesheet", href: BASE + "theme/css/con-graph.css",
        "data-con-graph-css": ""
      }));
    }
    var data = window.CON_GRAPH_DATA
      ? Promise.resolve(window.CON_GRAPH_DATA)
      : fetch(BASE + "graph/graph.json").then(function (r) {
          if (!r.ok) throw new Error("could not load the graph data (" + r.status + ")");
          return r.json();
        });
    var vendor = window.CONGraphVendor
      ? Promise.resolve()
      : loadScript(BASE + "theme/vendor/con-graph/vendor.min.js");
    loading = Promise.all([data, vendor]).then(function (got) {
      return index(got[0]);
    });
    return loading;
  }

  function index(data) {
    data.byId = {};
    data.nodes.forEach(function (n) { data.byId[n.id] = n; });
    data.sourceLabel = {};
    data.sources.forEach(function (s) { data.sourceLabel[s.id] = s.label; });
    data.edgeAt = {};
    data.edges.forEach(function (e) { data.edgeAt[e.s + "|" + e.t] = e; });
    // "type|key" -> node id, for joining other sites' nodes with ours.  A
    // key two of our own nodes share (a preprint and its article have one
    // title) points at neither: null.
    data.byKey = {};
    data.loaded = {};     // source id -> "live" | "saved"
    publishKeys(data, data.nodes.map(function (n) { return [n, n.keys || []]; }));
    return data;
  }

  // Make one source's keys visible to the sources joined after it.
  function publishKeys(data, pairs) {
    var mine = {};
    pairs.forEach(function (p) {
      p[1].forEach(function (k) {
        var at = p[0].type + "|" + k;
        if (!(at in mine)) mine[at] = p[0].id;
        else if (mine[at] !== p[0].id) mine[at] = null;
      });
    });
    Object.keys(mine).forEach(function (at) {
      if (!(at in data.byKey)) data.byKey[at] = mine[at];
    });
  }

  // --- another site's graph: loaded from that site, joined with ours ------

  var LOCAL = "xyzrins:";   // the pid namespace every ORINOCO site shares

  function fetchJSON(url, ms) {
    var stop = new AbortController();
    var timer = setTimeout(function () { stop.abort(); }, ms);
    return fetch(url, { signal: stop.signal }).then(function (r) {
      if (!r.ok) throw new Error(url + ": " + r.status);
      return r.json();
    }).finally(function () { clearTimeout(timer); });
  }

  var joining = {};

  function addSource(data, id) {
    if (joining[id]) return joining[id];
    var src = data.sources.filter(function (s) { return s.id === id; })[0];
    if (!src || !src.graph_url) return Promise.resolve();
    joining[id] = fetchJSON(src.graph_url, 10000).then(function (raw) {
      return { raw: raw, how: "live" };
    }, function () {
      // the site is down, slow, or no longer lets us read it: our copy
      return fetchJSON(BASE + "graph/" + src.fallback, 20000).then(function (raw) {
        return { raw: raw, how: "saved" };
      });
    }).then(function (got) {
      join(data, src, got.raw);
      data.loaded[id] = got.how;
    });
    joining[id].catch(function () { delete joining[id]; });   // may be retried
    return joining[id];
  }

  function normTitle(text) {
    return (text || "").normalize("NFKD").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
  }

  // The keys of a node of another site; scripts/congraph.py:external_graph()
  // is the same rule, and documents it.
  function keysOf(n, src) {
    var keys = ["pid:" + n.id];
    if (n.id.indexOf(LOCAL) !== 0) keys.push(n.id);
    else if (src.match_local_paths && n.id !== LOCAL + ".") keys.push("path:" + n.id.slice(LOCAL.length));
    (n.ids || []).forEach(function (k) {
      keys.push(k.indexOf("doi:") === 0
        ? "doi:" + k.slice(4).replace(/^(https?:\/\/(dx\.)?doi\.org\/|doi:)/i, "").toLowerCase()
        : k);
    });
    if (n.type === "publication" && n.label) keys.push("title:" + normTitle(n.label));
    return keys.sort();
  }

  // Join a site's graph.json ({nodes: [{id, label, type, url}], edges:
  // [{source, target}]}) into ours; scripts/congraph.py:merge() in Python.
  function join(data, src, raw) {
    var nodes = raw.nodes, edges = raw.edges;
    if (src.within) {
      // only what lies this many links from that site's root
      var near = {}, frontier = {};
      near[LOCAL + "."] = frontier[LOCAL + "."] = true;
      for (var d = 0; d < src.within; d++) {
        var next = {};
        edges.forEach(function (e) {
          if (frontier[e.source] && !near[e.target]) next[e.target] = true;
          if (frontier[e.target] && !near[e.source]) next[e.source] = true;
        });
        Object.keys(next).forEach(function (id) { near[id] = true; });
        frontier = next;
      }
      nodes = nodes.filter(function (n) { return near[n.id]; });
      edges = edges.filter(function (e) { return near[e.source] && near[e.target]; });
    }
    var base = src.base_url.replace(/\/$/, "");
    var local = {}, pairs = [];
    nodes.forEach(function (n) {
      var keys = keysOf(n, src), node = null;
      for (var i = 0; i < keys.length && !node; i++) {
        var hit = data.byKey[n.type + "|" + keys[i]];
        if (hit) node = data.byId[hit];
      }
      if (!node) {
        node = {
          id: n.id.indexOf(LOCAL) === 0 ? src.id + ":" + n.id.slice(LOCAL.length) : n.id,
          label: n.label || n.id, type: n.type, sources: [], links: []
        };
        data.nodes.push(node);
        data.byId[node.id] = node;
      }
      if (node.sources.indexOf(src.id) < 0) node.sources.push(src.id);
      if (n.url) node.links.push({ k: src.id, href: base + (n.url === "/." ? "/" : n.url) });
      local[n.id] = node.id;
      pairs.push([node, keys]);
    });
    publishKeys(data, pairs);
    edges.forEach(function (e) {
      var s = local[e.source], t = local[e.target];
      if (!s || !t || s === t) return;
      var edge = data.edgeAt[s + "|" + t];
      if (!edge) {
        edge = data.edgeAt[s + "|" + t] = { s: s, t: t, type: e.type || "", sources: [] };
        data.edges.push(edge);
      }
      if (edge.sources.indexOf(src.id) < 0) edge.sources.push(src.id);
    });
  }

  // --- the filter: the one place a view of the graph is decided ----------
  //
  // scripts/congraph.py:neighbourhood() counts with the same rules, which is
  // why "Graph (12 projects, ...)" in a summary matches what opens.

  function filterGraph(data, view) {
    var want = {};
    view.sources.forEach(function (s) { want[s] = true; });
    function shown(sources) {
      return sources.some(function (s) { return want[s]; });
    }
    var keep = {};
    data.nodes.forEach(function (n) {
      if (!shown(n.sources)) return;
      if (view.shared && n.sources.length < 2) return;
      keep[n.id] = true;
    });
    var edges = data.edges.filter(function (e) {
      return shown(e.sources) && keep[e.s] && keep[e.t];
    });
    if (view.root && keep[view.root]) {
      var near = {};
      near[view.root] = 0;
      var frontier = [view.root];
      for (var d = 1; d <= (view.depth || 1); d++) {
        var next = [];
        edges.forEach(function (e) {
          [[e.s, e.t], [e.t, e.s]].forEach(function (p) {
            if (near[p[0]] === d - 1 && near[p[1]] === undefined) {
              near[p[1]] = d;
              next.push(p[1]);
            }
          });
        });
        frontier = next;
      }
      keep = near;
      edges = edges.filter(function (e) {
        return keep[e.s] !== undefined && keep[e.t] !== undefined;
      });
    } else {
      // without a root, a thing nothing shown links to is left out
      var linked = {};
      edges.forEach(function (e) { linked[e.s] = linked[e.t] = true; });
      keep = linked;
    }
    return {
      nodes: data.nodes.filter(function (n) { return keep[n.id] !== undefined; }),
      edges: edges
    };
  }

  // A small seeded generator: the same view lays out the same way on every
  // visit, so a reader finds a node where they left it.
  function rng(seed) {
    return function () {
      seed |= 0; seed = seed + 0x6D2B79F5 | 0;
      var t = Math.imul(seed ^ seed >>> 15, 1 | seed);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  }

  function trim(text, n) {
    return text.length > n ? text.slice(0, n - 1).trimEnd() + "…" : text;
  }

  // --- one graph on the page ---------------------------------------------

  function render(host, options) {
    options = options || {};
    var compact = (options.controls || "full") === "compact";
    var view = {
      sources: (options.sources || ["con"]).slice(),
      root: options.root || null,
      depth: options.depth || 1,
      shared: false
    };
    var hiddenTypes = {};
    var unavailable = {};   // sources that could not be loaded at all
    var stopRotating = function () {};
    // what is drawn besides the dots; kept when the view is rebuilt
    var showEdges = true, showLabels = true;
    var selected = null, hovered = null;
    var sigma = null, graph = null, layoutTimer = null;
    var data = null;

    host.classList.add("con-graph", compact ? "con-graph-compact" : "con-graph-full");
    host.textContent = "";
    var toolbar = el("div", { "class": "cg-toolbar" });
    var stage = el("div", { "class": "cg-stage" });
    var canvas = el("div", {
      "class": "cg-canvas", role: "img",
      "aria-label": "Graph of linked people, projects and research outputs"
    });
    var legend = el("div", { "class": "cg-legend" });
    var card = el("div", { "class": "cg-card", hidden: "" });
    var status = el("div", { "class": "cg-status", text: "Loading the graph…" });
    var hint = el("div", { "class": "cg-hint",
      text: "Drag to move \u00b7 scroll to zoom \u00b7 Shift-drag to rotate" });
    stage.appendChild(canvas);
    // over the drawing where there is room, under it where there is not
    if (!compact) stage.appendChild(legend);
    stage.appendChild(card);
    stage.appendChild(status);
    stage.appendChild(hint);
    host.appendChild(toolbar);
    host.appendChild(stage);
    if (compact) host.appendChild(legend);

    if (!compact) readHash();
    rotateWithShiftDrag();

    load().then(function (d) {
      data = d;
      view.sources = view.sources.filter(function (s) { return data.sourceLabel[s]; });
      if (!view.sources.length) view.sources = [data.sources[0].id];
      return withSources();
    }).then(function () {
      if (view.root && !data.byId[view.root]) view.root = null;
      rebuild();
    }).catch(function (err) {
      status.textContent = "The graph could not be shown: " + err.message;
      status.hidden = false;
    });

    // Load and join whatever other sites the view asks for.  One that can
    // be had neither from its site nor from our copy is dropped from the
    // view, and the reader is told.
    function withSources() {
      var home = data.sources[0].id;
      var need = view.sources.filter(function (id) { return id !== home && !data.loaded[id]; });
      if (!need.length) return Promise.resolve();
      status.textContent = "Loading " + need.map(function (id) { return data.sourceLabel[id]; }).join(", ") + "\u2026";
      status.hidden = false;
      return Promise.all(need.map(function (id) {
        return addSource(data, id).catch(function () {
          view.sources = view.sources.filter(function (x) { return x !== id; });
          if (view.sources.length < 2) view.shared = false;
          unavailable[id] = true;
        });
      }));
    }

    // Sigma pans on drag and zooms on scroll but has no way to turn the
    // drawing with a mouse (only with two fingers on a touch screen).  With
    // Shift held, a drag turns it about the centre of the canvas instead.
    // Listening in the capture phase keeps sigma from also panning.
    function rotateWithShiftDrag() {
      var from = null;
      function pointerAngle(e) {
        var box = canvas.getBoundingClientRect();
        return Math.atan2(e.clientY - (box.top + box.height / 2),
                          e.clientX - (box.left + box.width / 2));
      }
      canvas.addEventListener("mousedown", function (e) {
        if (!e.shiftKey || e.button !== 0 || !sigma) return;
        e.stopPropagation();
        e.preventDefault();
        from = { pointer: pointerAngle(e), camera: sigma.getCamera().getState().angle };
        canvas.style.cursor = "grabbing";
      }, true);
      function move(e) {
        if (!from || !sigma) return;
        sigma.getCamera().setState({ angle: from.camera + ROTATE_SIGN * (pointerAngle(e) - from.pointer) });
      }
      function up() {
        if (from) { from = null; canvas.style.cursor = ""; }
      }
      window.addEventListener("mousemove", move);
      window.addEventListener("mouseup", up);
      stopRotating = function () {
        window.removeEventListener("mousemove", move);
        window.removeEventListener("mouseup", up);
      };
    }

    // -- state in the address, so a view can be linked to (full page only)

    function readHash() {
      var h = new URLSearchParams(location.hash.replace(/^#/, ""));
      if (h.get("root")) view.root = h.get("root");
      if (h.get("depth")) view.depth = Math.max(1, Math.min(3, +h.get("depth") || 1));
      if (h.get("sources")) view.sources = h.get("sources").split(",");
      view.shared = h.get("shared") === "1";
    }

    function writeHash() {
      if (compact) return;
      history.replaceState(null, "", location.pathname + location.search + "#" + viewHash(view));
    }

    function viewHash(v) {
      var parts = ["sources=" + v.sources.join(",")];
      if (v.root) parts.push("root=" + encodeURIComponent(v.root), "depth=" + v.depth);
      if (v.shared) parts.push("shared=1");
      return parts.join("&");
    }

    // -- (re)building the drawing for the current view

    function rebuild() {
      var V = window.CONGraphVendor;
      var old = {};
      if (graph) graph.forEachNode(function (id, a) { old[id] = [a.x, a.y]; });
      if (layoutTimer) cancelAnimationFrame(layoutTimer);
      var turned = sigma ? sigma.getCamera().getState().angle : 0;
      if (sigma) sigma.kill();
      selected = hovered = null;

      var part = filterGraph(data, view);
      var multi = view.sources.length > 1;
      var home = data.sources[0].id;
      var random = rng(part.nodes.length * 7919 + part.edges.length);
      graph = new V.Graph({ type: "undirected", multi: false });
      var degree = {};
      part.edges.forEach(function (e) {
        degree[e.s] = (degree[e.s] || 0) + 1;
        degree[e.t] = (degree[e.t] || 0) + 1;
      });
      var small = part.nodes.length <= 60;
      part.nodes.forEach(function (n) {
        var ring = !multi ? RING.home
          : n.sources.length > 1 ? RING.shared
          : n.sources[0] === home ? RING.home : RING.other;
        var isRoot = n.id === view.root;
        var angle = random() * 2 * Math.PI, r = 50 + random() * 50;
        var at = old[n.id] || [Math.cos(angle) * r, Math.sin(angle) * r];
        graph.addNode(n.id, {
          x: at[0], y: at[1],
          size: (isRoot ? 6 : 0) + (small ? 5 : 3) + 1.8 * Math.sqrt(degree[n.id] || 0),
          label: trim(n.label, isRoot ? 60 : 38),
          color: TYPE_COLOR[n.type] || "#888",
          // alone, the root is ringed; among several sources the ring
          // already means "where from", so the root is told by its size
          borderColor: isRoot && !multi ? INK : ring.color,
          borderSize: isRoot && !multi ? 0.3 : ring.size,
          kind: n.type,
          forceLabel: isRoot,
          zIndex: isRoot ? 2 : 1
        });
      });
      part.edges.forEach(function (e) {
        if (!graph.hasEdge(e.s, e.t)) graph.addEdge(e.s, e.t, { kind: e.type });
      });

      status.hidden = part.nodes.length > 0;
      if (!part.nodes.length) {
        status.textContent = "Nothing to show for this selection.";
      }

      sigma = new V.Sigma(graph, canvas, {
        defaultNodeType: "bordered",
        nodeProgramClasses: {
          bordered: V.createNodeBorderProgram({
            borders: [
              { size: { attribute: "borderSize", defaultValue: 0.12 },
                color: { attribute: "borderColor" } },
              { size: { fill: true }, color: { attribute: "color" } }
            ]
          })
        },
        // few links can afford to be seen; a thousand must recede
        defaultEdgeColor: small ? "#b3b2ab" : EDGE,
        labelFont: '"Open Sans", sans-serif',
        labelSize: 12,
        labelColor: { color: "#3b3a37" },
        labelDensity: small ? 3 : 0.9,
        labelRenderedSizeThreshold: small ? 0 : 7,
        renderLabels: showLabels,
        zIndex: true,
        minCameraRatio: 0.05,
        maxCameraRatio: 3,
        nodeReducer: nodeReducer,
        edgeReducer: edgeReducer
      });
      if (turned) sigma.getCamera().setState({ angle: turned });
      sigma.on("enterNode", function (e) { hovered = e.node; canvas.style.cursor = "pointer"; sigma.refresh({ skipIndexation: true }); });
      sigma.on("leaveNode", function () { hovered = null; canvas.style.cursor = ""; sigma.refresh({ skipIndexation: true }); });
      sigma.on("clickNode", function (e) { select(e.node); });
      sigma.on("doubleClickNode", function (e) { e.preventSigmaDefault(); focus(e.node); });
      sigma.on("clickStage", function () { select(null); });

      layout(part.nodes.length, Object.keys(old).length > 0);
      drawToolbar(part);
      drawLegend(part);
      drawCard();
      writeHash();
    }

    // ForceAtlas2 in slices, so a large graph settles on screen instead of
    // freezing the page until it is done.
    function layout(n, warm) {
      if (n < 3) return;
      var V = window.CONGraphVendor;
      var settings = V.forceAtlas2.inferSettings(graph);
      settings.barnesHutOptimize = n > 250;
      // Hubs (a person on 140 papers) are pushed outwards and take their
      // leaves with them, instead of everything collapsing on the centre.
      settings.outboundAttractionDistribution = true;
      settings.gravity = n > 250 ? 0.25 : 0.6;
      settings.scalingRatio = n > 250 ? 30 : 12;
      settings.slowDown = 1 + Math.log(n);
      var left = Math.round((warm ? 0.5 : 1) * Math.min(600, 150 + n));
      var mine = graph;
      (function step() {
        if (graph !== mine) return;
        var k = Math.min(left, n > 250 ? 12 : 30);
        V.forceAtlas2.assign(graph, { iterations: k, settings: settings });
        left -= k;
        if (left > 0) layoutTimer = requestAnimationFrame(step);
      })();
    }

    function nodeReducer(id, a) {
      var out = Object.assign({}, a);
      if (hiddenTypes[a.kind]) { out.hidden = true; return out; }
      var centre = hovered || selected;
      if (centre && centre !== id && !graph.areNeighbors(centre, id)) {
        out.color = FADED; out.borderColor = FADED; out.label = ""; out.zIndex = 0;
      } else if (centre) {
        out.forceLabel = true; out.zIndex = 3;
      }
      if (id === selected) { out.borderColor = INK; out.borderSize = 0.3; out.highlighted = true; }
      return out;
    }

    function edgeReducer(id, a) {
      var out = Object.assign({}, a);
      var s = graph.source(id), t = graph.target(id);
      if (hiddenTypes[graph.getNodeAttribute(s, "kind")] ||
          hiddenTypes[graph.getNodeAttribute(t, "kind")]) { out.hidden = true; return out; }
      var centre = hovered || selected;
      if (centre) {
        if (s === centre || t === centre) { out.color = "#6b6a64"; out.size = 1.5; out.zIndex = 2; }
        else out.hidden = true;
      } else if (!showEdges) {
        // links off: only those of the node under the pointer, or selected
        out.hidden = true;
      }
      return out;
    }

    // -- actions

    function select(id) {
      selected = id;
      drawCard();
      sigma.refresh({ skipIndexation: true });
    }

    function focus(id) {
      view.root = id;
      if (!id) view.depth = 1;
      rebuild();
      if (id) select(id);
    }

    function goTo(id) {
      if (!graph.hasNode(id)) return;
      var n = data.byId[id];
      if (hiddenTypes[n.type]) { delete hiddenTypes[n.type]; drawLegend(filterGraph(data, view)); }
      select(id);
      var at = sigma.getNodeDisplayData(id);
      sigma.getCamera().animate({ x: at.x, y: at.y, ratio: 0.35 }, { duration: 500 });
    }

    function href(link) {
      return link.href.charAt(0) === "/" ? BASE + link.href.slice(1) : link.href;
    }

    function linkLabel(link) {
      if (link.k === data.sources[0].id) return "On this site";
      if (data.sourceLabel[link.k]) return "At " + data.sourceLabel[link.k];
      return link.k === "doi" ? "DOI" : "Website";
    }

    // -- the pieces around the drawing

    function check(label, on, change, title) {
      var box = el("input", { type: "checkbox", onchange: function () { change(box.checked); } });
      box.checked = on;
      return el("label", { "class": "cg-check", title: title || null },
        [box, el("span", { text: " " + label })]);
    }

    function drawToolbar(part) {
      toolbar.textContent = "";
      if (!compact) {
        var list = el("datalist", { id: "cg-names-" + Math.random().toString(36).slice(2) });
        var names = {};
        part.nodes.forEach(function (n) {
          if (!names[n.label]) { names[n.label] = n.id; list.appendChild(el("option", { value: n.label })); }
        });
        var search = el("input", {
          type: "search", "class": "cg-search", list: list.id,
          placeholder: "Find a person, project, paper…", "aria-label": "Find a node",
          onchange: function () {
            var q = search.value.trim().toLowerCase();
            if (!q) return;
            var hit = names[search.value] || (part.nodes.filter(function (n) {
              return n.label.toLowerCase().indexOf(q) >= 0;
            })[0] || {}).id;
            // `change` fires again when the field loses focus; going to the
            // node a second time would redraw the card under the reader's click
            if (hit && hit !== selected) goTo(hit);
          }
        });
        toolbar.appendChild(el("span", { "class": "cg-group" }, [search, list]));
      }
      if (data.sources.length > 1) {
        var group = el("span", { "class": "cg-group" }, [el("span", { "class": "cg-label", text: "Show" })]);
        data.sources.forEach(function (s) {
          group.appendChild(check(s.label, view.sources.indexOf(s.id) >= 0, function (on) {
            var next = data.sources.map(function (x) { return x.id; }).filter(function (id) {
              return id === s.id ? on : view.sources.indexOf(id) >= 0;
            });
            if (!next.length) next = [s.id];          // never an empty graph
            view.sources = next;
            if (next.length < 2) view.shared = false;
            withSources().then(rebuild);
          }));
        });
        if (!compact && view.sources.length > 1) {
          group.appendChild(check("only what they share", view.shared, function (on) {
            view.shared = on; rebuild();
          }, "Only things that appear on more than one of the sites"));
        }
        toolbar.appendChild(group);
      }
      if (view.root && data.byId[view.root]) {
        var depth = el("span", { "class": "cg-group" }, [el("span", { "class": "cg-label", text: "Reach" })]);
        [[1, "direct links"], [2, "one step further"]].forEach(function (d) {
          depth.appendChild(el("button", {
            type: "button", "class": "cg-btn" + (view.depth === d[0] ? " cg-on" : ""),
            "aria-pressed": String(view.depth === d[0]), text: d[1],
            onclick: function () { view.depth = d[0]; rebuild(); }
          }));
        });
        toolbar.appendChild(depth);
        if (!compact) {
          toolbar.appendChild(el("button", {
            type: "button", "class": "cg-btn", text: "✕ Whole graph",
            onclick: function () { focus(null); }
          }));
        }
      }
      // where another site's part came from, when it is not that site
      data.sources.slice(1).forEach(function (s) {
        var note = unavailable[s.id] ? s.label + " could not be loaded"
          : view.sources.indexOf(s.id) >= 0 && data.loaded[s.id] === "saved"
            ? s.label + ": site not reachable, showing our saved copy" : null;
        if (note) toolbar.appendChild(el("span", { "class": "cg-note", text: note }));
      });
      var draw = el("span", { "class": "cg-group" }, [el("span", { "class": "cg-label", text: "Draw" })]);
      draw.appendChild(check("links", showEdges, function (on) {
        showEdges = on; sigma.refresh({ skipIndexation: true });
      }, "Lines between linked things; when off, only those of the dot you point at or select"));
      draw.appendChild(check("labels", showLabels, function (on) {
        showLabels = on; sigma.setSetting("renderLabels", on);
      }, "Names next to the dots; when off, a name shows when you point at a dot"));
      toolbar.appendChild(draw);
      var count = el("span", { "class": "cg-count", text: part.nodes.length + " things, " + part.edges.length + " links" });
      toolbar.appendChild(count);
      if (compact) {
        toolbar.appendChild(el("a", {
          "class": "cg-open", href: BASE + "explore/#" + viewHash(view),
          text: "Open in Explore →"
        }));
      }
    }

    function drawLegend(part) {
      legend.textContent = "";
      var counts = {};
      part.nodes.forEach(function (n) { counts[n.type] = (counts[n.type] || 0) + 1; });
      if (Object.keys(counts).length > 1) {
        var setAll = function (on) {
          hiddenTypes = {};
          if (!on) Object.keys(counts).forEach(function (t) { hiddenTypes[t] = true; });
          if (!on && selected) select(null);
          drawLegend(part);
          sigma.refresh();
        };
        legend.appendChild(el("div", { "class": "cg-allnone" }, [
          el("button", { type: "button", "class": "cg-link", text: "all",
            title: "Show every type", onclick: function () { setAll(true); } }),
          el("button", { type: "button", "class": "cg-link", text: "none",
            title: "Hide every type, then tick the ones you want",
            onclick: function () { setAll(false); } })
        ]));
      }
      data.types.forEach(function (t) {
        if (!counts[t]) return;
        var box = el("input", { type: "checkbox", onchange: function () {
          if (box.checked) delete hiddenTypes[t]; else hiddenTypes[t] = true;
          sigma.refresh();
        } });
        box.checked = !hiddenTypes[t];
        legend.appendChild(el("label", { "class": "cg-type" }, [
          box,
          el("span", { "class": "cg-dot", style: "background:" + TYPE_COLOR[t] }),
          el("span", { text: TYPE_LABEL[t] || t }),
          el("span", { "class": "cg-n", text: String(counts[t]) })
        ]));
      });
      if (view.sources.length > 1) {
        var home = data.sources[0].label;
        var others = view.sources.filter(function (s) { return s !== data.sources[0].id; });
        var other = others.length === 1 ? data.sourceLabel[others[0]] : "another site";
        var rings = el("div", { "class": "cg-rings" });
        [["home", home + " only"], ["other", other + " only"], ["shared", "shared"]].forEach(function (r) {
          rings.appendChild(el("span", { "class": "cg-ring-row" }, [
            el("span", { "class": "cg-dot cg-ring-" + r[0] }), el("span", { text: r[1] })
          ]));
        });
        legend.appendChild(rings);
      }
    }

    function drawCard() {
      card.textContent = "";
      var n = selected && data.byId[selected];
      card.hidden = !n;
      if (!n) return;
      card.appendChild(el("button", {
        type: "button", "class": "cg-close", "aria-label": "Close", text: "✕",
        onclick: function () { select(null); }
      }));
      card.appendChild(el("div", { "class": "cg-kind" }, [
        el("span", { "class": "cg-dot", style: "background:" + TYPE_COLOR[n.type] }),
        el("span", { text: n.type + (data.sources.length > 1
          ? " · " + n.sources.map(function (s) { return data.sourceLabel[s] || s; }).join(" + ") : "") })
      ]));
      card.appendChild(el("div", { "class": "cg-title", text: n.label }));
      var links = el("div", { "class": "cg-links" });
      n.links.forEach(function (l) {
        links.appendChild(el("a", { href: href(l), text: linkLabel(l) }));
      });
      if (n.links.length) card.appendChild(links);
      if (n.id !== view.root) {
        card.appendChild(el("button", {
          type: "button", "class": "cg-btn", text: "Show only its links",
          onclick: function () { focus(n.id); }
        }));
      }
      // The neighbours as text: the same information as the drawing, for
      // reading, searching and keyboard use.
      var groups = {};
      graph.forEachNeighbor(n.id, function (id) {
        var m = data.byId[id];
        (groups[m.type] = groups[m.type] || []).push(m);
      });
      data.types.forEach(function (t) {
        var items = groups[t];
        if (!items) return;
        items.sort(function (a, b) { return a.label.localeCompare(b.label); });
        var ul = el("ul");
        items.forEach(function (m) {
          ul.appendChild(el("li", {}, [el("button", {
            type: "button", "class": "cg-item", text: m.label,
            onclick: function () { goTo(m.id); }
          })]));
        });
        var box = el("details", { "class": "cg-near" }, [
          el("summary", { text: items.length + " " + plural(t, items.length) }), ul
        ]);
        if (items.length <= 6) box.open = true;
        card.appendChild(box);
      });
    }

    // Give back what the drawing holds.  A browser allows a page only some
    // sixteen WebGL contexts and a graph takes a few, so a page of forty
    // expanders must not keep those of the ones the reader has closed: past
    // the limit the oldest drawing simply goes blank.
    function destroy() {
      if (layoutTimer) cancelAnimationFrame(layoutTimer);
      if (sigma) sigma.kill();
      sigma = graph = null;
      stopRotating();
      host.textContent = "";
    }

    return {
      destroy: destroy,
      focus: focus, select: select, view: view,
      // where a node is drawn, in canvas pixels (for tests)
      _at: function (id) { return sigma.graphToViewport(graph.getNodeAttributes(id)); }
    };
  }

  // --- finding the graphs a page declares ---------------------------------

  function options(host) {
    var d = host.dataset;
    return {
      controls: d.controls || "full",
      sources: d.sources ? d.sources.split(",") : null,
      root: d.root || null,
      depth: d.depth ? +d.depth : 1
    };
  }

  function auto() {
    document.querySelectorAll("[data-con-graph]").forEach(function (host) {
      if (host.conGraph) return;
      var fold = host.closest("details");
      function go() { if (!host.conGraph) host.conGraph = render(host, options(host)); }
      if (fold) {
        // drawn while open, released when closed
        fold.addEventListener("toggle", function () {
          if (fold.open) go();
          else if (host.conGraph) { host.conGraph.destroy(); host.conGraph = null; }
        });
        if (fold.open) go();
      } else {
        go();
      }
    });
  }

  window.CONGraph = { render: render, load: load, filter: filterGraph, auto: auto };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", auto);
  else auto();
})();
