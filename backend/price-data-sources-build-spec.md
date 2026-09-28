# Build Spec: Multi-Source Lab Test Pricing Layer

## Goal

Extend the existing biomarker → LOINC → CPT/HCPCS → price pipeline (used by the
Physiological Fitness Landscape dashboard / Expected Hazard Information Value
work) so that each biomarker's price is no longer sourced from a single
site (findalabtest.com) but from a ranked set of sources, each tagged by
type. This gives the dashboard a defensible "price" figure (backed by a
government-published rate) plus a realistic "what a person would actually
pay" figure (cash-pay comparison), and a citation-grade source for the paper.

## Data model

Add a `price_observations` table (or equivalent document store) with one row
per (biomarker/test, source, observation):

| field | type | notes |
|---|---|---|
| `test_id` | string | internal ID, joins to existing biomarker/LOINC table |
| `loinc_code` | string | nullable — not all sources map cleanly to LOINC |
| `cpt_hcpcs_code` | string | nullable |
| `source` | enum | see Source registry below |
| `source_tier` | enum | `authoritative` \| `aggregator_transparency` \| `consumer_cash_pay` |
| `price_usd` | decimal | |
| `price_type` | enum | `medicare_reimbursement` \| `negotiated_rate` \| `cash_price` \| `list_price` |
| `payer` | string | nullable — populated for negotiated rates (e.g. specific insurer) |
| `region` | string | nullable — ZIP/state/national |
| `observed_at` | date | date the price was pulled/published |
| `source_url` | string | deep link if available |
| `raw_payload_ref` | string | pointer to raw stored response, for auditability |

Keep the existing `findalabtest.com` scrape as one row per test under
`source = find_a_lab_test`, `source_tier = consumer_cash_pay` — don't
discard it, just stop treating it as the only price.

## Source registry (in priority order)

### 1. CMS Clinical Laboratory Fee Schedule (CLFS) — `source_tier: authoritative`

- **What**: Medicare's published national and carrier-specific payment
  rates per CPT/HCPCS code for lab tests. Updated annually (with quarterly
  files for some categories).
- **Access**: Public, no API key. Downloadable flat files from CMS
  (`https://www.cms.gov/medicare/payment/fee-schedules/clinical-laboratory-fee-schedule-files`).
  Look for the current-year "Annual CLFS file" and any quarterly update
  files. Confirm the exact current URL by fetching the CMS CLFS page — CMS
  reorganizes this page periodically.
- **Format**: Fixed-width or CSV, keyed by HCPCS code, with columns for
  labor/component pricing and the final national/carrier rate.
- **Task for the agent**:
  1. Write an ingestion job that downloads the current CLFS file(s) on a
     schedule (annual, checked monthly for updates).
  2. Parse into `price_observations` rows with `source = cms_clfs`,
     `price_type = medicare_reimbursement`, `region = national` (plus
     carrier-specific rows if a test's rate varies by MAC/locality — flag
     this rather than silently averaging).
  3. Join on HCPCS code to the existing CPT/HCPCS mapping already built
     for the Quest-test-ID → CPT step.
  4. Where no CLFS rate exists for a given HCPCS code (some newer/rarer
     tests, especially molecular pathology codes under the CLFS's
     "gapfill"/"crosswalk" process), leave the row absent rather than
     interpolating, and log it to a `missing_clfs_rate` list for manual
     review.

### 2. Turquoise Health (hospital/payer price-transparency data) — `source_tier: aggregator_transparency`

- **What**: Aggregates the machine-readable negotiated-rate files hospitals
  and payers are required to publish under U.S. price-transparency rules.
  Gives real negotiated rates by payer/plan, not just list price.
- **Access**: Commercial API with a free tier / trial; check current terms
  before committing — this may require a data license for
  redistribution in a public dashboard. If licensing is a blocker, note
  that the underlying raw hospital transparency files (bafflingly large,
  poorly standardized JSON/CSV per hospital) are technically public and
  could be ingested directly as a fallback, at much higher engineering
  cost. Flag this as a build decision for a human before implementing —
  don't default to scraping if a licensing conversation hasn't happened.
- **Task for the agent** (once access/licensing is confirmed):
  1. Ingest negotiated rates matched by CPT/HCPCS code for a representative
     sample of major national payers.
  2. Store as `source = turquoise_health`, `source_tier =
     aggregator_transparency`, `price_type = negotiated_rate`,
     populating `payer` and `region`.
  3. Compute and cache a distribution (median, IQR) per test across payers
     rather than surfacing every individual rate in the UI — the raw
     spread is very wide and a single number per payer is not
     meaningful without a payer-mix context.

### 3. Consumer cash-pay sites — `source_tier: consumer_cash_pay`

Add these alongside the existing findalabtest.com scraper, using the same
scraping/ingestion pattern already built for it:

- Testing.com (formerly Health Testing Centers)
- Walk-In Lab
- Ulta Lab Tests
- DiscountedLabs
- Request A Test
- PrivateMDLabs
- Quest Diagnostics QuestDirect (self-pay portal)
- Labcorp OnDemand (self-pay portal)

For each:
1. Check the site's terms of service for scraping restrictions before
   building a scraper — several of these are run by small operators who
   may object; a polite, low-frequency, cached scrape (e.g. weekly) is
   preferable to live-fetching on every dashboard request regardless.
2. Map each site's test name to the internal `test_id` via a
   name-matching step (fuzzy match + manual override table — test names
   are not standardized across these sites, e.g. "Total Testosterone" vs
   "Testosterone, Total, Serum").
3. Store as `source = <site_slug>`, `source_tier = consumer_cash_pay`,
   `price_type = cash_price`.
4. Because these prices change frequently and inconsistently, keep a
   rolling history rather than overwriting — the dashboard's "expected
   hazard information value" cost input should use a recency-weighted
   average or the most recent observation, decided explicitly rather than
   defaulting to "whatever the last scrape returned."

## Dashboard-facing aggregation

For each biomarker/test, expose three numbers rather than one:

- **Reference price** = CMS CLFS national rate (or carrier rate if
  regionalized) — used as the primary input to the EHIV/VOI cost
  calculation, since it's the most defensible, citable figure.
- **Negotiated-rate range** = median and IQR from Turquoise Health, if
  available — shown as context, not used directly in EHIV math unless a
  future iteration wants a payer-specific mode.
- **Cash-pay range** = min/median/max across the consumer sites — this is
  what an uninsured or high-deductible individual would actually pay
  out of pocket, and is the more realistic number for the
  willingness-to-pay comparison in the paper.

Do not silently blend these into a single "price" — a reviewer or user
should be able to see which figure is being used where and why.

## Paper/citation implications (not a coding task, but keep in view)

- The Methods section should describe this three-tier source structure and
  cite CMS CLFS as the primary price source, with the consumer-cash-pay
  layer described as a secondary, non-peer-reviewed comparison (this
  addresses the reviewer-style comment already flagged on the
  findalabtest.com-only version of the manuscript).
- Log `observed_at` for every price pulled during the analysis window,
  since the paper will need to state the vintage of the pricing data used
  in the final tables.

## Suggested build order

1. CMS CLFS ingestion + join to existing CPT/HCPCS table (highest value,
   no licensing blockers, unblocks the "authoritative price" citation).
2. Extend the existing findalabtest.com scraper pattern to the other
   consumer cash-pay sites.
3. Turquoise Health integration, gated on a licensing decision.
4. Dashboard UI changes to show the three-tier price breakdown instead of
   a single price field.
