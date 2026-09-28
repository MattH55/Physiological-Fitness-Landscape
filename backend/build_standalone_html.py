"""
Single-file HTML compiler for Physiological Fitness Landscape.
Compiles backend SQLite database (including the entire Optimization Layer:
scenarios, curves, models, expected values, domain guardrails, and benefit distributions),
embedded frontend stylesheets, FontAwesome, Tailwind CDN, and Plotly.js into
a single self-contained, fully interactive `frontend/index.html` file that runs
100% offline without any server dependencies.
"""

import json
import sqlite3
from pathlib import Path

from backend.life_tables import serialize_life_tables
from backend.voi import voi_config_dict

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "mortality_biomarkers.db"
FRONTEND_HTML_PATH = BASE_DIR / "frontend" / "index.html"
DIST_HTML_PATH = BASE_DIR / "dist" / "index.html"
ROOT_HTML_PATH = BASE_DIR / "index.html"
CSS_PATH = BASE_DIR / "frontend" / "styles.css"


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def compile_database_payload():
    conn = get_db_connection()
    c = conn.cursor()

    # 1. Fetch all biomarkers
    c.execute("SELECT * FROM biomarker ORDER BY category, name")
    biomarker_rows = [dict(row) for row in c.fetchall()]

    # 2. Fetch associations, distributions, interventions, sources, diseases, and alterations
    c.execute("SELECT * FROM mortality_association")
    associations = [dict(row) for row in c.fetchall()]

    c.execute("SELECT * FROM population_distribution")
    distributions = [dict(row) for row in c.fetchall()]

    c.execute("SELECT * FROM intervention")
    interventions = [dict(row) for row in c.fetchall()]

    c.execute("SELECT * FROM source")
    sources = [dict(row) for row in c.fetchall()]
    source_by_id = {s["id"]: s for s in sources}

    def _attach_source(row):
        if not row:
            return row
        sid = row.get("source_id")
        if sid is not None and sid in source_by_id:
            row["source"] = source_by_id[sid]
        return row

    for a in associations:
        _attach_source(a)
    for d in distributions:
        _attach_source(d)
    for i in interventions:
        _attach_source(i)

    try:
        c.execute("SELECT * FROM disease ORDER BY category, name")
        disease_rows = [dict(row) for row in c.fetchall()]
    except Exception:
        disease_rows = []

    try:
        # Order so that gene alterations (Type A Molecular / subtype 'Gene') are LOWEST priority.
        # Priority: Functional (E) -> Lab/Clinical (B) -> Pathology (D) -> Scales & PROs (C) -> Molecular (A) last.
        # Within any type, subtype 'Gene' rows are pushed to the end.
        c.execute(
            """
            SELECT * FROM disease_alteration
            ORDER BY
                CASE alteration_type_code
                    WHEN 'E' THEN 1
                    WHEN 'B' THEN 2
                    WHEN 'D' THEN 3
                    WHEN 'C' THEN 4
                    WHEN 'A' THEN 5
                    ELSE 6
                END,
                CASE WHEN subtype = 'Gene' THEN 1 ELSE 0 END,
                name
            """
        )
        disease_alterations = [dict(row) for row in c.fetchall()]
    except Exception:
        disease_alterations = []

    # 3. Fetch Optimization Layer tables
    try:
        c.execute("SELECT * FROM optimization_scenario ORDER BY shift_magnitude ASC")
        scenarios = [dict(row) for row in c.fetchall()]
    except Exception:
        scenarios = []

    try:
        c.execute("SELECT * FROM biomarker_hr_curve")
        hr_curves = [dict(row) for row in c.fetchall()]
    except Exception:
        hr_curves = []

    try:
        c.execute("SELECT * FROM biomarker_optimization_model")
        optimization_models = [dict(row) for row in c.fetchall()]
    except Exception:
        optimization_models = []

    try:
        c.execute("SELECT * FROM biomarker_expected_value")
        expected_values = [dict(row) for row in c.fetchall()]
    except Exception:
        expected_values = []

    # 4. Fetch Conditions, Biomarker Signatures, Distribution Fits, and HR Functions
    try:
        c.execute("SELECT * FROM condition ORDER BY name")
        condition_rows = [dict(row) for row in c.fetchall()]
    except Exception:
        condition_rows = []

    try:
        c.execute("SELECT * FROM biomarker_signature ORDER BY panel_name, biomarker_name")
        signature_rows = [dict(row) for row in c.fetchall()]
    except Exception:
        signature_rows = []

    try:
        c.execute("SELECT * FROM distribution_fit")
        dist_fit_rows = [dict(row) for row in c.fetchall()]
    except Exception:
        dist_fit_rows = []

    try:
        c.execute("SELECT * FROM hr_function")
        hr_func_rows = [dict(row) for row in c.fetchall()]
    except Exception:
        hr_func_rows = []

    # Test prices (findlabtest.com cash-pay scrape / CMS CLFS) keyed by biomarker_id.
    # cash_pay_median/cash_pay_source_count come from the real
    # backend.ingest_find_a_lab_test scrape (price-data-sources-build-spec.md);
    # reference_price is the real CMS CLFS national rate from
    # backend.ingest_cms_clfs. Both fall back to the older
    # reference_consumer_price/cms_clfs fields for tests seeded before that
    # pipeline existed.
    price_by_bm = {}
    try:
        c.execute(
            """
            SELECT t.canonical_biomarker_id, t.test_id, t.loinc_code,
                   s.reference_consumer_price, s.cms_clfs,
                   s.cash_pay_median, s.cash_pay_min, s.cash_pay_max, s.cash_pay_source_count,
                   s.cash_pay_standalone_median, s.cash_pay_standalone_min,
                   s.cash_pay_standalone_max, s.cash_pay_standalone_count,
                   s.reference_price, s.reference_price_source
            FROM lab_tests t
            LEFT JOIN test_cost_summary s ON s.test_id = t.test_id
            WHERE t.canonical_biomarker_id IS NOT NULL
            """
        )
        for row in c.fetchall():
            bid = row["canonical_biomarker_id"]
            mapping = dict(price_by_bm.get(bid) or {})
            loinc_map = dict(mapping.get("loincToTestId") or {})
            if row["loinc_code"] and row["test_id"]:
                loinc_map[row["loinc_code"]] = row["test_id"]
            cash_median = row["cash_pay_median"] if row["cash_pay_median"] is not None else row["reference_consumer_price"]
            if cash_median is not None:
                mapping["testPriceUSD"] = cash_median
                mapping["testPriceMin"] = row["cash_pay_min"]
                mapping["testPriceMax"] = row["cash_pay_max"]
                mapping["testPriceSourceCount"] = row["cash_pay_source_count"]
                # Standalone-analyte subset (multi-analyte panels excluded) —
                # the figure actually comparable to this one biomarker's test
                # cost, since a panel's price also buys several other analytes.
                # Stays None when the source has no standalone product at all
                # (e.g. 25-hydroxyvitamin D, only sold in panels).
                mapping["testPriceStandaloneMedian"] = row["cash_pay_standalone_median"]
                mapping["testPriceStandaloneMin"] = row["cash_pay_standalone_min"]
                mapping["testPriceStandaloneMax"] = row["cash_pay_standalone_max"]
                mapping["testPriceStandaloneCount"] = row["cash_pay_standalone_count"]
            cms_rate = row["reference_price"] if row["reference_price"] is not None else row["cms_clfs"]
            if cms_rate is not None:
                mapping["cmsReimbursementUSD"] = cms_rate
            mapping["loincToTestId"] = loinc_map
            price_by_bm[bid] = mapping
    except Exception:
        price_by_bm = {}

    # Build maps
    assoc_map = {}
    for a in associations:
        assoc_map.setdefault(a["biomarker_id"], []).append(a)

    dist_map = {}
    for d in distributions:
        dist_map.setdefault(d["biomarker_id"], []).append(d)

    itv_map = {}
    for i in interventions:
        itv_map.setdefault(i["biomarker_id"], []).append(i)

    curve_map = {}
    for cv in hr_curves:
        curve_map.setdefault(cv["biomarker_id"], []).append(cv)

    model_map = {}
    for om in optimization_models:
        model_map.setdefault(om["biomarker_id"], []).append(om)

    ev_map = {}
    for ev in expected_values:
        ev_map.setdefault(ev["biomarker_id"], []).append(ev)

    dist_fit_map = {}
    for df in dist_fit_rows:
        dist_fit_map.setdefault(df["biomarker_id"], []).append(_attach_source(df))

    hr_func_map = {}
    for hf in hr_func_rows:
        hr_func_map.setdefault(hf["biomarker_id"], []).append(_attach_source(hf))

    scenario_by_id = {s["id"]: s for s in scenarios}

    # Enrich diseases with alterations & stats
    disease_by_id = {d["id"]: d for d in disease_rows}
    disease_by_slug = {d["slug"]: d for d in disease_rows}
    disease_alterations_map = {}
    biomarker_disease_alterations_map = {}

    for alt in disease_alterations:
        alt_dict = dict(alt)
        d_parent = disease_by_id.get(alt["disease_id"])
        if d_parent:
            alt_dict["disease_name"] = d_parent["name"]
            alt_dict["disease_slug"] = d_parent["slug"]
            alt_dict["disease_category"] = d_parent["category"]
            alt_dict["us_dalys"] = d_parent.get("us_dalys")

        disease_alterations_map.setdefault(alt["disease_id"], []).append(alt_dict)

        if alt.get("is_biomarker_match") and alt.get("biomarker_id"):
            biomarker_disease_alterations_map.setdefault(alt["biomarker_id"], []).append(alt_dict)

    enriched_diseases = []
    for d in disease_rows:
        d_id = d["id"]
        d_alts = disease_alterations_map.get(d_id, [])
        d_dict = dict(d)
        d_dict["alterations"] = d_alts
        d_dict["alterations_count"] = len(d_alts)
        d_dict["biomarker_matches_count"] = sum(1 for a in d_alts if a.get("is_biomarker_match"))
        enriched_diseases.append(d_dict)

    # Enrich biomarkers
    enriched_biomarkers = []
    for b in biomarker_rows:
        b_id = b["id"]
        b_assocs = assoc_map.get(b_id, [])
        b_dists = dist_map.get(b_id, [])
        b_itvs = itv_map.get(b_id, [])
        b_curves = curve_map.get(b_id, [])
        b_models = model_map.get(b_id, [])
        b_evs = ev_map.get(b_id, [])

        overall_dist = next((d for d in b_dists if d["sex"] == "all" and d["age_band"] == "all"), (b_dists[0] if b_dists else None))
        max_hr = max([a["hazard_ratio"] for a in b_assocs], default=None)
        primary_dir = b_assocs[0]["direction"] if b_assocs else "positive"

        # Enrich expected values with scenario slug/name
        enriched_evs = []
        for ev in b_evs:
            ev_dict = dict(ev)
            sc = scenario_by_id.get(ev["scenario_id"])
            if sc:
                ev_dict["scenario_slug"] = sc["slug"]
                ev_dict["scenario_name"] = sc["name"]
                ev_dict["shift_magnitude"] = sc["shift_magnitude"]
                ev_dict["shift_type"] = sc["shift_type"]
            enriched_evs.append(ev_dict)

        enriched_b = dict(b)
        enriched_b["associations"] = b_assocs
        enriched_b["population_distributions"] = b_dists
        enriched_b["interventions"] = b_itvs
        enriched_b["curves"] = b_curves
        enriched_b["distribution_fits"] = dist_fit_map.get(b_id, [])
        enriched_b["hr_functions"] = hr_func_map.get(b_id, [])
        enriched_b["optimization_models"] = b_models
        enriched_b["expected_values"] = enriched_evs
        enriched_b["max_hazard_ratio"] = max_hr
        enriched_b["primary_direction"] = primary_dir
        enriched_b["population_median"] = overall_dist.get("p50") if overall_dist else None
        enriched_b["population_mean"] = overall_dist.get("mean") if overall_dist else None
        enriched_b["population_sd"] = overall_dist.get("sd") if overall_dist else None
        enriched_b["interventions_count"] = len(b_itvs)
        enriched_b["has_nhanes"] = bool(b["nhanes_code"])

        priced = price_by_bm.get(b_id) or {}
        enriched_b["testPriceUSD"] = b.get("test_price_usd") if b.get("test_price_usd") is not None else priced.get("testPriceUSD")
        enriched_b["cmsReimbursementUSD"] = b.get("cms_reimbursement_usd") if b.get("cms_reimbursement_usd") is not None else priced.get("cmsReimbursementUSD")
        enriched_b["testPriceMin"] = priced.get("testPriceMin")
        enriched_b["testPriceMax"] = priced.get("testPriceMax")
        enriched_b["testPriceSourceCount"] = priced.get("testPriceSourceCount")
        # Standalone-analyte figures: None (not 0) when no standalone product
        # exists in the source, so the pane can say "panel-only" instead of
        # implying a free test.
        enriched_b["testPriceStandaloneMedian"] = priced.get("testPriceStandaloneMedian")
        enriched_b["testPriceStandaloneMin"] = priced.get("testPriceStandaloneMin")
        enriched_b["testPriceStandaloneMax"] = priced.get("testPriceStandaloneMax")
        enriched_b["testPriceStandaloneCount"] = priced.get("testPriceStandaloneCount")
        # True when c_test comes from panel prices only — the pane must say so,
        # since a panel's price also buys the other analytes it contains.
        enriched_b["testPriceBlendedMedian"] = priced.get("testPriceUSD")
        enriched_b["testPriceIsPanelDerived"] = (
            priced.get("testPriceStandaloneMedian") is None
            and enriched_b.get("testPriceUSD") is not None
        )
        loinc_map = b.get("loinc_to_test_id")
        if isinstance(loinc_map, str):
            try:
                loinc_map = json.loads(loinc_map)
            except Exception:
                loinc_map = {}
        enriched_b["loincToTestId"] = loinc_map or priced.get("loincToTestId") or {}
        # findlabtest.com (no "a" — "findalabtest.com" does not exist and
        # was a longstanding typo here) is a price-comparison aggregator,
        # not the payer of record; cite it as such rather than as a single
        # store. n_sources counts observed price points, not distinct
        # providers: several cards can belong to the same lab, so label it
        # "price points" rather than overstating provider coverage.
        n_sources = priced.get("testPriceSourceCount")
        n_standalone = priced.get("testPriceStandaloneCount")
        enriched_b["testPriceSourceUrl"] = "https://www.findlabtest.com"
        if n_sources:
            label = f"findlabtest.com (median across {n_sources} price points"
            label += f"; {n_standalone} standalone)" if n_standalone else "; panel-only)"
        else:
            label = "findlabtest.com"
        enriched_b["testPriceSourceLabel"] = label

        # Top 1.0-SD optimization metric for quick preview
        ev_100 = next((ev for ev in enriched_evs if ev.get("scenario_slug") == "sd_100"), None)
        if ev_100:
            enriched_b["rel_hazard_red_100"] = ev_100.get("relative_hazard_reduction")
            enriched_b["delta_hr_100"] = ev_100.get("delta_hr")
            enriched_b["baseline_expected_hr"] = ev_100.get("baseline_expected_hr")
            enriched_b["optimized_expected_hr_100"] = ev_100.get("optimized_expected_hr")
        else:
            enriched_b["rel_hazard_red_100"] = 0.0
            enriched_b["delta_hr_100"] = 0.0
            enriched_b["baseline_expected_hr"] = 1.0
            enriched_b["optimized_expected_hr_100"] = 1.0

        enriched_biomarkers.append(enriched_b)

    categories = sorted(list({b["category"] for b in biomarker_rows if b["category"]}))
    specimens = sorted(list({b["specimen_type"] for b in biomarker_rows if b["specimen_type"]}))
    bodily_fluids = sorted(list({b["bodily_fluid"] for b in biomarker_rows if b.get("bodily_fluid")}))
    primary_organs = sorted(list({b["primary_organ"] for b in biomarker_rows if b.get("primary_organ")}))
    tissue_origins = sorted(list({b["tissue_origin"] for b in biomarker_rows if b.get("tissue_origin")}))
    disease_categories = sorted(list({d["category"] for d in disease_rows if d.get("category")}))

    stats = {
        "biomarkers_total": len(biomarker_rows),
        "mortality_associations_total": len(associations),
        "population_distributions_total": len(distributions),
        "interventions_total": len(interventions),
        "sources_total": len(sources),
        "scenarios_total": len(scenarios),
        "diseases_total": len(disease_rows),
        "disease_alterations_total": len(disease_alterations),
        "disease_biomarker_matches_total": sum(1 for a in disease_alterations if a.get("is_biomarker_match")),
        "categories": categories,
        "disease_categories": disease_categories,
        "specimen_types": specimens,
        "bodily_fluids": bodily_fluids,
        "primary_organs": primary_organs,
        "tissue_origins": tissue_origins
    }

    conn.close()
    return {
        "biomarkers": enriched_biomarkers,
        "scenarios": scenarios,
        "sources": sources,
        "diseases": enriched_diseases,
        "biomarker_diseases": biomarker_disease_alterations_map,
        "stats": stats,
        "lifeTables": serialize_life_tables(),
        "voiConfig": voi_config_dict(),
    }


