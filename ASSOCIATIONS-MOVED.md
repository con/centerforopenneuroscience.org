# Moved

The association records, their evidence overlays, the curation rules and the
validator now live in **`ORINOCO-Lite/con-site-specific`**:

| was here                                   | is now                                        |
| ------------------------------------------ | --------------------------------------------- |
| `content/associations/records/`            | `metadata/records/`                           |
| `content/associations/overlays/`           | `sources/curation-evidence/`                  |
| `content/associations/SCHEMA.md`           | `docs/metadata-curation.md`                   |
| `scripts/validate_associations.py`         | `tools/validate_records.py`                   |
| —                                          | `tools/linkml_check.sh` (schema validation)   |

They were written here on the assumption that `con-site-specific` was a
future destination. It is not: it is the source of CON's metadata, already
holding 24 project, 35 person and 8 organization records. What it was missing
was temporal extent and provenance of the date, which is exactly what this
work adds, so it belongs there and not in a second copy.

The right-hand column is the store's layout after it merged `main` on
2026-10-13, which moved the evidence out of `metadata/overlays/` and the
rules into `docs/`. Nothing in this repo reads those two paths -- the
generators read `metadata/records/` and `content/` -- so the move cost
nothing but this table and a node in the flow diagram.

What stays here are the **generators**: `whoweare.html` and `projects.html`
are rendered from those records.
