# Physiological Fitness Landscape — Mortality Biomarker Dashboard

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![Plotly.js](https://img.shields.io/badge/Plotly.js-2.29%2B-3F4F75.svg)](https://plotly.com/javascript/)
[![SQLite](https://img.shields.io/badge/SQLite-3-003B57.svg)](https://www.sqlite.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An evidence-based, interactive scientific dashboard mapping the continuous non-linear relationship between 25 physiological biomarkers and all-cause / cause-specific mortality hazard ratios (HR), juxtaposed with NHANES empirical population distributions, stratified demographics, evidence sources, and grade-ranked clinical and lifestyle interventions.

---

## 🌟 Overview & Scientific Motivation

Clinical medicine often evaluates biomarkers using binary cut-offs (e.g., normal vs. high). However, physiological fitness and mortality risk reside on continuous landscapes featuring **U-shaped**, **J-shaped**, **inverse**, or **supralinear** dose-response curves.

The **Physiological Fitness Landscape Dashboard** bridges epidemiological prospective cohort data (Framingham, UK Biobank, NHANES III/Continuous, Emerging Risk Factors Collaboration, ARIC, MESA, WHS) with interactive visual analytics:
1. **Interactive Risk Landscape**: Dual-axis visualization overlaying continuous non-linear Mortality Hazard Ratio (HR) curves with empirical population density distribution and optimal physiological ranges (HR ≤ 1.0).
2. **Interactive Patient Value Probe**: Input personal or lab values to dynamically compute hazard ratios and population percentile rankings with actionable clinical interpretations.
3. **Forest Plots of Evidence**: Forest plots displaying individual prospective studies and meta-analyses with 95% Confidence Intervals (CIs).
4. **Stratified Population Demographics**: NHANES population percentile curves broken down by Sex (All, Male, Female) and Age Bands (20–39, 40–59, 60–79, 80+).
5. **Evidence-Graded Interventions**: Quantitative effect sizes across Diet, Exercise, Pharmacologic, Supplementation, and Sleep/Environmental modalities with evidence grade badges (Meta-Analysis, Large RCT, Cohort Study).
6. **Side-by-Side Multi-Biomarker Comparison**: Compare up to 3 biomarkers simultaneously with synchronized risk curves, optimal physiological zones, and comparative metrics.

---

## 🔬 25 Included Biomarkers Across 7 Organ Systems

| Category | Biomarkers | Specimen |
|---|---|---|
| **Lipids & Atherogenic Lipoproteins** | Total Cholesterol, HDL-C, LDL-C, Triglycerides, Apolipoprotein B (ApoB), Lipoprotein(a) [Lp(a)] | Serum / Plasma |
| **Glycemic Control & Metabolism** | Fasting Blood Glucose, Hemoglobin A1c (HbA1c), Fasting Insulin, HOMA-IR | Serum / Whole Blood |
| **Systemic Inflammation & Immune** | High-Sensitivity C-Reactive Protein (hs-CRP), Fibrinogen, Homocysteine, Uric Acid | Serum / Plasma |
| **Renal Function & Filtration** | Serum Creatinine, Estimated GFR (eGFR CKD-EPI), Cystatin C | Serum |
| **Hepatic Function & Enzymes** | Alanine Aminotransferase (ALT), Aspartate Aminotransferase (AST), Gamma-Glutamyl Transferase (GGT), Serum Albumin | Serum |
| **Hematology & Iron Homeostasis** | Hemoglobin, Red Blood Cell Distribution Width (RDW), Serum Ferritin | Whole Blood / Serum |
| **Cardiovascular & Hemodynamics** | Systolic Blood Pressure (SBP) | Blood Pressure / Hemodynamics |

---

## 🏗 System Architecture

```
Physiological Fitness Landscape/
├── backend/
│   ├── main.py              # FastAPI application & REST API endpoints
│   ├── models.py            # SQLAlchemy 2.0 relational schema
│   ├── nhanes_etl.py        # CDC NHANES data pipeline & calibrated fallbacks
│   └── seed_data.py         # Comprehensive database seeder (25 markers, 20 sources)
├── frontend/
│   ├── index.html           # Single-page application layout & glassmorphic UI
│   ├── styles.css           # Modern clinical CSS with responsive design & dark mode
│   └── app.js               # Plotly.js visualizations & reactive UI logic
├── data/
│   ├── mortality_biomarkers.db  # SQLite database
│   └── raw/                 # Downloaded CDC NHANES XPT cache
├── tests/
│   ├── test_api.py          # FastAPI endpoint integration tests (10 tests)
│   └── test_etl.py          # NHANES ETL and calculation tests (4 tests)
├── requirements.txt         # Python dependencies
└── README.md                # Documentation
```

---

## 🌐 Zero-Backend Online Static Hosting (Data Embedded in HTML)

The platform includes a dedicated compiler (`backend/build_standalone_html.py`) that bundles all SQLite relational data (Biomarkers, Non-Linear Splines, NHANES Demographics, Interventions, Citations, 113+ Chronic Diseases, and the In-Browser Optimization Simulation Engine) **directly into self-contained HTML files**.

This enables instant, zero-server deployment to any static web host or CDN:

### 1. Compile the Standalone HTML Distribution
```bash
python backend/build_standalone_html.py
```
This outputs self-contained HTML bundles to:
- `index.html` (for GitHub Pages root deployment)
- `dist/index.html` (for Netlify / Vercel / Cloudflare Pages / AWS S3 static directories)
- `frontend/index.html` (for local frontend workspace serving)

### 2. Static Web Hosting Options

| Hosting Platform | Deployment Instructions |
|---|---|
| **GitHub Pages** | Push repository to GitHub &rarr; Go to **Settings** &rarr; **Pages** &rarr; Select `Deploy from a branch` &rarr; Branch: `main` / Folder: `/ (root)` &rarr; Save. |
| **Cloudflare Pages** | Connect your Git repository &rarr; Build directory: `dist` &rarr; Framework preset: `None` &rarr; Deploy. |
| **Netlify / Vercel** | Drag and drop the `dist/` folder or set Publish directory to `dist` in build settings. |
| **AWS S3 / GCP Cloud Storage** | Upload `dist/index.html` to your public static website bucket. |
| **Local Offline Execution** | Double-click `index.html` in your file explorer or serve via `python -m http.server 8080`. |

---

## 🚀 Local Development (FastAPI + Dynamic API)

### 1. Prerequisites
- Python 3.10, 3.11, 3.12, 3.13, or 3.14
- `pip` package manager

### 2. Installation
Clone the repository and install the dependencies:
```bash
git clone https://github.com/OpenSourceMed/physiological-fitness-landscape.git
cd "Physiological Fitness Landscape"

pip install -r requirements.txt
```

### 3. Database Initialization & Seeding
Seed the database with all 25 biomarkers, prospective mortality studies, population distributions, and clinical interventions:
```bash
python -m backend.seed_data
python -m backend.disease_intelligence_etl
python -m backend.optimization_engine
```

### 4. Running the Dynamic Server
Start the FastAPI backend:
```bash
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```
Open your browser and navigate to:
**`http://localhost:8000`**

---

## 🧪 Running Automated Tests

Run the full pytest suite:
```bash
python -m pytest -v tests
```

Expected output:
```
tests/test_api.py::test_get_stats PASSED
tests/test_api.py::test_list_biomarkers_default PASSED
tests/test_api.py::test_list_biomarkers_filter_category PASSED
tests/test_api.py::test_list_biomarkers_search_query PASSED
tests/test_api.py::test_get_biomarker_detail_by_slug PASSED
tests/test_api.py::test_get_biomarker_detail_not_found PASSED
tests/test_api.py::test_get_hr_distribution PASSED
tests/test_api.py::test_get_population_distribution PASSED
tests/test_api.py::test_compare_biomarkers PASSED
tests/test_api.py::test_list_sources PASSED
tests/test_etl.py::test_nhanes_variable_map PASSED
tests/test_etl.py::test_compute_distribution_stats PASSED
tests/test_etl.py::test_get_nhanes_calibrated_benchmarks PASSED
tests/test_etl.py::test_compute_nhanes_distributions_db_population PASSED
======================= 14 passed in 1.95s =======================
```

---

## 📡 REST API Documentation

Once the server is running, interactive Swagger OpenAPI docs are available at `http://localhost:8000/docs`.

### Key Endpoints:
- `GET /api/stats`: Summary counts of biomarkers, sources, associations, distributions, and interventions.
- `GET /api/biomarkers`: List biomarkers with optional category filtering and search queries (`?category=Lipids&search=ApoB`).
- `GET /api/biomarkers/{slug}`: Full biomarker profile with optimal ranges, descriptions, and linked data.
- `GET /api/biomarkers/{slug}/hr-distribution`: Non-linear mortality hazard ratio curve points and population distribution density.
- `GET /api/biomarkers/{slug}/population-distribution`: Stratified NHANES percentiles (P5, P25, P50, P75, P95) filterable by `sex` and `age_band`.
- `GET /api/biomarkers/{slug}/interventions`: Evidence-graded interventions filterable by modality (`Diet`, `Exercise`, `Pharmacologic`, `Supplement`, `Sleep/Environmental`).
- `GET /api/compare?slugs=apob,high_sensitivity_crp,systolic_blood_pressure`: Side-by-side comparison payload for up to 3 biomarkers.
- `GET /api/sources`: Academic and clinical prospective studies with PMIDs, DOIs, sample sizes, and follow-up durations.

---

## 📊 Methodology & Mathematical Formulations

### Non-Linear Mortality Risk Models
Hazard ratio curves $HR(x)$ are modeled using restricted cubic splines and empirical polynomial fits calibrated to prospective epidemiological cohorts:

$$HR(x) = \exp\left( \beta_1 (x - x_{\text{ref}}) + \beta_2 (x^2 - x_{\text{ref}}^2) + \dots \right)$$

- **U-Shaped / J-Shaped**: Elevated risk at both extremes (e.g., Total Cholesterol, Systolic BP, BMI, Ferritin).
- **Supralinear / Monotonic Positive**: Monotonically increasing risk with accelerating slopes (e.g., ApoB, hs-CRP, HbA1c, Homocysteine).
- **Inverse / Monotonic Negative**: Protective associations up to physiological saturation (e.g., Albumin, eGFR).

### Interactive Hazard Calculation
Given a user-provided biomarker value $x_0$, the system performs linear interpolation along the calibrated spline knots:
$$HR(x_0) = HR_k + \frac{x_0 - x_k}{x_{k+1} - x_k} (HR_{k+1} - HR_k)$$
and computes percentile placement against the empirical NHANES distribution.

---

## 📚 Key Literature & Evidence Sources

- **Emerging Risk Factors Collaboration (ERFC)**: *Lipid-related markers and cardiovascular risk*. JAMA & Lancet.
- **UK Biobank**: *Biomarker associations with all-cause and cause-specific mortality in 500,000 individuals*.
- **CDC NHANES Continuous Surveys**: *Laboratory Methods and National Health and Nutrition Examination Survey Percentiles*.
- **JUPITER & CANTOS Trials**: *hs-CRP reduction and cardiovascular event reduction*. NEJM.
- **KDIGO Guidelines**: *Chronic Kidney Disease Evaluation and Management*. Kidney Int.
- **SPRINT Research Group**: *A Randomized Trial of Intensive versus Standard Blood-Pressure Control*. NEJM.

---

## 📄 License
This project is licensed under the MIT License - see the LICENSE file for details.
