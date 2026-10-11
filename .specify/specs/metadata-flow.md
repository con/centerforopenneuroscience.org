# How metadata gets from the records to the website

Every arrow below is a command, and every command that writes into this
repository is run under `datalad run`, so the commit that produced a file
carries the command, its inputs and its outputs. `git log` on any generated
file answers "where did this come from".

```mermaid
flowchart TB
  subgraph upstream["upstream sources (outside both repos)"]
    direction LR
    GH["GitHub API<br/><i>repo created_at, archived,<br/>contributors</i>"]
    NIH["NIH RePORTER / NSF<br/><i>award periods, PI roles</i>"]
    ZOT["Zotero group 6197458<br/><i>publications</i>"]
    DRI["con/dump-research-info<br/><i>people, projects</i>"]
    BIB["haxbylab.bib + vita<br/><i>publications, funding</i>"]
    BEP["bids-website<br/>data/beps/beps.yml"]
  end

  subgraph store["ORINOCO-Lite/con-site-specific <b>(the source of truth)</b>"]
    direction TB
    REC["metadata/records/<br/>XYZProject · XYZPerson · XYZInstrument<br/>XYZOrganization · XYZGrant · XYZPublication<br/>XYZObjective · XYZAgentRole · …"]
    OVM["metadata/overlays/<br/>machine-provenance-annotations/<br/><i>what the importers vouch for</i>"]
    OVC["metadata/overlays/<br/>curation-evidence/<br/><i>why we believe a hand claim</i>"]
    AST["content/&lt;kind&gt;/&lt;slug&gt;/<br/>logo.* · portrait.*<br/><i>git-annex</i>"]
    GATE1{{"tools/linkml_check.sh<br/><i>schema</i>"}}
    GATE2{{"tools/validate_records.py<br/><i>curation rules</i>"}}
  end

  subgraph site["con/centerforopenneuroscience.org"]
    direction TB
    SUB["sourcedata/con-site-specific<br/><i>submodule — pins the revision</i>"]
    EXTR["content/people/ · content/projects/<br/><i>extraction of the OLD hand-written pages</i>"]
    INTRO["content/section-intros.yaml<br/><i>copy belonging to a section,<br/>not to any entity</i>"]
    THEME["theme/static/img/&lt;kind&gt;/&lt;slug&gt;/"]
    PAGES["content/pages/whoweare.html<br/>content/pages/projects.html"]
    OUT["output/<br/><i>pelican</i>"]
  end

  GH & NIH & ZOT & DRI & BIB & BEP -->|"by hand, with evidence"| REC
  DRI -->|"source adapters"| OVM
  REC -.->|"must pass"| GATE1
  REC -.->|"must pass"| GATE2
  OVC -.-> GATE2
  REC --> SUB
  AST --> SUB

  EXTR -->|"enrich_people.py<br/>enrich_projects.py"| REC
  EXTR -->|"records_from_page.py"| REC
  SUB -->|"<b>datalad run</b><br/>sync_assets_to_theme.py"| THEME
  SUB -->|"<b>datalad run</b><br/>render_whoweare.py"| PAGES
  SUB -->|"<b>datalad run</b><br/>render_projects.py"| PAGES
  INTRO --> PAGES
  THEME --> OUT
  PAGES -->|"pelican"| OUT

  classDef src fill:#eef4fb,stroke:#5b7fa6
  classDef rec fill:#f3f0fa,stroke:#7a6aa8
  classDef gen fill:#eef7ef,stroke:#5d8a63
  classDef gate fill:#fdf3e3,stroke:#b58b3a
  class GH,NIH,ZOT,DRI,BIB,BEP src
  class REC,OVM,OVC,AST,SUB rec
  class THEME,PAGES,OUT,EXTR,INTRO gen
  class GATE1,GATE2 gate
```

## Which command alters what

| command | reads | writes | run under |
| --- | --- | --- | --- |
| `enrich_people.py --write` | `content/people/` | records `XYZPerson`, `content/persons/*/portrait.*` | by hand |
| `enrich_projects.py --write` | `content/projects/` | records `XYZProject` and friends | by hand |
| `records_from_page.py --write` | `content/projects/` | new `XYZProject` records | by hand |
| `sync_logos.py --write` | `theme/static/img/3rd/` | `content/<kind>/<slug>/logo.*` | by hand |
| `harvest_join_dates.py` | this repo's git history | a JSON report (records edited by hand from it) | by hand |
| **`sync_assets_to_theme.py --write`** | submodule `content/` | `theme/static/img/<kind>/<slug>/`, `theme/static/img/team/` | **`datalad run`** |
| **`render_whoweare.py --out …`** | submodule `metadata/records/`, submodule `content/`, `content/section-intros.yaml` | `content/pages/whoweare.html` | **`datalad run`** |
| **`render_projects.py --out …`** | the same three | `content/pages/projects.html` | **`datalad run`** |
| `pelican content -o output` | `content/`, `theme/` | `output/` | build step |

The first group runs **into** the store and is how hand-curated facts get in.
The second group runs **out of** it and is where `datalad run` applies: those
three commands are the only ones that write generated files into this repo,
so those are the files whose provenance has to be recoverable.

## The direction that bit us

The flow is **one-way**: `store → theme → pages`. An edit made downstream
survives only until the next sync. Portraits were cropped in
`theme/static/img/team/` and the next `sync_assets_to_theme.py` silently
restored the 954 KB originals from the store. The fix belonged in
`content/persons/<slug>/portrait.*`, where the asset lives.

Anything hand-edited in `theme/static/img/<kind>/` or in
`content/pages/{whoweare,projects}.html` is temporary. The pages even say so
in a comment: *"Edit the records, not this file."*

## Re-running any of it

```bash
# what produced this file, and from what
git log --format=%B -1 -- content/pages/whoweare.html

# do it again, byte for byte
datalad rerun --explicit <that commit>
```

`--explicit` is needed because the working tree usually carries unrelated
untracked files; the declared inputs and outputs are then the whole of what
the command touches.
