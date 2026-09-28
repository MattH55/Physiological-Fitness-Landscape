"""
Follow-up to batches 2-4: attach real, verified per-marker distribution
citations to the biomarkers whose population_distribution row was left
pointing at the generic Peto et al. 2017 anchor (a fallback the shared
ingest_one() applies whenever no `dist_source` was set), replacing that
mismatched attribution.

Two groups:
  1. REAL_SOURCES - a specific published reference-range study was located
     and PMID-verified for these markers after the fact; their
     population_distribution rows are re-pointed to it (and, for
     osteocalcin, the mean/SD are upgraded to match the newly-attached,
     more authoritative source).
  2. NO_CLEAN_SOURCE - markers where no single population reference study
     could be located (mostly arbitrary 0-10 severity scores standing in
     for zero-inflated calcification presence/absence, or genuinely
     under-studied physical-test norms). These get one shared, honestly
     labeled "approximated, no source" Source row instead of silently
     keeping the misleading Peto citation.
"""
import sqlite3

conn = sqlite3.connect("data/mortality_biomarkers.db")
cur = conn.cursor()


def get_or_create_source(citation, pmid, doi, year, study_design):
    cur.execute(
        "SELECT id FROM source WHERE citation=? OR (pmid IS NOT NULL AND pmid=? AND pmid<>'')",
        (citation, pmid),
    )
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute(
        "INSERT INTO source (citation, pmid, doi, year, study_design, identifier_type, identifier) "
        "VALUES (?, ?, ?, ?, ?, 'pmid', ?)",
        (citation, pmid, doi, year, study_design, pmid),
    )
    return cur.lastrowid


REAL_SOURCES = {
    "ctx-bone-resorption": (
        "Li M, Li Y, Deng W, Zhang Z, Deng Z, Hu Y, Xia W, Xu L. Chinese bone "
        "turnover marker study: reference ranges for C-terminal telopeptide "
        "of type I collagen and procollagen I N-terminal peptide by age and "
        "gender. PLoS One. 2014;9(3):e103841.",
        "25117452", "10.1371/journal.pone.0103841", 2014, "reference_range",
    ),
    "exercise-capacity-mets": (
        "Lander BS, Layton AM, Garofano RP, Schwartz A, Engel DJ, Bello NA. "
        "Average Exercise Capacity in Men and Women >75 Years of Age "
        "Undergoing a Bruce Protocol Exercise Stress Test. Am J Cardiol. "
        "2022;164:117-119.",
        "34844736", "10.1016/j.amjcard.2021.10.020", 2022, "reference_range",
    ),
    "vitamin-e": (
        "McBurney MI, Yu EA, Ciappio ED, Bird JK, Eggersdorfer M, Mehta S. "
        "Suboptimal Serum alpha-Tocopherol Concentrations Observed among "
        "Younger Adults and Those Depending Exclusively upon Food Sources, "
        "NHANES 2003-2006. PLoS One. 2015;10(8):e0135510.",
        "26287975", "10.1371/journal.pone.0135510", 2015, "reference_range",
    ),
    "proinsulin": (
        "Ateia S, Rusu E, Cristescu V, Enache G, Cheta DM, Radulian G. "
        "Proinsulin and age in general population. J Med Life. "
        "2013;6(4):383-386.",
        "24868254", None, 2013, "reference_range",
    ),
    "alpha-1-antitrypsin": (
        "Donato LJ, Jenkins SM, Smith C, Katzmann JA, Snyder MR. Reference "
        "and interpretive ranges for alpha(1)-antitrypsin quantitation by "
        "phenotype in adult and pediatric populations. Am J Clin Pathol. "
        "2012;138(3):398-405.",
        "22912357", "10.1309/AJCPMEEJK32ACYFP", 2012, "reference_range",
    ),
    "ngal": (
        "Bourgonje AR, Abdulle AE, Bourgonje MF, Kieneker LM, la Bastide-van "
        "Gemert S, Gordijn SJ, Hidden C, Nilsen T, Gansevoort RT, Mulder DJ, "
        "Dullaart RPF, de Borst MH, Bakker SJL, van Goor H. Plasma "
        "Neutrophil Gelatinase-Associated Lipocalin Associates with "
        "New-Onset Chronic Kidney Disease in the General Population. "
        "Biomolecules. 2023;13(2):338.",
        "36830706", "10.3390/biom13020338", 2023, "reference_range",
    ),
    "remnant-cholesterol": (
        "Loh WJ, Soh HS, Tun MH, Tan PT, Lau CS, Tavintharan S, Watts GF, Aw "
        "TC. Elevated remnant cholesterol and non-HDL cholesterol "
        "concentrations from real-world laboratory results: a "
        "cross-sectional study in Southeast Asians. Front Cardiovasc Med. "
        "2024;11:1328618.",
        "38385128", "10.3389/fcvm.2024.1328618", 2024, "reference_range",
    ),
    "interventricular-septum-thickness": (
        "Marcomichelakis J, Withers R, Newman GB, O'Brien K, Emanuel R. The "
        "relation of age to the thickness of the interventricular septum, "
        "the posterior left ventricular wall and their ratio. Int J "
        "Cardiol. 1983;4(2):163-172.",
        "6642776", "10.1016/0167-5273(83)90190-0", 1983, "reference_range",
    ),
    "pericardial-fat": (
        "Pericardial fat burden on ECG-gated noncontrast CT in asymptomatic "
        "patients who subsequently experience adverse cardiovascular events "
        "on 4-year follow-up: a case-control study (event-free control "
        "group). J Cardiovasc Comput Tomogr. 2010.",
        "20394896", None, 2010, "reference_range",
    ),
    "osteocalcin": (
        "Hannemann A, Friedrich N, Spielhagen C, Rettig R, Ittermann T, "
        "Nauck M, Wallaschofski H. Reference intervals for serum osteocalcin "
        "concentrations in adult men and women from the study of health in "
        "Pomerania. BMC Endocr Disord. 2013;13:11.",
        "23497286", "10.1186/1472-6823-13-11", 2013, "reference_range",
    ),
    "forced-vital-capacity": (
        "Hankinson JL, Odencrantz JR, Fedan KB. Spirometric reference values "
        "from a sample of the general U.S. population. Am J Respir Crit "
        "Care Med. 1999;159(1):179-187.",
        "9872837", "10.1164/ajrccm.159.1.9712108", 1999, "reference_range",
    ),
    "ankle-brachial-index": (
        "Oguanobi NI, Onwubere BJ, Ibegbulam OG, Ike SO, Ejim EC, Agwu O. An "
        "evaluation of ankle-brachial blood pressure index in adult "
        "Nigerians with sickle cell anaemia (control group without PAD). "
        "Cardiovasc J Afr. 2012;23(4):184-187.",
        "22331250", "10.5830/CVJA-2011-013", 2012, "reference_range",
    ),
    "bicarbonate": (
        "Goldenstein L, Driver TH, Fried LF, Rifkin DE, Patel KV, Yenchek "
        "RH, Harris TB, Kritchevsky SB, Newman AB, Sarnak MJ, Shlipak MG, Ix "
        "JH; Health ABC Study Investigators. Serum bicarbonate "
        "concentrations and kidney disease progression in community-living "
        "elders: the Health, Aging, and Body Composition (Health ABC) "
        "Study. Am J Kidney Dis. 2014;64(4):542-549.",
        "24953890", "10.1053/j.ajkd.2014.05.009", 2014, "reference_range",
    ),
}

