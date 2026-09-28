"""
Conventional clinical reference bands used ONLY by the distributional
"borderline mass" testing-priority metric (testing_priority.py). These are
NOT derived from the mortality model or from NHANES data -- they're
standard clinical decision points, included here so "how much of this
cohort sits near the point where a test result would change risk
category" can be computed without needing outcome data at all.

Every band below is the "decision zone" around a well-established
guideline cutoff, not the full abnormal range. Sourced and verified this
session unless noted; a clinician should still review before production
use, and several biomarkers are deliberately left undefined (None) rather
than guessed, because they don't have one clean two-sided cutoff to band
around (WBC, platelets, hemoglobin, creatinine -- these have context-
dependent or two-sided normal ranges that resist a simple "band," and
creatinine in particular needs eGFR, not a raw cutoff, to mean anything
clinically).

- crp: AHA hs-CRP cardiovascular risk categories -- <1.0 low, 1.0-3.0
  average, >3.0 high. Verified against multiple sources this session
  (e.g. AHA-referenced lab reference ranges). Band = the average-risk
  zone itself (1.0-3.0), since that's the officially recognized
  "intermediate/borderline" category, not an invented narrower window.
- glucose: ADA fasting-glucose criteria -- <100 normal, 100-125
  prediabetes, >=126 diabetes. Band = the prediabetes zone (100-125),
  same reasoning as CRP.
- total_cholesterol: NCEP ATP III -- <200 desirable, 200-239 borderline
  high, >=240 high. Band = a window around the 200 mg/dL cutoff
  (190-210), since ATP III's "borderline" category is wide (200-239);
  narrowed here to the zone right at the decision point rather than the
  whole 40mg/dL category.
- hdl: ATP III low-HDL cutoffs differ by sex (<40 mg/dL men, <50 mg/dL
  women count as low). Provided as sex-specific bands; apply the one
  matching the cohort's sex_label.
"""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class ThresholdBand:
    low: float
    high: float
    label: str
    source_note: str


CLINICAL_REFERENCE_BANDS: Dict[str, Optional[ThresholdBand]] = {
    "crp": ThresholdBand(1.0, 3.0, "AHA average-risk zone",
                          "AHA hs-CRP cardiovascular risk categories"),
    "glucose": ThresholdBand(100, 125, "ADA prediabetes zone",
                              "ADA fasting plasma glucose criteria"),
    "total_cholesterol": ThresholdBand(190, 210, "near ATP III 200mg/dL cutoff",
                                        "NCEP ATP III desirable/borderline-high boundary"),
    "wbc": None,
    "hemoglobin": None,
    "platelet": None,
    "albumin": None,
    "creatinine": None,  # needs eGFR (age/sex/race-adjusted), not a raw cutoff
}

# hdl needs a sex-specific band -- handled separately since it doesn't fit
# the single-band shape above.
HDL_BANDS_BY_SEX = {
    "Male": ThresholdBand(35, 45, "near ATP III 40mg/dL low-HDL cutoff (men)",
                           "NCEP ATP III low-HDL threshold, men"),
    "Female": ThresholdBand(45, 55, "near ATP III 50mg/dL low-HDL cutoff (women)",
                             "NCEP ATP III low-HDL threshold, women"),
}
