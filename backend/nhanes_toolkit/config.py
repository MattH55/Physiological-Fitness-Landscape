"""
Configuration: NHANES survey cycles, file locations, and biomarker variable maps.

NHANES publishes data in two-year cycles as SAS transport (.XPT) files, hosted
at a stable, predictable URL pattern:

    https://wwwn.cdc.gov/Nchs/Nhanes/{cycle_years}/{COMPONENT}_{suffix}.XPT

Mortality follow-up (linked to the National Death Index) is published
separately as fixed-width .dat files:

    https://ftp.cdc.gov/pub/Health_Statistics/NCHS/datalinkage/linked_mortality/
        NHANES_{start}_{end}_MORT_2019_PUBLIC.dat

NOTE ON NETWORK ACCESS: this code was written and syntax/logic-tested in a
sandboxed environment that cannot reach cdc.gov. It has NOT been run against
the live CDC servers. Run it yourself in an environment with normal internet
access; if CDC changes a URL/layout, the errors will point at the exact
request that failed.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

NHANES_BASE = "https://wwwn.cdc.gov/Nchs/Nhanes"
MORTALITY_BASE = "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/datalinkage/linked_mortality"


@dataclass
class Cycle:
    years: str          # e.g. "2017-2018" -> used in the data URL path
    suffix: str          # e.g. "_J" -> appended to component file names
    mort_start: int       # e.g. 2017 -> used in the mortality file name
    mort_end: int         # e.g. 2018


# Cycles with stable CBC/BIOPRO/mortality-linkage coverage (1999-2018).
# 2017-March 2020 and 2021-2023 cycles have different mortality-linkage
# naming and are left out here; add them the same way once you confirm the
# current file names on the NCHS data-linkage page.
CYCLES: List[Cycle] = [
    Cycle("1999-2000", "",   1999, 2000),
    Cycle("2001-2002", "_B", 2001, 2002),
    Cycle("2003-2004", "_C", 2003, 2004),
    Cycle("2005-2006", "_D", 2005, 2006),
    Cycle("2007-2008", "_E", 2007, 2008),
    Cycle("2009-2010", "_F", 2009, 2010),
    Cycle("2011-2012", "_G", 2011, 2012),
    Cycle("2013-2014", "_H", 2013, 2014),
    Cycle("2015-2016", "_I", 2015, 2016),
    Cycle("2017-2018", "_J", 2017, 2018),
]


@dataclass
class Biomarker:
    """
    A biomarker measured in a specific NHANES lab component file.
    `component` is the file stem (e.g. "CBC", "BIOPRO"); the cycle suffix
    is appended automatically. `variable` is the SAS variable name for the
    measured value. `label`/`units` are for display only.

    Some biomarkers change variable name or component across cycles (CRP is
    the classic example: LBXCRP in CRP_x through ~2009-2010, then a
    high-sensitivity assay LBXHSCRP in HSCRP_x from 2015-2016 on, with a gap
    in between). For those, use `variable_overrides`/`component_overrides`
    keyed by cycle `years` string.
    """
    name: str
    component: str
    variable: str
    label: str
    units: str
    component_overrides: Dict[str, str] = field(default_factory=dict)
    variable_overrides: Dict[str, str] = field(default_factory=dict)

    def component_for(self, cycle: Cycle) -> str:
        return self.component_overrides.get(cycle.years, self.component)

    def variable_for(self, cycle: Cycle) -> str:
        return self.variable_overrides.get(cycle.years, self.variable)


# A starter set of biomarkers with stable naming across most/all of 1999-2018.
# Extend this dict freely -- it's the main thing you'll want to grow.
BIOMARKERS: Dict[str, Biomarker] = {
    "wbc": Biomarker("wbc", "CBC", "LBXWBCSI", "White blood cell count", "1000 cells/uL"),
    "hemoglobin": Biomarker("hemoglobin", "CBC", "LBXHGB", "Hemoglobin", "g/dL"),
    "platelet": Biomarker("platelet", "CBC", "LBXPLTSI", "Platelet count", "1000 cells/uL"),
    "albumin": Biomarker("albumin", "BIOPRO", "LBXSAL", "Serum albumin", "g/dL"),
    "creatinine": Biomarker("creatinine", "BIOPRO", "LBXSCR", "Serum creatinine", "mg/dL"),
    "glucose": Biomarker("glucose", "BIOPRO", "LBXSGL", "Serum glucose (random)", "mg/dL"),
    "total_cholesterol": Biomarker("total_cholesterol", "TCHOL", "LBXTC", "Total cholesterol", "mg/dL"),
    "hdl": Biomarker("hdl", "HDL", "LBDHDD", "HDL cholesterol", "mg/dL"),
    "crp": Biomarker(
        "crp", "CRP", "LBXCRP", "C-reactive protein", "mg/dL",
        component_overrides={
            "2015-2016": "HSCRP", "2017-2018": "HSCRP",
        },
        variable_overrides={
            "2015-2016": "LBXHSCRP", "2017-2018": "LBXHSCRP",
        },
    ),
}

# Demographics variables we always pull, present in every DEMO_x file.
DEMO_VARS = {
    "seqn": "SEQN",
    "sex": "RIAGENDR",        # 1 = Male, 2 = Female
    "age_years": "RIDAGEYR",  # age at screening, top-coded at 80/85 depending on cycle
    "race_eth": "RIDRETH3",   # detailed race/Hispanic-origin recode (from 2011-2012 on; RIDRETH1 before)
    "exam_weight": "WTMEC2YR",  # 2-year MEC exam weight
    "psu": "SDMVPSU",
    "strata": "SDMVSTRA",
}

# RIDRETH1 (used 1999-2010) and RIDRETH3 (used 2011-2018) category labels.
# RIDRETH3 adds a separate "Non-Hispanic Asian" category that RIDRETH1 lacks.
RACE_ETH_LABELS_RIDRETH1 = {
    1: "Mexican American",
    2: "Other Hispanic",
    3: "Non-Hispanic White",
    4: "Non-Hispanic Black",
    5: "Other/Multiracial",
}
RACE_ETH_LABELS_RIDRETH3 = {
    1: "Mexican American",
    2: "Other Hispanic",
    3: "Non-Hispanic White",
    4: "Non-Hispanic Black",
    6: "Non-Hispanic Asian",
    7: "Other/Multiracial",
}

SEX_LABELS = {1: "Male", 2: "Female"}