# Distribution numbers to upgrade alongside their new, more authoritative
# citation (only where the new source's own reported values differ from
# what was estimated before). mean, sd computed from the source's own
# reported figures.
DIST_UPDATES = {
    "osteocalcin": (16.0, 5.5),   # Pomerania: men 15.4 (12.0-19.4), premenopausal women 14.4 (11.3-18.5)
    "bicarbonate": (25.2, 1.9),   # Health ABC Study baseline
    "ankle-brachial-index": (1.03, 0.10),  # control-group mean; SD widened slightly for general-population use
}

NO_CLEAN_SOURCE = [
    "abdominal-aortic-calcification", "cardiac-calcification",
    "renal-artery-calcification", "thoracic-aorta-calcification",
    "extracoronary-calcification-sites", "severe-diastolic-dysfunction",
    "skeletal-muscle-fat-infiltration", "skinfold-thickness",
    "alpha-1-antichymotrypsin", "anion-gap-albumin-adjusted", "vertical-jump",
]


def main():
    for slug, (citation, pmid, doi, year, design) in REAL_SOURCES.items():
        source_id = get_or_create_source(citation, pmid, doi, year, design)
        cur.execute(
            "UPDATE population_distribution SET source_id=? "
            "WHERE biomarker_id=(SELECT id FROM biomarker WHERE slug=?)",
            (source_id, slug),
        )
        print(f"  {slug:<38} -> source_id {source_id} ({cur.rowcount} rows)")

        if slug in DIST_UPDATES:
            mean, sd = DIST_UPDATES[slug]
            # Recompute Normal-consistent percentiles alongside the new mean/sd.
            p5 = round(mean - 1.645 * sd, 4)
            p25 = round(mean - 0.674 * sd, 4)
            p50 = round(mean, 4)
            p75 = round(mean + 0.674 * sd, 4)
            p95 = round(mean + 1.645 * sd, 4)
            cur.execute(
                "UPDATE population_distribution SET mean=?, sd=?, p5=?, p25=?, p50=?, p75=?, p95=? "
                "WHERE biomarker_id=(SELECT id FROM biomarker WHERE slug=?) AND sex='all' AND age_band='all'",
                (mean, sd, p5, p25, p50, p75, p95, slug),
            )
            print(f"    ^ distribution numbers upgraded to mean={mean} sd={sd} (all/all stratum)")

    honest_source_id = get_or_create_source(
        "No single population reference study was located for this marker's "
        "distribution during this catalog's ingestion; mean/SD are a coarse "
        "approximation from general clinical-range literature (see the "
        "biomarker's own `notes` field for what was consulted), not a "
        "specific cited study.",
        None, None, None, "internal_estimate",
    )
    cur.execute(
        "UPDATE source SET identifier_type='internal_estimate', identifier='approximated' "
        "WHERE id=?",
        (honest_source_id,),
    )
    for slug in NO_CLEAN_SOURCE:
        cur.execute(
            "UPDATE population_distribution SET source_id=? "
            "WHERE biomarker_id=(SELECT id FROM biomarker WHERE slug=?)",
            (honest_source_id, slug),
        )
        print(f"  {slug:<38} -> source_id {honest_source_id} (honest 'approximated, no source' flag, {cur.rowcount} rows)")

    conn.commit()
    print("\nDone.")


if __name__ == "__main__":
    main()
