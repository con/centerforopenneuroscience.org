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

### Durations: the pattern exists, and I had it wrong

A second pass over psychoinformatics and the TRR379 records settles this.
My earlier reading — "grants carry no dates, nobody upstream has solved it"
— was right about the grant record and wrong about the model.

**The grant is the award; the funded PROJECT carries the period.** Of 47
grants, **37 are linked from a project**, and **34 of those projects carry
`started`/`ended`**:

| project | period |
| ---------- | ------------------------- |
| TRR379 | 2024-10-01 .. 2028-09-30 |
| PETParTI | 2024-03-01 .. 2027-02-28 |
| BRAINTREE | 2024-05-01 .. 2027-04-30 |
| ONCOverse | 2026-04-01 .. 2031-03-31 |
| NEUROCAST | 2027-02-01 .. 2032-01-31 |

So there is no modelling gap to design around, and no need to ask upstream
about `ActivityMixin`. `XYZProject` is an Activity and already has the
slots; `XYZGrant` is an Entity and does not need them. Current versus past
funding falls out of the project's `ended` against today.

The link is `influenced_by` on the project with `FRAPO:Funding`, and four
grants additionally point back with `about: <project>` — so the backlink is
optional and rare.

Grants nest the same way projects do, via `part_of`: `trr379-q02` is
`part_of` `trr379`, `sfb1451-inf` is `part_of` `sfb1451`. ReproNim's
renewal (`2P41EB019936-06A1` after `1P41EB019936-01A1`) is the same shape.

### PI levels: there is no Co-PI or Co-I anywhere

Every role in use across 47 grants and the 67 associations on grant-funded
projects:

| role | on grants | on projects | means |
| ------------------- | --------- | ----------- | ----------------------- |
| `marcrel:fnd` | 31 | — | the funding **agency**, not a person |
| `obo:NCIT_C19924` | 3 | 28 | Principal investigator |
| `obo:NCIT_C45284` | 2 | — | Coordinator |
| `marcrel:app` | 2 | 1 | Applicant |
| `marcrel:led` | 1 | 5 | Lead |
| `marcrel:rtm` | — | 11 | Research team member |

**Co-PI and Co-I do not exist in either store**, and MARC has no equivalent.
The CV distinguishes four levels — PI, Co-PI, Co-I, and Subcontract PI /
TR&D lead — so two or three roles need minting under
`xyzrins:agent-roles/`, as Debian packager and steering-committee member
were. Worth proposing upstream rather than minting locally, since NIH's
levels are not CON-specific.

Note also where the per-person detail goes: TRR379 puts the contributor's
homepage, a prose description and an `Identifier` whose `creator` is the
grant **on the association itself**, not on the person. That is how one
person can have a different blurb per grant.

### Where to get the durations

The CV's Current/Past split is a date but not a dated one. Better sources,
all machine-readable:

- **NIH RePORTER** — `https://api.reporter.nih.gov/v2/projects/search`,
  POST by `project_num`. Returns `project_start_date`, `project_end_date`,
  PI list with roles, and the award amount. Covers 7 of the 10.
- **NSF** — `https://api.nsf.gov/services/v1/awards.json?id=1912266`.
  Returns `startDate`, `expDate`, PI and co-PI names. Covers 2.
- **Meta Platforms** has no public portal; the CV is the only source.

Both give a PI/Co-PI split from the funder's own record, which is a better
authority than the CV for who held which level.

### Stages

1. Copy the `FRAPO:Funding` entity-role record; mint or source the Co-PI and
   Co-I agent roles.
2. Pull periods and PI lists from NIH RePORTER (7 awards) and the NSF award
   API (2), with the response as the evidence `source`.
3. Write the 7 missing grants; link all 10 from their projects with
   `influenced_by` + `FRAPO:Funding`; set `started`/`ended` on the projects
   that do not have them.
4. Render funding on the project entry — one line, like Components.
   Current versus past is then `ended` against today, not a hand-kept
   split.

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

1. ~~**Grant periods**~~ — **answered by the second pass.** The funded
   project carries `started`/`ended`; 34 of 37 grant-linked projects
   upstream already do. Nothing to design, nothing to ask upstream.
2. **Co-PI / Co-I / Subcontract PI**: genuinely absent from both stores and
   from MARC. Mint two or three under `xyzrins:agent-roles/`, or propose
   them upstream? NIH's levels are not CON-specific, so upstream seems
   right — but that is a slower path than this work needs.
3. **Is the haxbylab bib the authority for YOH's publication list**, or is
   the vita's own `\cite` set? The bib has 301 entries for the whole lab;
   147 name Halchenko, and the vita cites a curated subset of those.
4. **Meta Platforms** is funding without a public award id. Record it with
   no identifier, or leave it out?
5. **DICOM WG16** — the CV says "fly on the wall", which is not a role in
   any vocabulary. Worth a record at all?
