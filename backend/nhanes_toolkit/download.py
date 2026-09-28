"""
Fetch and locally cache NHANES .XPT files, and load them with pandas.

pandas can read SAS XPORT (.XPT) files directly via pd.read_sas(...,
format="xport"), including straight from a URL, but caching to disk avoids
re-downloading on every run (files are 1-50MB each; a full multi-cycle,
multi-component pull is a few hundred MB).
"""

import os
import time
from typing import Optional

import pandas as pd
import requests

from .config import NHANES_BASE, Cycle

CACHE_DIR = os.environ.get("NHANES_CACHE_DIR", os.path.join(os.getcwd(), "nhanes_cache"))
os.makedirs(CACHE_DIR, exist_ok=True)


def _component_url(cycle: Cycle, component: str) -> str:
    fname = f"{component}{cycle.suffix}.XPT"
    return f"{NHANES_BASE}/{cycle.years}/{fname}"


def _cache_path(cycle: Cycle, component: str) -> str:
    return os.path.join(CACHE_DIR, f"{component}{cycle.suffix}_{cycle.years}.XPT")


def fetch_component(cycle: Cycle, component: str, retries: int = 3, timeout: int = 60) -> Optional[pd.DataFrame]:
    """
    Download (or load from cache) one NHANES component file for one cycle
    and return it as a DataFrame. Returns None if the file doesn't exist for
    that cycle (not every component is measured every cycle) -- callers
    should skip that cycle for that biomarker rather than treat it as fatal.
    """
    path = _cache_path(cycle, component)
    if os.path.exists(path):
        return pd.read_sas(path, format="xport", encoding="utf-8")

    url = _component_url(cycle, component)
    last_err = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, timeout=timeout)
            if resp.status_code == 404:
                return None  # component not collected this cycle
            resp.raise_for_status()
            with open(path, "wb") as f:
                f.write(resp.content)
            return pd.read_sas(path, format="xport", encoding="utf-8")
        except requests.RequestException as e:
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Failed to fetch {url} after {retries} attempts: {last_err}")


def fetch_demo(cycle: Cycle) -> pd.DataFrame:
    df = fetch_component(cycle, "DEMO")
    if df is None:
        raise RuntimeError(f"DEMO file missing for cycle {cycle.years} -- unexpected, check the URL by hand.")
    return df
