MiniSearch 7.2.0 (MIT), https://github.com/lucaong/minisearch

`minisearch.js` is `dist/umd/index.js` of the npm package, unmodified:

    npm pack minisearch@7.2.0
    tar xzf minisearch-7.2.0.tgz package/dist/umd/index.js package/LICENSE.txt

Used by `theme/static/js/con-search.js`, which loads it when the search box
is first opened.
