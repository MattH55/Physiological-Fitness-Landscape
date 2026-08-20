# Physiological Fitness Landscape — Project Summary & Architecture

## Overview
The **Physiological Fitness Landscape** is an interactive, open-source precision medicine, biomarker optimization, and chronic disease intelligence platform. It models non-linear all-cause mortality hazard ratios as a function of physiological biomarkers, integrates population-level reference distributions (e.g., CDC NHANES), maps multi-scale pathological alterations across 113+ chronic diseases, and simulates continuous population/individual shift interventions in real-time.

Crucially, the platform features a **Zero-Backend Online Static Architecture** where all database tables, curve splines, demographic strata, disease alterations, and numerical simulation routines are pre-compiled and embedded directly inside standalone HTML files (`index.html`, `dist/index.html`, `frontend/index.html`).

---

## 1. Key Capabilities & Features

### 1.1 Biomarker Mortality Hazard Landscape (50 Biomarkers)
- **Categorical & Anatomical Coverage**: Metabolic, Cardiovascular, Inflammatory, Renal, Hepatic, Hematologic, Endocrine, Pulmonary, and Functional domains.
- **Dose-Response Splines**: Natural cubic spline & quadratic hazard ratio curves $HR(x)$, normalized such that $HR(x_{ref}) = 1.00$.
- **Population Reference Distributions**: Stratified by age bands (`20-39`, `40-59`, `60-79`, `80+`, `all`) and sex (`male`, `female`, `all`) with percentiles ($p5, p10, p25, p50, p75, p90, p95$), standard deviations, and discrete probability densities $f(x)$.

### 1.2 Multi-Scale Chronic Disease Intelligence (113+ Diseases)
Maps human chronic diseases across 5 physiological alteration types:
- **Type A (Molecular / Genomic)**: Gene mutations, genetic variants, epigenetic methylation, and transcriptomic shifts.
- **Type B (Lab / Clinical)**: Routine serum chemistry, hematology, lipid panels, metabolic assays, and hormone levels.
- **Type C (Scales / Patient-Reported Outcomes)**: Validated clinical risk scores, disability indices, and cognitive scales (e.g., NYHA, MMSE, UPDRS, Charlson Index).
- **Type D (Pathology / Imaging / Structural)**: Histopathology, biopsy grades, CT/MRI findings, coronary calcium scores (CAC), and echocardiographic parameters.
- **Type E (Functional Tests)**: Cardiorespiratory fitness ($VO_2\text{ max}$), spirometry ($FEV_1/FVC$), grip strength, gait speed, and 6-minute walk distance.

### 1.3 Real-Time Population & Individual Simulation Engine
- **Population Expected Hazard Shift**:
  $$\mathbb{E}[HR] = \int_{a}^{b} HR(x) \cdot f(x) \, dx$$
- **Continuous SD Shift Simulation**: Simulates positive and negative standard deviation shifts ($\pm 0.1 \sigma$ to $\pm 2.0 \sigma$) with clamped biological bounds to quantify population-attributable mortality reductions.
- **Optimization Scenarios**: Precomputed and dynamic scenario leaderboards highlighting high-impact public health targets (e.g., fasting glucose, systolic BP, hs-CRP, $VO_2\text{ max}$).
- **Individual Benefit Estimator**: Calculates risk reduction quantiles based on personalized baseline biomarker levels.

### 1.4 Zero-Backend Online Deployment
- **Self-Contained Single-File Deliverable**: All 50 biomarkers, 113+ diseases, 500+ literature citations, precomputed optimization scenarios, and CSS/JS code are embedded into single standalone HTML files.
- **No Python/FastAPI Dependency in Production**: Can be hosted on any static web server or CDN (GitHub Pages, Cloudflare Pages, Netlify, Vercel, AWS S3) or opened directly in a web browser.

---

## 2. Directory Structure & Key Artifacts

