# Multi-Source Pricing Layer — Build Status

Implements `price-data-sources-build-spec.md` on top of the existing
`test_cost_models.py` / `test_cost_ingestion.py` / `seed_test_cost_data.py`
pipeline (kept, not replaced — see "What changed" below).

## What's implemented and verified working

1. **Schema** (`test_cost_models.py`)
   - `TestPrice` gained `source_tier`, `payer`, `raw_payload_ref`.
   - `TestCostSummary` gained explicit tier-1/2/3 fields
     (`reference_price*`, `negotiated_rate_*`, `cash_pay_*`) alongside the
     legacy `d2c_*`/`cms_clfs`/`cms_private_payer_*` fields (kept for
     backward compatibility).
   - `SOURCE_REGISTRY` — the canonical source → tier mapping, including
     legacy slug aliases (`FINDLABTEST`, `CMS_CLFS`, `CMS_PRIVATE_PAYER`).
   - Migration: `python -m backend.migrate_price_sources_schema` (adds the
     new columns to the existing SQLite tables; `create_all` alone won't
     alter existing tables).

2. **CMS CLFS ingestion — real, tested against production CMS data**
   (`backend/ingest_cms_clfs.py`, run via `python -m backend.ingest_cms_clfs`)
   - Discovers the current quarterly file from the live CLFS files page
     (two-step: listing page → detail page → AMA license-click-through
     zip link), downloads it, parses the CSV, and joins it onto every
     `TestBillingCode` row by HCPCS code (CPT/HCPCS duplicates for the
     same numeric code are deduped, preferring HCPCS per
     `TEST_COST_BUILD_SPEC.md` §0.3 — CPT descriptions are AMA-copyrighted,
     HCPCS is public domain).
   - Verified end-to-end on 2026-09-12 against the real CY2026 Q3 CLFS
     file: 6 of the 10 seed HCPCS codes matched (hba1c $9.71, LDL $6.47,
     HDL $11.53, triglycerides $5.74, eGFR $8.46, ferritin $5.16 — all
     real national Medicare rates). The other 4 (hs-CRP `81671`,
     ALT `82928`, AST `82936`, vitamin D `82312`) do **not** exist in the
     CLFS file — those were placeholder/incorrect codes in the seed data,
     not omissions in this ingestion. They're logged to
     `data/missing_clfs_rate.csv` rather than silently priced, per spec;
     someone needs to look up the correct HCPCS codes for those four
     (hs-CRP is `86141`, ALT is `84460`, AST is `84450` — not yet verified
     against the CLFS file or wired back into the seed data).
   - `discover_current_clfs_file()` fails loudly (not silently) if CMS
     reorganizes the page again; `CLFS_FILE_SLUG` env var overrides it.

3. **Three-tier dashboard aggregation** — `TestCostSummary.to_dict()["three_tier_price"]`
   exposes `reference_price` / `negotiated_rate_range` / `cash_pay_range`
   as three separate labeled objects, never blended, matching the spec's
   "Dashboard-facing aggregation" section. Surfaced automatically through
   the existing `/api/tests/{test_id}` and `/api/biomarkers/{id}/test-value`
   endpoints (no endpoint changes needed — `TestCostSummary.to_dict()` is
   already called there).
   - Verified: `test_hba1c` now returns
     `reference_price.amount = 9.71` (source `cms_clfs`, real),
     `cash_pay_range = {min: 20, median: 35, max: 50}` (from the existing
     seed placeholder prices), `negotiated_rate_range` all-null (correctly
     empty — Turquoise Health isn't implemented; see below).

4. **`/api/price-sources/status`** — new audit endpoint listing every
   registered source, its tier, and (for consumer cash-pay sites) live
   robots.txt findings and whether it's blocked pending human review.

5. **Consumer cash-pay framework** (`backend/consumer_price_sources.py`)
   — the shared plumbing every site scraper needs: robots.txt check,
   weekly-cache-by-date fetch/save, rolling-history price upsert (never
   overwrites a prior day's pull), and the tier-3 min/median/max rollup
   (`update_cash_pay_summary` — chosen default: most recent retrieval
   date's observations, not a recency-weighted average across all
   history; documented in the docstring per the spec's instruction to
   decide explicitly).

## What's deliberately NOT implemented, and why

- **Per-site HTML parsers for the 8 new consumer cash-pay sites
  (Testing.com, Walk-In Lab, Ulta Lab Tests, DiscountedLabs, Request A
  Test, PrivateMDLabs, QuestDirect, Labcorp OnDemand) and find_a_lab_test
  itself.** The spec requires checking each site's robots.txt/ToS before
  scraping — done for robots.txt (results in `SOURCE_REGISTRY[...]
  ["robots_txt_status"]` and `/api/price-sources/status`), but a
  robots.txt allow is not a ToS reading, and two sites
  (DiscountedLabs, Request A Test) actively serve a Cloudflare bot
  challenge to non-browser requests — scraping those without explicit
  permission would mean deliberately working around a bot defense, which
  this build does not do. `ulta_lab_tests` has no robots.txt content
  either way (inconclusive). Building a reliable parser for each of the
  remaining 6 open sites means iterating against each site's real,
  changing markup — real work, not something to fabricate selectors for
  sight unseen. `consumer_price_sources.py` has the fetch/cache/upsert
  scaffolding ready; each site needs one `parse_price_page()` function
  written and verified against a live pull.

- **Turquoise Health.** Per the spec's explicit instruction ("Flag this
  as a build decision for a human before implementing — don't default to
  scraping if a licensing conversation hasn't happened"), this is a stub
  (`backend/turquoise_health.py`) that raises `NotImplementedError` naming
  the two real options (paid API license vs. ingesting the raw
  CMS-mandated hospital transparency files directly) rather than picking
  one. `negotiated_rate_range` will stay empty until someone decides.

## Next steps for a human

1. Pick a licensing path for Turquoise Health (or explicitly defer it).
2. Read the actual Terms of Service (not just robots.txt) for the 6 open
   consumer cash-pay sites before writing their parsers.
3. Fix the 4 wrong/placeholder HCPCS codes in `seed_test_cost_data.py`
   (hs-CRP, ALT, AST, vitamin D) — see `data/missing_clfs_rate.csv`.
4. Schedule `python -m backend.ingest_cms_clfs` to run monthly (the CLFS
   file updates quarterly; checking monthly catches CMS's schedule
   without over-fetching).