def generate_standalone_html():
    payload = compile_database_payload()
    json_data_str = json.dumps(payload, separators=(',', ':'))

    css_content = ""
    if CSS_PATH.exists():
        with open(CSS_PATH, "r", encoding="utf-8") as f:
            css_content = f.read()

    html_template = f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Physiological Fitness Landscape & Optimization Engine</title>
    
    <!-- Tailwind CSS CDN -->
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {{
            darkMode: 'class',
            theme: {{
                extend: {{
                    colors: {{
                        slate: {{
                            750: '#293548',
                            850: '#172033',
                            950: '#0b0f19',
                        }},
                        indigo: {{
                            450: '#6366f1',
                            550: '#4f46e5'
                        }},
                        emerald: {{
                            450: '#10b981',
                            550: '#059669'
                        }}
                    }}
                }}
            }}
        }}
    </script>
    
    <!-- Plotly.js CDN -->
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    
    <!-- Font Awesome Icons with CDN Fallback -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css" integrity="sha512-DTOQO9RWCH3ppGqcWaEA1BIZOC6xxalwEsw9c2QQeAIftl+Vegovlnee1c9QX4TctnWMn13TZye+giMm8e2LwA==" crossorigin="anonymous" referrerpolicy="no-referrer" />
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.5.1/css/all.min.css">
    
    <style>
{css_content}
        /* Custom scrollbar and aesthetics */
        ::-webkit-scrollbar {{
            width: 6px;
            height: 6px;
        }}
        ::-webkit-scrollbar-track {{
            background: #0f172a;
        }}
        ::-webkit-scrollbar-thumb {{
            background: #334155;
            border-radius: 3px;
        }}
        ::-webkit-scrollbar-thumb:hover {{
            background: #475569;
        }}
        .metric-card-gradient {{
            background: linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.85) 100%);
        }}
        .plot-provenance {{
            margin-top: 8px;
            padding: 8px 10px;
            font-size: 10px;
            line-height: 1.5;
            color: #94a3b8;
            background: rgba(2, 6, 23, 0.65);
            border: 1px solid #1e293b;
            border-radius: 8px;
        }}
        .plot-provenance .prov-row + .prov-row {{
            margin-top: 4px;
        }}
        .plot-provenance .prov-label {{
            display: inline-block;
            min-width: 7.5rem;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            font-weight: 700;
            font-size: 9px;
        }}
        .plot-provenance a {{
            color: #67e8f9;
            text-decoration: none;
        }}
        .plot-provenance a:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen flex flex-col font-sans antialiased selection:bg-indigo-500 selection:text-white">

    <!-- Header Navigation -->
    <header class="sticky top-0 z-50 bg-slate-900/90 backdrop-blur-md border-b border-slate-800 shadow-md">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
            <div class="flex items-center gap-3 cursor-pointer" onclick="navigateTab('biomarkers')">
                <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-emerald-400 flex items-center justify-center shadow-lg shadow-indigo-500/20 text-white font-bold text-lg">
                    <i class="fa-solid fa-dna"></i>
                </div>
                <div>
                    <h1 class="text-base font-bold tracking-tight text-white flex items-center gap-2">
                        Physiological Fitness Landscape
                        <span class="text-[10px] uppercase font-mono px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">v2.0 Optimization</span>
                    </h1>
                    <p class="text-xs text-slate-400">Mortality Hazard Functions & Population Optimization Engine</p>
                </div>
            </div>

            <!-- Global Tabs Navigation -->
            <nav class="flex items-center gap-1 sm:gap-2 bg-slate-950/70 p-1 rounded-lg border border-slate-800 overflow-x-auto max-w-full">
                <button id="tab-biomarkers" class="tab-btn active px-3 py-1.5 text-xs font-semibold rounded-md transition-colors bg-indigo-600 text-white shadow">
                    <i class="fa-solid fa-flask-vial mr-1.5"></i>Biomarkers
                </button>
                <button id="tab-diseases" class="tab-btn px-3 py-1.5 text-xs font-semibold rounded-md transition-colors text-slate-400 hover:text-white hover:bg-slate-800">
                    <i class="fa-solid fa-disease mr-1.5 text-rose-400"></i>Disease Explorer
                </button>
                <button id="tab-leaderboard" class="tab-btn px-3 py-1.5 text-xs font-semibold rounded-md transition-colors text-slate-400 hover:text-white hover:bg-slate-800">
                    <i class="fa-solid fa-trophy mr-1.5 text-amber-400"></i>Optimization Leaderboard
                </button>
                <button id="tab-compare" class="tab-btn px-3 py-1.5 text-xs font-semibold rounded-md transition-colors text-slate-400 hover:text-white hover:bg-slate-800">
                    <i class="fa-solid fa-scale-balanced mr-1.5"></i>Compare
                </button>
                <button id="tab-sources" class="tab-btn px-3 py-1.5 text-xs font-semibold rounded-md transition-colors text-slate-400 hover:text-white hover:bg-slate-800">
                    <i class="fa-solid fa-book-bookmark mr-1.5"></i>Evidence Sources
                </button>
            </nav>
        </div>
    </header>

    <!-- Main Container -->
    <main class="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">

        <!-- Platform Metric Highlights Bar -->
        <div class="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
            <div class="metric-card-gradient border border-slate-800 rounded-xl p-3 flex flex-col justify-between">
                <span class="text-[11px] font-medium text-slate-400">Biomarkers</span>
                <div class="flex items-baseline justify-between mt-1">
                    <span id="stat-biomarkers" class="text-xl font-black text-indigo-400">--</span>
                    <i class="fa-solid fa-vial text-slate-600 text-sm"></i>
                </div>
            </div>
            <div class="metric-card-gradient border border-slate-800 rounded-xl p-3 flex flex-col justify-between">
                <span class="text-[11px] font-medium text-slate-400">Chronic Diseases</span>
                <div class="flex items-baseline justify-between mt-1">
                    <span id="stat-diseases" class="text-xl font-black text-rose-400">--</span>
                    <i class="fa-solid fa-disease text-slate-600 text-sm"></i>
                </div>
            </div>
            <div class="metric-card-gradient border border-slate-800 rounded-xl p-3 flex flex-col justify-between">
                <span class="text-[11px] font-medium text-slate-400">Multi-Scale Alts</span>
                <div class="flex items-baseline justify-between mt-1">
                    <span id="stat-alterations" class="text-xl font-black text-amber-400">--</span>
                    <i class="fa-solid fa-layer-group text-slate-600 text-sm"></i>
                </div>
            </div>
            <div class="metric-card-gradient border border-slate-800 rounded-xl p-3 flex flex-col justify-between">
                <span class="text-[11px] font-medium text-slate-400">Hazard Curves</span>
                <div class="flex items-baseline justify-between mt-1">
                    <span id="stat-associations" class="text-xl font-black text-pink-400">--</span>
                    <i class="fa-solid fa-chart-line text-slate-600 text-sm"></i>
                </div>
            </div>
            <div class="metric-card-gradient border border-slate-800 rounded-xl p-3 flex flex-col justify-between">
                <span class="text-[11px] font-medium text-slate-400">NHANES Cohorts</span>
                <div class="flex items-baseline justify-between mt-1">
                    <span id="stat-distributions" class="text-xl font-black text-emerald-400">--</span>
                    <i class="fa-solid fa-users text-slate-600 text-sm"></i>
                </div>
            </div>
            <div class="metric-card-gradient border border-slate-800 rounded-xl p-3 flex flex-col justify-between">
                <span class="text-[11px] font-medium text-slate-400">Interventions</span>
                <div class="flex items-baseline justify-between mt-1">
                    <span id="stat-interventions" class="text-xl font-black text-cyan-400">--</span>
                    <i class="fa-solid fa-dumbbell text-slate-600 text-sm"></i>
                </div>
            </div>
            <div class="metric-card-gradient border border-slate-800 rounded-xl p-3 flex flex-col justify-between">
                <span class="text-[11px] font-medium text-slate-400">Evidence Sources</span>
                <div class="flex items-baseline justify-between mt-1">
                    <span id="stat-sources" class="text-xl font-black text-purple-400">--</span>
                    <i class="fa-solid fa-book-medical text-slate-600 text-sm"></i>
                </div>
            </div>
        </div>

        <!-- VIEW 1: Biomarkers Explorer & Deep Dive -->
        <div id="view-biomarkers" class="space-y-6">
            <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">

                <!-- Left Sidebar: Filters & Biomarker List -->
                <div class="lg:col-span-4 xl:col-span-4 space-y-4">
                    <div class="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3 shadow-md">
                        <!-- Search Box -->
                        <div class="relative">
                            <i class="fa-solid fa-magnifying-glass absolute left-3.5 top-3.5 text-slate-500 text-xs"></i>
                            <input type="text" id="biomarker-search" placeholder="Search biomarkers, codes, organ systems..."
                                class="w-full pl-9 pr-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 transition">
                        </div>

                        <!-- Grouping Controls -->
                        <div>
                            <label class="block text-[10px] font-semibold text-slate-400 mb-1.5 uppercase tracking-wider">Group Biomarkers By</label>
                            <div class="grid grid-cols-4 gap-1 bg-slate-950/80 p-1 rounded-lg border border-slate-800" id="group-by-controls">
                                <button type="button" data-group="flat" class="group-by-btn active px-2 py-1 text-[11px] font-medium rounded text-center transition bg-indigo-600 text-white shadow-sm">None</button>
                                <button type="button" data-group="primary_organ" class="group-by-btn px-2 py-1 text-[11px] font-medium rounded text-center transition text-slate-400 hover:text-white hover:bg-slate-800">Organ</button>
                                <button type="button" data-group="bodily_fluid" class="group-by-btn px-2 py-1 text-[11px] font-medium rounded text-center transition text-slate-400 hover:text-white hover:bg-slate-800">Fluid</button>
                                <button type="button" data-group="tissue_origin" class="group-by-btn px-2 py-1 text-[11px] font-medium rounded text-center transition text-slate-400 hover:text-white hover:bg-slate-800">Tissue</button>
                            </div>
                        </div>

                        <!-- Filters Grid -->
                        <div class="grid grid-cols-2 gap-2 text-xs">
                            <div>
                                <label class="block text-[10px] font-medium text-slate-400 mb-1">Organ / System</label>
                                <select id="filter-organ" class="w-full bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5 text-xs text-slate-200 focus:outline-none focus:ring-1 focus:ring-indigo-500">
                                    <option value="">All Organs</option>
                                </select>
                            </div>
                            <div>
                                <label class="block text-[10px] font-medium text-slate-400 mb-1">Bodily Fluid</label>
                                <select id="filter-fluid" class="w-full bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5 text-xs text-slate-200 focus:outline-none focus:ring-1 focus:ring-indigo-500">
                                    <option value="">All Fluids</option>
                                </select>
                            </div>
                            <div>
                                <label class="block text-[10px] font-medium text-slate-400 mb-1">Tissue Origin</label>
                                <select id="filter-tissue" class="w-full bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5 text-xs text-slate-200 focus:outline-none focus:ring-1 focus:ring-indigo-500">
                                    <option value="">All Tissues</option>
                                </select>
                            </div>
                            <div>
                                <label class="block text-[10px] font-medium text-slate-400 mb-1">Category</label>
                                <select id="filter-category" class="w-full bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5 text-xs text-slate-200 focus:outline-none focus:ring-1 focus:ring-indigo-500">
                                    <option value="">All Categories</option>
                                </select>
                            </div>
                        </div>
                    </div>

                    <!-- Biomarkers Count & List Scroll Container -->
                    <div class="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-md">
                        <div class="px-4 py-2.5 bg-slate-850 border-b border-slate-800 flex items-center justify-between text-xs">
                            <span class="font-semibold text-slate-300">Biomarkers (<span id="biomarkers-count">0</span>)</span>
                            <span class="text-[10px] text-slate-500 font-mono" id="group-active-indicator">Grouped: None</span>
                        </div>
                        <div id="biomarkers-list" class="divide-y divide-slate-800/60 max-h-[620px] overflow-y-auto">
                            <!-- Populated dynamically via JS -->
                        </div>
                    </div>
                </div>

                <!-- Right Content Area: Detailed Landscape View -->
                <div class="lg:col-span-8 xl:col-span-8 space-y-4">
                    <div id="biomarker-detail-container" class="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-xl min-h-[600px] flex flex-col">
                        <!-- Header Banner -->
                        <div id="detail-header" class="p-5 bg-gradient-to-r from-slate-900 via-slate-850 to-slate-900 border-b border-slate-800">
                            <!-- Populated dynamically -->
                            <div class="animate-pulse space-y-2">
                                <div class="h-6 bg-slate-800 rounded w-1/3"></div>
                                <div class="h-4 bg-slate-800 rounded w-2/3"></div>
                            </div>
                        </div>

                        <!-- Sub-tab Navigation for Biomarker Detail -->
                        <div class="flex border-b border-slate-800 bg-slate-950/50 px-4 pt-2 gap-2 overflow-x-auto">
                            <button id="subtab-landscape" class="subtab-btn px-3 py-2 text-xs font-semibold rounded-t-lg bg-indigo-600 text-white transition flex items-center gap-1.5">
                                <i class="fa-solid fa-mountain-sun"></i> Fitness Landscape
                            </button>
                            <button id="subtab-diseases" class="subtab-btn px-3 py-2 text-xs font-semibold rounded-t-lg text-slate-400 hover:text-white hover:bg-slate-800/50 transition flex items-center gap-1.5">
                                <i class="fa-solid fa-disease text-rose-400"></i> Chronic Disease Alterations
                            </button>
                            <button id="subtab-optimization" class="subtab-btn px-3 py-2 text-xs font-semibold rounded-t-lg text-slate-400 hover:text-white hover:bg-slate-800/50 transition flex items-center gap-1.5">
                                <i class="fa-solid fa-sliders text-purple-400"></i> Optimization Simulator
                            </button>
                            <button id="subtab-forest" class="subtab-btn px-3 py-2 text-xs font-semibold rounded-t-lg text-slate-400 hover:text-white hover:bg-slate-800/50 transition flex items-center gap-1.5">
                                <i class="fa-solid fa-square-poll-horizontal"></i> Hazard Ratios
                            </button>
                            <button id="subtab-interventions" class="subtab-btn px-3 py-2 text-xs font-semibold rounded-t-lg text-slate-400 hover:text-white hover:bg-slate-800/50 transition flex items-center gap-1.5">
                                <i class="fa-solid fa-dumbbell"></i> Interventions
                            </button>
                            <button id="subtab-demographics" class="subtab-btn px-3 py-2 text-xs font-semibold rounded-t-lg text-slate-400 hover:text-white hover:bg-slate-800/50 transition flex items-center gap-1.5">
                                <i class="fa-solid fa-chart-column"></i> Demographics
                            </button>
                        </div>

                        <!-- Sub-tab Views Content -->
                        <div class="p-5 flex-1 bg-slate-900/60">

                            <!-- SUBVIEW 1: Interactive Fitness Landscape Plot -->
                            <div id="subview-landscape" class="space-y-4">
                                <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                                    <div>
                                        <h3 class="text-sm font-bold text-white flex items-center gap-2">
                                            <span>All-Cause Mortality Hazard Landscape</span>
                                            <span id="landscape-model-badge" class="text-[10px] px-2 py-0.5 rounded font-mono bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">Continuous Spline</span>
                                        </h3>
                                        <p class="text-xs text-slate-400">Non-linear mortality hazard ratio curve overlaying NHANES representative population distribution.</p>
                                    </div>
                                    <div class="flex items-center gap-2 text-xs">
                                        <span class="inline-flex items-center gap-1 text-indigo-400"><span class="w-2.5 h-2.5 rounded-full bg-indigo-500"></span> Hazard Ratio</span>
                                        <span class="inline-flex items-center gap-1 text-emerald-400"><span class="w-2.5 h-2.5 rounded-full bg-emerald-500/30 border border-emerald-500"></span> Density</span>
                                    </div>
                                </div>

                                <!-- Age / Sex selectors for age-conditional HR curves -->
                                <div class="flex flex-wrap items-center gap-3 text-xs">
                                    <label class="flex items-center gap-1.5 text-slate-400">
                                        <span>Age:</span>
                                        <select id="landscape-age-select" class="bg-slate-800 border border-slate-700 rounded px-2 py-1 text-xs text-white focus:outline-none focus:ring-1 focus:ring-indigo-500">
                                            <option value="30">30</option>
                                            <option value="40">40</option>
                                            <option value="50" selected>50</option>
                                            <option value="60">60</option>
                                            <option value="70">70</option>
                                            <option value="80">80</option>
                                        </select>
                                    </label>
                                    <label class="flex items-center gap-1.5 text-slate-400">
                                        <span>Sex:</span>
                                        <select id="landscape-sex-select" class="bg-slate-800 border border-slate-700 rounded px-2 py-1 text-xs text-white focus:outline-none focus:ring-1 focus:ring-indigo-500">
                                            <option value="all" selected>All</option>
                                            <option value="M">Male</option>
                                            <option value="F">Female</option>
                                        </select>
                                    </label>
                                    <span id="landscape-curve-specificity" class="text-[10px] px-2 py-0.5 rounded font-mono bg-slate-800 text-slate-400 border border-slate-700">pooled</span>
                                </div>

                                <div id="plot-landscape" class="w-full h-[380px] rounded-lg bg-slate-950/70 border border-slate-800"></div>
                                <div id="prov-landscape" class="plot-provenance"></div>

                                <!-- Landscape Metric Callouts -->
                                <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2">
                                    <div class="bg-slate-950/50 border border-slate-800 p-3 rounded-lg">
                                        <div class="text-[10px] text-slate-400">Optimal Physiological Point ($x^*$)</div>
                                        <div id="callout-optimal" class="text-sm font-bold text-emerald-400 mt-0.5">--</div>
                                    </div>
                                    <div class="bg-slate-950/50 border border-slate-800 p-3 rounded-lg">
                                        <div class="text-[10px] text-slate-400">Population Median ($P_{{50}}$)</div>
                                        <div id="callout-median" class="text-sm font-bold text-slate-200 mt-0.5">--</div>
                                    </div>
                                    <div class="bg-slate-950/50 border border-slate-800 p-3 rounded-lg">
                                        <div class="text-[10px] text-slate-400">Baseline Expected HR $E[HR_0]$</div>
                                        <div id="callout-baseline-hr" class="text-sm font-bold text-indigo-300 mt-0.5">--</div>
                                    </div>
                                    <div class="bg-slate-950/50 border border-slate-800 p-3 rounded-lg">
                                        <div class="text-[10px] text-slate-400">Valid Domain Boundary</div>
                                        <div id="callout-domain-range" class="text-sm font-bold text-amber-400 mt-0.5">--</div>
                                    </div>
                                </div>
                            </div>

                            <!-- SUBVIEW 2: Optimization Simulator & Benefit Distribution -->
                            <div id="subview-optimization" class="space-y-5 hidden">
                                <div>
                                    <h3 class="text-sm font-bold text-white flex items-center gap-2">
                                        <i class="fa-solid fa-calculator text-purple-400"></i>
                                        Derived Analytics Optimization Layer
                                    </h3>
                                    <p class="text-xs text-slate-400">
                                        Quantifying the expected mortality hazard reduction if the entire population distribution shifts toward optimal physiological targets.
                                    </p>
                                </div>

                                <!-- Interactive Simulator Control Panel -->
                                <div class="bg-slate-950/70 border border-slate-800 p-4 rounded-xl space-y-4">
                                    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                                        <div>
                                            <span class="text-xs font-semibold text-slate-200">Interactive Population Shift Scenario:</span>
                                            <div class="text-xs text-slate-400">Select preset or adjust continuous SD shift slider.</div>
                                        </div>
                                        <div class="flex flex-wrap gap-1.5" id="sim-preset-buttons">
                                            <button onclick="setSimPreset('sd_025')" class="px-2.5 py-1 text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 rounded border border-slate-700 font-medium transition">0.25 SD</button>
                                            <button onclick="setSimPreset('sd_050')" class="px-2.5 py-1 text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 rounded border border-slate-700 font-medium transition">0.50 SD</button>
                                            <button onclick="setSimPreset('sd_100')" class="px-2.5 py-1 text-xs bg-purple-600/40 hover:bg-purple-600 text-purple-200 rounded border border-purple-500/50 font-bold transition">1.00 SD (Standard)</button>
                                            <button onclick="setSimPreset('sd_150')" class="px-2.5 py-1 text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 rounded border border-slate-700 font-medium transition">1.50 SD</button>
                                            <button onclick="setSimPreset('sd_200')" class="px-2.5 py-1 text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 rounded border border-slate-700 font-medium transition">2.00 SD</button>
                                            <button onclick="setSimPreset('percentile_p25_to_p50')" class="px-2.5 py-1 text-xs bg-indigo-900/40 hover:bg-indigo-800 text-indigo-200 rounded border border-indigo-500/50 font-medium transition">P25 &rarr; P50</button>
                                        </div>
                                    </div>

                                    <!-- Slider Row -->
                                    <div class="space-y-2 pt-2 border-t border-slate-800/80">
                                        <div class="flex items-center justify-between text-xs">
                                            <span class="text-slate-300 font-medium">Standard Deviation Shift (\\(\\delta \\cdot \\sigma\\)):</span>
                                            <span id="sim-slider-val" class="font-mono text-purple-400 font-bold text-sm">1.00 SD</span>
                                        </div>
                                        <input type="range" id="sim-slider" min="0.0" max="3.0" step="0.05" value="1.0"
                                            class="w-full accent-purple-500 cursor-pointer" oninput="handleSimSliderInput(this.value)">
                                        <div class="flex justify-between text-[10px] text-slate-500 font-mono">
                                            <span>0.0 SD (No change)</span>
                                            <span>1.0 SD</span>
                                            <span>2.0 SD</span>
                                            <span>3.0 SD (Maximum)</span>
                                        </div>
                                    </div>
                                </div>

                                <!-- Dynamic Simulation Result Cards -->
                                <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
                                    <div class="bg-slate-950/60 border border-slate-800 p-3 rounded-lg">
                                        <div class="text-[10px] text-slate-400 font-medium">Relative Hazard Reduction ($RHR$)</div>
                                        <div id="sim-res-rhr" class="text-lg font-black text-purple-400 mt-1">--</div>
                                        <div class="text-[9px] text-slate-500">\\(1 - E[HR_\\delta]/E[HR_0]\\)</div>
                                    </div>
                                    <div class="bg-slate-950/60 border border-slate-800 p-3 rounded-lg">
                                        <div class="text-[10px] text-slate-400 font-medium">Expected Absolute HR Drop (&Delta;HR)</div>
                                        <div id="sim-res-delta" class="text-lg font-black text-indigo-400 mt-1">--</div>
                                        <div id="sim-res-fractions" class="text-sm font-bold text-emerald-400 mt-1">--</div>
                                    </div>
                                    <div class="p-3 bg-slate-900/60 rounded-xl border border-slate-700/50">
                                        <div class="text-[10px] text-slate-400 font-medium">Percent with Benefit</div>
                                        <div id="sim-res-benefited" class="text-lg font-black text-emerald-400 mt-1">--</div>
                                        <div class="text-[9px] text-slate-500">Based on individual &Delta;HR_i</div>
                                    </div>
                                    <div class="bg-slate-950/60 border border-slate-800 p-3 rounded-lg">
                                        <div class="text-[10px] text-slate-400 font-medium">Domain Guardrails Status</div>
                                        <div id="sim-res-domain" class="text-sm font-bold text-slate-300 mt-1">--</div>
                                        <div id="sim-res-domain-clamped" class="text-[9px] text-slate-500">0% Clamped</div>
                                    </div>
                                </div>

                                <!-- Value of Information / EHIV panel (shares the SD-shift slider above) -->
                                <div id="voi-panel" class="bg-slate-950/70 border border-cyan-800/40 p-4 rounded-xl space-y-4">
                                    <div class="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                                        <div>
                                            <h4 class="text-sm font-bold text-white flex items-center gap-2">
                                                <i class="fa-solid fa-scale-balanced text-cyan-400"></i>
                                                Value of Information
                                            </h4>
                                            <p class="text-xs text-slate-400 mt-1 max-w-2xl">
                                                Expected years of life lost and dollar-valued information from measuring this biomarker,
                                                using the same SD-shift as the simulator above. Life tables: CDC NVSS US 2022 (period).
                                                Uses age/sex from the Fitness Landscape filters.
                                            </p>
                                        </div>
                                        <div class="text-[10px] font-mono text-slate-500" id="voi-filter-caption">age 50 · sex all</div>
                                    </div>

                                    <div class="flex flex-wrap items-end gap-4">
                                        <label class="flex flex-col gap-1 text-xs text-slate-300">
                                            <span class="flex items-center gap-1.5">
                                                λ (willingness-to-pay, $/DALY)
                                                <span class="relative group cursor-help text-slate-500" title="λ is a normative policy choice, not an empirical estimate. Common ranges are 1–3× per-capita GDP or an ICER-style $/DALY threshold. Changing λ rescales EHIV; it does not change the underlying DALY VOI.">
                                                    <i class="fa-solid fa-circle-info text-cyan-500/80"></i>
                                                </span>
                                            </span>
                                            <input type="number" id="voi-lambda-input" min="0" step="10000" value="150000"
                                                class="bg-slate-900 border border-slate-700 rounded px-2 py-1 text-xs text-white w-36 focus:outline-none focus:ring-1 focus:ring-cyan-500"
                                                oninput="handleVoiLambdaInput(this.value)">
                                        </label>
                                        <div class="flex flex-wrap gap-1" id="voi-lambda-presets"></div>
                                        <label class="flex flex-col gap-1 text-xs text-slate-300">
                                            <span>c<sub>int</sub> (intervention cost, DALYs)</span>
                                            <input type="number" id="voi-cint-input" min="0" step="0.01" value="0"
                                                class="bg-slate-900 border border-slate-700 rounded px-2 py-1 text-xs text-white w-28 focus:outline-none focus:ring-1 focus:ring-cyan-500"
                                                oninput="handleVoiCIntInput(this.value)">
                                        </label>
                                    </div>

                                    <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
                                        <div class="bg-slate-900/80 border border-slate-800 p-3 rounded-lg">
                                            <div class="text-[10px] text-slate-400">EHIV (net $)</div>
                                            <div id="voi-ehiv" class="text-xl font-black text-cyan-300 mt-1">--</div>
                                            <div id="voi-ehiv-badge" class="mt-1"></div>
                                        </div>
                                        <div class="bg-slate-900/80 border border-slate-800 p-3 rounded-lg">
                                            <div class="text-[10px] text-slate-400">VOI (DALYs / person)</div>
                                            <div id="voi-dalys" class="text-lg font-bold text-slate-100 mt-1">--</div>
                                            <div class="text-[9px] text-slate-500">E[max(0, ΔDALY(x) − ΔDALY(x′)) − c<sub>int</sub>]</div>
                                        </div>
                                        <div class="bg-slate-900/80 border border-slate-800 p-3 rounded-lg">
                                            <div class="text-[10px] text-slate-400">λ · VOI</div>
                                            <div id="voi-lambda-voi" class="text-lg font-bold text-slate-100 mt-1">--</div>
                                            <div class="text-[9px] text-slate-500">Dollar-valued information before test cost</div>
                                        </div>
                                        <div class="bg-slate-900/80 border border-slate-800 p-3 rounded-lg">
                                            <div class="text-[10px] text-slate-400">c<sub>test</sub></div>
                                            <div id="voi-ctest" class="text-lg font-bold text-slate-100 mt-1">--</div>
                                            <div id="voi-ctest-cite" class="text-[9px] text-slate-500"></div>
                                        </div>
                                    </div>

                                    <div class="grid grid-cols-3 gap-3 text-xs">
                                        <div class="bg-slate-900/50 border border-slate-800 p-2.5 rounded-lg">
                                            <div class="text-[10px] text-slate-400">EYLL at mean x</div>
                                            <div id="voi-eyll" class="font-mono text-slate-200 mt-0.5">--</div>
                                        </div>
                                        <div class="bg-slate-900/50 border border-slate-800 p-2.5 rounded-lg">
                                            <div class="text-[10px] text-slate-400">ΔDALY(x) (mortality-only)</div>
                                            <div id="voi-ddaly" class="font-mono text-slate-200 mt-0.5">--</div>
                                        </div>
                                        <div class="bg-slate-900/50 border border-slate-800 p-2.5 rounded-lg">
                                            <div class="text-[10px] text-slate-400">VOI(x) at mean</div>
                                            <div id="voi-indiv" class="font-mono text-slate-200 mt-0.5">--</div>
                                        </div>
                                    </div>
                                    <p class="text-[10px] text-slate-500">
                                        EHIV = λ · E[VOI] − c<sub>test</sub>. λ is not a scientific estimate of “correct” value —
                                        it is the decision-maker’s willingness to pay per DALY. Population VOI on the leaderboard
                                        sums exclusive age × sex cells (overlapping NHANES aggregations are excluded).
                                    </p>
                                    <div id="prov-voi" class="plot-provenance"></div>
                                </div>

                                <!-- Shifted Distribution & Benefit Chart -->
                                <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
                                    <div class="bg-slate-950/70 border border-slate-800 p-3 rounded-lg">
                                        <div class="text-xs font-bold text-white mb-2 flex items-center justify-between">
                                            <span>Population Shift Simulation Plot</span>
                                            <span class="text-[10px] text-slate-400 font-normal">Baseline vs. Shifted Density</span>
                                        </div>
                                        <div id="plot-sim-shift" class="w-full h-[240px]"></div>
                                        <div id="prov-sim-shift" class="plot-provenance"></div>
                                    </div>
                                    <div class="bg-slate-950/70 border border-slate-800 p-3 rounded-lg">
                                        <div class="text-xs font-bold text-white mb-2 flex items-center justify-between">
                                            <span>Individual Benefit Distribution (&Delta;HR_i)</span>
                                            <span class="text-[10px] text-slate-400 font-normal">Quantiles & Heterogeneity</span>
                                        </div>
                                        <div id="plot-sim-benefit" class="w-full h-[240px]"></div>
                                        <div id="prov-sim-benefit" class="plot-provenance"></div>
                                    </div>
                                </div>

                                <!-- Precalculated Scenarios Table -->
                                <div class="bg-slate-950/70 border border-slate-800 rounded-lg overflow-hidden">
                                    <div class="p-3 bg-slate-900 border-b border-slate-800 flex items-center justify-between">
                                        <span class="text-xs font-bold text-white">Precomputed Standard Intervention Scenarios</span>
                                        <span class="text-[10px] text-slate-400 font-mono">Calibrated via Numerical Integration</span>
                                    </div>
                                    <div class="overflow-x-auto">
                                        <table class="w-full text-left text-xs">
                                            <thead class="bg-slate-950 text-slate-400 uppercase text-[10px] border-b border-slate-800">
                                                <tr>
                                                    <th class="p-2.5">Scenario</th>
                                                    <th class="p-2.5">Baseline $E[HR_0]$</th>
                                                    <th class="p-2.5">Optimized \\(E[HR_\\delta]\\)</th>
                                                    <th class="p-2.5">&Delta; HR</th>
                                                    <th class="p-2.5 text-purple-400 font-bold">Rel. Reduction ($RHR$)</th>
                                                    <th class="p-2.5">% Benefiting</th>
                                                    <th class="p-2.5">Domain Status</th>
                                                </tr>
                                            </thead>
                                            <tbody id="precalc-scenarios-table-body" class="divide-y divide-slate-850">
                                                <!-- Dynamic rows -->
                                            </tbody>
                                        </table>
                                    </div>
                                </div>
                            </div>

                            <!-- SUBVIEW 3: Forest Plot for Hazard Ratios -->
                            <div id="subview-forest" class="space-y-4 hidden">
                                <div>
                                    <h3 class="text-sm font-bold text-white">Hazard Ratios by Clinical Category & Strata</h3>
                                    <p class="text-xs text-slate-400">Point estimates and 95% confidence intervals from prospective cohort studies.</p>
                                </div>
                                <div id="plot-forest" class="w-full h-[380px] rounded-lg bg-slate-950/70 border border-slate-800"></div>
                                <div id="prov-forest" class="plot-provenance"></div>
                                <div id="forest-table-container" class="overflow-x-auto rounded-lg border border-slate-800 bg-slate-950/50"></div>
                            </div>

                            <!-- SUBVIEW 4: Interventions View -->
                            <div id="subview-interventions" class="space-y-4 hidden">
                                <div>
                                    <h3 class="text-sm font-bold text-white">Evidence-Based Clinical & Lifestyle Interventions</h3>
                                    <p class="text-xs text-slate-400">Dietary, pharmacological, physical activity, and supplemental modalities impacting this biomarker.</p>
                                </div>

                                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    <div class="space-y-3">
                                        <div class="flex items-center gap-2 pb-2 border-b border-emerald-500/30 text-emerald-400 text-xs font-bold uppercase tracking-wider">
                                            <i class="fa-solid fa-arrow-trend-up"></i> Favorable Modalities
                                        </div>
                                        <div id="favorable-interventions-list" class="space-y-2.5"></div>
                                    </div>
                                    <div class="space-y-3">
                                        <div class="flex items-center gap-2 pb-2 border-b border-rose-500/30 text-rose-400 text-xs font-bold uppercase tracking-wider">
                                            <i class="fa-solid fa-triangle-exclamation"></i> Aggravating / Adverse Factors
                                        </div>
                                        <div id="unfavorable-interventions-list" class="space-y-2.5"></div>
                                    </div>
                                </div>
                            </div>

                            <!-- SUBVIEW: Chronic Disease Alterations -->
                            <div id="subview-diseases" class="space-y-4 hidden">
                                <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                                    <div>
                                        <h3 class="text-sm font-bold text-white flex items-center gap-2">
                                            <i class="fa-solid fa-disease text-rose-400"></i>
                                            Chronic Diseases Altering this Biomarker
                                        </h3>
                                        <p class="text-xs text-slate-400">Multi-scale catalog of disease states that significantly shift or dysregulate this biomarker.</p>
                                    </div>
                                    <div id="biomarker-disease-count-badge" class="text-xs font-mono px-2.5 py-1 rounded bg-rose-500/20 text-rose-300 border border-rose-500/30 shrink-0">
                                        0 Associated Diseases
                                    </div>
                                </div>

                                <div id="biomarker-diseases-container" class="grid grid-cols-1 md:grid-cols-2 gap-3.5">
                                    <!-- Dynamic biomarker disease cards -->
                                </div>
                            </div>

                            <!-- SUBVIEW 5: Demographics & NHANES Stratification -->
                            <div id="subview-demographics" class="space-y-4 hidden">
                                <div>
                                    <h3 class="text-sm font-bold text-white">NHANES Population Benchmarks by Age Band & Sex</h3>
                                    <p class="text-xs text-slate-400">Stratified median and 75th percentile values across representative adult cohorts.</p>
                                </div>
                                <div id="plot-demographics" class="w-full h-[350px] rounded-lg bg-slate-950/70 border border-slate-800"></div>
                                <div id="prov-demographics" class="plot-provenance"></div>
                                <div id="demographics-table-container" class="overflow-x-auto rounded-lg border border-slate-800 bg-slate-950/50"></div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- VIEW: Chronic Disease Explorer -->
        <div id="view-diseases" class="space-y-6 hidden">
            <!-- Disease Filters & Search Header -->
            <div class="bg-slate-900 p-5 rounded-xl border border-slate-800 shadow-sm space-y-4">
                <div class="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                    <div>
                        <h2 class="text-lg font-bold text-white flex items-center gap-2">
                            <i class="fa-solid fa-disease text-rose-400"></i>
                            Chronic Disease Intelligence & Multi-Scale Alterations Explorer
                        </h2>
                        <p class="text-xs text-slate-400">
                            113+ chronic diseases across cardiovascular, metabolic, neurodegenerative, respiratory, oncology, musculoskeletal, and immune categories with multi-scale alteration profiles (Type A-E).
                        </p>
                    </div>
                    <div class="flex flex-wrap items-center gap-2.5">
                        <div class="relative w-full sm:w-64">
                            <i class="fa-solid fa-magnifying-glass absolute left-3.5 top-3 text-slate-500 text-xs"></i>
                            <input type="text" id="disease-search" placeholder="Search diseases, ICD-10, organ systems..."
                                class="w-full pl-9 pr-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-rose-500 transition">
                        </div>
                        <select id="filter-disease-category" class="bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:ring-1 focus:ring-rose-500">
                            <option value="">All Disease Categories</option>
                        </select>
                        <select id="filter-disease-sort" class="bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:ring-1 focus:ring-rose-500">
                            <option value="name">Sort: Name (A-Z)</option>
                            <option value="dalys">Sort: US DALYs Impact</option>
                            <option value="alterations">Sort: Alterations Count</option>
                        </select>
                    </div>
                </div>

                <!-- Multi-Scale Category Legend -->
                <div class="flex flex-wrap items-center gap-2 pt-2 border-t border-slate-800 text-[11px] text-slate-400">
                    <span class="font-semibold text-slate-300">Alteration Types:</span>
                    <span class="badge-type-b px-2 py-0.5 rounded font-mono text-[10px]">Type B: Lab / Clinical</span>
                    <span class="badge-type-c px-2 py-0.5 rounded font-mono text-[10px]">Type C: Scales & PROs</span>
                    <span class="badge-type-d px-2 py-0.5 rounded font-mono text-[10px]">Type D: Pathology / Imaging</span>
                    <span class="badge-type-e px-2 py-0.5 rounded font-mono text-[10px]">Type E: Functional Tests</span>
                    <span class="badge-type-a px-2 py-0.5 rounded font-mono text-[10px]">Type A: Molecular / Genomic</span>
                </div>
            </div>

            <!-- Disease Cards Grid -->
            <div id="disease-cards-container" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                <!-- Populated via JavaScript -->
            </div>
        </div>

        <!-- VIEW 2: Optimization Leaderboard -->
        <div id="view-leaderboard" class="space-y-6 hidden">
            <div class="bg-slate-900 p-5 rounded-xl border border-slate-800 shadow-sm space-y-4">
                <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div>
                        <h2 class="text-lg font-bold text-white flex items-center gap-2">
                            <i class="fa-solid fa-trophy text-amber-400"></i>
                            Optimization & Population Impact Leaderboard
                        </h2>
                        <p class="text-xs text-slate-400">
                            Comparative ranking of all biomarkers by standardized expected mortality hazard reduction ($RHR = 1 - E[HR_\\delta]/E[HR_0]$).
                        </p>
                    </div>
                    <div class="flex items-center gap-3">
                        <label class="text-xs text-slate-300 font-medium">Scenario:</label>
                        <select id="leaderboard-scenario-select" class="bg-slate-950 border border-slate-750 text-xs text-slate-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-purple-500" onchange="renderOptimizationLeaderboard()">
                            <!-- Scenario options -->
                        </select>
                        <label class="text-xs text-slate-300 font-medium">Sort:</label>
                        <select id="leaderboard-sort-select" class="bg-slate-950 border border-slate-750 text-xs text-slate-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-cyan-500" onchange="handleLeaderboardSort(this.value)">
                            <option value="rhr" selected>RHR (default)</option>
                            <option value="ehiv">EHIV ($)</option>
                            <option value="pop_voi">Population VOI (DALYs)</option>
                        </select>
                    </div>
                </div>

                <!-- Leaderboard Chart -->
                <div class="bg-slate-950/70 p-3 rounded-lg border border-slate-800">
                    <div id="plot-leaderboard" class="w-full h-[400px]"></div>
                    <div id="prov-leaderboard" class="plot-provenance"></div>
                </div>
            </div>

            <!-- Leaderboard Table -->
            <div class="bg-slate-900 rounded-xl border border-slate-800 shadow-sm overflow-hidden">
                <div class="p-4 bg-slate-850 border-b border-slate-800 flex items-center justify-between">
                    <h3 class="text-sm font-bold text-white">Full Physiological Optimization Ranking</h3>
                    <span class="text-xs text-slate-400">Click any row to inspect biomarker curve & individual benefit breakdown</span>
                </div>
                <div id="leaderboard-table-container" class="overflow-x-auto">
                    <!-- Dynamic Table -->
                </div>
            </div>
        </div>

        <!-- VIEW 3: Comparative Multi-Biomarker Landscape -->
        <div id="view-compare" class="space-y-6 hidden">
            <div class="bg-slate-900 p-5 rounded-xl border border-slate-800 shadow-sm space-y-4">
                <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div>
                        <h2 class="text-lg font-bold text-white">Multi-Biomarker Comparative Landscape</h2>
                        <p class="text-xs text-slate-400">Compare mortality hazard ratios, population distributions, and risk curves across up to 8 physiological markers simultaneously.</p>
                    </div>
                    <div class="flex items-center gap-2">
                        <button id="btn-compare-preset-all" class="px-3 py-1.5 bg-indigo-600/30 hover:bg-indigo-600/50 border border-indigo-500/40 text-indigo-200 text-xs rounded-lg font-semibold transition">
                            <i class="fa-solid fa-wand-magic-sparkles mr-1"></i> Core Panel
                        </button>
                        <button id="btn-compare-clear" class="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs rounded-lg font-semibold transition">
                            <i class="fa-solid fa-trash-can mr-1"></i> Clear
                        </button>
                    </div>
                </div>

                <div id="compare-selection-chips" class="flex flex-wrap gap-2 pt-2 border-t border-slate-800">
                    <!-- Dynamic comparison chips -->
                </div>
            </div>

            <div class="bg-slate-900 p-5 rounded-xl border border-slate-800 shadow-sm space-y-3">
                <h3 class="text-sm font-bold text-white">Comparative All-Cause Mortality Hazard Ratios</h3>
                <div id="plot-compare-forest" class="w-full h-[380px] rounded-lg bg-slate-950/70 border border-slate-800"></div>
                <div id="prov-compare" class="plot-provenance"></div>
            </div>

            <div class="bg-slate-900 rounded-xl border border-slate-800 shadow-sm overflow-hidden">
                <div class="p-4 bg-slate-850 border-b border-slate-800">
                    <h3 class="text-sm font-bold text-white">Comparative Benchmark Metrics</h3>
                </div>
                <div id="compare-table-container" class="overflow-x-auto"></div>
            </div>
        </div>

        <!-- VIEW 4: Primary Literature & Evidence Citations -->
        <div id="view-sources" class="space-y-6 hidden">
            <div class="bg-slate-900 p-5 rounded-xl border border-slate-800 shadow-sm flex flex-col md:flex-row items-center justify-between gap-4">
                <div>
                    <h2 class="text-lg font-bold text-white">Primary Literature & Cohort Citations</h2>
                    <p class="text-xs text-slate-400">Comprehensive registry of prospective cohort studies, NHANES epidemiological reports, and clinical trials.</p>
                </div>
                <div class="relative w-full md:w-80">
                    <i class="fa-solid fa-magnifying-glass absolute left-3.5 top-3.5 text-slate-500 text-xs"></i>
                    <input type="text" id="source-search" placeholder="Filter citations by author, journal, PMID..."
                        class="w-full pl-9 pr-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 transition">
                </div>
            </div>

            <div id="sources-list-container" class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <!-- Populated via JavaScript -->
            </div>
        </div>

    </main>

    <!-- Disease Detail Modal -->
    <div id="disease-modal" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm hidden">
        <div class="bg-slate-900 border border-slate-800 rounded-2xl max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col shadow-2xl animate-in fade-in zoom-in duration-150">
            <!-- Modal Header -->
            <div id="disease-modal-header" class="p-6 bg-gradient-to-r from-slate-900 via-slate-850 to-slate-900 border-b border-slate-800 flex items-start justify-between gap-4">
                <div>
                    <div class="flex items-center gap-2.5 flex-wrap">
                        <h2 id="modal-disease-name" class="text-xl font-black text-white tracking-tight">Disease Name</h2>
                        <span id="modal-disease-category" class="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-500/20 text-rose-300 border border-rose-500/30">Category</span>
                        <span id="modal-disease-icd10" class="px-2 py-0.5 rounded text-[10px] font-mono bg-slate-800 text-slate-300 border border-slate-700">ICD-10</span>
                    </div>
                    <p id="modal-disease-desc" class="text-xs text-slate-300 mt-2 leading-relaxed">Disease detailed description and physiological background.</p>
                    <div class="flex items-center gap-4 mt-3 text-xs text-slate-400">
                        <span>Organ: <strong id="modal-disease-organ" class="text-slate-200">System</strong></span>
                        <span>US DALYs: <strong id="modal-disease-dalys" class="text-rose-400 font-mono">--</strong></span>
                        <a id="modal-disease-repurpos-link" href="#" target="_blank" rel="noopener noreferrer" class="inline-flex items-center gap-1 text-indigo-400 hover:text-indigo-300 font-semibold underline underline-offset-2 transition"><i class="fa-solid fa-arrow-up-right-from-square"></i> View on RepurpOS Disease Intelligence</a>
                        <span>Multi-Scale Alterations: <strong id="modal-disease-alt-count" class="text-indigo-400 font-mono">0</strong></span>
                    </div>
                </div>
                <button id="btn-close-disease-modal" class="text-slate-400 hover:text-white p-2 rounded-lg hover:bg-slate-800 transition shrink-0">
                    <i class="fa-solid fa-xmark text-lg"></i>
                </button>
            </div>

            <!-- Modal Alteration Category Filter Tabs -->
            <div class="flex border-b border-slate-800 bg-slate-950/60 px-6 pt-2 gap-2 overflow-x-auto">
                <button class="modal-tab-btn active px-3 py-2 text-xs font-semibold rounded-t-lg bg-indigo-600 text-white transition flex items-center gap-1.5" data-modal-tab="all">
                    <i class="fa-solid fa-layer-group"></i> All Alterations (<span id="modal-count-all">0</span>)
                </button>
                <button class="modal-tab-btn px-3 py-2 text-xs font-semibold rounded-t-lg text-slate-400 hover:text-white hover:bg-slate-800/50 transition flex items-center gap-1.5" data-modal-tab="B">
                    <span class="w-2 h-2 rounded-full bg-cyan-500"></span> Type B: Lab/Clinical (<span id="modal-count-b">0</span>)
                </button>
                <button class="modal-tab-btn px-3 py-2 text-xs font-semibold rounded-t-lg text-slate-400 hover:text-white hover:bg-slate-800/50 transition flex items-center gap-1.5" data-modal-tab="C">
                    <span class="w-2 h-2 rounded-full bg-amber-500"></span> Type C: Scales (<span id="modal-count-c">0</span>)
                </button>
                <button class="modal-tab-btn px-3 py-2 text-xs font-semibold rounded-t-lg text-slate-400 hover:text-white hover:bg-slate-800/50 transition flex items-center gap-1.5" data-modal-tab="D">
                    <span class="w-2 h-2 rounded-full bg-purple-500"></span> Type D: Pathology (<span id="modal-count-d">0</span>)
                </button>
                <button class="modal-tab-btn px-3 py-2 text-xs font-semibold rounded-t-lg text-slate-400 hover:text-white hover:bg-slate-800/50 transition flex items-center gap-1.5" data-modal-tab="E">
                    <span class="w-2 h-2 rounded-full bg-emerald-500"></span> Type E: Functional (<span id="modal-count-e">0</span>)
                </button>
                <button class="modal-tab-btn px-3 py-2 text-xs font-semibold rounded-t-lg text-slate-400 hover:text-white hover:bg-slate-800/50 transition flex items-center gap-1.5" data-modal-tab="A">
                    <span class="w-2 h-2 rounded-full bg-rose-500"></span> Type A: Molecular (<span id="modal-count-a">0</span>)
                </button>
            </div>

            <!-- Modal Body: Scrollable Alterations List -->
            <div id="disease-modal-alterations-list" class="p-6 overflow-y-auto space-y-3 flex-1 bg-slate-900/70 divide-y divide-slate-800/60">
                <!-- Populated via JavaScript -->
            </div>
        </div>
    </div>

    <!-- Footer -->
    <footer class="bg-slate-900/60 border-t border-slate-800 py-4 text-center text-xs text-slate-500">
        <div class="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2">
            <span>Physiological Fitness Landscape</span>
            <span>Calibrated with NHANES Empirical Distributions & Non-Linear Spline Hazard Functions</span>
        </div>
    </footer>

    <!-- EMBEDDED DATA PAYLOAD -->
    <script id="embedded-biomarker-data" type="application/json">
{json_data_str}
    </script>

    <!-- STANDALONE APPLICATION CLIENT LOGIC & SIMULATION ENGINE -->
    <script>
    /**
     * Physiological Fitness Landscape — Standalone Client & Numerical Simulation Engine
     */
    const EMBEDDED_DATA = JSON.parse(document.getElementById('embedded-biomarker-data').textContent);

    const AppState = {{
        biomarkers: EMBEDDED_DATA.biomarkers || [],
        scenarios: EMBEDDED_DATA.scenarios || [],
        selectedBiomarker: null,
        selectedBiomarkerDetail: null,
        selectedBiomarkerDiseases: [],
        diseases: EMBEDDED_DATA.diseases || [],
        biomarkerDiseasesMap: EMBEDDED_DATA.biomarker_diseases || {{}},
        selectedDisease: null,
        sources: EMBEDDED_DATA.sources || [],
        stats: EMBEDDED_DATA.stats || {{}},
        activeTab: 'biomarkers',
        activeSubTab: 'landscape',
        activeDiseaseModalTab: 'all',
        compareSlugs: new Set(['high_sensitivity_crp', 'hba1c', 'estimated_gfr_ckd_epi', 'serum_albumin', 'rdw', 'resting_heart_rate']),
        groupBy: 'flat', // 'flat' | 'primary_organ' | 'bodily_fluid' | 'tissue_origin'
        filters: {{
            search: '',
            category: '',
            specimen: '',
            organ: '',
            fluid: '',
            tissue: ''
        }},
        diseaseFilters: {{
            search: '',
            category: '',
            sortBy: 'name'
        }},
        sourceSearch: '',
        currentSimShiftSD: 1.0,
        currentSimScenarioSlug: 'sd_100',
        landscapeAge: 50,
        landscapeSex: 'all',
        voiLambda: (EMBEDDED_DATA.voiConfig && EMBEDDED_DATA.voiConfig.lambdaDefault) || 150000,
        voiCIntDaly: (EMBEDDED_DATA.voiConfig && EMBEDDED_DATA.voiConfig.cIntDalyDefault) || 0,
        leaderboardSort: 'rhr',
        lifeTables: EMBEDDED_DATA.lifeTables || {{}},
        voiConfig: EMBEDDED_DATA.voiConfig || {{}}
    }};

    const plotlyDarkTheme = {{
        paper_bgcolor: '#090d16',
        plot_bgcolor: '#090d16',
        font: {{
            family: 'ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
            color: '#94a3b8',
            size: 11
        }},
        margin: {{ l: 50, r: 40, t: 30, b: 40 }},
        xaxis: {{
            gridcolor: '#1e293b',
            zerolinecolor: '#334155',
            tickfont: {{ color: '#94a3b8' }}
        }},
        yaxis: {{
            gridcolor: '#1e293b',
            zerolinecolor: '#334155',
            tickfont: {{ color: '#94a3b8' }}
        }}
    }};

    const plotlyConfig = {{
        responsive: true,
        displayModeBar: false
    }};

    function escapeHtml(s) {{
        if (s == null) return '';
        return String(s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }}

    function sourceHref(src) {{
        if (!src) return null;
        if (src.pmid && /^\\d+$/.test(String(src.pmid))) {{
            return 'https://pubmed.ncbi.nlm.nih.gov/' + src.pmid;
        }}
        if (src.doi) return 'https://doi.org/' + src.doi;
        if (src.url) return src.url;
        return null;
    }}

    function sourceShortHtml(src, fallback) {{
        if (!src) return escapeHtml(fallback || 'Source not recorded');
        let text = src.citation || fallback || 'Untitled source';
        if (text.length > 180) text = text.slice(0, 177) + '…';
        const href = sourceHref(src);
        const bits = [];
        if (href) bits.push(`<a href="${{href}}" target="_blank" rel="noopener">${{escapeHtml(text)}}</a>`);
        else bits.push(escapeHtml(text));
        if (src.year) bits.push(`<span class="font-mono text-slate-500">${{src.year}}</span>`);
        if (src.pmid && /^\\d+$/.test(String(src.pmid))) {{
            bits.push(`<a class="font-mono" href="https://pubmed.ncbi.nlm.nih.gov/${{src.pmid}}" target="_blank" rel="noopener">PMID ${{src.pmid}}</a>`);
        }} else if (src.doi) {{
            bits.push(`<span class="font-mono text-slate-500">${{escapeHtml(src.doi)}}</span>`);
        }}
        return bits.join(' · ');
    }}

    function setProvenance(elId, rows) {{
        const el = document.getElementById(elId);
        if (!el) return;
        const html = (rows || []).filter(r => r && r.html).map(r =>
            `<div class="prov-row"><span class="prov-label">${{escapeHtml(r.label)}}</span> ${{r.html}}</div>`
        ).join('');
        el.innerHTML = html || '<div class="prov-row text-slate-600">No provenance recorded for this plot.</div>';
    }}

    function overallDist(detail) {{
        const dists = (detail && detail.population_distributions) || [];
        return dists.find(d => d.sex === 'all' && d.age_band === 'all') || dists[0] || null;
    }}

    function nhanesProvenanceRow(detail) {{
        const d = overallDist(detail);
        if (!d) return {{ label: 'Population', html: 'No NHANES distribution on file for this marker.' }};
        const cycle = d.survey_cycle ? `NHANES ${{d.survey_cycle}}` : 'NHANES';
        const n = d.sample_n ? ` (n=${{d.sample_n}})` : '';
        const src = d.source ? sourceShortHtml(d.source, 'NCHS / CDC NHANES') : 'NCHS / CDC National Health and Nutrition Examination Survey';
        return {{ label: 'Population', html: `${{escapeHtml(cycle)}}${{n}}. ${{src}}` }};
    }}

    function hrProvenanceRow(detail, curve) {{
        const assocs = (detail && detail.associations) || [];
        const primary = assocs.find(a => a.source) || assocs[0];
        const parts = [];
        if (primary && primary.source) {{
            parts.push(sourceShortHtml(primary.source));
            if (primary.cohort_description) {{
                parts.push(escapeHtml(primary.cohort_description));
            }}
            if (primary.hr_type) {{
                parts.push(escapeHtml(`reported as ${{primary.hr_type}} HR=${{primary.hazard_ratio}}`));
            }}
        }} else if (curve && curve.citation_summary) {{
            parts.push(escapeHtml(curve.citation_summary));
        }} else {{
            parts.push('Synthesized continuous HR function from published mortality associations.');
        }}
        if (curve && curve.citation_summary && primary && primary.source) {{
            parts.push('Model: ' + escapeHtml(curve.citation_summary));
        }}
        if (curve && ((curve.sex && curve.sex !== 'all') || (curve.age_band && curve.age_band !== 'all'))) {{
            parts.push(`Stratum ${{escapeHtml(curve.sex || 'all')}}/${{escapeHtml(curve.age_band || 'all')}} derived from the pooled HR using NHANES moments.`);
        }}
        return {{ label: 'Hazard function', html: parts.join(' · ') }};
    }}

    function methodProvenanceRow(text) {{
        return {{ label: 'Method', html: escapeHtml(text) }};
    }}

    // --- CLIENT-SIDE NUMERICAL INTEGRATION & SIMULATION ENGINE ---

    function evaluateHR(x, curve, age, sex) {{
        if (!curve) return 1.0;
        if (x === null || x === undefined || isNaN(x) || !isFinite(x)) return 1.0;

        const curveType = curve.curve_type || 'linear_log';
        const ref = (curve.reference_value != null) ? curve.reference_value : 0.0;
        const optimal = (curve.optimal_value != null) ? curve.optimal_value : null;

        // Parse the parameters JSON blob (e.g. a string like a beta or a/x_opt object)
        let params = curve.parameters;
        if (typeof params === 'string') {{
            try {{ params = JSON.parse(params); }} catch (e) {{ params = {{}}; }}
        }}
        if (!params || typeof params !== 'object') params = {{}};

        const clip = (v) => Math.max(-5.0, Math.min(5.0, v));
        let logHR = 0.0;

        if (curveType === 'linear_log' || curveType === 'log_linear_per_sd' || curveType === 'log_linear_per_unit' || curveType === 'linear') {{
            // ln(HR(x)) = beta * (x - reference_value)
            const beta = params.beta != null ? params.beta : 0.0;
            logHR = beta * (x - ref);
        }} else if (curveType === 'quadratic') {{
            // ln(HR(x)) = a * (x - x_opt)^2 - a * (ref - x_opt)^2  (HR(ref) == 1.0)
            const a = params.a != null ? params.a : 0.001;
            const xOpt = (optimal != null) ? optimal : (params.x_opt != null ? params.x_opt : ref);
            logHR = a * Math.pow(x - xOpt, 2) - a * Math.pow(ref - xOpt, 2);
        }} else if (curveType === 'log_log') {{
            // ln(HR(x)) = beta * (ln(x) - ln(reference_value))
            const beta = params.beta != null ? params.beta : 0.0;
            const xSafe = Math.max(x, 1e-4);
            const refSafe = Math.max(ref, 1e-4);
            logHR = beta * (Math.log(xSafe) - Math.log(refSafe));
        }} else if (curveType === 'piecewise') {{
            // f(v) = slope_low*(x_opt - v) if v < x_opt else slope_high*(v - x_opt)
            // ln(HR(x)) = f(x) - f(ref)  (HR(ref) == 1.0)
            const xOpt = (optimal != null) ? optimal : (params.x_opt != null ? params.x_opt : ref);
            const slopeLow = params.slope_low != null ? params.slope_low : 0.0;
            const slopeHigh = params.slope_high != null ? params.slope_high : 0.0;
            const f = (v) => (v < xOpt) ? slopeLow * (xOpt - v) : slopeHigh * (v - xOpt);
            logHR = f(x) - f(ref);
        }} else if (curveType === 'age_interaction') {{
            // ln(HR(x, age)) = beta_x * (x - ref) + beta_age * (age - ref_age) + beta_x_age * (x - ref) * (age - ref_age)
            const betaX = params.beta_x != null ? params.beta_x : 0.0;
            const betaAge = params.beta_age != null ? params.beta_age : 0.0;
            const betaXAge = params.beta_x_age != null ? params.beta_x_age : 0.0;
            const refAge = params.reference_age != null ? params.reference_age : 50.0;
            const a = (age != null) ? age : refAge;
            logHR = betaX * (x - ref) + betaAge * (a - refAge) + betaXAge * (x - ref) * (a - refAge);
        }} else {{
            // Fallback linear log
            const beta = params.beta != null ? params.beta : 0.0;
            logHR = beta * (x - ref);
        }}

        // Clamp to physiologically plausible range [0.10, 20.0]
        const hr = Math.exp(clip(logHR));
        return Math.max(0.10, Math.min(20.0, hr));
    }}

    function generatePopulationBins(dist, numBins = 300) {{
        let mean = dist.mean;
        let sd = dist.sd;
        let p50 = dist.p50;
        let p10 = dist.p10;
        let p90 = dist.p90;

        if (sd == null || sd <= 0) {{
            if (p90 != null && p10 != null && p90 > p10) {{
                sd = (p90 - p10) / 2.56;
            }} else if (p50 != null && p50 > 0) {{
                sd = p50 * 0.25;
            }} else {{
                sd = 1.0;
            }}
        }}

        if (mean == null) {{
            mean = p50 != null ? p50 : 0.0;
        }}

        const minVal = mean - 3.8 * sd;
        const maxVal = mean + 3.8 * sd;
        const step = (maxVal - minVal) / (numBins - 1);

        const xVals = [];
        const pVals = [];
        let totalP = 0.0;

        for (let i = 0; i < numBins; i++) {{
            const x = minVal + i * step;
            const z = (x - mean) / sd;
            const pdf = Math.exp(-0.5 * z * z) / (sd * Math.sqrt(2 * Math.PI));
            xVals.push(x);
            pVals.push(pdf);
            totalP += pdf;
        }}

        const normP = pVals.map(p => p / totalP);
        return {{ x: xVals, p: normP, mean, sd, p10, p90, p50, p5: dist.p5, p95: dist.p95 }};
    }}

    // X-axis range that just covers the observed biomarker distribution.
    // Prefer empirical p5–p95 with a small pad; do not expand out to the
    // physiological / HR-curve domain (those are often many times wider).
    function distributionDisplayRange(dist, bins, validMin, validMax) {{
        const mean = (dist && dist.mean != null) ? dist.mean
            : (bins && bins.mean != null ? bins.mean : 0);
        let sd = (dist && dist.sd != null && dist.sd > 0) ? dist.sd
            : (bins && bins.sd != null && bins.sd > 0 ? bins.sd : 0);
        const p5 = (dist && dist.p5 != null) ? dist.p5 : (bins && bins.p5 != null ? bins.p5 : null);
        const p95 = (dist && dist.p95 != null) ? dist.p95 : (bins && bins.p95 != null ? bins.p95 : null);
        const p10 = (dist && dist.p10 != null) ? dist.p10 : (bins && bins.p10 != null ? bins.p10 : null);
        const p90 = (dist && dist.p90 != null) ? dist.p90 : (bins && bins.p90 != null ? bins.p90 : null);
        if (sd <= 0) {{
            if (p95 != null && p5 != null && p95 > p5) sd = (p95 - p5) / 3.29;
            else if (p90 != null && p10 != null && p90 > p10) sd = (p90 - p10) / 2.56;
            else sd = Math.max(Math.abs(mean) * 0.15, 1e-6);
        }}
        let lo, hi;
        if (p5 != null && p95 != null && p95 > p5) {{
            const pad = Math.max((p95 - p5) * 0.08, sd * 0.2);
            lo = p5 - pad;
            hi = p95 + pad;
        }} else if (p10 != null && p90 != null && p90 > p10) {{
            const pad = Math.max((p90 - p10) * 0.12, sd * 0.25);
            lo = p10 - pad;
            hi = p90 + pad;
        }} else {{
            lo = mean - 2.8 * sd;
            hi = mean + 2.8 * sd;
        }}
        // Clip to physiological bounds if the distribution tails exceed them;
        // never expand the axis out to the full valid domain.
        if (validMin != null && isFinite(validMin)) lo = Math.max(lo, validMin);
        if (validMax != null && isFinite(validMax)) hi = Math.min(hi, validMax);
        // Non-negative lab values should not show a large empty negative region.
        if (mean >= 0 && (p5 == null || p5 >= 0) && lo < 0) lo = Math.max(0, lo);
        if (!(hi > lo)) {{
            lo = mean - Math.abs(sd);
            hi = mean + Math.abs(sd);
            if (!(hi > lo)) {{ hi = lo + 1; }}
        }}
        return [lo, hi];
    }}

    // Re-normalize bins.p to a proper TRUNCATED density over the visible
    // [dataMin, dataMax] domain. Points that fall outside the domain are
    // excluded, and the remaining bins are scaled so the visible mass sums
    // to 1.0 (probability-consistent integration for HR expectations).
    function truncateBinsToDomain(bins, domainMin, domainMax) {{
        if (domainMin == null && domainMax == null) return bins;
        const mask = bins.x.map(x =>
            (domainMin == null || x >= domainMin) &&
            (domainMax == null || x <= domainMax));
        const totalP = mask.reduce((s, m, i) => s + (m ? bins.p[i] : 0), 0);
        if (totalP <= 0) return bins; // No mass in domain: fall back to original
        const truncatedP = bins.p.map((p, i) => (mask[i] ? p / totalP : 0));
        return {{ ...bins, p: truncatedP }};
    }}

    // --- VOI / EHIV (DALY-dollar) engine: eq. (5)–(13) ---

    function lookupS0FromBirth(age, sex) {{
        const tables = AppState.lifeTables || {{}};
        const clampAge = Math.max(0, Math.min(age, tables.max_age || 110));
        const lerp = (arr) => {{
            if (!arr || !arr.length) return 0;
            if (clampAge <= 0) return arr[0];
            const lo = Math.floor(clampAge);
            const hi = Math.min(lo + 1, arr.length - 1);
            const t = clampAge - lo;
            return arr[lo] * (1 - t) + arr[hi] * t;
        }};
        if (sex === 'F') return lerp((tables.F || {{}}).S0);
        if (sex === 'M') return lerp((tables.M || {{}}).S0);
        return 0.5 * (lerp((tables.M || {{}}).S0) + lerp((tables.F || {{}}).S0));
    }}

    function conditionalSurvivalFromAge(age, sex) {{
        const maxAge = (AppState.lifeTables && AppState.lifeTables.max_age) || 110;
        const sStart = lookupS0FromBirth(age, sex);
        const out = [];
        if (sStart <= 0) return [1.0];
        for (let t = 0; age + t <= maxAge; t++) {{
            out.push(Math.max(0, Math.min(1, lookupS0FromBirth(age + t, sex) / sStart)));
        }}
        if (!out.length) out.push(1.0);
        out[out.length - 1] = 0;
        return out;
    }}

    function eyllFromSurvival(hrX, hrRef, s0cond) {{
        let total = 0;
        for (let i = 0; i < s0cond.length; i++) {{
            const s = s0cond[i];
            total += Math.pow(s, hrRef) - Math.pow(s, hrX);
        }}
        return total;
    }}

    function formatUSD(v) {{
        if (v == null || !isFinite(v)) return '--';
        const abs = Math.abs(v);
        const sign = v < 0 ? '-' : '';
        if (abs >= 1e9) return sign + '$' + (abs / 1e9).toFixed(2) + 'B';
        if (abs >= 1e6) return sign + '$' + (abs / 1e6).toFixed(2) + 'M';
        if (abs >= 1e3) return sign + '$' + (abs / 1e3).toFixed(1) + 'k';
        return sign + '$' + abs.toFixed(0);
    }}

    function formatDalys(v) {{
        if (v == null || !isFinite(v)) return '--';
        if (Math.abs(v) >= 1e6) return (v / 1e6).toFixed(2) + 'M';
        if (Math.abs(v) >= 1e3) return (v / 1e3).toFixed(1) + 'k';
        return v.toFixed(3);
    }}

    function computeVOIFromSim(biomarker, sim, age, sex, epsilon, cIntDaly, lam) {{
        if (!sim || !biomarker) return null;
        const curves = biomarker.curves || [];
        const primaryCurve = curves[0] || null;
        if (!primaryCurve) return null;
        const xRef = (primaryCurve.reference_value != null) ? primaryCurve.reference_value : (sim.bins.p50 != null ? sim.bins.p50 : sim.bins.mean);
        const s0 = conditionalSurvivalFromAge(age, sex);
        const yld = 0; // named extension point — morbidity/YLD not built
        let eVoi = 0, eEyll = 0, eEyllS = 0, eDaly = 0;
        const n = sim.bins.x.length;
        for (let i = 0; i < n; i++) {{
            const p = sim.bins.p[i];
            if (p <= 0) continue;
            const hr0 = evaluateHR(sim.bins.x[i], primaryCurve, age, sex);
            const hrS = evaluateHR(sim.shiftedX[i], primaryCurve, age, sex);
            const hrRef = evaluateHR(xRef, primaryCurve, age, sex);
            const eyll0 = eyllFromSurvival(hr0, hrRef, s0);
            const eyllS = eyllFromSurvival(hrS, hrRef, s0);
            const d0 = eyll0 + yld;
            const d1 = eyllS + yld;
            const voi = Math.max(0, d0 - d1 - cIntDaly);
            eVoi += p * voi;
            eEyll += p * eyll0;
            eEyllS += p * eyllS;
            eDaly += p * d0;
        }}
        const meanX = sim.bins.mean;
        const meanIdx = sim.bins.x.reduce((best, x, i) => Math.abs(x - meanX) < Math.abs(sim.bins.x[best] - meanX) ? i : best, 0);
        const hrMean = evaluateHR(sim.bins.x[meanIdx], primaryCurve, age, sex);
        const hrMeanS = evaluateHR(sim.shiftedX[meanIdx], primaryCurve, age, sex);
        const hrRef = evaluateHR(xRef, primaryCurve, age, sex);
        const eyllMean = eyllFromSurvival(hrMean, hrRef, s0);
        const eyllMeanS = eyllFromSurvival(hrMeanS, hrRef, s0);
        const voiMean = Math.max(0, (eyllMean + yld) - (eyllMeanS + yld) - cIntDaly);
        const cTest = (biomarker.testPriceUSD != null) ? biomarker.testPriceUSD : 0;
        const lambdaVoi = lam * eVoi;
        const ehivVal = lambdaVoi - cTest;
        return {{
            expectedVoi: eVoi,
            expectedEyll: eEyll,
            expectedEyllShifted: eEyllS,
            expectedDeltaDaly: eDaly,
            eyllMean,
            deltaDalyMean: eyllMean + yld,
            voiMean,
            cTest,
            cTestKnown: biomarker.testPriceUSD != null,
            cms: biomarker.cmsReimbursementUSD,
            lambdaVoi,
            ehiv: ehivVal,
            favorable: ehivVal > 0,
            lam,
            epsilon,
            cIntDaly,
            age,
            sex
        }};
    }}

    function exclusiveStrataForBiomarker(biomarker) {{
        const dists = biomarker.population_distributions || [];
        const byKey = {{}};
        dists.forEach(d => {{
            const sex = d.sex || 'all';
            const band = d.age_band || 'all';
            const key = sex + '|' + band;
            if (!byKey[key] || (d.sample_n || 0) > (byKey[key].sample_n || 0)) byKey[key] = d;
        }});
        const included = [];
        const usedBands = new Set();
        ['20-39', '40-59', '60+'].forEach(band => {{
            const m = byKey['M|' + band];
            const f = byKey['F|' + band];
            const both = byKey['all|' + band];
            if (m && f) {{ included.push(m, f); usedBands.add(band); }}
            else if (m) {{ included.push(m); usedBands.add(band); }}
            else if (f) {{ included.push(f); usedBands.add(band); }}
            else if (both) {{ included.push(both); usedBands.add(band); }}
        }});
        if (usedBands.size === 0) {{
            const mAll = byKey['M|all'];
            const fAll = byKey['F|all'];
            const allAll = byKey['all|all'];
            if (mAll && fAll) included.push(mAll, fAll);
            else if (mAll) included.push(mAll);
            else if (fAll) included.push(fAll);
            else if (allAll) included.push(allAll);
        }}
        return included;
    }}

    function populationN(sex, ageBand) {{
        const table = (AppState.lifeTables && AppState.lifeTables.population_n) || {{}};
        if (sex === 'M' || sex === 'F') {{
            const direct = table[sex + '|' + ageBand];
            if (direct) return direct;
            if (ageBand === 'all') {{
                return ['20-39', '40-59', '60+'].reduce((s, b) => s + (table[sex + '|' + b] || 0), 0);
            }}
            return 0;
        }}
        if (ageBand === 'all') {{
            return Object.values(table).reduce((s, n) => s + (n || 0), 0);
        }}
        return (table['M|' + ageBand] || 0) + (table['F|' + ageBand] || 0);
    }}

    function ageBandMidpoint(band) {{
        const m = (AppState.lifeTables && AppState.lifeTables.age_band_midpoint) || {{ '20-39': 30, '40-59': 50, '60+': 70, all: 50 }};
        return m[band] != null ? m[band] : 50;
    }}

    function computePopulationVOI(biomarker, shiftSD, isPercentile, lam, cIntDaly) {{
        const strata = exclusiveStrataForBiomarker(biomarker);
        const cTest = (biomarker.testPriceUSD != null) ? biomarker.testPriceUSD : 0;
        let totalVoi = 0, totalEhiv = 0, totalN = 0;
        const byStratum = [];
        strata.forEach(d => {{
            if (d.sample_n != null && d.sample_n < 50) return;
            const clone = {{ ...biomarker, population_distributions: [d] }};
            const sim = runClientSimulation(clone, shiftSD, isPercentile, 80);
            if (!sim) return;
            const age = ageBandMidpoint(d.age_band || 'all');
            const sex = d.sex || 'all';
            const voi = computeVOIFromSim(biomarker, sim, age, sex, shiftSD, cIntDaly, lam);
            if (!voi) return;
            const n = populationN(sex, d.age_band || 'all');
            totalVoi += n * voi.expectedVoi;
            totalEhiv += n * voi.ehiv;
            totalN += n;
            byStratum.push({{ sex, age_band: d.age_band, n, expectedVoi: voi.expectedVoi, ehiv: voi.ehiv }});
        }});
        return {{ totalVoi, totalEhiv, totalN, byStratum, cTest }};
    }}

    function handleVoiLambdaInput(val) {{
        AppState.voiLambda = Math.max(0, parseFloat(val) || 0);
        runAndDisplaySimulation();
    }}

    function handleVoiCIntInput(val) {{
        AppState.voiCIntDaly = Math.max(0, parseFloat(val) || 0);
        runAndDisplaySimulation();
    }}

    function handleLeaderboardSort(val) {{
        AppState.leaderboardSort = val || 'rhr';
        renderOptimizationLeaderboard();
    }}

    function initVoiLambdaPresets() {{
        const wrap = document.getElementById('voi-lambda-presets');
        if (!wrap) return;
        const presets = (AppState.voiConfig && AppState.voiConfig.lambdaPresets) || [];
        wrap.innerHTML = '';
        presets.forEach(p => {{
            const btn = document.createElement('button');
            btn.className = 'px-2 py-1 text-[10px] bg-slate-800 hover:bg-slate-700 text-slate-300 rounded border border-slate-700';
            btn.textContent = p.label;
            btn.onclick = () => {{
                AppState.voiLambda = p.value;
                const inp = document.getElementById('voi-lambda-input');
                if (inp) inp.value = p.value;
                runAndDisplaySimulation();
            }};
            wrap.appendChild(btn);
        }});
        const inp = document.getElementById('voi-lambda-input');
        if (inp) inp.value = AppState.voiLambda;
    }}

    function renderVOIPanel(biomarker, sim) {{
        const age = AppState.landscapeAge || 50;
        const sex = AppState.landscapeSex || 'all';
        const caption = document.getElementById('voi-filter-caption');
        if (caption) caption.textContent = `age ${{age}} · sex ${{sex}}`;
        if (!sim) return;
        const voi = computeVOIFromSim(biomarker, sim, age, sex, AppState.currentSimShiftSD, AppState.voiCIntDaly, AppState.voiLambda);
        if (!voi) return;
        const ehivEl = document.getElementById('voi-ehiv');
        if (ehivEl) ehivEl.textContent = formatUSD(voi.ehiv);
        const badge = document.getElementById('voi-ehiv-badge');
        if (badge) {{
            badge.innerHTML = voi.favorable
                ? '<span class="text-[10px] px-1.5 py-0.5 rounded font-mono bg-emerald-500/20 text-emerald-300">favorable</span>'
                : '<span class="text-[10px] px-1.5 py-0.5 rounded font-mono bg-rose-500/20 text-rose-300">unfavorable</span>';
        }}
        const dalysEl = document.getElementById('voi-dalys');
        if (dalysEl) dalysEl.textContent = formatDalys(voi.expectedVoi);
        const lamVoiEl = document.getElementById('voi-lambda-voi');
        if (lamVoiEl) lamVoiEl.textContent = formatUSD(voi.lambdaVoi);
        const ctestEl = document.getElementById('voi-ctest');
        if (ctestEl) ctestEl.textContent = voi.cTestKnown ? formatUSD(voi.cTest) : 'Not priced';
        const cite = document.getElementById('voi-ctest-cite');
        if (cite) {{
            if (voi.cTestKnown) {{
                const basis = biomarker.testPriceIsPanelDerived
                    ? ' — panel prices only; no standalone test sold'
                    : '';
                cite.innerHTML = `<a href="${{biomarker.testPriceSourceUrl || 'https://www.findlabtest.com'}}" target="_blank" class="text-cyan-400 hover:underline">${{biomarker.testPriceSourceLabel || 'findlabtest.com'}} <i class="fa-solid fa-arrow-up-right-from-square text-[8px]"></i></a><span class="text-amber-300/80">${{basis}}</span>`;
            }} else {{
                cite.textContent = 'No findlabtest.com price mapped for this marker';
            }}
        }}
        const eyllEl = document.getElementById('voi-eyll');
        if (eyllEl) eyllEl.textContent = formatDalys(voi.eyllMean) + ' yr';
        const ddalyEl = document.getElementById('voi-ddaly');
        if (ddalyEl) ddalyEl.textContent = formatDalys(voi.deltaDalyMean);
        const indivEl = document.getElementById('voi-indiv');
        if (indivEl) indivEl.textContent = formatDalys(voi.voiMean);
        biomarker._lastVoi = voi;
        const lt = (AppState.voiConfig && AppState.voiConfig.lifeTableSource) ||
            'CDC NVSS United States Life Tables, 2022 (period, sex-specific).';
        // Panel-only markers (e.g. 25-OH vitamin D, where every observed
        // findlabtest.com product bundles other analytes) must not present
        // their price as the cost of this test alone.
        const blendedNote = biomarker.testPriceIsPanelDerived
            ? 'findlabtest.com self-pay median' + formatUSD(biomarker.testPriceBlendedMedian != null ? biomarker.testPriceBlendedMedian : voi.cTest) + ' — panel-only: every observed product bundles other analytes, so this overstates the cost of this test alone'
            : 'findlabtest.com self-pay median' + formatUSD(voi.cTest) + ' (standalone product)';
        const priceHtml = voi.cTestKnown
            ? sourceShortHtml({{}})
            : 'No priced test mapped; c<sub>test</sub> treated as $0.';
        if (voi.cTestKnown) {{
            priceHtml.citation = blendedNote;
            priceHtml.url = biomarker.testPriceSourceUrl || 'https://www.findlabtest.com';
        }}
        setProvenance('prov-voi', [
            hrProvenanceRow(biomarker, (biomarker.curves || [])[0]),
            nhanesProvenanceRow(biomarker),
            {{ label: 'Life table', html: escapeHtml(lt) }},
            {{ label: 'Test price', html: priceHtml }},
            methodProvenanceRow('EYLL from S0(t)^HR; VOI = max(0, ΔDALY(x) − ΔDALY(x′) − c_int); EHIV = λ·E[VOI] − c_test.')
        ]);
    }}

    function runClientSimulation(biomarker, shiftSD, isPercentileShift = false, numBins = 300) {{
        const dists = biomarker.population_distributions || [];
        const overallDist = dists.find(d => d.sex === 'all' && d.age_band === 'all') || dists[0];
        const curves = biomarker.curves || [];
        const primaryCurve = curves[0] || null;

        if (!overallDist || !primaryCurve) {{
            return null;
        }}

        // Prefer the parametric distribution_fit's valid domain (it carries
        // the physiologically sensible [domain_min, domain_max]); fall back
        // to the biomarker's valid_domain_min/max.
        const fits = biomarker.distribution_fits || [];
        const overallFit = fits.find(f => f.sex === 'all' && f.age_band === 'all') || null;
        const fitMin = overallFit && overallFit.domain_min != null ? overallFit.domain_min : biomarker.valid_domain_min;
        const fitMax = overallFit && overallFit.domain_max != null ? overallFit.domain_max : biomarker.valid_domain_max;

        const bins = generatePopulationBins(overallDist, numBins);
        const direction = biomarker.directionality || 'MONOTONIC_INCREASING';
        const dMin = fitMin;
        const dMax = fitMax;

        // Re-normalize the probability mass to the physiologically valid
        // domain so HR expectations integrate to a proper density.
        const truncatedBins = truncateBinsToDomain(bins, dMin, dMax);

        // Baseline numerical integration E[HR_0]
        let eHr0 = 0.0;
        for (let i = 0; i < truncatedBins.x.length; i++) {{
            const hr = evaluateHR(truncatedBins.x[i], primaryCurve);
            eHr0 += truncatedBins.p[i] * hr;
        }}

        // Calculate shifted x values
        const shiftedX = [];
        const individualBenefits = [];
        let clampedCount = 0;
        let totalClampedProb = 0.0;

        const p25 = overallDist.p25 || (bins.mean - 0.674 * bins.sd);
        const p50 = overallDist.p50 || bins.mean;

        for (let i = 0; i < truncatedBins.x.length; i++) {{
            const x0 = truncatedBins.x[i];
            let xShifted = x0;

            if (isPercentileShift) {{
                if (direction === 'MONOTONIC_DECREASING') {{
                    // Beneficial to increase: shift low (< P25) up to P50
                    if (x0 < p25) xShifted = p50;
                }} else if (direction === 'MONOTONIC_INCREASING') {{
                    // Beneficial to lower: shift high (> P75) down to P50
                    const p75 = overallDist.p75 || (bins.mean + 0.674 * bins.sd);
                    if (x0 > p75) xShifted = p50;
                }} else {{
                    if (x0 < p25) xShifted = p50;
                }}
            }} else {{
                // Standard continuous SD shift
                if (direction === 'MONOTONIC_DECREASING') {{
                    xShifted = x0 + shiftSD * bins.sd;
                }} else if (direction === 'MONOTONIC_INCREASING') {{
                    xShifted = x0 - shiftSD * bins.sd;
                }} else {{
                    // Non-monotonic (U/J shaped): move toward optimal target x*
                    const optimalTarget = biomarker.optimal_target != null ? biomarker.optimal_target : p50;
                    const diff = optimalTarget - x0;
                    const shiftDist = Math.min(Math.abs(diff), shiftSD * bins.sd);
                    xShifted = x0 + Math.sign(diff) * shiftDist;
                }}
            }}

            // Domain clamping
            let wasClamped = false;
            if (dMin != null && xShifted < dMin) {{
                xShifted = dMin;
                wasClamped = true;
            }}
            if (dMax != null && xShifted > dMax) {{
                xShifted = dMax;
                wasClamped = true;
            }}

            if (wasClamped) {{
                clampedCount++;
                totalClampedProb += truncatedBins.p[i];
            }}

            shiftedX.push(xShifted);

            // Individual Delta HR_i = HR(x0) - HR(xShifted)
            const hr0 = evaluateHR(x0, primaryCurve);
            const hrShifted = evaluateHR(xShifted, primaryCurve);
            const benefit = hr0 - hrShifted;
            individualBenefits.push({{ benefit, weight: truncatedBins.p[i], hr0, hrShifted }});
        }}

        // Shifted numerical integration E[HR_delta]
        let eHrDelta = 0.0;
        let benefitingProb = 0.0;
        let harmedProb = 0.0;

        for (let i = 0; i < shiftedX.length; i++) {{
            const hrShifted = evaluateHR(shiftedX[i], primaryCurve);
            eHrDelta += truncatedBins.p[i] * hrShifted;

            const b = individualBenefits[i].benefit;
            if (b > 1e-4) benefitingProb += truncatedBins.p[i];
            else if (b < -1e-4) harmedProb += truncatedBins.p[i];
        }}

        const deltaHR = eHr0 - eHrDelta;
        const relativeHazardReduction = eHr0 > 0 ? (deltaHR / eHr0) : 0.0;

        let domainStatus = 'IN_DOMAIN';
        if (totalClampedProb > 0.15) domainStatus = 'OUT_OF_DOMAIN';
        else if (totalClampedProb > 0) domainStatus = 'BOUNDARY_REACHED';

        // Quantiles of benefit
        const sortedBenefits = [...individualBenefits].sort((a, b) => a.benefit - b.benefit);
        function getWeightedQuantile(q) {{
            let cum = 0.0;
            for (let item of sortedBenefits) {{
                cum += item.weight;
                if (cum >= q) return item.benefit;
            }}
            return sortedBenefits[sortedBenefits.length - 1].benefit;
        }}

        return {{
            baseline_expected_hr: eHr0,
            optimized_expected_hr: eHrDelta,
            delta_hr: deltaHR,
            relative_hazard_reduction: relativeHazardReduction,
            fraction_benefiting: benefitingProb,
            fraction_harmed: harmedProb,
            fraction_out_of_domain: totalClampedProb,
            domain_status: domainStatus,
            bins: truncatedBins,
            shiftedX,
            individualBenefits,
            q10: getWeightedQuantile(0.10),
            q25: getWeightedQuantile(0.25),
            q50: getWeightedQuantile(0.50),
            q75: getWeightedQuantile(0.75),
            q90: getWeightedQuantile(0.90),
            max_benefit: sortedBenefits[sortedBenefits.length - 1].benefit
        }};
    }}

    // --- INITIALIZATION & GLOBAL NAVIGATION ---

    document.addEventListener('DOMContentLoaded', () => {{
        initApp();
    }});

    function initApp() {{
        populateStats();
        populateFilterDropdowns();
        renderBiomarkersList();
        renderDiseasesView();
        renderSourcesList();
        initLeaderboardScenarioOptions();
        setupNavigationTabs();
        setupSubTabs();
        setupFilterListeners();
        setupDiseaseListeners();
        setupCompareListeners();
        setupLandscapeAgeSexListeners();
        initVoiLambdaPresets();

        // Select first biomarker by default
        if (AppState.biomarkers.length > 0) {{
            selectBiomarker(AppState.biomarkers[0].slug);
        }}
    }}

    function populateStats() {{
        const elBio = document.getElementById('stat-biomarkers');
        if (elBio) elBio.textContent = AppState.stats.biomarkers_total || AppState.biomarkers.length;

        const elDis = document.getElementById('stat-diseases');
        if (elDis) elDis.textContent = AppState.stats.diseases_total || AppState.diseases.length;

        const elAlt = document.getElementById('stat-alterations');
        if (elAlt) elAlt.textContent = AppState.stats.disease_alterations_total || '--';

        const elAssoc = document.getElementById('stat-associations');
        if (elAssoc) elAssoc.textContent = AppState.stats.mortality_associations_total || '--';

        const elDist = document.getElementById('stat-distributions');
        if (elDist) elDist.textContent = AppState.stats.population_distributions_total || '--';

        const elItv = document.getElementById('stat-interventions');
        if (elItv) elItv.textContent = AppState.stats.interventions_total || '--';

        const elSrc = document.getElementById('stat-sources');
        if (elSrc) elSrc.textContent = AppState.stats.sources_total || AppState.sources.length;
    }}

    function populateFilterDropdowns() {{
        const catSelect = document.getElementById('filter-category');
        (AppState.stats.categories || []).forEach(cat => {{
            const opt = document.createElement('option');
            opt.value = cat;
            opt.textContent = cat;
            catSelect.appendChild(opt);
        }});

        const disCatSelect = document.getElementById('filter-disease-category');
        if (disCatSelect) {{
            (AppState.stats.disease_categories || []).forEach(cat => {{
                const opt = document.createElement('option');
                opt.value = cat;
                opt.textContent = cat;
                disCatSelect.appendChild(opt);
            }});
        }}

        const organSelect = document.getElementById('filter-organ');
        if (organSelect) {{
            (AppState.stats.primary_organs || []).forEach(org => {{
                const opt = document.createElement('option');
                opt.value = org;
                opt.textContent = org;
                organSelect.appendChild(opt);
            }});
        }}

        const fluidSelect = document.getElementById('filter-fluid');
        if (fluidSelect) {{
            (AppState.stats.bodily_fluids || []).forEach(fl => {{
                const opt = document.createElement('option');
                opt.value = fl;
                opt.textContent = fl;
                fluidSelect.appendChild(opt);
            }});
        }}

        const tissueSelect = document.getElementById('filter-tissue');
        if (tissueSelect) {{
            (AppState.stats.tissue_origins || []).forEach(t => {{
                const opt = document.createElement('option');
                opt.value = t;
                opt.textContent = t;
                tissueSelect.appendChild(opt);
            }});
        }}
    }}

    function initLeaderboardScenarioOptions() {{
        const select = document.getElementById('leaderboard-scenario-select');
        select.innerHTML = '';
        (AppState.scenarios || []).forEach(sc => {{
            const opt = document.createElement('option');
            opt.value = sc.slug;
            opt.textContent = sc.name;
            if (sc.slug === 'sd_100') opt.selected = true;
            select.appendChild(opt);
        }});
    }}

    function setupNavigationTabs() {{
        const tabs = [
            {{ btn: 'tab-biomarkers', view: 'view-biomarkers' }},
            {{ btn: 'tab-diseases', view: 'view-diseases' }},
            {{ btn: 'tab-leaderboard', view: 'view-leaderboard' }},
            {{ btn: 'tab-compare', view: 'view-compare' }},
            {{ btn: 'tab-sources', view: 'view-sources' }}
        ];

        tabs.forEach(t => {{
            const btnEl = document.getElementById(t.btn);
            if (btnEl) {{
                btnEl.addEventListener('click', () => {{
                    tabs.forEach(o => {{
                        const otherBtn = document.getElementById(o.btn);
                        const otherView = document.getElementById(o.view);
                        if (otherBtn) otherBtn.className = 'tab-btn px-3 py-1.5 text-xs font-semibold rounded-md transition-colors text-slate-400 hover:text-white hover:bg-slate-800';
                        if (otherView) otherView.classList.add('hidden');
                    }});
                    btnEl.className = 'tab-btn active px-3 py-1.5 text-xs font-semibold rounded-md transition-colors bg-indigo-600 text-white shadow';
                    document.getElementById(t.view).classList.remove('hidden');
                    AppState.activeTab = t.view.replace('view-', '');

                    if (t.view === 'view-diseases') {{
                        renderDiseasesView();
                    }} else if (t.view === 'view-leaderboard') {{
                        renderOptimizationLeaderboard();
                    }} else if (t.view === 'view-compare') {{
                        renderCompareView();
                    }}
                }});
            }}
        }});
    }}

    function navigateTab(tabName) {{
        const btn = document.getElementById(`tab-${{tabName}}`);
        if (btn) btn.click();
    }}

    function setupSubTabs() {{
        const subtabs = [
            {{ btn: 'subtab-landscape', view: 'subview-landscape' }},
            {{ btn: 'subtab-diseases', view: 'subview-diseases' }},
            {{ btn: 'subtab-optimization', view: 'subview-optimization' }},
            {{ btn: 'subtab-forest', view: 'subview-forest' }},
            {{ btn: 'subtab-interventions', view: 'subview-interventions' }},
            {{ btn: 'subtab-demographics', view: 'subview-demographics' }}
        ];

        subtabs.forEach(st => {{
            const btnEl = document.getElementById(st.btn);
            if (btnEl) {{
                btnEl.addEventListener('click', () => {{
                    subtabs.forEach(o => {{
                        const otherBtn = document.getElementById(o.btn);
                        const otherView = document.getElementById(o.view);
                        if (otherBtn) otherBtn.className = 'subtab-btn px-3 py-2 text-xs font-semibold rounded-t-lg text-slate-400 hover:text-white hover:bg-slate-800/50 transition flex items-center gap-1.5';
                        if (otherView) otherView.classList.add('hidden');
                    }});
                    btnEl.className = 'subtab-btn active px-3 py-2 text-xs font-semibold rounded-t-lg bg-indigo-600 text-white transition flex items-center gap-1.5';
                    document.getElementById(st.view).classList.remove('hidden');
                    AppState.activeSubTab = st.view.replace('subview-', '');

                    if (st.view === 'subview-landscape' && AppState.selectedBiomarkerDetail) {{
                        renderLandscapePlot(AppState.selectedBiomarkerDetail);
                    }} else if (st.view === 'subview-diseases' && AppState.selectedBiomarkerDetail) {{
                        renderBiomarkerDiseasesView(AppState.selectedBiomarkerDetail);
                    }} else if (st.view === 'subview-optimization' && AppState.selectedBiomarkerDetail) {{
                        renderOptimizationSubview(AppState.selectedBiomarkerDetail);
                    }} else if (st.view === 'subview-forest' && AppState.selectedBiomarkerDetail) {{
                        renderForestPlot(AppState.selectedBiomarkerDetail);
                    }} else if (st.view === 'subview-demographics' && AppState.selectedBiomarkerDetail) {{
                        renderDemographicsPlot(AppState.selectedBiomarkerDetail);
                    }}
                }});
            }}
        }});
    }}

    function setupDiseaseListeners() {{
        const searchInput = document.getElementById('disease-search');
        if (searchInput) {{
            searchInput.addEventListener('input', (e) => {{
                AppState.diseaseFilters.search = e.target.value.toLowerCase();
                renderDiseasesView();
            }});
        }}

        const catFilter = document.getElementById('filter-disease-category');
        if (catFilter) {{
            catFilter.addEventListener('change', (e) => {{
                AppState.diseaseFilters.category = e.target.value;
                renderDiseasesView();
            }});
        }}

        const sortSelect = document.getElementById('filter-disease-sort');
        if (sortSelect) {{
            sortSelect.addEventListener('change', (e) => {{
                AppState.diseaseFilters.sortBy = e.target.value;
                renderDiseasesView();
            }});
        }}

        const btnClose = document.getElementById('btn-close-disease-modal');
        if (btnClose) {{
            btnClose.addEventListener('click', closeDiseaseModal);
        }}

        const modalOverlay = document.getElementById('disease-modal');
        if (modalOverlay) {{
            modalOverlay.addEventListener('click', (e) => {{
                if (e.target === modalOverlay) closeDiseaseModal();
            }});
        }}

        document.querySelectorAll('.modal-tab-btn').forEach(btn => {{
            btn.addEventListener('click', () => {{
                const tab = btn.getAttribute('data-modal-tab');
                switchModalTab(tab);
            }});
        }});
    }}

    function setupFilterListeners() {{
        const searchInput = document.getElementById('biomarker-search');
        searchInput.addEventListener('input', (e) => {{
            AppState.filters.search = e.target.value.toLowerCase();
            renderBiomarkersList();
        }});

        const catFilter = document.getElementById('filter-category');
        if (catFilter) {{
            catFilter.addEventListener('change', (e) => {{
                AppState.filters.category = e.target.value;
                renderBiomarkersList();
            }});
        }}

        const organFilter = document.getElementById('filter-organ');
        if (organFilter) {{
            organFilter.addEventListener('change', (e) => {{
                AppState.filters.organ = e.target.value;
                renderBiomarkersList();
            }});
        }}

        const fluidFilter = document.getElementById('filter-fluid');
        if (fluidFilter) {{
            fluidFilter.addEventListener('change', (e) => {{
                AppState.filters.fluid = e.target.value;
                renderBiomarkersList();
            }});
        }}

        const tissueFilter = document.getElementById('filter-tissue');
        if (tissueFilter) {{
            tissueFilter.addEventListener('change', (e) => {{
                AppState.filters.tissue = e.target.value;
                renderBiomarkersList();
            }});
        }}

        // Group By Toggle Buttons
        const groupBtns = document.querySelectorAll('.group-by-btn');
        groupBtns.forEach(btn => {{
            btn.addEventListener('click', () => {{
                groupBtns.forEach(b => {{
                    b.classList.remove('active', 'bg-indigo-600', 'text-white', 'shadow-sm');
                    b.classList.add('text-slate-400');
                }});
                btn.classList.add('active', 'bg-indigo-600', 'text-white', 'shadow-sm');
                btn.classList.remove('text-slate-400');
                
                AppState.groupBy = btn.getAttribute('data-group');
                const labelMap = {{
                    flat: 'None',
                    primary_organ: 'Organ / System',
                    bodily_fluid: 'Bodily Fluid',
                    tissue_origin: 'Tissue Origin'
                }};
                document.getElementById('group-active-indicator').textContent = `Grouped: ${{labelMap[AppState.groupBy] || 'None'}}`;
                renderBiomarkersList();
            }});
        }});

        document.getElementById('source-search').addEventListener('input', (e) => {{
            AppState.sourceSearch = e.target.value.toLowerCase();
            renderSourcesList();
        }});
    }}

    // --- BIOMARKERS LIST RENDERING ---

    function getCausalBadgeHTML(status) {{
        if (status === 'RCT_SUPPORTED') return `<span class="px-1.5 py-0.5 rounded text-[9px] font-mono bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">RCT Proven</span>`;
        if (status === 'MENDELIAN_RANDOMIZATION') return `<span class="px-1.5 py-0.5 rounded text-[9px] font-mono bg-cyan-500/20 text-cyan-300 border border-cyan-500/40">MR Causal</span>`;
        if (status === 'QUASI_EXPERIMENTAL') return `<span class="px-1.5 py-0.5 rounded text-[9px] font-mono bg-indigo-500/20 text-indigo-300 border border-indigo-500/40">Quasi-Exp</span>`;
        if (status === 'STRONG_OBSERVATIONAL') return `<span class="px-1.5 py-0.5 rounded text-[9px] font-mono bg-amber-500/20 text-amber-300 border border-amber-500/40">Strong Obs</span>`;
        return `<span class="px-1.5 py-0.5 rounded text-[9px] font-mono bg-slate-750 text-slate-400 border border-slate-700">Observational</span>`;
    }}

    function renderBiomarkersList() {{
        const container = document.getElementById('biomarkers-list');
        const countSpan = document.getElementById('biomarkers-count');
        
        let filtered = AppState.biomarkers.filter(b => {{
            const matchesSearch = !AppState.filters.search || 
                b.name.toLowerCase().includes(AppState.filters.search) || 
                (b.common_name && b.common_name.toLowerCase().includes(AppState.filters.search)) ||
                (b.category && b.category.toLowerCase().includes(AppState.filters.search)) ||
                (b.primary_organ && b.primary_organ.toLowerCase().includes(AppState.filters.search)) ||
                (b.bodily_fluid && b.bodily_fluid.toLowerCase().includes(AppState.filters.search)) ||
                (b.tissue_origin && b.tissue_origin.toLowerCase().includes(AppState.filters.search)) ||
                (b.slug && b.slug.toLowerCase().includes(AppState.filters.search));
            
            const matchesCategory = !AppState.filters.category || b.category === AppState.filters.category;
            const matchesOrgan = !AppState.filters.organ || b.primary_organ === AppState.filters.organ;
            const matchesFluid = !AppState.filters.fluid || b.bodily_fluid === AppState.filters.fluid;
            const matchesTissue = !AppState.filters.tissue || b.tissue_origin === AppState.filters.tissue;

            return matchesSearch && matchesCategory && matchesOrgan && matchesFluid && matchesTissue;
        }});

        // Sort by 1.0-SD Relative Hazard Reduction descending
        filtered.sort((a, b) => (b.rel_hazard_red_100 || 0) - (a.rel_hazard_red_100 || 0));

        countSpan.textContent = filtered.length;
        container.innerHTML = '';

        if (filtered.length === 0) {{
            container.innerHTML = `<div class="p-6 text-center text-xs text-slate-500">No biomarkers matching active criteria</div>`;
            return;
        }}

        function createBiomarkerRow(b) {{
            const isSelected = AppState.selectedBiomarker === b.slug;
            const item = document.createElement('div');
            item.className = `p-3.5 cursor-pointer transition-colors flex items-center justify-between ${{
                isSelected 
                    ? 'bg-indigo-950/70 border-l-4 border-indigo-500 text-white' 
                    : 'hover:bg-slate-850 text-slate-300 border-l-4 border-transparent'
            }}`;

            const rhrPct = ((b.rel_hazard_red_100 || 0) * 100).toFixed(1);
            const causalBadge = getCausalBadgeHTML(b.causal_status);

            const organBadge = b.primary_organ ? `<span class="px-1.5 py-0.2 rounded text-[9px] bg-slate-800 text-slate-300 border border-slate-700 font-medium">${{b.primary_organ}}</span>` : '';
            const fluidBadge = b.bodily_fluid ? `<span class="px-1.5 py-0.2 rounded text-[9px] bg-cyan-950/50 text-cyan-300 border border-cyan-800/40 font-medium">${{b.bodily_fluid}}</span>` : '';

            item.innerHTML = `
                <div class="space-y-1 min-w-0 flex-1 pr-2">
                    <div class="flex items-center gap-1.5 flex-wrap">
                        <span class="font-bold text-xs truncate text-slate-100">${{b.name}}</span>
                        ${{causalBadge}}
                    </div>
                    <div class="flex items-center gap-1.5 flex-wrap text-[11px] text-slate-400">
                        ${{organBadge}}
                        ${{fluidBadge}}
                        <span class="font-mono text-slate-400">${{b.units}}</span>
                    </div>
                </div>
                <div class="text-right flex flex-col items-end shrink-0">
                    <div class="text-xs font-black ${{b.rel_hazard_red_100 > 0.15 ? 'text-purple-400' : 'text-slate-300'}}">
                        -${{rhrPct}}%
                    </div>
                    <div class="text-[9px] text-slate-500 font-mono">1.0-SD RHR</div>
                </div>
            `;

            item.addEventListener('click', () => {{
                selectBiomarker(b.slug);
            }});

            return item;
        }}

        if (AppState.groupBy === 'flat' || !AppState.groupBy) {{
            filtered.forEach(b => {{
                container.appendChild(createBiomarkerRow(b));
            }});
        }} else {{
            // Group biomarkers by the selected anatomical/physiological dimension
            const groupKey = AppState.groupBy;
            const groups = {{}};
            filtered.forEach(b => {{
                const groupName = b[groupKey] || 'Unclassified';
                if (!groups[groupName]) groups[groupName] = [];
                groups[groupName].push(b);
            }});

            const sortedGroupNames = Object.keys(groups).sort();
            sortedGroupNames.forEach(groupName => {{
                const groupList = groups[groupName];
                const header = document.createElement('div');
                header.className = 'px-3.5 py-2 bg-slate-950/90 text-slate-200 text-xs font-bold uppercase tracking-wider flex items-center justify-between border-y border-slate-800 sticky top-0 z-10';
                
                let icon = 'fa-solid fa-folder';
                if (groupKey === 'primary_organ') icon = 'fa-solid fa-heart-pulse text-rose-400';
                else if (groupKey === 'bodily_fluid') icon = 'fa-solid fa-droplet text-cyan-400';
                else if (groupKey === 'tissue_origin') icon = 'fa-solid fa-microscope text-amber-400';

                header.innerHTML = `
                    <span class="flex items-center gap-1.5">
                        <i class="${{icon}} text-[11px]"></i>
                        <span>${{groupName}}</span>
                    </span>
                    <span class="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">${{groupList.length}}</span>
                `;
                container.appendChild(header);

                groupList.forEach(b => {{
                    container.appendChild(createBiomarkerRow(b));
                }});
            }});
        }}
    }}

    function selectBiomarker(slug) {{
        AppState.selectedBiomarker = slug;
        const b = AppState.biomarkers.find(item => item.slug === slug);
        if (!b) return;

        AppState.selectedBiomarkerDetail = b;
        renderBiomarkersList();
        renderBiomarkerDetailHeader(b);

        if (AppState.activeSubTab === 'landscape') {{
            renderLandscapePlot(b);
        }} else if (AppState.activeSubTab === 'diseases') {{
            renderBiomarkerDiseasesView(b);
        }} else if (AppState.activeSubTab === 'optimization') {{
            renderOptimizationSubview(b);
        }} else if (AppState.activeSubTab === 'forest') {{
            renderForestPlot(b);
        }} else if (AppState.activeSubTab === 'interventions') {{
            renderInterventionsView(b);
        }} else if (AppState.activeSubTab === 'demographics') {{
            renderDemographicsPlot(b);
        }}
    }}

    function renderBiomarkerDetailHeader(b) {{
        const header = document.getElementById('detail-header');
        const causalBadge = getCausalBadgeHTML(b.causal_status);
        const rel100 = ((b.rel_hazard_red_100 || 0) * 100).toFixed(1);

        header.innerHTML = `
            <div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div class="space-y-1.5">
                    <div class="flex items-center gap-2.5 flex-wrap">
                        <h2 class="text-lg font-black text-white tracking-tight">${{b.name}}</h2>
                        ${{causalBadge}}
                        <span class="px-2 py-0.5 rounded text-[10px] font-mono bg-slate-800 text-slate-300 border border-slate-700">
                            ${{b.directionality || 'MONOTONIC_INCREASING'}}
                        </span>
                    </div>
                    <p class="text-xs text-slate-300 max-w-2xl leading-relaxed">${{b.description || ''}}</p>
                </div>
                <div class="flex items-center gap-3 bg-slate-950/80 p-3 rounded-xl border border-slate-800 shrink-0">
                    <div>
                        <div class="text-[10px] text-slate-400 font-medium">Standard 1-SD Impact</div>
                        <div class="text-base font-black text-purple-400">-${{rel100}}% Hazard</div>
                    </div>
                    <div class="w-px h-8 bg-slate-800"></div>
                    <div>
                        <div class="text-[10px] text-slate-400 font-medium">Domain Range</div>
                        <div class="text-xs font-mono text-emerald-400 font-bold">${{b.valid_domain_min ?? 0}} - ${{b.valid_domain_max ?? 'Max'}} ${{b.units}}</div>
                    </div>
                </div>
            </div>
        `;

        // Update Landscape Metric Callouts
        document.getElementById('callout-optimal').textContent = b.optimal_target != null ? `${{b.optimal_target}} ${{b.units}}` : (b.directionality === 'MONOTONIC_DECREASING' ? 'Upper Physiological Limit' : 'Lower Physiological Limit');
        document.getElementById('callout-median').textContent = b.population_median != null ? `${{b.population_median}} ${{b.units}}` : '--';
        document.getElementById('callout-baseline-hr').textContent = b.baseline_expected_hr != null ? `${{b.baseline_expected_hr.toFixed(3)}}` : '1.000';
        document.getElementById('callout-domain-range').textContent = `[${{b.valid_domain_min ?? 0}}, ${{b.valid_domain_max ?? 'Inf'}}] ${{b.units}}`;
    }}

    // --- SUBVIEW 1: FITNESS LANDSCAPE PLOT ---

    function renderLandscapePlot(detail) {{
        const plotDiv = document.getElementById('plot-landscape');
        const dists = detail.population_distributions || [];
        const overallDist = dists.find(d => d.sex === 'all' && d.age_band === 'all') || dists[0];
        const curves = detail.curves || [];
        const age = AppState.landscapeAge;
        const sex = AppState.landscapeSex;

        // Select the best curve for the given age/sex using stratum-specific curves:
        // 1. Prefer age_interaction curves (parametric, evaluated at the selected age)
        // 2. Prefer stratum-specific curves matching both age_band AND sex
        // 3. Fall back to age-band-specific curves (sex='all')
        // 4. Fall back to sex-specific curves (age_band='all')
        // 5. Fall back to the pooled curve (age_band='all', sex='all')
        let primaryCurve = null;
        let curveSpecificity = 'pooled';

        // Determine the age band from the selected age
        const ageBand = age < 40 ? '20-39' : (age < 60 ? '40-59' : '60+');

        const ageInteractionCurves = curves.filter(c => c.curve_type === 'age_interaction');
        const stratumCurves = curves.filter(c => c.curve_type !== 'age_interaction');

        if (ageInteractionCurves.length > 0) {{
            primaryCurve = ageInteractionCurves[0];
            curveSpecificity = sex === 'all' ? `age=${{age}}` : `age=${{age}}, sex=${{sex}}`;
        }} else if (sex !== 'all') {{
            // Try age_band + sex match first
            const ageSexMatch = stratumCurves.find(c => c.age_band === ageBand && c.sex === sex);
            if (ageSexMatch) {{
                primaryCurve = ageSexMatch;
                curveSpecificity = `age=${{ageBand}}, sex=${{sex}}`;
            }} else {{
                // Fall back to age_band only
                const ageMatch = stratumCurves.find(c => c.age_band === ageBand && (!c.sex || c.sex === 'all'));
                if (ageMatch) {{
                    primaryCurve = ageMatch;
                    curveSpecificity = `age=${{ageBand}}`;
                }} else {{
                    // Fall back to sex only
                    const sexMatch = stratumCurves.find(c => c.sex === sex && (!c.age_band || c.age_band === 'all'));
                    if (sexMatch) {{
                        primaryCurve = sexMatch;
                        curveSpecificity = `sex=${{sex}}`;
                    }} else {{
                        primaryCurve = stratumCurves.find(c => (!c.age_band || c.age_band === 'all') && (!c.sex || c.sex === 'all')) || stratumCurves[0];
                        curveSpecificity = 'pooled';
                    }}
                }}
            }}
        }} else {{
            // Sex is 'all': try age_band match
            const ageMatch = stratumCurves.find(c => c.age_band === ageBand && (!c.sex || c.sex === 'all'));
            if (ageMatch) {{
                primaryCurve = ageMatch;
                curveSpecificity = `age=${{ageBand}}`;
            }} else {{
                primaryCurve = stratumCurves.find(c => (!c.age_band || c.age_band === 'all') && (!c.sex || c.sex === 'all')) || stratumCurves[0];
                curveSpecificity = 'pooled';
            }}
        }}

        if (!overallDist || !primaryCurve) {{
            plotDiv.innerHTML = `<div class="p-8 text-center text-xs text-slate-500">Distribution or Spline Curve Data Unavailable</div>`;
            return;
        }}

        // Prefer the parametric distribution_fit for the selected stratum
        // (it carries fit_type, parameters, AND the valid plotting domain),
        // falling back to the legacy population_distributions mean/sd.
        const fits = detail.distribution_fits || [];
        const fitForStratum = () => {{
            if (ageBand === 'all') return null;
            return fits.find(f => f.sex === sex && f.age_band === ageBand)
                || fits.find(f => f.age_band === ageBand)
                || fits.find(f => f.sex === sex && f.age_band === 'all')
                || fits.find(f => f.sex === 'all' && f.age_band === ageBand);
        }};
        const overallFit = fits.find(f => f.sex === 'all' && f.age_band === 'all') || null;
        const paramFit = fitForStratum() || overallFit;

        // Extract mean/sd/p50/etc. for use in generatePopulationBins().
        // For a lognormal fit the parameters are on the log-scale, so
        // back-transform them to the arithmetic mean and standard
        // deviation of the original variable.
        const pdfParams = (fit) => {{
            const p = fit.parameters || {{}};
            const fitType = fit.fit_type || 'normal';
            if (fitType === 'lognormal') {{
                const mu = p.mu != null ? p.mu : p.mean;
                const sigma = p.sigma != null ? p.sigma : p.sd;
                const logMean = Math.exp(mu);
                const logSd = Math.sqrt(Math.exp(sigma * sigma) - 1.0);
                const mean = logMean * (1 + sigma * sigma / 2);
                const sd = Math.sqrt((Math.exp(sigma * sigma) - 1.0)
                    * Math.exp(Math.pow(mu, 2) + sigma * sigma));
                return {{ mean, sd, p50: logMean }};
            }}
            return {{ mean: p.mean != null ? p.mean : p.mu, sd: p.sd != null ? p.sd : p.sigma, p50: p.median }};
        }};

        let distLike;
        let paramDomain = null;
        if (paramFit && overallFit) {{
            // Use the matched stratum's parameters but the overall stratum's
            // p-quantiles if available; fall back to deriving quantiles.
            const fitParams = pdfParams(paramFit);
            const fallbackD = dists.find(d => d.sex === 'all' && d.age_band === 'all') || dists[0];
            distLike = {{
                mean: fitParams.mean,
                sd: fitParams.sd,
                p50: fitParams.p50 != null ? fitParams.p50 : (fallbackD ? fallbackD.p50 : fitParams.mean),
                p5: fallbackD ? fallbackD.p5 : null,
                p10: fallbackD ? fallbackD.p10 : null,
                p25: fallbackD ? fallbackD.p25 : null,
                p75: fallbackD ? fallbackD.p75 : null,
                p90: fallbackD ? fallbackD.p90 : null,
                p95: fallbackD ? fallbackD.p95 : null
            }};
            paramDomain = [paramFit.domain_min, paramFit.domain_max];
        }} else if (overallFit) {{
            const fitParams = pdfParams(overallFit);
            distLike = {{
                mean: fitParams.mean,
                sd: fitParams.sd,
                p50: fitParams.p50,
                p5: overallDist.p5, p10: overallDist.p10,
                p25: overallDist.p25, p75: overallDist.p75,
                p90: overallDist.p90, p95: overallDist.p95
            }};
            paramDomain = [overallFit.domain_min, overallFit.domain_max];
        }} else {{
            // Fall back to legacy population_distributions payload
            distLike = overallDist;
        }}

        const bins = generatePopulationBins(distLike);
        const hrLabel = (curveSpecificity === 'pooled') ? 'Mortality Hazard Ratio HR(x)' : `Mortality HR(x) | ${{curveSpecificity}}`;

        // Update the curve specificity badge
        const specBadge = document.getElementById('landscape-curve-specificity');
        if (specBadge) specBadge.textContent = curveSpecificity;

        // Plot only the observed population support (p5–p95 + small pad).
        // Physiological / HR-curve domains are often many times wider and
        // leave the density as a thin spike in empty space.
        const validMin = (detail.valid_domain_min != null) ? detail.valid_domain_min
            : (primaryCurve.valid_min != null ? primaryCurve.valid_min : null);
        const validMax = (detail.valid_domain_max != null) ? detail.valid_domain_max
            : (primaryCurve.valid_max != null ? primaryCurve.valid_max : null);
        const [dataMin, dataMax] = distributionDisplayRange(distLike, bins, validMin, validMax);

        // The density trace must integrate to 1.0 over the PLOTTED range only.
        // Re-grid the population density onto a fine grid spanning exactly
        // [dataMin, dataMax] and re-normalize the visible mass to 1.0, so the
        // drawn distribution is a proper truncated density (not a clipped one).
        const NUM_PLOT_BINS = 300;
        const plotStep = (dataMax - dataMin) / (NUM_PLOT_BINS - 1);
        const plotX = [];
        for (let i = 0; i < NUM_PLOT_BINS; i++) plotX.push(dataMin + i * plotStep);

        const traceDensity = {{
            x: plotX,
            y: bins.p.map((_, i) => {{
                const x = plotX[i];
                const z = (x - bins.mean) / bins.sd;
                const pdf = Math.exp(-0.5 * z * z) / (bins.sd * Math.sqrt(2 * Math.PI));
                return pdf;
            }}),
            type: 'scatter',
            mode: 'lines',
            name: 'NHANES Population Density',
            yaxis: 'y2',
            line: {{ color: 'rgba(16, 185, 129, 0.6)', width: 2 }},
            fill: 'tozeroy',
            fillcolor: 'rgba(16, 185, 129, 0.12)'
        }};

        // Normalize traceDensity.y so the visible density integrates to 1.0
        // over the plotted range (truncated-normal semantics), then scale the
        // right-hand density axis so the peak reads ~1.0 for a clean display.
        const visTotal = traceDensity.y.reduce((a, c) => a + c, 0) || 1;
        traceDensity.y = traceDensity.y.map(p => p / visTotal);

        // Build the HR trace ONLY over x-values within the data boundary,
        // sampled on the same fine grid as the density trace.
        const hrY = plotX.map(x => evaluateHR(x, primaryCurve, age, sex));

        const traceHR = {{
            x: plotX,
            y: hrY,
            type: 'scatter',
            mode: 'lines',
            name: hrLabel,
            line: {{ color: '#818cf8', width: 3.5 }},
            connectgaps: false
        }};

        // --- Selection boxes: Male / Female & Age-group distribution overlays ---
        // Build a truncated-normal density trace on the SAME x-grid as the
        // overall density, normalized so the VISIBLE mass sums to 1.0 as well.
        const buildOverlayTrace = (d, label, color) => {{
            if (!d) return null;
            const b = generatePopulationBins(d);
            const ys = plotX.map(x => {{
                const z = (x - b.mean) / b.sd;
                return Math.exp(-0.5 * z * z) / (b.sd * Math.sqrt(2 * Math.PI));
            }});
            const total = ys.reduce((a, c) => a + c, 0) || 1;
            return {{
                x: plotX,
                y: ys.map(p => p / total),
                type: 'scatter',
                mode: 'lines',
                name: label,
                yaxis: 'y2',
                line: {{ color: color, width: 1.5, dash: 'dot' }},
                opacity: 0.9
            }};
        }};

        const overlayTraces = [];
        const isMale = (d) => d.sex === 'M' || d.sex === 'male';
        const isFemale = (d) => d.sex === 'F' || d.sex === 'female';

        // Sex selection boxes (Male vs Female)
        const maleDist = dists.find(d => isMale(d) && d.age_band === 'all') || dists.find(d => isMale(d));
        const femaleDist = dists.find(d => isFemale(d) && d.age_band === 'all') || dists.find(d => isFemale(d));
        const maleT = buildOverlayTrace(maleDist, 'Male Distribution', '#f472b6');
        const femaleT = buildOverlayTrace(femaleDist, 'Female Distribution', '#a78bfa');
        if (maleT) overlayTraces.push(maleT);
        if (femaleT) overlayTraces.push(femaleT);

        // Age-group selection boxes
        const ageColors = {{ '20-39': '#34d399', '40-59': '#fbbf24', '60+': '#fb923c' }};
        ['20-39', '40-59', '60+'].forEach(age => {{
            const ad = dists.find(d => d.sex === 'all' && d.age_band === age) || dists.find(d => d.age_band === age);
            const t = buildOverlayTrace(ad, `Age ${{age}}`, ageColors[age] || '#94a3b8');
            if (t) overlayTraces.push(t);
        }});

        // Clamp the x-axis to the range where actual data exists [dataMin, dataMax].
        // The density trace is truncated to exactly this range and renormalized
        // to integrate to 1.0, so the area under the plotted curve = 1.
        const layout = {{
            ...plotlyDarkTheme,
            xaxis: {{
                ...plotlyDarkTheme.xaxis,
                title: `${{detail.name}} (${{detail.units}})`,
                range: [dataMin, dataMax]
            }},
            yaxis: {{
                ...plotlyDarkTheme.yaxis,
                title: 'Hazard Ratio (HR)',
                rangemode: 'tozero'
            }},
            yaxis2: {{
                title: 'Population Density',
                overlaying: 'y',
                side: 'right',
                showgrid: false,
                zeroline: false,
                tickfont: {{ color: '#10b981' }},
                rangemode: 'normal',
                range: [0, Math.max(
                    ...traceDensity.y,
                    ...overlayTraces.flatMap(t => t.y || []),
                    1e-6
                ) * 1.12]
            }},
            shapes: [],
            legend: {{ orientation: 'h', y: 1.12, x: 0.1 }}
        }};

        Plotly.newPlot(plotDiv, [traceDensity, ...overlayTraces, traceHR], layout, plotlyConfig);
        setProvenance('prov-landscape', [
            hrProvenanceRow(detail, primaryCurve),
            nhanesProvenanceRow(detail),
            methodProvenanceRow('Continuous HR(x) overlaid on the NHANES empirical / fitted density. Axis limited to observed p5–p95.')
        ]);
    }}

    // --- Age/Sex selector listeners for landscape plot ---
    function setupLandscapeAgeSexListeners() {{
        const ageSelect = document.getElementById('landscape-age-select');
        const sexSelect = document.getElementById('landscape-sex-select');
        if (ageSelect) {{
            ageSelect.addEventListener('change', (e) => {{
                AppState.landscapeAge = parseInt(e.target.value, 10);
                if (AppState.selectedBiomarkerDetail) {{
                    renderLandscapePlot(AppState.selectedBiomarkerDetail);
                    runAndDisplaySimulation();
                }}
            }});
        }}
        if (sexSelect) {{
            sexSelect.addEventListener('change', (e) => {{
                AppState.landscapeSex = e.target.value;
                if (AppState.selectedBiomarkerDetail) {{
                    renderLandscapePlot(AppState.selectedBiomarkerDetail);
                    runAndDisplaySimulation();
                }}
            }});
        }}
    }}

    // --- SUBVIEW 2: OPTIMIZATION SIMULATOR ---

    function renderOptimizationSubview(detail) {{
        renderPrecalculatedScenariosTable(detail);
        runAndDisplaySimulation();
    }}

    function renderPrecalculatedScenariosTable(detail) {{
        const tbody = document.getElementById('precalc-scenarios-table-body');
        tbody.innerHTML = '';

        const evs = detail.expected_values || [];
        if (evs.length === 0) {{
            tbody.innerHTML = `<tr><td colspan="7" class="p-3 text-center text-slate-500">No precalculated models stored</td></tr>`;
            return;
        }}

        evs.forEach(ev => {{
            const tr = document.createElement('tr');
            tr.className = 'hover:bg-slate-850/60 transition cursor-pointer';
            
            const rhrPct = ((ev.relative_hazard_reduction || 0) * 100).toFixed(1);
            const delta = (ev.delta_hr || 0).toFixed(3);
            const benPct = ((ev.fraction_benefiting || 0) * 100).toFixed(0);
            const dom = ev.domain_status || 'IN_DOMAIN';
            
            let domBadge = `<span class="text-[9px] px-1.5 py-0.5 rounded font-mono bg-emerald-500/20 text-emerald-300">IN DOMAIN</span>`;
            if (dom === 'BOUNDARY_REACHED') domBadge = `<span class="text-[9px] px-1.5 py-0.5 rounded font-mono bg-amber-500/20 text-amber-300">CLAMPED</span>`;
            if (dom === 'OUT_OF_DOMAIN') domBadge = `<span class="text-[9px] px-1.5 py-0.5 rounded font-mono bg-rose-500/20 text-rose-300">OUT OF DOMAIN</span>`;

            tr.innerHTML = `
                <td class="p-2.5 font-semibold text-slate-200">${{ev.scenario_name || ev.scenario_slug}}</td>
                <td class="p-2.5 font-mono text-slate-300">${{(ev.baseline_expected_hr || 1.0).toFixed(3)}}</td>
                <td class="p-2.5 font-mono text-slate-300">${{(ev.optimized_expected_hr || 1.0).toFixed(3)}}</td>
                <td class="p-2.5 font-mono text-indigo-400 font-bold">-${{delta}}</td>
                <td class="p-2.5 font-mono text-purple-400 font-black">-${{rhrPct}}%</td>
                <td class="p-2.5 font-mono text-emerald-400">${{benPct}}%</td>
                <td class="p-2.5">${{domBadge}}</td>
            `;

            tr.addEventListener('click', () => {{
                setSimPreset(ev.scenario_slug);
            }});

            tbody.appendChild(tr);
        }});
    }}

    function setSimPreset(slug) {{
        AppState.currentSimScenarioSlug = slug;
        if (slug === 'sd_025') {{ AppState.currentSimShiftSD = 0.25; }}
        else if (slug === 'sd_050') {{ AppState.currentSimShiftSD = 0.50; }}
        else if (slug === 'sd_100') {{ AppState.currentSimShiftSD = 1.00; }}
        else if (slug === 'sd_150') {{ AppState.currentSimShiftSD = 1.50; }}
        else if (slug === 'sd_200') {{ AppState.currentSimShiftSD = 2.00; }}
        else if (slug === 'percentile_p25_to_p50') {{ AppState.currentSimShiftSD = 0.67; }}

        document.getElementById('sim-slider').value = AppState.currentSimShiftSD;
        document.getElementById('sim-slider-val').textContent = slug === 'percentile_p25_to_p50' ? 'P25 -> P50' : `${{AppState.currentSimShiftSD.toFixed(2)}} SD`;
        runAndDisplaySimulation();
    }}

    function handleSimSliderInput(val) {{
        AppState.currentSimShiftSD = parseFloat(val);
        AppState.currentSimScenarioSlug = 'custom';
        document.getElementById('sim-slider-val').textContent = `${{AppState.currentSimShiftSD.toFixed(2)}} SD`;
        runAndDisplaySimulation();
    }}

    function runAndDisplaySimulation() {{
        const b = AppState.selectedBiomarkerDetail;
        if (!b) return;

        const isPercentile = AppState.currentSimScenarioSlug === 'percentile_p25_to_p50';
        const sim = runClientSimulation(b, AppState.currentSimShiftSD, isPercentile);
        if (!sim) return;

        // Display results
        const rhrPct = (sim.relative_hazard_reduction * 100).toFixed(1);
        document.getElementById('sim-res-rhr').textContent = `-${{rhrPct}}%`;
        document.getElementById('sim-res-delta').textContent = `-${{sim.delta_hr.toFixed(3)}}`;
        
        const benPct = (sim.fraction_benefiting * 100).toFixed(0);
        const harmPct = (sim.fraction_harmed * 100).toFixed(0);
        document.getElementById('sim-res-fractions').textContent = `${{benPct}}% Benefited / ${{harmPct}}% Harmed`;

        let domBadge = `<span class="text-emerald-400">In Bounds</span>`;
        if (sim.domain_status === 'BOUNDARY_REACHED') domBadge = `<span class="text-amber-400">Boundary Clamped</span>`;
        if (sim.domain_status === 'OUT_OF_DOMAIN') domBadge = `<span class="text-rose-400">Out of Domain</span>`;
        document.getElementById('sim-res-domain').innerHTML = domBadge;
        document.getElementById('sim-res-domain-clamped').textContent = `${{(sim.fraction_out_of_domain * 100).toFixed(1)}}% Population Clamped`;

        // Render Shift Plot
        renderSimShiftPlot(b, sim);
        // Render Benefit Plot
        renderSimBenefitPlot(sim, b);
        // VOI panel shares this sim / slider state
        renderVOIPanel(b, sim);
    }}

    function renderSimShiftPlot(detail, sim) {{
        const plotDiv = document.getElementById('plot-sim-shift');
        const bins = sim.bins;

        const traceBase = {{
            x: bins.x,
            y: bins.p,
            type: 'scatter',
            mode: 'lines',
            name: 'Baseline Population Density',
            line: {{ color: 'rgba(148, 163, 184, 0.7)', width: 2 }},
            fill: 'tozeroy',
            fillcolor: 'rgba(148, 163, 184, 0.08)'
        }};

        const traceShifted = {{
            x: sim.shiftedX,
            y: bins.p,
            type: 'scatter',
            mode: 'lines',
            name: 'Shifted Optimization Density',
            line: {{ color: '#c084fc', width: 2.5 }},
            fill: 'tozeroy',
            fillcolor: 'rgba(192, 132, 252, 0.15)'
        }};

        const [baseLo, baseHi] = distributionDisplayRange(detail, bins, detail.valid_domain_min, detail.valid_domain_max);
        let shiftLo = baseLo, shiftHi = baseHi;
        if (sim.shiftedX && sim.shiftedX.length) {{
            const sMin = Math.min(...sim.shiftedX);
            const sMax = Math.max(...sim.shiftedX);
            const span = baseHi - baseLo;
            shiftLo = Math.min(baseLo, Math.max(sMin, baseLo - 0.35 * span));
            shiftHi = Math.max(baseHi, Math.min(sMax, baseHi + 0.35 * span));
        }}
        const layout = {{
            ...plotlyDarkTheme,
            margin: {{ l: 40, r: 20, t: 15, b: 35 }},
            xaxis: {{
                ...plotlyDarkTheme.xaxis,
                title: `${{detail.name}} (${{detail.units}})`,
                range: [shiftLo, shiftHi]
            }},
            yaxis: {{ ...plotlyDarkTheme.yaxis, title: 'Density' }},
            legend: {{ orientation: 'h', y: 1.18, x: 0.05 }}
        }};

        Plotly.newPlot(plotDiv, [traceBase, traceShifted], layout, plotlyConfig);
        const curve = (detail.curves || [])[0];
        setProvenance('prov-sim-shift', [
            hrProvenanceRow(detail, curve),
            nhanesProvenanceRow(detail),
            methodProvenanceRow('Counterfactual population shift of the NHANES density toward the favorable direction; not a causal intervention estimate.')
        ]);
    }}

    function renderSimBenefitPlot(sim, detail) {{
        const plotDiv = document.getElementById('plot-sim-benefit');
        const benefits = sim.individualBenefits.map(b => b.benefit);
        const weights = sim.individualBenefits.map(b => b.weight);

        const trace = {{
            x: benefits,
            y: weights,
            type: 'scatter',
            mode: 'lines',
            name: 'Individual Benefit $\\Delta HR_i$',
            line: {{ color: '#38bdf8', width: 2.5 }},
            fill: 'tozeroy',
            fillcolor: 'rgba(56, 189, 248, 0.15)'
        }};

        const layout = {{
            ...plotlyDarkTheme,
            margin: {{ l: 40, r: 20, t: 15, b: 35 }},
            xaxis: {{ ...plotlyDarkTheme.xaxis, title: 'Individual Hazard Reduction (ΔHR_i)' }},
            yaxis: {{ ...plotlyDarkTheme.yaxis, title: 'Population Fraction' }},
            shapes: [
                {{
                    type: 'line',
                    x0: 0,
                    x1: 0,
                    y0: 0,
                    y1: Math.max(...weights) * 1.1,
                    line: {{ color: 'rgba(239, 68, 68, 0.5)', width: 1.5, dash: 'dash' }}
                }}
            ]
        }};

        Plotly.newPlot(plotDiv, [trace], layout, plotlyConfig);
        if (detail) {{
            const curve = (detail.curves || [])[0];
            setProvenance('prov-sim-benefit', [
                hrProvenanceRow(detail, curve),
                nhanesProvenanceRow(detail),
                methodProvenanceRow('Individual ΔHR_i = HR(x_i) − HR(x_i shifted), weighted by the NHANES density.')
            ]);
        }}
    }}

    // --- VIEW 2: OPTIMIZATION LEADERBOARD ---

    function renderOptimizationLeaderboard() {{
        const scenarioSlug = document.getElementById('leaderboard-scenario-select').value || 'sd_100';
        const plotDiv = document.getElementById('plot-leaderboard');
        const tableContainer = document.getElementById('leaderboard-table-container');

        // Extract leaderboard data across all biomarkers for this scenario
        const isPerc = scenarioSlug === 'percentile_p25_to_p50';
        let shift = 1.0;
        if (scenarioSlug === 'sd_025') shift = 0.25;
        else if (scenarioSlug === 'sd_050') shift = 0.50;
        else if (scenarioSlug === 'sd_150') shift = 1.50;
        else if (scenarioSlug === 'sd_200') shift = 2.00;
        else if (scenarioSlug === 'sd_100') shift = 1.00;

        const items = [];
        AppState.biomarkers.forEach(b => {{
            const ev = (b.expected_values || []).find(e => e.scenario_slug === scenarioSlug);
            const sim = runClientSimulation(b, shift, isPerc);
            if (!ev && !sim) return;
            const voi = sim ? computeVOIFromSim(b, sim, 50, 'all', shift, AppState.voiCIntDaly, AppState.voiLambda) : null;
            const popKey = [scenarioSlug, AppState.voiLambda, AppState.voiCIntDaly].join('|');
            if (!b._popVoiCache || b._popVoiCache.key !== popKey) {{
                b._popVoiCache = {{ key: popKey, val: computePopulationVOI(b, shift, isPerc, AppState.voiLambda, AppState.voiCIntDaly) }};
            }}
            const pop = b._popVoiCache.val;
            items.push({{
                biomarker: b,
                rhr: (ev && ev.relative_hazard_reduction != null) ? ev.relative_hazard_reduction : (sim ? sim.relative_hazard_reduction : 0),
                delta_hr: (ev && ev.delta_hr != null) ? ev.delta_hr : (sim ? sim.delta_hr : 0),
                baseline_expected_hr: (ev && ev.baseline_expected_hr != null) ? ev.baseline_expected_hr : (sim ? sim.baseline_expected_hr : 1),
                optimized_expected_hr: (ev && ev.optimized_expected_hr != null) ? ev.optimized_expected_hr : (sim ? sim.optimized_expected_hr : 1),
                fraction_benefiting: (ev && ev.fraction_benefiting != null) ? ev.fraction_benefiting : (sim ? sim.fraction_benefiting : 0),
                domain_status: (ev && ev.domain_status) ? ev.domain_status : (sim ? sim.domain_status : 'IN_DOMAIN'),
                ehiv: voi ? voi.ehiv : 0,
                popVoi: pop ? pop.totalVoi : 0,
                popEhiv: pop ? pop.totalEhiv : 0
            }});
        }});

        const sortBy = AppState.leaderboardSort || 'rhr';
        if (sortBy === 'ehiv') items.sort((a, b) => b.ehiv - a.ehiv);
        else if (sortBy === 'pop_voi') items.sort((a, b) => b.popVoi - a.popVoi);
        else items.sort((a, b) => b.rhr - a.rhr);

        // Render Bar Chart (Top 15) — axis follows the active sort
        const top15 = items.slice(0, 15).reverse();
        const barX = sortBy === 'ehiv' ? top15.map(i => i.ehiv)
            : sortBy === 'pop_voi' ? top15.map(i => i.popVoi)
            : top15.map(i => i.rhr * 100);
        const barTitle = sortBy === 'ehiv' ? 'EHIV ($ / person)'
            : sortBy === 'pop_voi' ? 'Population VOI (DALYs)'
            : 'Relative Expected Hazard Reduction (RHR %)';
        const trace = {{
            x: barX,
            y: top15.map(i => i.biomarker.name),
            type: 'bar',
            orientation: 'h',
            marker: {{
                color: top15.map(i => (sortBy === 'rhr' ? (i.rhr > 0.15) : (i.ehiv > 0)) ? '#22d3ee' : '#6366f1'),
                line: {{ color: '#67e8f9', width: 1 }}
            }}
        }};

        const layout = {{
            ...plotlyDarkTheme,
            margin: {{ l: 180, r: 30, t: 20, b: 40 }},
            xaxis: {{ ...plotlyDarkTheme.xaxis, title: barTitle }},
            yaxis: {{ ...plotlyDarkTheme.yaxis, automargin: true }}
        }};

        Plotly.newPlot(plotDiv, [trace], layout, plotlyConfig);
        const lt = (AppState.voiConfig && AppState.voiConfig.lifeTableSource) || 'CDC NVSS US Life Tables, 2022';
        setProvenance('prov-leaderboard', [
            {{
                label: 'RHR',
                html: 'Per-biomarker 1-SD (or selected-scenario) relative hazard reduction from the continuous HR function integrated over NHANES. Default sort is RHR.'
            }},
            {{
                label: 'EHIV / VOI',
                html: 'Dollar-valued information using ' + escapeHtml(lt) + '; test prices from findlabtest.com where mapped. λ is a policy willingness-to-pay, not an empirical estimate.'
            }},
            methodProvenanceRow('Derived analytics — not a new primary study. Click a row for the marker-level sources.')
        ]);

        // Render Leaderboard Table
        let tableHTML = `
            <table class="w-full text-left text-xs">
                <thead class="bg-slate-950 text-slate-400 uppercase text-[10px] border-b border-slate-800">
                    <tr>
                        <th class="p-3">Rank</th>
                        <th class="p-3">Biomarker</th>
                        <th class="p-3">Category</th>
                        <th class="p-3">Causal Tier</th>
                        <th class="p-3">Baseline E[HR₀]</th>
                        <th class="p-3">Optimized E[HR_δ]</th>
                        <th class="p-3">&Delta; HR</th>
                        <th class="p-3 text-purple-400 font-bold">Rel. Reduction ($RHR$)</th>
                        <th class="p-3 text-cyan-400 font-bold">EHIV ($/person)</th>
                        <th class="p-3 text-cyan-400 font-bold">Population VOI (DALYs)</th>
                        <th class="p-3">% Benefiting</th>
                        <th class="p-3">Domain Status</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-slate-850">
        `;

        items.forEach((item, idx) => {{
            const b = item.biomarker;
            const rhrPct = (item.rhr * 100).toFixed(1);
            const causalBadge = getCausalBadgeHTML(b.causal_status);
            const benPct = (item.fraction_benefiting * 100).toFixed(0);

            let domBadge = `<span class="text-[9px] px-1.5 py-0.5 rounded font-mono bg-emerald-500/20 text-emerald-300">IN DOMAIN</span>`;
            if (item.domain_status === 'BOUNDARY_REACHED') domBadge = `<span class="text-[9px] px-1.5 py-0.5 rounded font-mono bg-amber-500/20 text-amber-300">CLAMPED</span>`;
            if (item.domain_status === 'OUT_OF_DOMAIN') domBadge = `<span class="text-[9px] px-1.5 py-0.5 rounded font-mono bg-rose-500/20 text-rose-300">OUT OF DOMAIN</span>`;

            tableHTML += `
                <tr class="hover:bg-slate-850/70 transition cursor-pointer" onclick="selectBiomarkerAndNavigate('${{b.slug}}')">
                    <td class="p-3 font-mono font-bold text-slate-400">#${{idx + 1}}</td>
                    <td class="p-3 font-bold text-white">${{b.name}}</td>
                    <td class="p-3 text-slate-300">${{b.category}}</td>
                    <td class="p-3">${{causalBadge}}</td>
                    <td class="p-3 font-mono text-slate-300">${{item.baseline_expected_hr.toFixed(3)}}</td>
                    <td class="p-3 font-mono text-slate-300">${{item.optimized_expected_hr.toFixed(3)}}</td>
                    <td class="p-3 font-mono text-indigo-400 font-bold">-${{item.delta_hr.toFixed(3)}}</td>
                    <td class="p-3 font-mono text-purple-400 font-black">-${{rhrPct}}%</td>
                    <td class="p-3 font-mono ${{item.ehiv > 0 ? 'text-emerald-400' : 'text-rose-400'}}">${{formatUSD(item.ehiv)}}</td>
                    <td class="p-3 font-mono text-cyan-300">${{formatDalys(item.popVoi)}}</td>
                    <td class="p-3 font-mono text-emerald-400">${{benPct}}%</td>
                    <td class="p-3">${{domBadge}}</td>
                </tr>
            `;
        }});

        tableHTML += `</tbody></table>`;
        tableContainer.innerHTML = tableHTML;
    }}

    function selectBiomarkerAndNavigate(slug) {{
        navigateTab('biomarkers');
        selectBiomarker(slug);
        document.getElementById('subtab-optimization').click();
    }}

    // --- SUBVIEW 3: FOREST PLOT ---

    function renderForestPlot(detail) {{
        const plotDiv = document.getElementById('plot-forest');
        const assocs = detail.associations || [];

        if (assocs.length === 0) {{
            plotDiv.innerHTML = `<div class="p-8 text-center text-xs text-slate-500">No Mortality Associations Available</div>`;
            setProvenance('prov-forest', [{{ label: 'Estimates', html: 'No published mortality associations are linked to this marker.' }}]);
            return;
        }}

        const labels = assocs.map(a => {{
            const cohort = a.cohort_description || a.population_type || 'Cohort';
            const yr = (a.source && a.source.year) ? ` ${{a.source.year}}` : '';
            return `${{cohort}}${{yr}}`;
        }}).reverse();
        const hrs = assocs.map(a => a.hazard_ratio).reverse();
        const ciLows = assocs.map(a => a.ci_lower).reverse();
        const ciHighs = assocs.map(a => a.ci_upper).reverse();

        const errors = hrs.map((hr, idx) => {{
            return ciHighs[idx] != null ? (ciHighs[idx] - hr) : 0;
        }});
        const errorsMinus = hrs.map((hr, idx) => {{
            return ciLows[idx] != null ? (hr - ciLows[idx]) : 0;
        }});

        const trace = {{
            x: hrs,
            y: labels,
            type: 'scatter',
            mode: 'markers',
            marker: {{ color: '#f43f5e', size: 8, symbol: 'square' }},
            error_x: {{
                type: 'data',
                symmetric: false,
                array: errors,
                arrayminus: errorsMinus,
                color: '#f43f5e',
                thickness: 1.5,
                width: 4
            }}
        }};

        const layout = {{
            ...plotlyDarkTheme,
            margin: {{ l: 200, r: 30, t: 20, b: 40 }},
            xaxis: {{
                ...plotlyDarkTheme.xaxis,
                title: 'Hazard Ratio (95% CI)',
                type: 'log',
                tickvals: [0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0]
            }},
            yaxis: {{ ...plotlyDarkTheme.yaxis, automargin: true }},
            shapes: [
                {{
                    type: 'line',
                    x0: 1.0,
                    x1: 1.0,
                    y0: -0.5,
                    y1: labels.length - 0.5,
                    line: {{ color: 'rgba(255, 255, 255, 0.3)', width: 1, dash: 'dash' }}
                }}
            ]
        }};

        Plotly.newPlot(plotDiv, [trace], layout, plotlyConfig);

        const uniqueSources = [];
        const seen = new Set();
        assocs.forEach(a => {{
            const key = (a.source && (a.source.pmid || a.source.doi || a.source.citation)) || a.source_id;
            if (key && !seen.has(key)) {{
                seen.add(key);
                uniqueSources.push(a.source);
            }}
        }});
        setProvenance('prov-forest', [
            {{
                label: 'Estimates',
                html: 'Study-level all-cause (or cause-specific) HRs with 95% CIs. Not the continuous HR(x) spline on the Fitness Landscape tab.'
            }},
            ...uniqueSources.slice(0, 6).map(src => ({{
                label: 'Source',
                html: sourceShortHtml(src)
            }}))
        ]);

        const tableEl = document.getElementById('forest-table-container');
        if (tableEl) {{
            let html = `<table class="w-full text-left text-xs"><thead class="bg-slate-950 text-slate-400 uppercase text-[10px] border-b border-slate-800"><tr>
                <th class="p-2.5">Cohort</th><th class="p-2.5">HR type</th><th class="p-2.5">HR (95% CI)</th><th class="p-2.5">Source</th>
            </tr></thead><tbody class="divide-y divide-slate-800">`;
            assocs.forEach(a => {{
                const ci = (a.ci_lower != null && a.ci_upper != null) ? `${{a.ci_lower.toFixed(2)}}–${{a.ci_upper.toFixed(2)}}` : '—';
                html += `<tr class="hover:bg-slate-850/60">
                    <td class="p-2.5 text-slate-200">${{escapeHtml(a.cohort_description || '—')}}</td>
                    <td class="p-2.5 font-mono text-slate-400">${{escapeHtml(a.hr_type || '')}}</td>
                    <td class="p-2.5 font-mono text-rose-300">${{(a.hazard_ratio || 0).toFixed(2)}} (${{ci}})</td>
                    <td class="p-2.5">${{sourceShortHtml(a.source, '—')}}</td>
                </tr>`;
            }});
            html += '</tbody></table>';
            tableEl.innerHTML = html;
        }}
    }}

    // --- SUBVIEW 4: INTERVENTIONS ---

    function renderInterventionsView(detail) {{
        const favContainer = document.getElementById('favorable-interventions-list');
        const unfavContainer = document.getElementById('unfavorable-interventions-list');
        
        favContainer.innerHTML = '';
        unfavContainer.innerHTML = '';

        const itvs = detail.interventions || [];
        const favorable = itvs.filter(i => i.direction === 'favorable' || i.direction === 'beneficial');
        const unfavorable = itvs.filter(i => i.direction === 'unfavorable' || i.direction === 'adverse');

        if (favorable.length === 0) {{
            favContainer.innerHTML = `<div class="text-xs text-slate-500">No favorable interventions recorded</div>`;
        }} else {{
            favorable.forEach(i => {{
                favContainer.appendChild(createInterventionCard(i, 'emerald'));
            }});
        }}

        if (unfavorable.length === 0) {{
            unfavContainer.innerHTML = `<div class="text-xs text-slate-500">No adverse factors recorded</div>`;
        }} else {{
            unfavorable.forEach(i => {{
                unfavContainer.appendChild(createInterventionCard(i, 'rose'));
            }});
        }}
    }}

    function createInterventionCard(i, color) {{
        const card = document.createElement('div');
        card.className = `p-3 bg-slate-950/70 border border-slate-800 rounded-lg space-y-1.5`;
        card.innerHTML = `
            <div class="flex items-center justify-between">
                <span class="text-xs font-bold text-white">${{i.name}}</span>
                <span class="text-[10px] font-mono px-1.5 py-0.5 rounded bg-${{color}}-500/20 text-${{color}}-300 border border-${{color}}-500/30">
                    ${{i.modality || 'Lifestyle'}}
                </span>
            </div>
            <p class="text-[11px] text-slate-300">${{i.description || ''}}</p>
            <div class="text-[10px] text-slate-500 flex items-center justify-between pt-1">
                <span>Expected Impact: <strong class="text-slate-300 font-mono">${{i.quantified_effect || i.expected_effect || 'Variable'}}</strong></span>
                <span>Evidence: <strong class="text-slate-300">${{i.evidence_strength || i.evidence_level || 'Moderate'}}</strong></span>
            </div>
            <div class="text-[10px] text-slate-500 pt-1">${{sourceShortHtml(i.source, '')}}</div>
        `;
        return card;
    }}

    // --- SUBVIEW 5: DEMOGRAPHICS ---

    function renderDemographicsPlot(detail) {{
        const plotDiv = document.getElementById('plot-demographics');
        const dists = detail.population_distributions || [];
        const stratified = dists.filter(d => d.age_band !== 'all' || d.sex !== 'all');

        if (stratified.length === 0) {{
            plotDiv.innerHTML = `<div class="p-8 text-center text-xs text-slate-500">Demographic Stratifications Unavailable</div>`;
            return;
        }}

        const labels = stratified.map(d => `${{d.sex === 'all' ? 'Overall' : (d.sex === 'male' ? 'Male' : 'Female')}} (${{d.age_band}}y)`);
        const medians = stratified.map(d => d.p50);
        const p25s = stratified.map(d => d.p25);
        const p75s = stratified.map(d => d.p75);

        const trace = {{
            x: labels,
            y: medians,
            type: 'bar',
            name: 'Median (P50)',
            marker: {{ color: '#10b981' }}
        }};

        const layout = {{
            ...plotlyDarkTheme,
            xaxis: {{ ...plotlyDarkTheme.xaxis, automargin: true }},
            yaxis: {{ ...plotlyDarkTheme.yaxis, title: `${{detail.name}} (${{detail.units}})` }}
        }};

        Plotly.newPlot(plotDiv, [trace], layout, plotlyConfig);
        setProvenance('prov-demographics', [
            nhanesProvenanceRow(detail),
            methodProvenanceRow('Age- and sex-stratified NHANES medians (P50). Error bars omitted; P25/P75 are in the table when present.')
        ]);
    }}

    // --- VIEW 3: COMPARE VIEW ---

    function setupCompareListeners() {{
        document.getElementById('btn-compare-preset-all').addEventListener('click', () => {{
            AppState.compareSlugs = new Set(['high_sensitivity_crp', 'hba1c', 'estimated_gfr_ckd_epi', 'serum_albumin', 'rdw', 'resting_heart_rate']);
            renderCompareView();
        }});

        document.getElementById('btn-compare-clear').addEventListener('click', () => {{
            AppState.compareSlugs.clear();
            renderCompareView();
        }});
    }}

    function renderCompareView() {{
        const chipsContainer = document.getElementById('compare-selection-chips');
        chipsContainer.innerHTML = '';

        AppState.biomarkers.forEach(b => {{
            const isSelected = AppState.compareSlugs.has(b.slug);
            const chip = document.createElement('button');
            chip.className = `px-2.5 py-1 rounded-full text-xs font-semibold transition ${{
                isSelected 
                    ? 'bg-indigo-600 text-white shadow' 
                    : 'bg-slate-950 text-slate-400 hover:text-slate-200 border border-slate-800'
            }}`;
            chip.innerHTML = `${{isSelected ? '<i class="fa-solid fa-check mr-1 text-[10px]"></i>' : ''}}${{b.name}}`;
            chip.addEventListener('click', () => {{
                if (isSelected) AppState.compareSlugs.delete(b.slug);
                else AppState.compareSlugs.add(b.slug);
                renderCompareView();
            }});
            chipsContainer.appendChild(chip);
        }});

        const selectedBiomarkers = AppState.biomarkers.filter(b => AppState.compareSlugs.has(b.slug));
        renderCompareForestPlot(selectedBiomarkers);
        renderCompareTable(selectedBiomarkers);
    }}

    function renderCompareForestPlot(biomarkers) {{
        const plotDiv = document.getElementById('plot-compare-forest');
        if (biomarkers.length === 0) {{
            plotDiv.innerHTML = `<div class="p-8 text-center text-xs text-slate-500">Select biomarkers above to compare</div>`;
            return;
        }}

        const labels = biomarkers.map(b => b.name);
        const hrs = biomarkers.map(b => b.max_hazard_ratio || 1.0);

        const trace = {{
            x: hrs,
            y: labels,
            type: 'scatter',
            mode: 'markers',
            marker: {{ color: '#a855f7', size: 10, symbol: 'diamond' }}
        }};

        const layout = {{
            ...plotlyDarkTheme,
            margin: {{ l: 200, r: 30, t: 20, b: 40 }},
            xaxis: {{ ...plotlyDarkTheme.xaxis, title: 'Peak Observed Mortality Hazard Ratio (HR)' }},
            yaxis: {{ ...plotlyDarkTheme.yaxis, automargin: true }}
        }};

        Plotly.newPlot(plotDiv, [trace], layout, plotlyConfig);
        const srcBits = biomarkers.map(b => {{
            const a = (b.associations || []).find(x => x.source) || (b.associations || [])[0];
            if (!a) return null;
            return {{ label: b.name, html: sourceShortHtml(a.source, a.cohort_description || 'unpublished association') }};
        }}).filter(Boolean);
        setProvenance('prov-compare', [
            {{ label: 'Metric', html: 'Peak observed HR from the mortality-association registry for each selected marker (not the continuous spline).' }},
            ...srcBits.slice(0, 8)
        ]);
    }}

    function renderCompareTable(biomarkers) {{
        const container = document.getElementById('compare-table-container');
        if (biomarkers.length === 0) {{
            container.innerHTML = `<div class="p-6 text-center text-xs text-slate-500">No biomarkers selected for comparison</div>`;
            return;
        }}

        let tableHTML = `
            <table class="w-full text-left text-xs">
                <thead class="bg-slate-950 text-slate-400 uppercase text-[10px] border-b border-slate-800">
                    <tr>
                        <th class="p-3">Biomarker</th>
                        <th class="p-3">Category</th>
                        <th class="p-3">Units</th>
                        <th class="p-3">Population Median</th>
                        <th class="p-3">Peak HR</th>
                        <th class="p-3 text-purple-400 font-bold">1.0-SD Potential</th>
                        <th class="p-3 text-cyan-400 font-bold">EHIV</th>
                        <th class="p-3">Causal Tier</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-slate-850">
        `;

        biomarkers.forEach(b => {{
            const rhrPct = ((b.rel_hazard_red_100 || 0) * 100).toFixed(1);
            const causalBadge = getCausalBadgeHTML(b.causal_status);
            const sim = runClientSimulation(b, 1.0, false);
            const voi = sim ? computeVOIFromSim(b, sim, AppState.landscapeAge || 50, AppState.landscapeSex || 'all', 1.0, AppState.voiCIntDaly, AppState.voiLambda) : null;
            const ehivTxt = voi ? formatUSD(voi.ehiv) : '--';

            tableHTML += `
                <tr class="hover:bg-slate-850/60 transition cursor-pointer" onclick="selectBiomarkerAndNavigate('${{b.slug}}')">
                    <td class="p-3 font-bold text-white">${{b.name}}</td>
                    <td class="p-3 text-slate-300">${{b.category}}</td>
                    <td class="p-3 font-mono text-slate-400">${{b.units}}</td>
                    <td class="p-3 font-mono text-slate-200">${{b.population_median ?? '--'}}</td>
                    <td class="p-3 font-mono text-rose-400 font-bold">${{b.max_hazard_ratio ? b.max_hazard_ratio.toFixed(2) : '--'}}</td>
                    <td class="p-3 font-mono text-purple-400 font-black">-${{rhrPct}}%</td>
                    <td class="p-3 font-mono ${{voi && voi.ehiv > 0 ? 'text-emerald-400' : 'text-rose-400'}}">${{ehivTxt}}</td>
                    <td class="p-3">${{causalBadge}}</td>
                </tr>
            `;
        }});

        tableHTML += `</tbody></table>`;
        container.innerHTML = tableHTML;
    }}

    // --- VIEW 4: SOURCES LIST ---

    function renderSourcesList() {{
        const container = document.getElementById('sources-list-container');
        container.innerHTML = '';

        const query = AppState.sourceSearch || '';
        const filtered = AppState.sources.filter(s => {{
            return !query || 
                (s.title && s.title.toLowerCase().includes(query)) ||
                (s.authors && s.authors.toLowerCase().includes(query)) ||
                (s.journal && s.journal.toLowerCase().includes(query)) ||
                (s.citation && s.citation.toLowerCase().includes(query)) ||
                (s.pmid && s.pmid.includes(query));
        }});

        if (filtered.length === 0) {{
            container.innerHTML = `<div class="col-span-2 p-8 text-center text-xs text-slate-500">No matching literature references found</div>`;
            return;
        }}

        filtered.forEach(s => {{
            const card = document.createElement('div');
            card.className = 'bg-slate-900 border border-slate-800 p-4 rounded-xl space-y-2 shadow-sm flex flex-col justify-between';
            
            const doiLink = s.doi ? `<a href="https://doi.org/${{s.doi}}" target="_blank" class="text-indigo-400 hover:underline font-mono text-[10px]">DOI: ${{s.doi}} <i class="fa-solid fa-arrow-up-right-from-square text-[8px]"></i></a>` : '';
            const pmidLink = s.pmid ? `<a href="https://pubmed.ncbi.nlm.nih.gov/${{s.pmid}}" target="_blank" class="text-indigo-400 hover:underline font-mono text-[10px]">PMID: ${{s.pmid}} <i class="fa-solid fa-arrow-up-right-from-square text-[8px]"></i></a>` : '';

            card.innerHTML = `
                <div class="space-y-1.5">
                    <div class="flex items-start justify-between gap-2">
                        <span class="text-xs font-bold text-white leading-snug">${{s.title || s.citation}}</span>
                        <span class="text-[9px] px-1.5 py-0.5 rounded bg-slate-800 font-mono text-slate-300 border border-slate-700 shrink-0">
                            ${{s.year || ''}}
                        </span>
                    </div>
                    <p class="text-[11px] text-slate-400">${{s.authors || ''}}</p>
                    <div class="text-[11px] text-indigo-300 font-medium">${{s.journal || ''}}</div>
                </div>
                <div class="flex items-center justify-between border-t border-slate-800/80 pt-2 text-[10px] text-slate-500">
                    <span class="font-mono">${{s.study_design || 'Cohort Study'}}</span>
                    <div class="flex items-center gap-3">
                        ${{pmidLink}}
                        ${{doiLink}}
                    </div>
                </div>
            `;
            container.appendChild(card);
        }});
    }}

    // --- CHRONIC DISEASE INTELLIGENCE LOGIC & RENDERING ---

    function getAlterationBadgeClass(typeCode) {{
        switch (typeCode) {{
            case 'A': return 'badge-type-a';
            case 'B': return 'badge-type-b';
            case 'C': return 'badge-type-c';
            case 'D': return 'badge-type-d';
            case 'E': return 'badge-type-e';
            default: return 'bg-slate-800 text-slate-300 border border-slate-700';
        }}
    }}

    function getDirectionIcon(direction) {{
        if (!direction) return '';
        const dir = direction.toLowerCase();
        if (dir.includes('elevat') || dir.includes('increas') || dir.includes('high') || dir.includes('up')) {{
            return '<span class="direction-elevated font-mono font-bold text-xs"><i class="fa-solid fa-arrow-trend-up mr-0.5"></i> Elevated</span>';
        }} else if (dir.includes('reduc') || dir.includes('decreas') || dir.includes('low') || dir.includes('down')) {{
            return '<span class="direction-reduced font-mono font-bold text-xs"><i class="fa-solid fa-arrow-trend-down mr-0.5"></i> Reduced</span>';
        }}
        return `<span class="text-slate-400 font-mono text-xs">${{direction}}</span>`;
    }}

    function getEvidenceBadge(evidence) {{
        if (!evidence) return '';
        const ev = evidence.toLowerCase();
        if (ev.includes('definitive') || ev.includes('diagnostic') || ev.includes('gold')) {{
            return '<span class="evidence-definitive px-1.5 py-0.5 rounded text-[9px] font-mono border">Definitive</span>';
        }} else if (ev.includes('strong') || ev.includes('established')) {{
            return '<span class="evidence-strong px-1.5 py-0.5 rounded text-[9px] font-mono border">Strong Evidence</span>';
        }}
        return `<span class="px-1.5 py-0.5 rounded text-[9px] font-mono bg-slate-800 text-slate-400 border border-slate-700">${{evidence}}</span>`;
    }}

    function renderDiseasesView() {{
        const container = document.getElementById('disease-cards-container');
        if (!container) return;

        let filtered = AppState.diseases.filter(d => {{
            const query = AppState.diseaseFilters.search;
            const matchesSearch = !query ||
                d.name.toLowerCase().includes(query) ||
                (d.slug && d.slug.toLowerCase().includes(query)) ||
                (d.category && d.category.toLowerCase().includes(query)) ||
                (d.primary_organ_system && d.primary_organ_system.toLowerCase().includes(query)) ||
                (d.icd10_code && d.icd10_code.toLowerCase().includes(query)) ||
                (d.mesh_id && d.mesh_id.toLowerCase().includes(query));

            const matchesCategory = !AppState.diseaseFilters.category || d.category === AppState.diseaseFilters.category;
            return matchesSearch && matchesCategory;
        }});

        const sortBy = AppState.diseaseFilters.sortBy;
        if (sortBy === 'name') {{
            filtered.sort((a, b) => a.name.localeCompare(b.name));
        }} else if (sortBy === 'dalys') {{
            filtered.sort((a, b) => (b.us_dalys || 0) - (a.us_dalys || 0));
        }} else if (sortBy === 'alterations') {{
            filtered.sort((a, b) => (b.alterations_count || (b.alterations ? b.alterations.length : 0)) - (a.alterations_count || (a.alterations ? a.alterations.length : 0)));
        }}

        if (filtered.length === 0) {{
            container.innerHTML = `<div class="col-span-3 p-12 text-center text-xs text-slate-500">No diseases matching search or category filters</div>`;
            return;
        }}

        container.innerHTML = '';
        filtered.forEach(d => {{
            const card = document.createElement('div');
            card.className = 'disease-card bg-slate-900 border border-slate-800 p-4 rounded-xl space-y-3 cursor-pointer shadow-sm hover:border-slate-700 flex flex-col justify-between';

            const alts = d.alterations || [];
            const typeACount = alts.filter(a => a.alteration_type_code === 'A').length;
            const typeBCount = alts.filter(a => a.alteration_type_code === 'B').length;
            const typeCCount = alts.filter(a => a.alteration_type_code === 'C').length;
            const typeDCount = alts.filter(a => a.alteration_type_code === 'D').length;
            const typeECount = alts.filter(a => a.alteration_type_code === 'E').length;

            const icd10Badge = d.icd10_code ? `<span class="px-1.5 py-0.5 rounded text-[10px] font-mono bg-slate-800 text-slate-300 border border-slate-700">${{d.icd10_code}}</span>` : '';
            const dalysDisplay = d.us_dalys != null ? `${{d.us_dalys.toLocaleString()}} DALYs` : 'DALYs N/A';

            card.innerHTML = `
                <div class="space-y-2">
                    <div class="flex items-start justify-between gap-2">
                        <div>
                            <h3 class="font-bold text-sm text-white leading-snug group-hover:text-rose-400 transition">${{d.name}}</h3>
                            <div class="text-[11px] text-slate-400 mt-0.5 flex items-center gap-1.5 flex-wrap">
                                <span class="text-rose-300 font-medium">${{d.category}}</span>
                                <span>&bull;</span>
                                <span>${{d.primary_organ_system || 'Multi-system'}}</span>
                            </div>
                        </div>
                        ${{icd10Badge}}
                    </div>
                    <p class="text-[11px] text-slate-400 line-clamp-2 leading-relaxed">${{d.description || 'Chronic pathology with documented multi-scale biological alterations.'}}</p>
                </div>

                <div class="space-y-2 pt-2 border-t border-slate-800/80 text-[10px]">
                    <div class="flex items-center justify-between text-slate-400">
                        <span>US Burden: <strong class="text-rose-400 font-mono">${{dalysDisplay}}</strong></span>
                        <span>Total Alterations: <strong class="text-white font-mono">${{alts.length}}</strong></span>
                    </div>

                    <!-- Multi-scale pill breakdown -->
                    <div class="flex items-center gap-1 flex-wrap">
                        ${{typeBCount > 0 ? `<span class="badge-type-b px-1.5 py-0.5 rounded font-mono text-[9px]">B: ${{typeBCount}}</span>` : ''}}
                        ${{typeCCount > 0 ? `<span class="badge-type-c px-1.5 py-0.5 rounded font-mono text-[9px]">C: ${{typeCCount}}</span>` : ''}}
                        ${{typeDCount > 0 ? `<span class="badge-type-d px-1.5 py-0.5 rounded font-mono text-[9px]">D: ${{typeDCount}}</span>` : ''}}
                        ${{typeECount > 0 ? `<span class="badge-type-e px-1.5 py-0.5 rounded font-mono text-[9px]">E: ${{typeECount}}</span>` : ''}}
                        ${{typeACount > 0 ? `<span class="badge-type-a px-1.5 py-0.5 rounded font-mono text-[9px]">A: ${{typeACount}}</span>` : ''}}
                    </div>
                </div>
            `;

            card.addEventListener('click', () => {{
                openDiseaseModal(d);
            }});

            container.appendChild(card);
        }});
    }}

    function openDiseaseModal(disease) {{
        AppState.selectedDisease = disease;
        AppState.activeDiseaseModalTab = 'all';

        const modal = document.getElementById('disease-modal');
        document.getElementById('modal-disease-name').textContent = disease.name;
        document.getElementById('modal-disease-category').textContent = disease.category;
        document.getElementById('modal-disease-icd10').textContent = disease.icd10_code || disease.slug;
        document.getElementById('modal-disease-desc').textContent = disease.description || 'No detailed description available.';
        document.getElementById('modal-disease-organ').textContent = disease.primary_organ_system || 'Systemic';
        document.getElementById('modal-disease-dalys').textContent = disease.us_dalys != null ? `${{disease.us_dalys.toLocaleString()}} DALYs/yr` : 'Not calibrated';

        const repurposLink = document.getElementById('modal-disease-repurpos-link');
        if (repurposLink) {{
            repurposLink.href = `https://research.opensourcemed.info/disease-intelligence/${{disease.slug}}.html`;
        }}

        const alts = disease.alterations || [];
        document.getElementById('modal-disease-alt-count').textContent = alts.length;

        // Update Tab Counts
        document.getElementById('modal-count-all').textContent = alts.length;
        document.getElementById('modal-count-a').textContent = alts.filter(a => a.alteration_type_code === 'A').length;
        document.getElementById('modal-count-b').textContent = alts.filter(a => a.alteration_type_code === 'B').length;
        document.getElementById('modal-count-c').textContent = alts.filter(a => a.alteration_type_code === 'C').length;
        document.getElementById('modal-count-d').textContent = alts.filter(a => a.alteration_type_code === 'D').length;
        document.getElementById('modal-count-e').textContent = alts.filter(a => a.alteration_type_code === 'E').length;

        switchModalTab('all');
        modal.classList.remove('hidden');
    }}

    function closeDiseaseModal() {{
        const modal = document.getElementById('disease-modal');
        if (modal) modal.classList.add('hidden');
    }}

    function switchModalTab(tabCode) {{
        AppState.activeDiseaseModalTab = tabCode;

        document.querySelectorAll('.modal-tab-btn').forEach(btn => {{
            const t = btn.getAttribute('data-modal-tab');
            if (t === tabCode) {{
                btn.className = 'modal-tab-btn active px-3 py-2 text-xs font-semibold rounded-t-lg bg-indigo-600 text-white transition flex items-center gap-1.5';
            }} else {{
                btn.className = 'modal-tab-btn px-3 py-2 text-xs font-semibold rounded-t-lg text-slate-400 hover:text-white hover:bg-slate-800/50 transition flex items-center gap-1.5';
            }}
        }});

        renderModalAlterationsList();
    }}

    function renderModalAlterationsList() {{
        const container = document.getElementById('disease-modal-alterations-list');
        const disease = AppState.selectedDisease;
        if (!container || !disease) return;

        const alts = disease.alterations || [];
        const filtered = AppState.activeDiseaseModalTab === 'all'
            ? alts
            : alts.filter(a => a.alteration_type_code === AppState.activeDiseaseModalTab);

        if (filtered.length === 0) {{
            container.innerHTML = `<div class="p-8 text-center text-xs text-slate-500">No alterations documented under Type ${{AppState.activeDiseaseModalTab}} for this disease condition.</div>`;
            return;
        }}

        container.innerHTML = '';
        filtered.forEach(alt => {{
            const row = document.createElement('div');
            row.className = 'py-3.5 flex flex-col sm:flex-row sm:items-start justify-between gap-3 text-xs';

            const badgeClass = getAlterationBadgeClass(alt.alteration_type_code);
            const directionHTML = getDirectionIcon(alt.direction);
            const evidenceHTML = getEvidenceBadge(alt.evidence_strength);

            let biomarkerLink = '';
            if (alt.is_biomarker_match && alt.biomarker_slug) {{
                biomarkerLink = `
                    <button onclick="navigateToBiomarker('${{alt.biomarker_slug}}')" class="inline-flex items-center gap-1 text-[11px] text-indigo-400 hover:text-indigo-300 font-semibold underline underline-offset-2">
                        <i class="fa-solid fa-flask-vial"></i> View Fitness Curve & Simulator &rarr;
                    </button>
                `;
            }}

            row.innerHTML = `
                <div class="space-y-1.5 flex-1 min-w-0 pr-2">
                    <div class="flex items-center gap-2 flex-wrap">
                        <span class="${{badgeClass}} px-2 py-0.5 rounded font-mono text-[10px]">
                            Type ${{alt.alteration_type_code}}: ${{alt.alteration_type_name || 'Multi-Scale'}}
                        </span>
                        <span class="font-bold text-sm text-white">${{alt.name}}</span>
                        ${{alt.is_hallmark ? '<span class="px-1.5 py-0.5 rounded text-[9px] font-mono bg-rose-500/20 text-rose-300 border border-rose-500/40">Hallmark</span>' : ''}}
                        ${{alt.is_biomarker_match ? '<span class="px-1.5 py-0.5 rounded text-[9px] font-mono bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"><i class="fa-solid fa-link mr-1"></i>Biomarker Match</span>' : ''}}
                    </div>
                    <p class="text-slate-300 text-xs leading-relaxed">${{alt.description || ''}}</p>
                    ${{alt.mechanism ? `<p class="text-[11px] text-slate-400 italic">Mechanism: ${{alt.mechanism}}</p>` : ''}}
                    ${{biomarkerLink}}
                </div>

                <div class="flex sm:flex-col items-end justify-between sm:justify-start gap-1.5 shrink-0 text-right">
                    ${{directionHTML}}
                    ${{evidenceHTML}}
                    ${{alt.measurement_modality ? `<span class="text-[10px] text-slate-500 font-mono">${{alt.measurement_modality}}</span>` : ''}}
                </div>
            `;

            container.appendChild(row);
        }});
    }}

    function renderBiomarkerDiseasesView(biomarker) {{
        const container = document.getElementById('biomarker-diseases-container');
        const badge = document.getElementById('biomarker-disease-count-badge');
        if (!container) return;

        const diseaseAlts = AppState.biomarkerDiseasesMap[biomarker.id] || [];

        if (badge) {{
            badge.textContent = `${{diseaseAlts.length}} Associated Diseases`;
        }}

        if (diseaseAlts.length === 0) {{
            container.innerHTML = `
                <div class="col-span-2 p-8 text-center text-xs text-slate-500 bg-slate-950/40 rounded-xl border border-slate-800">
                    <i class="fa-solid fa-circle-info text-slate-600 text-lg mb-2 block"></i>
                    No specific chronic disease condition direct alterations currently mapped to this biomarker.
                </div>
            `;
            return;
        }}

        container.innerHTML = '';
        diseaseAlts.forEach(alt => {{
            const card = document.createElement('div');
            card.className = 'bg-slate-950/70 border border-slate-800 p-3.5 rounded-xl space-y-2 hover:border-slate-700 transition cursor-pointer flex flex-col justify-between';

            const badgeClass = getAlterationBadgeClass(alt.alteration_type_code);
            const dirHTML = getDirectionIcon(alt.direction);
            const evHTML = getEvidenceBadge(alt.evidence_strength);

            card.innerHTML = `
                <div class="space-y-1.5">
                    <div class="flex items-start justify-between gap-2">
                        <div>
                            <span class="text-xs font-bold text-white hover:text-rose-400 transition flex items-center gap-1.5">
                                <i class="fa-solid fa-disease text-rose-400 text-xs"></i>
                                ${{alt.disease_name}}
                            </span>
                            <span class="text-[10px] text-slate-400">${{alt.disease_category || 'Chronic Condition'}}</span>
                        </div>
                        <span class="${{badgeClass}} px-1.5 py-0.5 rounded font-mono text-[9px] shrink-0">
                            Type ${{alt.alteration_type_code}}
                        </span>
                    </div>
                    <p class="text-[11px] text-slate-300 leading-relaxed">${{alt.name}}: ${{alt.description || ''}}</p>
                </div>

                <div class="flex items-center justify-between border-t border-slate-800/80 pt-2 text-[10px]">
                    <div>${{dirHTML}}</div>
                    <div>${{evHTML}}</div>
                </div>
            `;

            card.addEventListener('click', () => {{
                const disease = AppState.diseases.find(d => d.id === alt.disease_id || d.slug === alt.disease_slug);
                if (disease) {{
                    openDiseaseModal(disease);
                }}
            }});

            container.appendChild(card);
        }});
    }}

    function navigateToBiomarker(slug) {{
        closeDiseaseModal();
        navigateTab('biomarkers');
        selectBiomarker(slug);
    }}
    </script>
</body>
</html>
"""

    # Write to frontend/index.html, dist/index.html (standard for static site hosts like GitHub Pages / Netlify / Cloudflare / Vercel), and root index.html
    target_paths = [FRONTEND_HTML_PATH, DIST_HTML_PATH, ROOT_HTML_PATH]
    for target in target_paths:
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(html_template)
        file_size_kb = target.stat().st_size / 1024
        print(f"Compiled Standalone HTML: {target} ({file_size_kb:.1f} KB)")


if __name__ == "__main__":
    generate_standalone_html()
