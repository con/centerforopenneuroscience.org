# Plan: funding records, and all of YOH's publications

**Status: plan only.** Written 2026-10-11 from
`/home/yoh/doc/resume/halchenko_vita.tex` and
`haxbylab.dartmouth.edu/source/_static/haxbylab.bib`, against
`con-site-specific` at `fd80c0f`.

---

## A. Efforts in the CV with no record

Checked each thing the vita's **Engagements** names against the store.
Present and correct: CON, DANDI, OpenNeuro, EMBER, DataLad,
datasets.datalad.org, SingularityHub (after-life), NeuroDebian, ReproNim,
TR&D3, HeuDiConv, BIDS, NWB, HED, PyMVPA, DueCredit.

Missing:

| effort | what the CV says | proposed record |
| --- | --- | --- |
| **NIDM / NIDM-PROV** | "Contributing to the development of data standards: … NIDM(-PROV)" | `XYZProject/nidm`, Standards |
| **OME-Zarr** | "OME-Zarr (Reviewer)" | `XYZProject/ome-zarr`, Standards, association role reviewer (`marcrel:rev`) |
| **DICOM WG16** | "DICOM (\`\`fly on the wall'' at WG16 meetings)" | `XYZOrganization/dicom-wg16`, association role observer — not a project of ours |
| **ReproIn** | "ReproIn/HeuDiConv", deployed at DBIC | likely an `XYZInstrument` of ReproNim, not a project; HeuDiConv's record already carries the combined name |

Also worth deciding: the CV gives **BIDS Steering Committee 2023–2025** and
**NWB Technical Advisory Board** — the store has the seats but, as noted
before, undated. The CV is the source for the BIDS dates.

---

## B. Funding

### What exists

3 `XYZGrant` records: `nih-dandi`, `nih-ember`, `nih-openneuro`. Each has a
title, an identifier, a NIH Reporter URL and `attributed_to` the PIs.

**None of them links to a project.** Nothing in the store says DANDI is
funded by the DANDI grant.

### What the CV has that the store does not

Nine funding entries, six current and three past, plus one industry award:

| role | funder | award | project |
| --- | --- | --- | --- |
| Co-PI | NIH | 1R24MH117295 | DANDI *(record exists)* |
| Subcontract PI, TR&D lead | NIH | 2P41EB019936-06A1 | ReproNim |
| Co-I | NIH | 2R24MH117179-06 | OpenNeuro *(record exists)* |
| Co-I | NIH | 1R24MH136632-01 | EMBER *(record exists)* |
| Co-I | NIH | 1R01MH127199-01A1 | hyperalignment (Haxby/Gobbini) |
| Co-I | NIH | 1R01MH129397-01A1 | HRF models (Lindquist/Wager) |
| PI | Meta Platforms | — | Brain and AI (OpenNeuro derivatives) |
| PI *(past)* | NSF | 1912266 | DataLad |
| PI *(past)* | NSF | 1429999 | CRCNS US-German data sharing |
| Subcontract PI, TR&D lead *(past)* | NIH | 1P41EB019936-01A1 | ReproNim (CRNC) |

So **7 grants to add and 3 to link**.

### How to model it

The pattern is already in use upstream — psychoinformatics has 47 grants —
and the link lives on the **funded thing**, not on the grant:

```yaml
# on XYZProject/datalad.yaml
influenced_by:
  - schema_type: xyzri:XYZInfluence
    object: xyzrins:grants/nsf-1912266
    roles: [FRAPO:Funding]
```

`FRAPO:Funding` already has an `XYZEntityRole` record upstream; it would be
copied in, as `long-term-goal` was.

Roles on the grant itself go in `attributed_to`, which the three existing
records already use with `obo:NCIT_C19924` (Principal investigator). The
CV distinguishes **Co-PI**, **Co-I** and **Subcontract PI / TR&D lead**;
only PI has a vocabulary term in use. Needs either MARC equivalents or two
minted roles.

