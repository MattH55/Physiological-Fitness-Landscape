"""Export the static GitHub Pages build of NPxP into the MattH55/npxp repo.

GitHub Pages serves static files only, so this script replaces the live FastAPI
backend with a JSON snapshot of every endpoint the frontend consumes:

  api/stats.json, api/evidence_tiers.json, api/drugs.json (+ per-id detail),
  api/cell_lines.json (+ api/cell_lines/<id>.json per line),
  api/modifiers.json (+ per-id detail), api/interactions.json (+ per-id detail),
  api/explorer_matrix.json   {"by_drug": {drug_id: matrix payload}, ...},
  api/scoring_models.json, api/prediction_readiness.json,
  api/opportunity_cell_lines.json, api/opportunity_cancer_types.json

It then copies the frontend (with js/config.js overwritten to STATIC_DATA=true),
the CNAME (npxp.opensourcemed.info) and BUILD_SPEC.md into the repo. The scoring
page runs entirely client-side in the static build (js/scoring-client.js is a
port of synlethality/scoring.py).

Payloads are produced by calling the real FastAPI app through a TestClient
against a throwaway seeded SQLite DB, so the snapshot is byte-identical to the
live API responses. Run from the project root:

    python scripts/export_static.py [--repo npxp-repo]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # allow `import synlethality` from any cwd
FRONTEND = ROOT / "frontend"
ZIP_ASSETS = ROOT / "npxp-zip"

README = """# NPxP — Non-Pharm × Pharm

An open, evidence-graded database modeling interactions between non-pharmacological interventions (dietary/metabolic, thermal, hypoxic, and similar modifiers) and pharmacological agents, at the cellular level, across cancer cell lines.

