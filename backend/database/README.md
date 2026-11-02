# Existing database reference

The live database is the existing Supabase PostgreSQL `parking_data` schema.
These files preserve its setup history; they do not run when the API starts.
See [the schema guide](../../data-pipeline/SCHEMA.md) for tables, fields and views.

- `schema.sql`, then `schema_v2.sql` through `schema_v8.sql`: historical schema steps.
- `seed_*.sql`: dated policy, operator and URA source snapshots, not automatically current prices.

Do not replay these scripts against the populated team database. A new database or
schema change needs a reviewed maintenance plan, including valid fresh pricing evidence.
This publication does not alter the database, permissions, tariffs or training history.