```
Physiological Fitness Landscape/
├── index.html                             # Root standalone static deployment build (GitHub Pages ready)
├── dist/
│   └── index.html                         # Dist standalone static build (CI/CD / Cloudflare / Netlify)
├── frontend/
│   ├── index.html                         # Frontend standalone static build / development template
│   ├── styles.css                         # UI styling, responsive layout, dark/light themes
│   └── app.js                             # Client-side numerical simulation engine, chart rendering, filters
├── backend/
│   ├── build_standalone_html.py           # Standalone compiler embedding SQLite data & assets into HTML
│   ├── models.py                          # SQLAlchemy ORM models (Biomarkers, Hazards, Distributions, Diseases)
│   ├── seed_data.py                       # 50 Biomarkers, 113+ Diseases, Splines & References seed routine
│   ├── optimization_engine.py             # Numerical integration & continuous SD shift simulation engine
│   ├── disease_intelligence_etl.py        # Multi-scale Disease Alterations ETL pipeline
│   ├── nhanes_etl.py                      # CDC NHANES demographic distribution ETL pipeline
│   ├── mortalitypredictors_etl.py         # Mortality predictors ingestion pipeline
│   ├── generate_raw_export.py             # Export generator for raw JSON/CSV datasets
│   └── main.py                            # FastAPI REST API (optional for local/API service usage)
├── data/
│   ├── mortality_biomarkers.db            # Complete SQLite database containing all records
│   └── raw/
│       ├── mortalitypredictors_raw_export.json
│       └── mortalitypredictors_raw_export.csv
├── tests/
│   ├── test_api.py                        # FastAPI endpoint verification tests
│   ├── test_biomarker_curves_and_distributions.py  # Monotonicity, normalization, and density integration tests
│   └── test_etl.py                        # ETL pipeline and ingestion tests
├── README.md                              # Complete deployment and user documentation
└── SUMMARY.md                             # Executive summary and architectural specification
```

---

## 3. Database Schema Overview

| Table Name | Description | Key Fields |
| :--- | :--- | :--- |
| `biomarkers` | Master table of 50 physiological biomarkers | `slug`, `name`, `category`, `anatomical_system`, `units`, `specimen_type`, `description` |
| `sources` | Scientific citations and cohorts | `citation`, `pmid`, `doi`, `year`, `cohort_name`, `sample_size` |
| `mortality_associations` | Curve parameters, spline knots, hazard ratios | `biomarker_id`, `hazard_ratio`, `reference_range_low`, `reference_range_high`, `curve_type`, `spline_knots_json` |
| `population_distributions`| Demographic strata reference statistics | `biomarker_id`, `sex`, `age_band`, `mean`, `std`, `p5`, `p25`, `p50`, `p75`, `p95`, `density_json` |
| `optimization_scenarios` | Precomputed and custom shift scenarios | `biomarker_id`, `scenario_name`, `sd_shift`, `baseline_expected_hr`, `shifted_expected_hr`, `hazard_reduction_pct` |
| `precalculated_expected_values`| Pre-integrated expected hazard ratios | `biomarker_id`, `sex`, `age_band`, `expected_hazard_ratio` |
| `diseases` | 113+ chronic medical conditions | `code`, `name`, `category`, `subspecialty`, `icd10_code`, `prevalence_us_pct`, `mortality_impact` |
| `disease_alterations` | Type A-E alterations mapped to biomarkers | `disease_id`, `biomarker_id`, `alteration_type`, `alteration_name`, `direction`, `clinical_significance` |

---

## 4. Static Build & Compilation Process

The compilation script `backend/build_standalone_html.py` performs the following steps:
1. Connects to `data/mortality_biomarkers.db`.
2. Queries all biomarkers, curves, demographic distributions, optimization scenarios, expected values, diseases, alterations, and citations.
3. Formats the data into a single, compact JSON payload.
4. Reads `frontend/index.html`, `frontend/styles.css`, and `frontend/app.js`.
5. Replaces external `<link>` and `<script>` tags with inline styles and scripts.
6. Injects the entire dataset into `<script id="embedded-biomarker-data" type="application/json">`.
7. Writes the resulting standalone file to `index.html`, `dist/index.html`, and `frontend/index.html`.

### How to Rebuild
```bash
python backend/build_standalone_html.py
```

---

## 5. Deployment Options

1. **GitHub Pages**:
   - Push repository with root `index.html`. In GitHub repository settings -> **Pages** -> Source: **Deploy from a branch** -> Branch: `main` / `root`.
2. **Cloudflare Pages / Netlify / Vercel**:
   - Set Build Output Directory to `dist` or root `/`. No build command required.
3. **AWS S3 / Google Cloud Storage / Azure Blob**:
   - Upload `index.html` to any static website hosting bucket.
4. **Local Browser**:
   - Simply double-click `index.html` to open it in Chrome, Edge, Safari, or Firefox without running any web server.

---

## 6. Verification and Testing

The platform includes a comprehensive test suite executed via `pytest`:
- `tests/test_api.py`: Validates all REST endpoints (status, biomarkers, distributions, comparisons, optimizations, diseases).
- `tests/test_biomarker_curves_and_distributions.py`: Validates database integrity (50 biomarkers, 113+ diseases), percentile monotonicity, $HR(x_{ref}) = 1.00$ normalization, finite domain bounds, and probability density integration.
- `tests/test_etl.py`: Validates ETL mappings, NHANES stats calculations, and data ingestion routines.

All 28 tests pass with 100% success rate:
```bash
python -m pytest -v tests
```
