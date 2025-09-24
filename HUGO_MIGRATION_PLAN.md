# Pelican to Hugo Migration Plan for CON Website

## Overview
Migrate the Center for Open Neuroscience website from Pelican to Hugo with enhanced taxonomies for people, projects, and bibliography integration. Key principle: **No duplication** - use Hugo taxonomies to create automatic bidirectional relationships.

## Core Architecture Principles

### Taxonomy Design
```yaml
# config.yaml taxonomies
taxonomies:
  people_category: people_categories  # centroids, emeritus, collaborators
  person: people                      # individual people (unused - for future)
  project_type: project_types         # own, participating, contributing
  project: projects                   # individual projects
  publication: publications           # individual publications
```

### Single Source of Truth
- **People pages**: Define ALL relationships (projects, publications)
- **Project pages**: Only intrinsic metadata (description, status, type)
- **Hugo taxonomies**: Automatically generate reverse relationships

### Content Structure Examples

**People Page (Source of Truth):**
```yaml
# content/people/yaroslav-halchenko.md
---
title: "Yaroslav O. Halchenko"
people_categories: ["centroids"]
position: "Founding Director"
email: "yaroslav.o.halchenko@oneukrainian.com"
phone: "+1(603)6469834"
social:
  github: "yarikoptic"
  twitter: "yarikoptic"
  mastodon: "https://fosstodon.org/@yarikoptic"
  research: "http://haxbylab.dartmouth.edu/ppl/yarik.html"
  cv: "http://www.oneukrainian.com/resume/halchenko_vita.pdf"
projects: ["dandi", "datalad", "pymvpa", "neurodebian"]
publications: ["halchenko2023dandi", "halchenko2022datalad"]
---
Research Professor of Psychological and Brain Sciences...
```

**Project Page (No Duplication):**
```yaml
# content/projects/dandi.md
---
title: "DANDI"
project_types: ["own"]
status: "active"
website: "https://dandiarchive.org"
# NO people: [] field - automatically generated via taxonomies
---
Distributed Archives for Neurophysiology Data Integration...
```

## Migration Phases

### Phase 1: Foundation Setup
1. Install Hugo extended version
2. Create initial site structure
3. Configure taxonomies
4. Set up basic theme/templates

### Phase 2: Content Migration
1. Extract people data from whoweare.html
2. Extract project data from projects.html
3. Convert to Hugo markdown with proper front matter
4. Implement taxonomy-based templates

### Phase 3: Bibliography Integration
1. Add hugo-bibliography plugin as git submodule
2. Set up Zotero integration for CON group: https://www.zotero.org/groups/6197458/centerforopenneuroscience
3. Create cron job to fetch Zotero data and format for hugo-bibliography
4. Link publications to people via taxonomies in front matter
5. Implement filtered bibliography views per person/project

### Phase 4: Advanced Features
1. Cross-referencing templates
2. Faceted browsing
3. Search functionality
4. Automated content updates

### Phase 5: Testing & Deployment
1. Content validation
2. URL mapping
3. CI/CD setup
4. Production deployment

## Template Examples

### Project Team Display (Auto-generated)
```go-html-template
<!-- layouts/projects/single.html -->
<h2>Team Members</h2>
{{ $projectPeople := where .Site.Pages "Params.projects" "intersect" (slice .Title) }}
{{ range $projectPeople }}
  <div class="person">
    <h3><a href="{{ .Permalink }}">{{ .Title }}</a></h3>
    <p>{{ .Params.position }}</p>
  </div>
{{ end }}
```

### Person's Projects Display
```go-html-template
<!-- layouts/people/single.html -->
<h2>Projects</h2>
{{ range .Params.projects }}
  {{ with $.Site.GetPage (printf "/projects/%s" .) }}
    <div class="project">
      <h3><a href="{{ .Permalink }}">{{ .Title }}</a></h3>
      <p>{{ .Summary }}</p>
    </div>
  {{ end }}
{{ end }}
```

### Person's Publications Display
```go-html-template
<!-- layouts/people/single.html -->
<h2>Publications</h2>
{{ if .Params.publications }}
  {{< bibliography filter="id" values=.Params.publications >}}
{{ end }}
```

## Bibliography Integration Details

### Zotero Setup
- Group URL: https://www.zotero.org/groups/6197458/centerforopenneuroscience
- Cron script will fetch latest bibliography data
- Format as CSL-JSON for hugo-bibliography plugin

### Bibliography Automation
```bash
# Cron script example (daily at 2 AM)
0 2 * * * /path/to/fetch-zotero.sh 6197458 > /path/to/data/bibliography.json
```

## Benefits
- **No Duplication**: Single source of truth prevents inconsistencies
- **Automatic Updates**: Change person's projects → automatically updates project team
- **Flexible Queries**: Find all X for Y, all Y for X
- **Future-Proof**: Easy to add new taxonomies/relationships
- **Performance**: Hugo's fast build times
- **Bibliography Integration**: Automated Zotero sync with filtered views

## Directory Structure
```
hugo-site/
├── config.yaml
├── content/
│   ├── people/
│   │   ├── yaroslav-halchenko.md
│   │   ├── austin-macdonald.md
│   │   └── _index.md
│   ├── projects/
│   │   ├── dandi.md
│   │   ├── datalad.md
│   │   └── _index.md
│   └── pages/
│       ├── engage.md
│       └── support.md
├── data/
│   └── bibliography.json
├── themes/
│   └── hugo-bibliography/
└── layouts/
    ├── people/
    ├── projects/
    └── taxonomy/
```

## Success Metrics
- [ ] Hugo builds successfully
- [ ] People pages display correctly
- [ ] Projects pages auto-populate team members
- [ ] Taxonomy pages work (all people, all projects)
- [ ] Cross-references function bidirectionally
- [ ] No content duplication
- [ ] URL structure preserved
- [ ] Bibliography integration functional with Zotero sync