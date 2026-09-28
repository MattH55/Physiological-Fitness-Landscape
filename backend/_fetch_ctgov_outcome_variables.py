"""
Harvest the ClinicalTrials.gov outcome variables associated with every
biomarker in biomarker_provenance.csv.

For each biomarker we take its MeSH heading (the controlled vocabulary
ClinicalTrials.gov indexes studies against, already resolved into
backend/_mesh_cache.json by _fetch_mesh_terms.py), plus the biomarker's
name, and search the outcome-measure text with `query.outc`.

VERIFIED against live traffic this session (not just docs):
  - base: https://clinicaltrials.gov/api/v2/studies
  - `query.outc` searches the protocol outcome-measure text.
  - `fields` accepts the alias names `NCTId`, `BriefTitle`, `StudyType`,
    `OverallStatus`, `PrimaryOutcomeMeasure`, `SecondaryOutcomeMeasure`,
    `OtherOutcomeMeasure` and returns nested
    `protocolSection.outcomesModule.{primary,secondary,other}Outcomes[].measure`.
  - `countTotal=true` returns `totalCount`.
  - Asking for an outcome field in `fields` ALSO drags in
    `resultsSection.outcomeMeasuresModule.outcomeMeasures[]` (with a huge
    `resultGroups` blob) for studies that have posted results. We ignore it.
  - `query.outc` is a RELEVANCE search, not a literal substring match: a
    search for "C-reactive protein" returned a study whose outcome text is
    "Aerobic fitness". So every returned measure is re-checked against the
    biomarker's terms before we call it associated -- see `_measure_matches`.

Output:
  backend/_ctgov_outcome_variables.json -- resumable raw cache (one entry per
      biomarker slug), so an interrupted run does not re-hit the API.
  biomarker_provenance.csv gains a `clinicaltrials_gov_outcome_variables`
      column (semicolon-joined, most common first, each tagged with the
      outcome type and the number of studies using it).

Usage:
  python backend/_fetch_ctgov_outcome_variables.py               # full run
  python backend/_fetch_ctgov_outcome_variables.py --limit 5     # smoke test
  python backend/_fetch_ctgov_outcome_variables.py --refresh     # ignore cache
  python backend/_fetch_ctgov_outcome_variables.py --no-csv      # cache only
"""

import argparse
import csv
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

CTGOV_BASE = "https://clinicaltrials.gov/api/v2/studies"
CACHE_PATH = "backend/_ctgov_outcome_variables.json"
PROVENANCE_CSV = "biomarker_provenance.csv"
CSV_COLUMN = "clinicaltrials_gov_outcome_variables"
MESH_COLUMN = "clinicaltrials_gov_mesh_term"

# Deliberately excludes resultsSection fields beyond what comes along free.
FIELDS = (
    "NCTId,BriefTitle,StudyType,OverallStatus,"
    "PrimaryOutcomeMeasure,SecondaryOutcomeMeasure,OtherOutcomeMeasure"
)

OUTCOME_TYPE_KEYS = [
    ("PRIMARY", "primaryOutcomes"),
    ("SECONDARY", "secondaryOutcomes"),
    ("OTHER", "otherOutcomes"),
]

# Generic words that carry no discriminating power when checking whether an
# outcome measure actually refers to the biomarker.
_STOPWORDS = {
    "level", "levels", "serum", "plasma", "blood", "concentration",
    "concentrations", "measurement", "measurements", "count", "total",
    "change", "baseline", "value", "values", "score", "test", "testing",
    "and", "or", "of", "in", "the", "a", "an", "at", "to", "for", "with",
    "over", "time", "fasting", "random", "randomized", "dietary",
}

# Short/ambiguous abbreviations must not be matched on their own -- an
# outcome title containing "hs" or "ua" or "kl" is not evidence of anything.
_MIN_TERM_LEN = 3

