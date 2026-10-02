# Pricing storage and calculator readiness — 30 September 2026

Schemas through `schema_v8.sql` and the pricing seeds below are applied to the team's Supabase PostgreSQL project. The database now stores rates separately from live lot counts and can calculate supported motor-car stays. **This is partial pricing coverage, not a guarantee that every carpark and stay can be priced.**

## Measured coverage

Counts were queried after loading and replaying the seeds. Identity totals include staging identities without a current motor-car reading.

| Agency | Canonical identities | Current approved calculators | Other stored evidence or exclusions |
|---|---:|---:|---|
| HDB | 2,284 | 2,122 | 12 restricted-purpose loading bays with separate tariffs; 138 other carparks marked no short-term parking; 12 identities without reference flags. |
| URA | 757 | 657, each explicitly partial | 658 motor-car rate codes in the current capture; one has no usable per-unit calculator. Another 99 identities have no matching motor-car tariff. |
| LTA agency | 40 | 12, with request guards | Five more have numeric operator facts awaiting confirmation; 21 have guide evidence only; Orchard Point and the aggregate Sentosa identity remain unresolved. |

There are 3,450 schedule versions: 2,791 current approved schedules, one current pending schedule and 658 superseded URA versions. `rate_schedule_rules` contains 42,802 rows including history. The latest approved schedules have 34,970 HDB rules, 3,876 URA rules and 80 operator rules (three of those operator rules intentionally block a disputed band). Numeric rates and caps use integer SGD cents. No per-hour float is used.

Both complete URA rate captures contain 3,960 raw rows and 11,880 day interpretations. Original vehicle categories remain separate. Their complete payload arrays were checksum-verified and equal before the newer capture was imported; separate capture timestamps and versions are retained rather than inventing an effective date.

## How the price is calculated

1. Find the current approved tariff version for the exact agency and carpark code.
2. Check capture/review age, parking permission, calendar, payment method and the full stay.
3. Apply the matching day/time bands in Singapore time, including higher-priority central, peak and free-parking rules where applicable.
4. Apply the published billing convention: per minute, rounded blocks, initial tiers or per entry. Grace applies only when the whole EPS stay is within it; it is not deducted from a longer stay.
5. Apply verified caps to their own windows. HDB parking-day caps reset at 07:00, not midnight. Caps are excluded for HDB peak-tariff carparks.
6. Return cents, payment assumption, schedule ID, source and breakdown, or an explicit reason the stay cannot be priced.

`comparison.py` loads schedules and delegates to `pricing.quote_schedule`. Its earlier `quote_hdb` helper is retained only for compatibility and is not used by the current comparison path. The calculator supports whole-minute stays up to 24 hours and near-term arrival within 24 hours. It is an estimate for general motor-car parking, excluding personal discounts, season parking and special vehicle tariffs.

## Checked examples using actual database schedules

These checks used a 30 September database export with the real stored rules. No synthetic availability was added. They exercise the production comparison loader through its six result sets, but do not verify a direct Python database connection.

| Carpark | Arrival (SGT) | Stay | Estimated charge |
|---|---|---:|---:|
| HDB Bras Basah, `BBB` | 1 Oct 10:00 | 60 min | $2.40 |
| HDB Ang Mo Kio, `A1` | 30 Sep 23:00 | 360 min | $5.00, night cap |
| URA Serangoon/Lavender, `S0049` | 1 Oct 10:00 | 60 min | $1.20 |
| Bedok Mall, LTA `65` | 1 Oct 10:00 | 60 min | $1.55 |
| Esplanade, LTA `4` | 1 Oct 10:00 | 60 min | $2.30 |
| IMM, LTA `53` | 1 Oct 10:00 | 60 min | $0.00 only when this is the day's first entry |

The 12 operator calculators cover Bedok Mall, Westgate, Lot One, Junction 8, Plaza Singapura, Funan, Raffles City, Bugis+, CQ @ Clarke Quay, IMM, Tampines Mall and Esplanade. They are partial: crossing operator tariff bands generally remains unquoted. Tampines Mall's weekend/PH 03:00–18:00 band is blocked because the official main table and FAQ disagree about the first-charge duration.

## What still needs confirmation

