# Vendored graph libraries

`theme/static/vendor/con-graph/vendor.min.js` is [sigma.js], [graphology] and
graphology's ForceAtlas2 layout (all MIT) in one file, so the site needs no
JavaScript toolchain to build.  The code that uses them,
`theme/static/js/con-graph.js`, is plain hand-written JavaScript and is not
bundled: edit it directly.

Rebuild the bundle only to change a library version:

```bash
make graph-vendor
```

[sigma.js]: https://www.sigmajs.org/
[graphology]: https://graphology.github.io/
