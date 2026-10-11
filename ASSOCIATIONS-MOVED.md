# Moved

The association records, their evidence overlays, the curation rules and the
validator now live in **`ORINOCO-Lite/con-site-specific`**:

| was here                                   | is now                                        |
| ------------------------------------------ | --------------------------------------------- |
| `content/associations/records/`            | `metadata/records/`                           |
| `content/associations/overlays/`           | `metadata/overlays/curation-evidence/`        |
| `content/associations/SCHEMA.md`           | `metadata/CURATION.md`                        |
| `scripts/validate_associations.py`         | `tools/validate_records.py`                   |
| —                                          | `tools/linkml_check.sh` (schema validation)   |

They were written here on the assumption that `con-site-specific` was a
future destination. It is not: it is the source of CON's metadata, already
holding 24 project, 35 person and 8 organization records. What it was missing
was temporal extent and provenance of the date, which is exactly what this
work adds, so it belongs there and not in a second copy.

What stays here are the **generators**: `whoweare.html` and `projects.html`
are rendered from those records.