Part of the [Open Source Medicine Foundation](https://opensourcemed.info) portfolio. Hosted at [npxp.opensourcemed.info](https://npxp.opensourcemed.info).

See `BUILD_SPEC.md` for the full data model, ingestion sources, API surface, and page structure.

## Repository layout (GitHub Pages deployment)

- `*.html`, `js/`, `css/` — the static frontend (vanilla JS + Tailwind CDN).
- `api/` — static JSON snapshot of the REST API responses; the frontend reads
  these files because GitHub Pages cannot run the FastAPI backend.
- `js/config.js` — sets `STATIC_DATA = true`; locally the same frontend runs
  against the live API instead (`STATIC_DATA = false`).
- `js/scoring-client.js` — browser port of the Step 1 synergy engine
  (Bliss/HSA/Loewe/ZIP), used by the scoring page in the static build.
- `CNAME` — custom domain `npxp.opensourcemed.info`.

The backend, ingestion pipeline, curation tooling, and tests live in the
development workspace (`synlethality/` package). After any data or frontend
change, regenerate this snapshot with:

```bash
python scripts/export_static.py --repo <path-to-this-repo>
```

No quantitative field is ever fabricated: `stress_signature_score.score` and
`interaction_effect.combined_effect_metric` are null until computed from raw
data by the ingestion pipeline.
"""


def _rmtree(path):
    """rmtree tolerant of OneDrive read-only/locked files on Windows.

    OneDrive's own sync process can hold a transient sharing-violation lock
    (WinError 32) on a file it's actively uploading, on top of the
    read-only-attribute case already handled here -- retry with backoff
    before giving up, rather than crashing the whole export over one file
    OneDrive will release within a few seconds.
    """
    import time

    def _onexc(func, p, exc):
        os.chmod(p, 0o666)
        last_exc = exc
        for attempt in range(6):
            try:
                func(p)
                return
            except (PermissionError, OSError) as e:
                last_exc = e
                time.sleep(2 ** attempt)  # 1,2,4,8,16,32s
        raise last_exc

    shutil.rmtree(path, onexc=_onexc)


def dump(client, path, out_file):
    """GET an endpoint and write the JSON response verbatim.

    Retries the write with backoff on a transient file lock (observed
    2026-09-22: some external process -- an editor/indexer with the file
    open, most likely -- can hold an exclusive lock on a large per-id JSON
    file in this OneDrive-synced folder). After exhausting retries, logs a
    warning and leaves that one file stale rather than aborting the entire
    export over one unwritable file.
    """
    import time

    r = client.get(path)
    r.raise_for_status()
    payload = r.json()
    out_file.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2)
    for attempt in range(6):
        try:
            out_file.write_text(text, encoding="utf-8")
            break
        except (PermissionError, OSError) as exc:
            if attempt == 5:
                print(f"WARNING: could not write {out_file} after retries ({exc}); "
                      "left stale -- re-run the export once the lock clears.")
            else:
                time.sleep(2 ** attempt)
    return payload


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", default=str(ROOT / "npxp-repo"),
                    help="Path to the checked-out MattH55/npxp repo.")
    args = ap.parse_args()
    repo = Path(args.repo)
    if not repo.is_dir():
        raise SystemExit(f"Repo directory not found: {repo}")

    # Throwaway seeded database; env var must be set before importing the app.
    tmp = tempfile.mkdtemp(prefix="npxp-export-")
    os.environ["SYNLETHALITY_DATABASE_URL"] = f"sqlite:///{Path(tmp) / 'export.db'}"
    from fastapi.testclient import TestClient  # noqa: E402
    from synlethality import bridging as _bridging  # noqa: E402
    from synlethality import curated_bulk_mechanisms  # noqa: E402
    from synlethality.database import make_session_factory  # noqa: E402
    from synlethality.database import get_engine  # noqa: E402
    from synlethality.heuristic_bridging import generate_heuristic_matches  # noqa: E402
    from synlethality.nearest_neighbor import generate_nearest_neighbor_candidates  # noqa: E402
    from synlethality.ingest.depmap_prism import DepmapPrismIngest  # noqa: E402
    from synlethality.ingest.prism_repurposing import PrismRepurposingIngest  # noqa: E402
    from synlethality.ingest.gdsc import GDSCIngest  # noqa: E402
    from synlethality.ingest.ctrp import CTRPIngest  # noqa: E402
    from synlethality.ingest.geo_modifiers import GEOModifierIngest  # noqa: E402
    from synlethality.ingest.msigdb import MSigDBIngest  # noqa: E402
    from synlethality.ingest.lincs_l1000 import LincsL1000Ingest  # noqa: E402
    from synlethality.main import app  # noqa: E402  (auto-seeds on import)
    from synlethality import config as _config  # noqa: E402

    # Bulk DepMap compound registry + OncoTree backfill (real ingestion, see
    # ingest/depmap_prism.py) -- additive to the curated seed, never
    # overwrites a curated row. Skipped gracefully if data/depmap/*.csv
    # hasn't been downloaded (extract() raises NotImplementedError).
    _Session = make_session_factory(get_engine(_config.DATABASE_URL))
    with _Session() as _s:
        try:
            _run = DepmapPrismIngest().run(_s)
            print(f"DepMap ingest: {_run.status}, {_run.row_count} rows")

            # Real PRISM Repurposing monotherapy viability data (drug_response
            # table, synlethality/ingest/prism_repurposing.py) -- must run
            # after the ingest above, since it only attaches data to drug_ids
            # that already exist (including the curated drugs DepMap's own
            # registry lists under a different identity; see
            # depmap_prism.CURATED_DRUG_ALIASES). Skipped gracefully if
            # data/prism/*.csv hasn't been downloaded.
            _prism_run = PrismRepurposingIngest().run(_s)
            _s.commit()
            print(f"PRISM Repurposing ingest: {_prism_run.status}, {_prism_run.row_count} rows")

            # Real GDSC1/GDSC2 cross-validation data (synlethality/ingest/gdsc.py)
            # -- only needs cell_line rows to already exist (curated from the
            # start), not the bulk DepMap registry, but grouped here with the
            # other drug_response ingestion steps for readability.
            _gdsc_run = GDSCIngest().run(_s)
            _s.commit()
            print(f"GDSC cross-validation ingest: {_gdsc_run.status}, {_gdsc_run.row_count} rows")

            # Real CTRPv2 cross-validation data (synlethality/ingest/ctrp.py)
            # -- reads the small CSV scripts/extract_ctrp.R produced from
            # the real .rds file; skipped gracefully if that extraction
            # hasn't been run (needs R, see ctrp.py's docstring).
            _ctrp_run = CTRPIngest().run(_s)
            _s.commit()
            print(f"CTRP cross-validation ingest: {_ctrp_run.status}, {_ctrp_run.row_count} rows")

            # Prediction Methodology Stage 1 at scale, first real slice
            # (synlethality/signature_correlation.py, PREDICTION_METHODOLOGY.md):
            # real Hallmark/KEGG gene sets (Enrichr mirror) + real per-gene
            # log2FC computed from GSE153830's own published expression
            # matrix, backfilling stress_signature_score.score for the 4
            # rows that study covers. Independent of the drug-side ingest
            # above; order relative to it doesn't matter.
            _msigdb_run = MSigDBIngest().run(_s)
            _s.commit()
            print(f"MSigDB/KEGG gene-set ingest: {_msigdb_run.status}, {_msigdb_run.row_count} rows")
            _geo_run = GEOModifierIngest("GSE153830").run(_s)
            _s.commit()
            print(f"GEO GSE153830 real DEG backfill: {_geo_run.status}, {_geo_run.row_count} rows")

            # Real LINCS L1000 induced signatures for the 6 curated drugs
            # matched in GSE70138 (synlethality/ingest/lincs_l1000.py) --
            # reads the small local cache scripts/extract_lincs_signatures.py
            # produced from the real (5.4GB) Level 5 GCTX file; skipped
            # gracefully if that extraction hasn't been run.
            _lincs_run = LincsL1000Ingest().run(_s)
            _s.commit()
            print(f"LINCS L1000 real signature ingest: {_lincs_run.status}, {_lincs_run.row_count} rows")

            # Real, PMID-verified resistance-mechanism research for 8 more
            # bulk-registry compounds (synlethality/curated_bulk_mechanisms.py)
            # -- must run after the ingest above, since these drug_ids only
            # exist in the DB once the bulk registry has been loaded.
            _bulk_mech_counts = curated_bulk_mechanisms.seed(_s)
            _s.commit()
            print(f"Curated bulk resistance mechanisms: {_bulk_mech_counts}")

            # bridging.generate_candidates() already ran once inside the
            # automatic seed_data.seed() pass (before the mechanisms above
            # existed) -- re-run it so the newly-curated mechanisms actually
            # get matched against modifier signatures for real Tier 3 output.
            _bridging_counts = _bridging.generate_candidates(_s)
            _s.commit()
            print(f"Bridging (re-run after bulk mechanisms): {_bridging_counts}")
        except Exception as exc:  # pragma: no cover - defensive, matches IngestionStep's own handling
            print(f"DepMap ingest / bulk mechanisms skipped: {exc}")
        # Tier 2c nearest-neighbor prediction (synlethality/nearest_neighbor.py,
        # reconciling the "NPxP Interaction Predictor" build spec's Stage
        # 1/E2 into this schema): only needs the curated tier_1/tier_2 rows,
        # which exist regardless of whether the DepMap ingest above
        # succeeded, so this runs unconditionally, before Tier 4.
        _nn_counts = generate_nearest_neighbor_candidates(_s)
        _s.commit()
        print(f"Tier 2c nearest-neighbor candidates: {_nn_counts}")

        # Tier 4 heuristic keyword match against the full DepMap registry
        # (synlethality/heuristic_bridging.py) -- run only after the bulk
        # registry (and the real mechanisms above, which it must skip) so
        # it has the ~7,000 compounds to match against. Not an IngestionStep
        # (no IngestionRun bookkeeping needed for a derived/computed layer,
        # same as bridging.generate_candidates).
        _heuristic_counts = generate_heuristic_matches(_s)
        _s.commit()
        print(f"Tier 4 heuristic matches: {_heuristic_counts}")

    client = TestClient(app)
    api = repo / "api"
    # Wipe stale per-id snapshots keyed by a uuid regenerated on every seed
    # (api/interactions/<uuid>.json) -- re-exports would otherwise leave
    # orphaned per-id files behind. Every other per-id directory
    # (drugs/cell_lines/modifiers) is keyed by a stable id that's only ever
    # added to, never renamed, so `dump()` below safely overwrites those in
    # place without a wipe first -- scoped this way specifically so a
    # transient OneDrive lock on one unrelated file (observed 2026-09-22)
    # can't abort the whole export over a directory that didn't need
    # deleting anyway.
    if (api / "interactions").exists():
        _rmtree(api / "interactions")

    # Whole-endpoint snapshots (unfiltered lists; frontend filters client-side).
    dump(client, "/api/stats", api / "stats.json")
    dump(client, "/api/evidence_tiers", api / "evidence_tiers.json")
    drugs = dump(client, "/api/drugs", api / "drugs.json")
    cell_lines = dump(client, "/api/cell_lines", api / "cell_lines.json")
    modifiers = dump(client, "/api/modifiers", api / "modifiers.json")
    interactions = dump(client, "/api/interactions", api / "interactions.json")
    dump(client, "/api/scoring/models", api / "scoring_models.json")
    dump(client, "/api/prediction/readiness", api / "prediction_readiness.json")
    dump(client, "/api/coverage-gaps", api / "coverage_gaps.json")
    dump(client, "/api/prioritization/methodology", api / "prioritization_methodology.json")
    dump(client, "/api/opportunity/cell-lines", api / "opportunity_cell_lines.json")
    dump(client, "/api/opportunity/cancer-types", api / "opportunity_cancer_types.json")

    # Prediction Methodology Stage 1 at scale, real on-demand computation
    # (synlethality/signature_correlation.py): the only (modifier, drug)
    # pairs with real signature data on both sides right now are
    # mcf7_glucose_hippo x each of the 6 LINCS-covered curated drugs.
    # Pre-computed and dumped here since the deployed site has no live
    # backend to call /api/signature-correlation on demand.
    _sig_corr_results = []
    for _drug_id in ("metformin", "5-fluorouracil", "mitomycin-c",
                      "doxorubicin", "paclitaxel", "temozolomide"):
        try:
            _sig_corr_results.append(
                client.get(
                    "/api/signature-correlation",
                    params={"modifier_key": "mcf7_glucose_hippo", "drug_id": _drug_id},
                ).json()
            )
        except Exception as exc:  # pragma: no cover - defensive
            print(f"signature-correlation skipped for {_drug_id}: {exc}")
    (api / "signature_correlations.json").write_text(
        json.dumps(_sig_corr_results, indent=2), encoding="utf-8")
    print(f"Signature correlations (real, both sides): {len(_sig_corr_results)} pairs")

    # Per-id detail snapshots.
    for cl in cell_lines:
        dump(client, f"/api/cell_lines/{cl['cell_line_id']}",
             api / "cell_lines" / f"{cl['cell_line_id']}.json")
    for m in modifiers:
        dump(client, f"/api/modifiers/{m['modifier_id']}",
             api / "modifiers" / f"{m['modifier_id']}.json")
    # Detail snapshots only for drugs with real content: the DepMap bulk
    # registry adds ~7,000 zero-interaction/zero-response compounds, and
    # precomputing an empty detail file for each would balloon the repo for
    # no benefit -- drugs.js renders those inline from the list payload
    # instead of fetching a detail file (see js/drugs.js).
    drugs_with_detail = [d for d in drugs if d["interaction_count"] or d["response_count"]]
    for d in drugs_with_detail:
        dump(client, f"/api/drugs/{d['drug_id']}",
             api / "drugs" / f"{d['drug_id']}.json")
    for it in interactions:
        dump(client, f"/api/interactions/{it['id']}",
             api / "interactions" / f"{it['id']}.json")
    # Mechanistic Bridging output (build spec v5) — fits the same per-id
    # detail path convention above (api/interactions/candidates.json), so
    # the existing static detail-route regex in common.js serves it with no
    # further changes.
    dump(client, "/api/interactions/candidates", api / "interactions" / "candidates.json")

    # Explorer matrices only for drugs with at least one curated interaction
    # -- a matrix for a zero-interaction bulk-registry compound is always
    # empty (explorer.html already handles "no interactions yet" for a
    # drug missing from by_drug), so skip generating ~7,000 empty ones.
    by_drug = {}
    tier_defs = None
    for d in drugs:
        if not d["interaction_count"]:
            continue
        payload = dump(client, f"/api/explorer/matrix?drug_id={d['drug_id']}",
                       Path(tmp) / "matrix.json")
        tier_defs = payload["evidence_tier_definitions"]
        by_drug[d["drug_id"]] = payload
    (api / "explorer_matrix.json").write_text(json.dumps(
        {"by_drug": by_drug, "evidence_tier_definitions": tier_defs}, indent=2),
        encoding="utf-8")

    # Frontend (then flip config.js to static mode).
    for item in FRONTEND.iterdir():
        dest = repo / item.name
        if item.is_dir():
            if dest.exists():
                _rmtree(dest)
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)
    (repo / "js" / "config.js").write_text(
        "/* Static GitHub Pages build — regenerated by scripts/export_static.py. "
        "The frontend reads the JSON snapshot under api/ instead of the live "
        "FastAPI backend. */\nconst STATIC_DATA = true;\n", encoding="utf-8")

    # Repo meta: CNAME + build spec from the NPxP skeleton, README, .nojekyll.
    shutil.copy2(ZIP_ASSETS / "CNAME", repo / "CNAME")
    shutil.copy2(ZIP_ASSETS / "BUILD_SPEC.md", repo / "BUILD_SPEC.md")
    (repo / "README.md").write_text(README, encoding="utf-8")
    (repo / ".nojekyll").write_text("", encoding="utf-8")

    shutil.rmtree(tmp, ignore_errors=True)
    n_json = len(list(api.rglob("*.json")))
    print(f"Exported {n_json} JSON snapshots + frontend to {repo}")


if __name__ == "__main__":
    main()
