// The libraries con-graph.js draws with, exposed as one global.  The same
// three that things-graph-renderer (the graph.js of www-from-model sites)
// is built from, plus the bordered-node program used to mark a node's source.
import Graph from "graphology";
import Sigma from "sigma";
import forceAtlas2 from "graphology-layout-forceatlas2";
import { createNodeBorderProgram } from "@sigma/node-border";

window.CONGraphVendor = { Graph, Sigma, forceAtlas2, createNodeBorderProgram };