# Generic container words. On their own these are the PARENT class of the
# biomarker, not the biomarker, so matching them sweeps in every sibling
# analyte. Observed live: stripping the chemical suffix from
# "Lipoprotein(a)" left the bare stem "Lipoprotein", whose substring match
# pulled LDL cholesterol, HDL cholesterol and Apolipoprotein B into
# lipoprotein(a)'s results; likewise "Blood Pressure" swamped the
# systolic/diastolic/pulse-pressure biomarkers and "Pulse" pulled
# "Pulse wave velocity" (vascular stiffness) into resting_heart_rate.
# A variant that reduces to one of these must be rejected as a match target
# unless the whole term IS that phrase (see _is_overbroad_stem).
_OVERBROAD_STEMS = {
    "lipoprotein", "blood pressure", "pulse", "protein", "calcium",
    "hemoglobin", "haemoglobin", "cholesterol", "glucose", "albumin",
    "hormone", "vitamin", "sodium", "potassium", "creatinine", "iron",
    "saturation", "oxygen", "cell", "volume", "mass", "fat", "water",
}


def sanitize_term(t: str) -> str:
    """
    Make a term safe to hand to CT.gov's query parser.

    MeSH headings routinely carry an NMCD synonym in square brackets --
    'Lipoprotein(a) [Lp(a)]' -- and the bracketed form is MeSH query
    syntax, not free text. Passing it through verbatim makes the CT.gov
    query parser reject the whole request with HTTP 400 ("mismatched
    input '[' expecting ..."), which silently costs that term its results.
    """
    return re.sub(r"\[[^\]]*\]", "", t or "").strip()


def _is_overbroad_stem(variant: str, full_term: str) -> bool:
    """
    True if `variant` is a generic parent-class word that is only acceptable
    when the biomarker genuinely is that whole concept.

    The guard only fires when the variant is BROADER than the term it came
    from: a biomarker whose canonical term IS "Blood Pressure" keeps it,
    while a biomarker named "Systolic Blood Pressure" does not get to match
    on bare "Blood Pressure".
    """
    norm_variant = _normalize(variant).strip()
    norm_term = _normalize(full_term).strip()
    if norm_variant not in _OVERBROAD_STEMS:
        return False
    # The variant is only acceptable if the term carries no additional
    # discriminating word beyond the generic stem itself.
    return norm_variant != norm_term

def strip_paren(s: str) -> str:
    """'Body Mass Index (BMI)' -> 'Body Mass Index'."""
    return re.sub(r"\([^)]*\)", "", s).strip()


