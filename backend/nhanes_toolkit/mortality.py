"""
Download and parse NCHS public-use mortality linkage files.

These are fixed-width text files, NOT XPT, with one row per NHANES
respondent (SEQN), giving vital status as of the linkage date, cause of
death recodes, and follow-up time in person-months.

Column layout below matches NCHS's published SAS/Stata/SUDAAN loader
programs for the "MORT_2019_PUBLIC" release. If CDC revises the layout in a
future release, re-check the column positions in the loader program they
ship alongside the .dat file -- a shifted column is easy to spot because
MORTSTAT / ELIGSTAT will stop being clean 0/1/2-ish values.
"""

import os
import time
from typing import Optional

import pandas as pd
import requests

from .config import MORTALITY_BASE, Cycle

CACHE_DIR = os.environ.get("NHANES_CACHE_DIR", os.path.join(os.getcwd(), "nhanes_cache"))
os.makedirs(CACHE_DIR, exist_ok=True)

# (start_col, end_col, dtype) -- 1-indexed, inclusive, per NCHS layout.
_COLSPECS_1INDEXED = {
    "seqn": (1, 6),
    "eligstat": (15, 15),
    "mortstat": (16, 16),
    "ucod_leading": (17, 19),
    "diabetes": (20, 20),
    "hyperten": (21, 21),
    "permth_int": (43, 45),
    "permth_exm": (46, 48),
}


def _colspecs_0indexed_halfopen():
    # pandas read_fwf wants 0-indexed, end-exclusive (start, end) tuples
    return [(s - 1, e) for s, e in _COLSPECS_1INDEXED.values()]


def _mortality_url(cycle: Cycle) -> str:
    fname = f"NHANES_{cycle.mort_start}_{cycle.mort_end}_MORT_2019_PUBLIC.dat"
    return f"{MORTALITY_BASE}/{fname}"


def _cache_path(cycle: Cycle) -> str:
    return os.path.join(CACHE_DIR, f"MORT_{cycle.mort_start}_{cycle.mort_end}.dat")


def fetch_mortality(cycle: Cycle, retries: int = 3, timeout: int = 60) -> pd.DataFrame:
    path = _cache_path(cycle)
    if not os.path.exists(path):
        url = _mortality_url(cycle)
        last_err = None
        for attempt in range(retries):
            try:
                resp = requests.get(url, timeout=timeout)
                resp.raise_for_status()
                with open(path, "wb") as f:
                    f.write(resp.content)
                break
            except requests.RequestException as e:
                last_err = e
                time.sleep(1.5 * (attempt + 1))
        else:
            raise RuntimeError(f"Failed to fetch {url} after {retries} attempts: {last_err}")

    df = pd.read_fwf(path, colspecs=_colspecs_0indexed_halfopen(), names=list(_COLSPECS_1INDEXED.keys()))
    for col in ("seqn", "eligstat", "mortstat", "diabetes", "hyperten", "permth_int", "permth_exm"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    # eligstat == 1 -> eligible for mortality follow-up; others (ineligible /
    # under age 18 at interview, etc.) should generally be dropped before
    # any survival analysis.
    return df
