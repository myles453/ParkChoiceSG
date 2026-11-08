# Existing database reference

The live database is the existing Supabase PostgreSQL `parking_data` schema.
These files preserve its setup history; they do not run when the API starts.
See [the schema guide](../../data-pipeline/SCHEMA.md) for tables, fields and views.

- `schema.sql`, then `schema_v2.sql` through `schema_v8.sql`: historical schema steps.
- `seed_*.sql`: dated policy, operator and URA source snapshots, not automatically current prices.

Do not replay these scripts against the populated team database. A new database or
schema change needs a reviewed maintenance plan, including valid fresh pricing evidence.
API startup does not alter the database, permissions, tariffs or training history.

## Refreshing current data

The [2 November refresh record](../validation/DATA-REFRESH-2026-11-02.md) documents
the completed live import and search verification. Historical seeds above were
not replayed.

- Availability and facility metadata: run `data-pipeline/collect_live.py` with the
  private database/provider environment configured. Its default also imports URA
  prices when the last compiled capture is over one day old; `--include-rates`
  forces a new URA capture and compilation.
- `collect_periodic.py` is the availability/training collector. It does not renew
  manually reviewed HDB or commercial tariffs.
- HDB tariffs: `refresh_hdb_policy.py CAPTURE_DIRECTORY` validates fresh rendered
  official HDB page captures and current facility flags, then reports the proposed
  versions. Add `--apply` only after reviewing the source facts and proposed rules.
  A changed list, peak-window description or unsupported reference flag needs a
  new review rather than an automatic approval.
- `refresh_operator_review_20261102.py` records this specific dated review of the
  archived operator and MOM pages. It deliberately refuses execution on another
  date. Future reviews must inspect current source content and resolve or retain
  blocked windows before approving new versions.

HDB/commercial policy reviews expire after 30 days; URA rate captures expire after
two days. Availability has a much shorter freshness window. A successful
availability pull does not renew a tariff policy. Keep those checks: update source
evidence and import reviewed versions instead of editing timestamps to bypass them.
