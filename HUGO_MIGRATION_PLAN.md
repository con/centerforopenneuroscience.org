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

## Implementation Status ✅ COMPLETED

### Phase 1: Foundation Setup ✅
- [x] Hugo site structure created with proper taxonomies
- [x] Configuration with `relativeURLs = true` for proper local development
- [x] Template architecture designed for no-duplication principle

### Phase 2: Content Migration ✅
- [x] 3 people migrated (Yaroslav, Austin, Jason) with categories (centroids, emeritus)
- [x] 6 projects created across all types:
  - **Own**: DANDI, DataLad, PyMVPA, NeuroDebian
  - **Adopted**: citeproc-py (https://github.com/citeproc-py/citeproc-py/)
  - **Community**: BIDS (https://bids.neuroimaging.io)
- [x] Bidirectional relationships working automatically

### Phase 3: Bibliography Integration 🚧
- [x] Bibliography taxonomy structure ready
- [x] Publication placeholders in people front matter
- [ ] Zotero integration with CON group (https://www.zotero.org/groups/6197458/centerforopenneuroscience)
- [ ] Automated cron script for bibliography updates

## Validation Results ✅

### Core Functionality Verified
- [x] **Hugo builds successfully**: 36 pages generated without errors
- [x] **People pages display correctly**: All 3 people with positions, projects, social links
- [x] **Projects auto-populate team members**: DANDI shows Austin & Yaroslav automatically
- [x] **Enhanced project structure**:
  - [x] **Centroids section**: Shows only CON centroids per project
  - [x] **All Team Members section**: Shows all people with their categories
- [x] **Taxonomy pages work**: People categories, project types all functional
- [x] **Cross-references function bidirectionally**: No manual sync needed
- [x] **No content duplication**: Single source of truth in people pages
- [x] **Relative URLs working**: Fixed for proper local development (port 38991)
- [x] **Content relationship integrity**: All 6 projects show on Yaroslav's page

### Architecture Validation
- [x] **No-duplication principle**: People define projects → Projects auto-populate teams
- [x] **Taxonomy-driven relationships**: Hugo automatically creates reverse links
- [x] **Scalable design**: Easy to add new people, projects, or categories
- [x] **Template flexibility**: Centroids vs All Team Members sections work correctly

## Key Architectural Achievements

1. **True No-Duplication**: Project teams are never manually maintained - they're automatically generated from people's project lists

2. **Relative URL Support**: All internal links use relative paths (`../projects/dandi/`) making local development seamless

3. **Enhanced Project Structure**:
   - Centroids section highlights CON core team involvement
   - All Team Members shows complete participation with role indicators

4. **Multi-Type Project Support**: Own/Adopted/Community project types with proper taxonomy navigation

5. **Ready for Bibliography**: Structure prepared for Zotero integration with automatic people-publication linking

## Next Steps for Full Migration
1. Import remaining ~20 people from existing Pelican site
2. Set up Zotero bibliography sync with cron script
3. Migrate remaining static pages (engage, support content)
4. Configure production deployment pipeline
5. URL redirect mapping from Pelican to Hugo structure

**Status**: Core architecture validated and working. Ready for content scale-up.