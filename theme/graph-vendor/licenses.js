// SPDX-FileCopyrightText: 2026 Yaroslav Halchenko <yaroslav.o.halchenko@dartmouth.edu>
// SPDX-License-Identifier: MIT
//
// Generated with Claude Code
//
// Writes ../static/vendor/con-graph/LICENSES.txt: the licence of every
// package esbuild put into vendor.min.js.  MIT asks that the copyright and
// permission notice travel with copies of the software, and a minified
// bundle carries neither; this file does.  Run by `npm run build`.
const fs = require("fs");
const path = require("path");

const meta = JSON.parse(fs.readFileSync("meta.json", "utf8"));
const out = Object.values(meta.outputs)[0];
const roots = new Set();
for (const input of Object.keys(out.inputs)) {
  const m = input.match(/^(.*node_modules\/(?:@[^/]+\/)?[^/]+)\//);
  if (m) roots.add(m[1]);
}
const parts = [
  "vendor.min.js bundles the packages below, unmodified, each under the",
  "licence reproduced after its name.  Built from theme/graph-vendor/.",
  "",
];
for (const root of [...roots].sort()) {
  const pkg = JSON.parse(fs.readFileSync(path.join(root, "package.json"), "utf8"));
  const file = fs.readdirSync(root).find((f) => /^licen[cs]e/i.test(f));
  if (!file) throw new Error(`${pkg.name}: no licence file to reproduce`);
  parts.push("=".repeat(72), `${pkg.name} ${pkg.version} -- ${pkg.license}`,
             "=".repeat(72), "", fs.readFileSync(path.join(root, file), "utf8").trim(), "");
}
fs.writeFileSync("../static/vendor/con-graph/LICENSES.txt", parts.join("\n"));
fs.unlinkSync("meta.json");
console.log(`LICENSES.txt: ${roots.size} packages`);