- URA zero/zero, missing and unfamiliar long-period rows are retained and block their matching windows. Only a $5/510-minute night row paired with the same 60c/30-minute 22:30–07:00 tariff has been approved as a night cap. No general URA day cap is inferred. Day-category changes across midnight and fractional-cent rounding remain guarded.
- HDB peak charges, central changes, free-window crossings, night caps and eligible EPS/Parking.sg day caps are implemented. Some peak public-holiday interpretations, observed-holiday treatment, paper-coupon boundary/day-cap cases and fractional-cent totals still require confirmation.
- Numeric operator facts for Marina Square, Paragon, Cineleisure, Singapore Flyer and National Gallery are stored with source hashes. They have no approved calculator while grace, GST where unclear, surcharges or crossing rules remain unresolved. National Gallery's gate hours and October 2026 closure notice are retained as evidence; a tariff does not imply the carpark is open.
- LTA guide entries are evidence only because GST, grace and billing details are not consistently confirmed. All 40 LTA identities have an evidence or unresolved record, but only 38 have a numeric guide match. The Sentosa feed identity is an aggregate; do not attach one individual beach-carpark rate to it.
- Only the 2026 holiday calendar is loaded. Rates need continued source review. Availability still requires regular collection, and routing/prediction are separate inputs. No arrival-time recommendation is produced yet.

## Stored objects and audit checks

`rate_schedules` stores the version, source, validity, review state, grace, calculator and coverage scope. `rate_schedule_rules` stores bands, billing/tier configuration, caps, priority and source row links. `tariff_source_evidence` stores public source facts, capture time, hash where captured, and review notes. `hdb_loading_bay_tariffs` preserves special tariffs while excluding those bays from ordinary parking recommendations. `carpark_pricing_coverage` reports storage coverage, not a request-specific price.

```sql
SELECT agency, pricing_storage_status, count(*)
FROM parking_data.carpark_pricing_coverage
GROUP BY 1, 2 ORDER BY 1, 2;

SELECT agency, carpark_id, display_name, pricing_storage_status, evidence_note
FROM parking_data.carpark_pricing_coverage
WHERE schedule_id IS NULL ORDER BY agency, carpark_id;
```

All 19 base tables have RLS enabled and no client grants. Informational no-policy notices are expected for this private backend-only schema; use scoped server credentials. The missing loading-bay foreign-key index was fixed. Remaining unused-index notices are informational ([Supabase explanation](https://supabase.com/docs/guides/database/database-linter?lint=0005_unused_index)).

## Seeds, refresh and verification

- Apply schema files in order through v8 before seeding. This is already done on the team project.
- `seed_hdb_rates.sql` materialises the reviewed HDB policy and facility flags into versioned per-carpark rules. `seed_operator_rates.sql` seeds the reviewed operator catalogue and guide evidence; `operator_tariffs_reviewed.json` is its readable snapshot. `seed_operator_capture_hashes.sql` attaches archived source hashes.
- `seed_pending_operator_facts.sql` stores the five additional operator fact sets from `operator_tariffs_pending.json`. Its generator, `seed_pending_operator_facts.py`, requires successful capture records and never promotes those facts into calculators.
- `import_ura_rates.py <verified-run-directory> <new-output-directory>` produces raw and draft import batches. Apply those after the ingestion run is loaded, inspect the raw interpretations, then review and version approved rules. The dated `seed_ura_review.sql` records this review; it is not an unattended approval policy. `seed_ura_capture_20260930.sql` is a one-time optimisation for the two checksum-verified equal captures, not a general refresh mechanism.
- `capture_tariff_sources.py <new-output-directory> <official-url> ...` archives public pages with checksums. Keep new captures immutable, compare changed facts and create a new version; do not simply bump review dates. Operator/HDB rates and flags expire after 30 days in the calculator; URA review and source capture expire after two days. These are project guards, not provider guarantees.
- 70 local tests pass. The database schedule queries and representative day/night quotes were checked, and replaying all five pricing seed files left the counts unchanged. SQL files parse successfully. Archived captures, fixtures and verification reports are under the ignored `data/pricing-research/` directory.

The standalone Python connection still needs a privately configured `DATABASE_URL`; Supabase MCP authentication does not supply it. After configuration, inspect a near-term request with `comparison.py --arrival "<minute-precision ISO time with +08:00>" --duration-minutes 60 --show-unready`. Use `--first-entry yes|no|unknown` for tariffs that require entry history. Stored availability is currently stale, so a correct price alone does not make a carpark eligible for live comparison.

Sources: [HDB charges](https://www.hdb.gov.sg/parking/other-parking-matters/shortterm-parking/shortterm-parking-charges), [HDB EPS](https://www.hdb.gov.sg/parking/other-parking-matters/shortterm-parking/electronic-parking), [URA API](https://eservice.ura.gov.sg/maps/api/), [URA Parking.sg](https://www.ura.gov.sg/car-parks/short-term-parking/parkingsg-mobile-application/), [URA coupon policy](https://www.ura.gov.sg/car-parks/short-term-parking/parking-coupons/), [SPF 2026 handbook](https://www.police.gov.sg/-/media/SPF/Knowledge-Hub/Traffic/BT-ENG-24126.pdf), [LTA guide](https://onemotoring.lta.gov.sg/content/onemotoring/home/owning/ongoing-car-costs/parking/parking_rates.1.html). Operator sources are linked in each stored schedule and fact row.
