"""
Turquoise Health integration — price-data-sources-build-spec.md source #2
(aggregator_transparency tier).

Per the spec: "Flag this as a build decision for a human before
implementing — don't default to scraping if a licensing conversation
hasn't happened." Turquoise Health's negotiated-rate API is commercial;
redistributing its data in a public dashboard may require a data license.
The raw hospital/payer transparency files it aggregates are technically
public but are (per the spec) "bafflingly large, poorly standardized
JSON/CSV per hospital" — a real fallback, but at much higher engineering
cost, and still not something to reach for by default.

This module is intentionally a stub. It exists so the rest of the pipeline
(schema, three-tier dashboard aggregation) has something concrete to call
once a human makes the licensing call, without that decision being made
silently by an agent defaulting to "just scrape the raw files."
"""

LICENSING_STATUS = "PENDING_HUMAN_LICENSING_DECISION"

DECISION_NEEDED = (
    "Turquoise Health integration is gated on a licensing decision that "
    "has not been made:\n"
    "  1. Turquoise Health API (turquoise.health) — commercial, has a "
    "free tier/trial; confirm current terms and whether the free tier "
    "permits redistributing derived stats (median/IQR) in a public "
    "dashboard, or whether a paid data license is required.\n"
    "  2. Fallback: ingest the raw CMS-mandated hospital/payer price-"
    "transparency machine-readable files directly. These are public but "
    "large and inconsistently formatted per hospital — substantially "
    "higher engineering cost, and still worth a licensing/ToS sanity "
    "check on any hospital-specific terms before publishing derived rates.\n"
    "Neither path should be implemented until a human picks one. See "
    "price-data-sources-build-spec.md, source #2."
)


def ingest_turquoise_health(*args, **kwargs):
    """
    Deliberately unimplemented. Raises with the decision that's pending,
    rather than silently returning no data or defaulting to scraping the
    raw transparency files.
    """
    raise NotImplementedError(DECISION_NEEDED)