def load_biomarkers(path: str = PROVENANCE_CSV) -> list:
    """Read the provenance CSV (written with a UTF-8 BOM)."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_cache() -> dict:
    try:
        with open(CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_cache(cache: dict) -> None:
    """
    Persist the cache atomically.

    The full sweep calls this after every biomarker, so a kill mid-write
    would otherwise leave a half-written file that `load_cache` cannot parse
    -- which is exactly how a 238-entry cache was once reduced to a 71-entry
    one. Writing to a sibling temp file and `os.replace`-ing it means the
    cache on disk is always either the old complete version or the new one.
    """
    tmp = CACHE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=1, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, CACHE_PATH)


def build_terms(row: dict) -> list:
    """
    Ordered, deduped search/match terms for one biomarker: MeSH heading
    first (that's what CT.gov indexes against), then the display name with
    parenthetical abbreviations stripped, then the raw name, then a
    slug-derived fallback. Bracket synonyms are stripped (see
    `sanitize_term`) so no term can 400 the query parser.
    """
    terms = []
    seen = set()

    def add(t):
        t = sanitize_term(t)
        key = t.lower()
        if t and key not in seen:
            seen.add(key)
            terms.append(t)

    add(row.get(MESH_COLUMN))
    add(strip_paren(row.get("name", "")))
    add(sanitize_term(row.get("name", "")))
    add(row.get("slug", "").replace("-", " ").replace("_", " ").strip())
    return terms


def _normalize(s: str) -> str:
    """Lowercase; treat hyphens/underscores/slashes uniformly as spaces."""
    return re.sub(r"[-_/]+", " ", (s or "").lower())


def _term_variants(term: str) -> list:
    """
    Match variants for one term. If a term carries a parenthetical
    abbreviation, match on the words OUTSIDE the parens and (separately) on
    the abbreviation itself, since outcome titles use either form
    ("Hemoglobin A1c" vs "HbA1c (lab test)").

    Two guards keep variants from becoming broader than the biomarker:
      * a variant that collapses to a generic parent-class word is dropped
        unless the term itself is that whole phrase (see
        `_is_overbroad_stem`) -- otherwise "Lipoprotein(a)" matches every
        lipoprotein and "Systolic Blood Pressure" matches every
        blood-pressure measure;
      * if stripping the parens destroys the term (they held a chemical
        suffix like "(a)", not an abbreviation), the intact term is kept
        so "Lipoprotein(a)" still matches "Lipoprotein(a)" titles.
    """
    variants = []
    inner = re.findall(r"\(([^)]*)\)", term)
    stripped = strip_paren(term)
    if stripped:
        variants.append(stripped)
    for i in inner:
        i = i.strip()
        # Parenthetical content may hold several comma/space separated
        # abbreviations: "Telopeptide of Type I Collagen (CTX, NTX)".
        for piece in re.split(r"[,;]", i):
            piece = piece.strip()
            if piece and len(piece) >= _MIN_TERM_LEN:
                variants.append(piece)

    # MeSH stores some headings inverted -- "Cholesterol, HDL" really means
    # "HDL Cholesterol", and "Ventricular Dysfunction, Left" means "Left
    # Ventricular Dysfunction". Outcome titles use the natural order, so add
    # the un-inverted reading as an extra variant.
    if "," in term and not inner:
        head, _, tail = term.partition(",")
        head, tail = head.strip(), tail.strip()
        if head and tail:
            variants.append(f"{tail} {head}")

    # Nothing usable survived: parentheses carried a chemical suffix
    # ("Lipoprotein(a)") or an abbreviation too short to trust ("Pulse
    # (bpm)"). Match the term verbatim rather than a mutilated stem.
    if not variants:
        variants.append(term)

    out, seen = [], set()
    for v in variants:
        k = _normalize(v).strip()
        if not k or k in seen:
            continue
        if _is_overbroad_stem(v, term):
            continue
        seen.add(k)
        out.append(v)

    # Every candidate was rejected as an over-broad stem -- the stripped
    # form was a generic parent word ("Lipoprotein" from "Lipoprotein(a)").
    # Match the term verbatim rather than nothing at all, so the biomarker
    # still finds titles that spell it out in full.
    if not out:
        k = _normalize(term).strip()
        if k:
            out.append(term)
    return out


def _sibling_narrows(biomarkers: list, slug: str, term: str,
                     own_mesh: str = "") -> bool:
    """
    True if `term` denotes a SIBLING biomarker's concept rather than this
    one's, so searching on it would sweep in that sibling's outcomes.

    Two directly checkable relations, both observed live:

    1. SHARED HEADING. ClinicalTrials.gov resolved `systolic_blood_pressure`,
       `diastolic_blood_pressure` and `pulse-pressure` all to the single MeSH
       heading "Blood Pressure". Searching any ONE of them on that heading
       necessarily returns the other two's outcome measures.

    2. OVER-BROAD HEADING WITH A QUALIFIED SIBLING. `resting_heart_rate`'s
       heading is "Pulse", and a sibling is named "Resting Heart Rate" --
       i.e. this biomarker's own name is the heading plus a qualifier, so the
       bare heading is the parent class, not the biomarker. "Pulse" matched
       "Pulse wave velocity", a vascular-stiffness measure.

    A heading that is neither shared nor qualified by a sibling is never
    narrowed, however generic it looks: "Calcium" is `serum_calcium`'s own
    heading, "Cholesterol" is `total_cholesterol`'s, "Glucose" is
    `fasting_glucose`'s, "Insulin" is `fasting_insulin`'s. Each is the
    correct concept for that biomarker and a genuine recall asset. Contrast
    `hdl_cholesterol`, whose own heading is the distinct "Cholesterol, HDL".
    """
    key = _normalize(term).strip()
    if not key or key != _normalize(own_mesh).strip():
        # Only our own MeSH heading can be a shared/over-broad heading; a
        # non-heading candidate is judged on its own merits elsewhere.
        return False

    for other_slug, other_terms, other_mesh in biomarkers:
        if other_slug == slug:
            continue
        if _normalize(other_mesh).strip() == key:
            return True
        # Relation 2: a sibling whose NAME is our heading plus a qualifier.
        # Specimen/state modifiers are stripped first, so "Total
        # Testosterone" and "Serum Calcium" reduce to exactly the heading and
        # are recognised as the SAME analyte rather than a qualified sibling.
        # "Resting Heart Rate" keeps "resting" (not a specimen/state word)
        # and so does count as a qualified sibling of the heading "Pulse".
        #
        # The qualifier must be a SINGLE plain word. That excludes the
        # false positives this relation otherwise produces, all of which are
        # separate concepts rather than narrower versions of the heading:
        #   "Testosterone-to-SHBG Ratio"  (derived ratio, hyphenated)
        #   "Non-HDL Cholesterol"         (subtype prefix, hyphenated)
        #   "Insulin-Like Growth Factor I"(different analyte, hyphenated)
        #   "Coronary Artery Calcium Score" (multi-word, different concept)
        #   "HDL Cholesterol" / "LDL Cholesterol" (sibling subtypes, whose
        #       prefix is an abbreviation rather than a qualifier word)
        for ot in other_terms:
            no_words = [w for w in _normalize(ot).split()
                        if w not in _STOPWORDS]
            no = " ".join(no_words)
            if not no or no == key:
                continue
            if no.startswith(key + " "):
                qualifier = no[len(key) + 1:]
            elif no.endswith(" " + key):
                qualifier = no[:-len(key) - 1]
            else:
                continue
            qword = qualifier.split()
            if len(qword) != 1 or "-" in ot:
                continue
            # A sibling subtype's qualifier is typically an ALL-CAPS
            # abbreviation ("HDL", "LDL", "VLDL"). Those are distinct
            # analytes with their own MeSH headings, not narrower readings of
            # this heading, so they must not narrow it. Checked against the
            # RAW term, since `_normalize` has already lowercased everything.
            raw_words = [w.strip("(),;") for w in ot.split()]
            if any(w and w.isupper() and w.lower() == qword[0]
                   for w in raw_words):
                continue
            return True
    return False


def _pick_search_terms(terms: list, slug: str = "", own_mesh: str = "",
                       biomarkers: list = None, max_terms: int = 2) -> list:
    """
    Choose the search terms to actually send to CT.gov.

    SUBSUMPTION, not substring: a term is dropped only when another
         candidate's normalized text contains it verbatim -- "Body Mass
         Index" is genuinely redundant beside "Body Mass Index (BMI)", so
         it goes. A term that is merely one TOKEN of a longer phrase is
         NOT dropped: "Insulin" (the MeSH heading for fasting_insulin) and
         "Testosterone" still catch the many trials that report the plain
         analyte name, so they stay as deliberate recall.
    """
    cleaned, seen = [], set()
    for t in terms:
        key = _normalize(t).strip()
        if not key or len(t) < _MIN_TERM_LEN or key in seen:
            continue
        seen.add(key)
        cleaned.append(t)

    # The MeSH heading is the term CT.gov actually indexes against, and its
    # synonymy (Leukocyte Count, Vitamin A, HbA1c) is the recall engine. It
    # is therefore exempt from subsumption and from the term budget, which
    # would otherwise discard it in favour of a longer display name whose
    # wording does not appear in the outcome titles at all.
    #
    # It is NOT exempt from sibling-narrowing: "Blood Pressure" is the MeSH
    # heading for the systolic biomarker yet is also every sibling's subject,
    # so it must still be dropped there. That is the bug this script exists
    # to not repeat.
    mesh_key = _normalize(own_mesh).strip()
    pinned = [t for t in cleaned if _normalize(t).strip() == mesh_key][:1]
    candidates = [t for t in cleaned if t not in pinned] if pinned else cleaned

    out = []
    for t in candidates:
        norm_t = _normalize(t).strip()
        covered = False
        for o in candidates:
            if o == t:
                continue
            norm_o = _normalize(o).strip()
            # Drop `t` only when `o` is the SAME PHRASE with extra trailing
            # detail -- i.e. `t` survives verbatim as a leading substring of
            # `o`. "Body Mass Index" is dropped for "Body Mass Index (BMI)"
            # for exactly this reason.
            #
            # A reworded or reordered synonym is NOT subsumed: "White Blood
            # Cell Count" carries different words from the MeSH heading
            # "Leukocyte Count", and a display name whose wording never
            # appears in outcome titles cannot replace it.
            if norm_o.startswith(norm_t) and norm_o != norm_t:
                covered = True
                break
        if not covered:
            out.append(t)

    # Narrowing pass: drop genuine parent-class terms of other biomarkers.
    # Applied to the pinned heading too, since a heading shared with a
    # sibling is precisely the contamination this guards against.
    if biomarkers:
        narrowed = [t for t in out
                    if not _sibling_narrows(biomarkers, slug, t, own_mesh)]
        if narrowed:
            out = narrowed
        pinned = [t for t in pinned
                  if not _sibling_narrows(biomarkers, slug, t, own_mesh)]

    # Keep the most specific non-pinned terms when over budget. Ordering by
    # variant count puts "Body Mass Index (BMI)" (2 variants) ahead of a
    # plain slug fallback (1), so truncation drops the weakest candidate
    # rather than an arbitrary one; the sort is stable, so `build_terms`'
    # original MeSH-first ordering breaks ties.
    if len(out) > max_terms:
        out = sorted(out, key=lambda t: -len(_term_variants(t)))
    out = out[:max(0, max_terms - len(pinned))]

    # Pinned MeSH heading leads. An empty list lets `main()` fail loudly
    # instead of silently querying nothing.
    return pinned + out


def _measure_matches(measure: str, term: str) -> str:
    """
    Return the matched term variant if the outcome measure text genuinely
    refers to the biomarker, else "".

    Exact normalized substring first -- cheap, high precision, and how
    nearly all real hits look ('HbA1c', 'Hemoglobin A1c (HbA1c) at 12
    Months'). Only if that fails, fall back to requiring every
    non-stopword token of the term to appear in the measure, which recovers
    reordered phrasings like 'C Reactive Protein, High Sensitivity' without
    letting a single generic word ('protein') create a false association.

    Also used as a guard on measures returned by a RELEVANCE search: a
    query for "C-reactive protein" legitimately returns a study whose only
    outcome is "Aerobic fitness", so the query result set is not evidence
    on its own -- this function is the gate.
    """
    norm_measure = _normalize(measure)
    variants = _term_variants(term)
    if not variants:
        return ""

    for variant in variants:
        norm_term = _normalize(variant).strip()
        if len(norm_term) < _MIN_TERM_LEN:
            continue
        if norm_term in norm_measure:
            return variant

    # Single-token variants are never bag-matched: one generic word is not
    # evidence. Require >=2 discriminating tokens.
    for variant in variants:
        tokens = [t for t in _normalize(variant).split()
                  if len(t) >= _MIN_TERM_LEN and t not in _STOPWORDS]
        if len(tokens) < 2:
            continue
        if all(re.search(rf"\b{re.escape(t)}", norm_measure) for t in tokens):
            return variant
    return ""


def _get_json(url: str, params: dict, timeout: int = 30, retries: int = 3) -> dict:
    last_err = None
    for attempt in range(retries):
        try:
            full = f"{url}?{urllib.parse.urlencode(params)}"
            req = urllib.request.Request(full, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
                json.JSONDecodeError) as e:
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"GET {url} failed after {retries} attempts: {last_err}")


def search_outcome_variables(term: str, page_size: int = 100, max_pages: int = 3,
                             pause: float = 0.25) -> dict:
    """
    Search `query.outc=<term>` and aggregate only the outcome measures that
    actually mention the biomarker.

    Returns:
      {"term": ..., "total_count": N, "studies_scanned": N,
       "measures": {measure_text: {"types": [...], "n_studies": N, "ncts": [...]}}}
    """
    measures: dict = {}
    total_count = 0
    scanned = 0
    next_token = None

    for page in range(max_pages):
        params = {
            "query.outc": term,
            "pageSize": page_size,
            "fields": FIELDS,
            "countTotal": "true",
        }
        if next_token:
            params["pageToken"] = next_token
        data = _get_json(CTGOV_BASE, params)
        if page == 0:
            total_count = data.get("totalCount", 0)

        studies = data.get("studies", [])
        for study in studies:
            scanned += 1
            proto = study.get("protocolSection", {})
            nct = proto.get("identificationModule", {}).get("nctId", "")
            outcomes = proto.get("outcomesModule", {})
            for outcome_type, key in OUTCOME_TYPE_KEYS:
                for om in outcomes.get(key, []) or []:
                    measure = (om.get("measure") or "").strip()
                    if not measure:
                        continue
                    matched = _measure_matches(measure, term)
                    if not matched:
                        continue
                    entry = measures.setdefault(
                        measure, {"types": [], "n_studies": 0, "ncts": [],
                                  "matched_via": {}})
                    if outcome_type not in entry["types"]:
                        entry["types"].append(outcome_type)
                    if nct and nct not in entry["ncts"]:
                        entry["ncts"].append(nct)
                    entry["n_studies"] = len(entry["ncts"])
                    # Record WHICH search term/variant justified this hit so a
                    # generic term's matches stay auditable and separable from
                    # a specific term's.
                    key_m = f"{term}\u0000{matched}"
                    entry["matched_via"][key_m] = entry["matched_via"].get(key_m, 0) + 1

        next_token = data.get("nextPageToken")
        if not next_token or not studies:
            break
        time.sleep(pause)

    return {
        "term": term,
        "total_count": total_count,
        "studies_scanned": scanned,
        "measures": measures,
    }


def format_measures(measures: dict, max_items: int = 25, max_ncts: int = 3) -> str:
    """
    Semicolon-joined summary for the provenance CSV cell, most-used first.
    Each item: '<TYPE> <measure text> (n=<studies>; e.g. NCT...)'.
    Bounded so the cell stays readable in a spreadsheet.
    """
    if not measures:
        return ""
    ordered = sorted(measures.items(), key=lambda kv: (-kv[1]["n_studies"], kv[0]))
    parts = []
    for measure, info in ordered[:max_items]:
        types = "/".join(info["types"]) or "UNKNOWN"
        ncts = ", ".join(info["ncts"][:max_ncts])
        suffix = f"; e.g. {ncts}" if ncts else ""
        parts.append(f"{types} {measure} (n={info['n_studies']}{suffix})")
    extra = len(ordered) - len(parts)
    if extra > 0:
        parts.append(f"[+{extra} more outcome variables]")
    return "; ".join(parts)


def _merge_into(merged: dict, measures: dict) -> None:
    for measure, info in measures.items():
        entry = merged.setdefault(
            measure, {"types": [], "n_studies": 0, "ncts": [], "matched_via": {}})
        for t in info["types"]:
            if t not in entry["types"]:
                entry["types"].append(t)
        for nct in info["ncts"]:
            if nct not in entry["ncts"]:
                entry["ncts"].append(nct)
        entry["n_studies"] = len(entry["ncts"])
        for k, v in info.get("matched_via", {}).items():
            entry["matched_via"][k] = entry["matched_via"].get(k, 0) + v


def main():
    global CACHE_PATH

    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--provenance", default=PROVENANCE_CSV)
    ap.add_argument("--cache", default=CACHE_PATH)
    ap.add_argument("--limit", type=int, default=0,
                    help="Only process the first N biomarkers (smoke test).")
    ap.add_argument("--pages", type=int, default=3,
                    help="Pages of 100 studies per term (default 3 = <=300 studies).")
    ap.add_argument("--only", nargs="*", default=None,
                    help="Only these biomarker slugs.")
    ap.add_argument("--refresh", action="store_true",
                    help="Ignore and overwrite existing cache entries.")
    ap.add_argument("--no-csv", action="store_true",
                    help="Write the JSON cache only; do not touch the CSV.")
    args = ap.parse_args()

    CACHE_PATH = args.cache

    rows = load_biomarkers(args.provenance)
    cache = load_cache()

    # Index every biomarker's candidate terms so the term picker can tell a
    # generic parent-class word ("Blood Pressure") from a useful recall
    # supplement ("Insulin" for fasting_insulin).
    biomarker_index = [
        (r.get("slug", ""), build_terms(r), r.get(MESH_COLUMN, "")) for r in rows
    ]

    if args.only:
        wanted = set(args.only)
        rows = [r for r in rows if r["slug"] in wanted]
    if args.limit:
        rows = rows[:args.limit]

    total = len(rows)
    print(f"Biomarkers to process: {total} (cache has {len(cache)} entries)")

    for i, row in enumerate(rows, 1):
        slug = row["slug"]
        if slug in cache and not args.refresh:
            print(f"[{i}/{total}] {slug:<42} cached "
                  f"({len(cache[slug].get('measures', {}))} outcome variables)")
            continue

        terms = build_terms(row)
        # Prefer the most specific terms: a generic parent word ("Blood
        # Pressure" for the systolic biomarker) adds recall we cannot
        # attribute, so it is dropped when a narrower synonym exists.
        # 3 terms: the MeSH heading, the display name, and one fallback. The
        # MeSH heading is what CT.gov indexes against, so it is worth its own
        # query even when a more specific display name exists -- for
        # hdl_cholesterol the heading "Cholesterol, HDL" is what catches the
        # reworded "High Density Lipoprotein Cholesterol (HDL-C)" measures
        # that the display name alone misses.
        search_terms = _pick_search_terms(terms, slug=slug,
                                          own_mesh=row.get(MESH_COLUMN, ""),
                                          biomarkers=biomarker_index,
                                          max_terms=3)
        merged: dict = {}
        scanned = 0
        total_count = 0
        used_terms = []
        failed_terms = []

        for term in search_terms:
            if len(term) < _MIN_TERM_LEN:
                continue
            try:
                res = search_outcome_variables(term, max_pages=args.pages)
            except RuntimeError as e:
                print(f"[{i}/{total}] {slug:<42} FAILED on '{term}': {e}")
                failed_terms.append(term)
                continue
            used_terms.append(term)
            scanned += res["studies_scanned"]
            total_count = max(total_count, res["total_count"])
            _merge_into(merged, res["measures"])
            time.sleep(0.25)

        # Every term failing is a real failure, not a legitimately empty
        # biomarker -- surface it so it cannot hide behind a 0-result row.
        if search_terms and not used_terms:
            print(f"[{i}/{total}] {slug:<42} ALL TERMS FAILED "
                  f"({failed_terms}) -- not caching")
            continue

        cache[slug] = {
            "biomarker_id": row["biomarker_id"],
            "name": row["name"],
            "mesh_term": row.get(MESH_COLUMN, ""),
            "search_terms": used_terms,
            "failed_terms": failed_terms,
            "total_count": total_count,
            "studies_scanned": scanned,
            "measures": merged,
            "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        print(f"[{i}/{total}] {slug:<42} {len(merged)} outcome variables "
              f"from {scanned} studies (totalCount {total_count})")
        save_cache(cache)

    save_cache(cache)
    print(f"\nCache written to {CACHE_PATH} ({len(cache)} biomarkers)")

    if args.no_csv:
        return

    write_provenance_column(args.provenance, cache)


def write_provenance_column(path: str, cache: dict) -> None:
    """Add/refresh the outcome-variables column on the provenance CSV."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        all_rows = list(reader)

    if CSV_COLUMN not in fieldnames:
        fieldnames.append(CSV_COLUMN)

    filled = 0
    for r in all_rows:
        entry = cache.get(r.get("slug", ""))
        r[CSV_COLUMN] = format_measures(entry["measures"]) if entry else ""
        if r[CSV_COLUMN]:
            filled += 1

    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"Updated {path}: {filled}/{len(all_rows)} rows have outcome "
          f"variables in '{CSV_COLUMN}'")


if __name__ == "__main__":
    main()
