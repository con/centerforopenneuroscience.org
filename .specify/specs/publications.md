# Plan: publications, per project and per person

**Status: plan only.** Nothing below is implemented. Written 2026-10-11
against `sourcedata/con-site-specific` at `fd80c0f` (343 records).

## What exists

131 `XYZPublication` records, imported from Zotero group 6197458 by
`xyzrins:source-adapters/zotero/v1`, with a curation decision each in
`curation-records/zotero.yaml` (all `accept`, reviewed in one GitHub
comment).

| | |
| ---------------------------------- | ------------------------------------ |
| author attributions (`attributed_to`) | 416, over 27 CON people |
| bibliographic type (`characterized_by`) | 126 of 131 |
| `dcterms:issued` | 126 of 131 |
| identifiers | 140 DOI, 33 URL, 166 other |
| year span | 1998–2026 |

Types: 79 `bibo:AcademicArticle`, 34 `bibo:Document`, 7 `bibo:Article`,
3 `bibo:BookSection`, 2 `bibo:Manuscript`, 1 `bibo:Thesis`.

Most-cited CON authors: Halchenko 125, Hanke 38, Ghosh 34, Haxby 27,
Poline 23, Poldrack 19.

## What blocks the two listings

**Per-person is nearly ready. Per-project is not possible today.**

1. **Only 1 of 131 publications links to a project.** The link slot exists —
   `generated_by[0].object` — and exactly one record uses it
   (`datalad-joss-2021` → `projects/datalad`). Without it there is nothing
   to list under a project entry. *This is the whole of the work.*

2. **Only 1 of 131 has a venue.** `generated_by[0].at_location`, one record,
   pointing at `ISSN:0147-006X`. Two `XYZPublicationVenue` records exist for
   131 publications, so a listing cannot say where anything appeared.

3. **`dcterms:issued` is in four formats and six values are malformed.**
   71 are `YYYY`, 41 `YYYY-MM`, 11 `YYYY-MM-DD`, and the rest are neither:

   ```
   datalad-joss-2021                     '2021/07/01'
   doi-10-1016-j-neuroimage-2022-119623  '11/2022'
   doi-10-1038-s41592-022-01681-2        '12/2022'
   doi-10-12688-f1000research-10783-2    '2017-6-15'
   doi-10-3389-fninf-2024-1376022        '2024-7-22'
   doi-10-3389-fnins-2022-871228         '2022-4-19'
   ```

   `11/2022` sorts before `1998`. Any listing ordered by date is wrong until
   this is normalised. Note these are *attributes*, not `at_time`, so the
   curation gate never looked at them — the same hole that let CON's
   founding date go unchecked.

4. **5 records have no bibliographic type**, so they cannot be grouped or
   formatted as a citation.

## Stages

### Stage 1 — make the dates trustworthy (small, do first)

Normalise `dcterms:issued` to `W3CISO8601` and teach
`validate_records.py` to check date-valued *attributes* by predicate, the
way it already does for `schema:foundingDate`. Six records change.

**Done when** every `dcterms:issued` matches `YYYY[-MM[-DD]]` and the gate
rejects one that does not.

### Stage 2 — link publications to projects (the enabling step)

This is the real work and it needs a decision, because nothing in the
records says which project a paper belongs to. Four possible sources, in
descending order of how much I would trust them:

| source | coverage | effort | notes |
| --- | --- | --- | --- |
| **Zotero collections/tags** | unknown | low | `source_record_id: item:XXXX` is recorded for all 131, so the group's own collection structure can be re-read via the Zotero API. If the group already organises by project this is nearly free. **Check this first.** |
| `con/dump-research-info` | unknown | low | already an adapter; may carry a project field the import dropped |
| DOI → text matching | partial | medium | match title/abstract against project names. Will produce false positives; needs review either way |
| manual curation | complete | high | 131 decisions, but authoritative |

**Done when** every publication either names a project or is explicitly
recorded as naming none, with provenance for the mapping.

### Stage 3 — per-project listing on `projects.html`

Mechanically identical to the Components line added for instruments: group
by `generated_by[0].object`, sort by `dcterms:issued` descending, render
under the project entry. Needs a citation formatter (authors, year, title,
venue, DOI link) — `bibo:` types already distinguish article from chapter.

**Done when** a project entry lists its papers and the round-trip against
the previous page shows no loss.

### Stage 4 — per-person listing on `whoweare.html`

`attributed_to` is already complete, so this needs only the formatter from
stage 3 and a decision about volume: Halchenko has 125 papers and the
tier layout gives each person a few lines. Options: the five most recent
with a "more" link; a count that links to the Publications page; or a
collapsed block.

**Done when** each person shows their publications without the page
becoming a bibliography.

### Stage 5 — a Publications page (delayable)

Only worth building once stages 2–4 exist, since it is the same records and
the same formatter with different grouping (by year, by project, by type).
Would want filtering, which means either client-side JS or pre-rendered
facet pages.

## Open questions

1. **Does the Zotero group already organise by project?** Stage 2's cost
   turns entirely on this, and it is one API call to find out.
2. **What counts as "a CON publication"?** All 131 are in the group, but
   `attributed_to` includes people who are collaborators rather than CON
   staff. A paper by Poldrack with no CON author would still be listed.
3. **Venues**: worth importing from Crossref for the 140 DOIs, or leave
   citations venue-less?
4. **Should publications be `part_of` a project instead of `generated_by`?**
   `generated_by` is Generation — the project produced the paper — which
   reads right and is what the one existing link uses. Recording it here so
   the choice is deliberate.

## Not in scope

Citation counts, altmetrics, and BibTeX export. Each is a separate source
with its own staleness, and none is needed for a page that lists what we
wrote.
