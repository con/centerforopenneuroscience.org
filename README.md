# Center for Open Neuroscience (CON)

This repository provides sources for the website at [http://centerforopenneuroscience.org](http://centerforopenneuroscience.org/)

## Website design

It is largely based on [buddycloud.com](http://buddycloud.com) design which was
released under Apache 2.0 license.  New content of the website is released
under CC BY 3.0 license.

## Licensing

The repository follows the [REUSE specification](https://reuse.software/):
`REUSE.toml` says which license covers which files, and `LICENSES/` holds
the texts.  In short:

- design, templates, styles and site-building code: Apache-2.0;
- website content (`content/`, images): CC-BY-3.0;
- files with their own `SPDX-License-Identifier` header (the graph, newer
  scripts): MIT, as the header says;
- vendored libraries (`theme/static/vendor/`): each under its own license;
- logos of other projects and organizations belong to their owners and are
  not relicensed here.

A new file needs no header unless it differs from what `REUSE.toml` says for
its location.  `tox -e reuse` checks that every file is covered.

## HOWTO

Install pelican (e.g. `pip install pelican`).
You might need to get files using `git-annex` so do `git annex get *`.
To start serving while developing

```shell
make devserver
```

and to stop later

```shell
make stopserver
```
