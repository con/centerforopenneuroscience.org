# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is the Center for Open Neuroscience (CON) website - a static site built with Pelican (Python static site generator). The site showcases neuroscience-related projects and team information at https://centerforopenneuroscience.org.

## Common Development Commands

### Build and Development

```bash
# Generate the website
make html

# Start development server with auto-reload (runs on http://localhost:8000)
make devserver

# Stop development server
make stopserver

# Clean generated files
make clean

# Generate using production settings
make publish
```

### Deployment

At the moment deployment is not automated at CI level, and need to be
done by someone with sufficient privileges via 

```bash
# Deploy via SSH to production
make ssh_upload

# Deploy via rsync+SSH
make rsync_upload
```

### Quality Assurance

```bash
# Run link checker locally (requires linkchecker installed)
make html && make serve &
linkchecker --check-extern -f .linkcheckerrc -t 1 http://localhost:8000
```

## Architecture and Code Structure

### Directory Layout

- `content/pages/` - HTML content files for website pages
- `theme/` - Custom theme based on buddycloud.com design
  - `templates/` - Jinja2 templates
  - `sass/` - SCSS source files
  - `static/` - Static assets (images, CSS, JS)
- `output/` - Generated static site (do not edit directly)
- `jinjaext/` - Custom Jinja extensions for table of contents
- `mdext/` - Custom Markdown extensions

### Key Technologies

- **Pelican** - Static site generator
- **Jinja2** - Template engine
- **SCSS/Compass** - CSS preprocessing
- **Git Annex** - Large file management for assets

### Custom Extensions

1. **Table of Contents Generator** (`jinjaext/table_of_contents.py`)
   - Automatically generates navigation from page headings
   - Used via Jinja filters: `extract_toc_info`, `create_toc`, `add_toc_hooks`

2. **Markdown Extensions** (`mdext/`)
   - `fix_code_blocks.py` - Code block processing
   - Used for the projects page rendering

3. **Graph** (`/explore/` and the per-person graphs on `/whoweare`)
   - `scripts/render_graph.py` (logic in `scripts/congraph.py`) writes
     `content/graph/graph.json`: CON's records joined with the graphs of the
     other sites listed in `content/graph-sources.yaml`. It is part of
     `make project`; do not edit the JSON by hand.
   - Other sites' graphs are read from copies in `sourcedata/graphs/`;
     `make fetch-graphs` refreshes them, `scripts/render_graph.py --report`
     lists which nodes were joined across sites and why.
   - `theme/static/js/con-graph.js` is the only renderer: any element with
     `data-con-graph` (plus `data-root`, `data-depth`, `data-sources`,
     `data-controls`) becomes a graph filtered from that one file. Its
     libraries are bundled in `theme/static/vendor/con-graph/`
     (`make graph-vendor`, see `theme/graph-vendor/README.md`).

### Development Workflow

1. Content is written as HTML files in `content/pages/`
2. Templates in `theme/templates/` control page layout
3. SCSS files in `theme/sass/` compile to CSS
4. Running `make devserver` watches for changes and auto-rebuilds

### CI/CD Pipeline

- GitHub Actions runs link checking on:
  - Pull requests to master
  - Weekly schedule (Sundays 00:00 UTC)
- Workflow defined in `.github/workflows/check-links.yaml`
- Link checker configuration in `.linkcheckerrc` (ignores ResearchGate, Scholar, etc.)

### Important Notes

- Assets managed with git-annex - run `git annex get *` to fetch large files
- Custom theme licensed under Apache 2.0 (from buddycloud.com)
- New content licensed under CC BY 3.0
- Production deployment targets `/srv/centerforopenneuroscience.org/www`