### The gap nobody upstream has solved

**Grants carry no dates.** I checked all 47 psychoinformatics grant records:
not one has `started`, `ended` or `at_time`. `XYZGrant` is an `EntityMixin`,
so it has no temporal slot at all — the same limitation as `XYZInstrument`.

That matters here because the CV's split into **Current** and **Past**
funding is exactly a date, and without one the store cannot render it. Three
options:

1. an attribute pair (`dcterms:valid`, or `schema:startDate`/`endDate`) —
   cheap, unenforced, and invisible to the bound rules;
2. a companion `XYZProject` per grant with `started`/`ended`, which is how
   psychoinformatics models funded *programmes* (PoF-IV and its sub-projects);
3. ask upstream whether `XYZGrant` should mix in `ActivityMixin`.

Option 2 is the only one that uses an existing, enforced mechanism. **This
is the question to settle before writing any grant record**, because it
decides the shape of all ten.

### Stages

1. Copy `FRAPO:Funding` role record; decide the PI/Co-PI/Co-I vocabulary.
2. Settle the grant-period question above.
3. Write the 7 missing grants; link all 10 to their projects.
4. Render funding on the project entry — one line, like Components.

---

## C. Publications: all of YOH's

### Where it stands

| | |
| --- | --- |
| bib entries naming Halchenko | **147** (98 with a DOI, 49 without) |
| publication records with a DOI | 98 |
| **in the CV bib, not in the store** | **17** (2015–2026; five from 2026) |
| in the store, not in the CV bib | 17 |

The 17-each-way split is the interesting part: the two sources have drifted
apart in both directions, so neither is a superset. And **49 bib entries
have no DOI at all** — posters, preprints, software citations, the thesis —
which cannot be matched automatically and have to be assessed by hand.

### The rule you asked for

> all of YOH's publications indexed; for others, publications done during
> work at CON

That is two different queries and only one of them is cheap:

- **YOH: everything.** The bib is the source; 17 DOIs to import plus a pass
  over the 49 without one.
- **Others: during CON work.** This needs each person's association span,
  which the store now has (`site-root` associations with `started`/`ended`),
  and each publication's date, which is **in four formats with six malformed
  values** — see `publications.md` stage 1. So the date normalisation is a
  prerequisite for the whole second half of the rule, not an aside.

A publication is then "in scope" when its `dcterms:issued` falls inside the
CON association span of at least one of its `attributed_to` people. That is
checkable, which means it can be a gate rather than a judgement call.

### Per-project listings, collapsed

Once publications link to projects (see `publications.md` stage 2 — only 1
of 131 does today), rendering is the same mechanism as Components:

```html
<details class="publications">
  <summary>Publications (12)</summary>
  <ol>…</ol>
</details>
```

`<details>` is the right element: collapsed by default, no JavaScript, and
it survives the table-of-contents extension's strict parse. The count in the
summary is worth having — it is the thing a reader scans for.

### Stages

1. Normalise `dcterms:issued` (blocks everything).
2. Import the 17 missing DOIs from the bib; triage the 49 without one.
3. Decide the scope rule for non-YOH authors and implement it as a check.
4. Link publications to projects.
5. Render the collapsed per-project block.

---

## Open questions

1. **Grant periods** — option 1, 2 or 3 above. Blocks all ten records.
2. **Co-PI / Co-I / Subcontract PI**: MARC has no exact terms. Mint, or map
   onto `obo:NCIT_C19924` + a qualifier?
3. **Is the haxbylab bib the authority for YOH's publication list**, or is
   the vita's own `\cite` set? The bib has 301 entries for the whole lab;
   147 name Halchenko, and the vita cites a curated subset of those.
4. **Meta Platforms** is funding without a public award id. Record it with
   no identifier, or leave it out?
5. **DICOM WG16** — the CV says "fly on the wall", which is not a role in
   any vocabulary. Worth a record at all?
