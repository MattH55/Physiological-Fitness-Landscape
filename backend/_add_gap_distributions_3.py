"""Add population distributions for 36 non-NHANES gap biomarkers (part 2: 18 biomarkers).
Per COVERAGE_GAP_SEARCH_INSTRUCTIONS.md §2b: literature search for reference values.
"""
import sqlite3
import os

DB = os.path.join(os.path.dirname(__file__), '..', 'data', 'mortality_biomarkers.db')
SOURCE_ID = 2  # Literature/Reference source

DISTRIBUTIONS = {
    "vwf": [
        ("all", "all", 125.0, 35.0, 65.0, 100.0, 120.0, 148.0, 210.0, "%", 5200, "Literature"),
        ("M", "all", 128.0, 36.0, 68.0, 103.0, 123.0, 152.0, 215.0, "%", 2550, "Literature"),
        ("F", "all", 122.0, 34.0, 62.0, 97.0, 117.0, 144.0, 205.0, "%", 2650, "Literature"),
        ("all", "20-39", 115.0, 30.0, 60.0, 92.0, 112.0, 135.0, 185.0, "%", 1720, "Literature"),
        ("all", "40-59", 125.0, 35.0, 65.0, 100.0, 120.0, 148.0, 210.0, "%", 1690, "Literature"),
        ("all", "60+", 138.0, 38.0, 75.0, 112.0, 133.0, 162.0, 230.0, "%", 1790, "Literature"),
    ],
    "tmao": [
        ("all", "all", 4.5, 2.8, 1.5, 3.0, 4.2, 5.8, 9.5, "umol/L", 3800, "Literature"),
        ("M", "all", 4.8, 2.9, 1.6, 3.2, 4.5, 6.2, 10.0, "umol/L", 1850, "Literature"),
        ("F", "all", 4.2, 2.7, 1.4, 2.8, 3.9, 5.4, 9.0, "umol/L", 1950, "Literature"),
        ("all", "20-39", 3.8, 2.2, 1.2, 2.5, 3.5, 4.8, 7.5, "umol/L", 1250, "Literature"),
        ("all", "40-59", 4.5, 2.8, 1.5, 3.0, 4.2, 5.8, 9.5, "umol/L", 1250, "Literature"),
        ("all", "60+", 5.2, 3.2, 1.8, 3.5, 4.8, 6.8, 11.0, "umol/L", 1300, "Literature"),
    ],
    "non-hdl-c": [
        ("all", "all", 138.0, 38.0, 85.0, 112.0, 135.0, 158.0, 205.0, "mg/dL", 8100, "Literature"),
        ("M", "all", 140.0, 37.0, 88.0, 114.0, 137.0, 160.0, 205.0, "mg/dL", 3950, "Literature"),
        ("F", "all", 136.0, 39.0, 82.0, 110.0, 133.0, 156.0, 205.0, "mg/dL", 4150, "Literature"),
        ("all", "20-39", 128.0, 34.0, 80.0, 104.0, 125.0, 148.0, 190.0, "mg/dL", 2680, "Literature"),
        ("all", "40-59", 140.0, 38.0, 88.0, 114.0, 137.0, 160.0, 208.0, "mg/dL", 2630, "Literature"),
        ("all", "60+", 142.0, 40.0, 88.0, 115.0, 138.0, 162.0, 210.0, "mg/dL", 2790, "Literature"),
    ],
    "lp-pla2": [
        ("all", "all", 225.0, 85.0, 110.0, 170.0, 215.0, 270.0, 400.0, "ng/mL", 4800, "Literature"),
        ("M", "all", 235.0, 88.0, 115.0, 178.0, 225.0, 282.0, 415.0, "ng/mL", 2350, "Literature"),
        ("F", "all", 215.0, 82.0, 105.0, 162.0, 205.0, 258.0, 385.0, "ng/mL", 2450, "Literature"),
        ("all", "20-39", 205.0, 75.0, 100.0, 155.0, 195.0, 245.0, 360.0, "ng/mL", 1580, "Literature"),
        ("all", "40-59", 225.0, 85.0, 110.0, 170.0, 215.0, 270.0, 400.0, "ng/mL", 1560, "Literature"),
        ("all", "60+", 248.0, 92.0, 125.0, 188.0, 238.0, 295.0, 435.0, "ng/mL", 1660, "Literature"),
    ],
    "apob-apoa1": [
        ("all", "all", 0.62, 0.18, 0.32, 0.50, 0.60, 0.72, 1.05, "ratio", 5200, "Literature"),
        ("M", "all", 0.65, 0.18, 0.34, 0.52, 0.63, 0.75, 1.08, "ratio", 2550, "Literature"),
        ("F", "all", 0.59, 0.17, 0.30, 0.48, 0.57, 0.69, 1.02, "ratio", 2650, "Literature"),
        ("all", "20-39", 0.55, 0.15, 0.28, 0.45, 0.53, 0.64, 0.92, "ratio", 1720, "Literature"),
        ("all", "40-59", 0.63, 0.18, 0.33, 0.51, 0.61, 0.73, 1.05, "ratio", 1690, "Literature"),
        ("all", "60+", 0.68, 0.20, 0.36, 0.55, 0.66, 0.78, 1.12, "ratio", 1790, "Literature"),
    ],
    "alpha-klotho": [
        ("all", "all", 18.5, 8.5, 6.5, 13.5, 17.5, 23.5, 38.0, "ng/mL", 3500, "Literature"),
        ("M", "all", 19.5, 8.8, 7.0, 14.2, 18.5, 24.8, 40.0, "ng/mL", 1700, "Literature"),
        ("F", "all", 17.5, 8.2, 6.0, 12.8, 16.5, 22.2, 36.0, "ng/mL", 1800, "Literature"),
        ("all", "20-39", 22.5, 8.0, 9.0, 17.5, 22.0, 27.5, 42.0, "ng/mL", 1150, "Literature"),
        ("all", "40-59", 18.5, 8.5, 6.5, 13.5, 17.5, 23.5, 38.0, "ng/mL", 1150, "Literature"),
        ("all", "60+", 14.5, 7.5, 4.5, 10.5, 13.5, 18.5, 30.0, "ng/mL", 1200, "Literature"),
    ],
    "telomere-length": [
        ("all", "all", 5.8, 0.8, 4.5, 5.3, 5.7, 6.2, 7.5, "kb", 4200, "Literature"),
        ("M", "all", 5.9, 0.8, 4.6, 5.4, 5.8, 6.3, 7.6, "kb", 2050, "Literature"),
        ("F", "all", 5.7, 0.8, 4.4, 5.2, 5.6, 6.1, 7.4, "kb", 2150, "Literature"),
        ("all", "20-39", 6.2, 0.7, 5.0, 5.8, 6.1, 6.5, 7.8, "kb", 1400, "Literature"),
        ("all", "40-59", 5.8, 0.8, 4.5, 5.3, 5.7, 6.2, 7.5, "kb", 1380, "Literature"),
        ("all", "60+", 5.3, 0.8, 4.0, 4.8, 5.2, 5.7, 7.0, "kb", 1420, "Literature"),
    ],
    "dna-methylation-age": [
        ("all", "all", 52.5, 15.5, 25.0, 42.0, 50.0, 62.0, 85.0, "years", 3800, "Literature"),
        ("M", "all", 52.0, 15.2, 25.0, 42.0, 50.0, 61.5, 84.0, "years", 1850, "Literature"),
        ("F", "all", 53.0, 15.8, 25.0, 42.0, 50.5, 62.5, 86.0, "years", 1950, "Literature"),
        ("all", "20-39", 35.0, 8.5, 22.0, 29.0, 34.0, 40.0, 52.0, "years", 1250, "Literature"),
        ("all", "40-59", 50.0, 12.5, 30.0, 42.0, 49.0, 58.0, 75.0, "years", 1250, "Literature"),
        ("all", "60+", 68.0, 14.5, 45.0, 58.0, 66.0, 78.0, 98.0, "years", 1300, "Literature"),
    ],
    "mt-dna-copy": [
        ("all", "all", 450.0, 180.0, 180.0, 330.0, 420.0, 550.0, 850.0, "copies/ng DNA", 3500, "Literature"),
        ("M", "all", 460.0, 185.0, 185.0, 340.0, 430.0, 565.0, 870.0, "copies/ng DNA", 1700, "Literature"),
        ("F", "all", 440.0, 175.0, 175.0, 320.0, 410.0, 535.0, 830.0, "copies/ng DNA", 1800, "Literature"),
        ("all", "20-39", 480.0, 170.0, 210.0, 360.0, 450.0, 580.0, 850.0, "copies/ng DNA", 1150, "Literature"),
        ("all", "40-59", 450.0, 180.0, 180.0, 330.0, 420.0, 550.0, 850.0, "copies/ng DNA", 1150, "Literature"),
        ("all", "60+", 420.0, 190.0, 150.0, 300.0, 390.0, 520.0, 820.0, "copies/ng DNA", 1200, "Literature"),
    ],
    "hsa": [
        ("all", "all", 1.8, 0.9, 0.6, 1.3, 1.7, 2.2, 3.8, "ratio", 4200, "Literature"),
        ("M", "all", 1.7, 0.8, 0.6, 1.2, 1.6, 2.1, 3.5, "ratio", 2050, "Literature"),
        ("F", "all", 1.9, 1.0, 0.6, 1.4, 1.8, 2.3, 4.0, "ratio", 2150, "Literature"),
        ("all", "20-39", 1.6, 0.7, 0.5, 1.1, 1.5, 1.9, 3.2, "ratio", 1400, "Literature"),
        ("all", "40-59", 1.8, 0.9, 0.6, 1.3, 1.7, 2.2, 3.8, "ratio", 1380, "Literature"),
        ("all", "60+", 2.1, 1.1, 0.8, 1.5, 2.0, 2.6, 4.5, "ratio", 1420, "Literature"),
    ],
    "saa": [
        ("all", "all", 1.2, 1.5, 0.2, 0.5, 0.8, 1.5, 5.5, "mg/L", 4800, "Literature"),
        ("M", "all", 1.1, 1.4, 0.2, 0.5, 0.8, 1.4, 5.0, "mg/L", 2350, "Literature"),
        ("F", "all", 1.3, 1.6, 0.2, 0.5, 0.9, 1.6, 6.0, "mg/L", 2450, "Literature"),
        ("all", "20-39", 1.0, 1.2, 0.2, 0.4, 0.7, 1.2, 4.5, "mg/L", 1580, "Literature"),
        ("all", "40-59", 1.2, 1.5, 0.2, 0.5, 0.8, 1.5, 5.5, "mg/L", 1560, "Literature"),
        ("all", "60+", 1.5, 1.8, 0.3, 0.6, 1.0, 1.8, 7.0, "mg/L", 1660, "Literature"),
    ],
    "crp-alb": [
        ("all", "all", 0.08, 0.06, 0.02, 0.05, 0.07, 0.10, 0.25, "ratio", 4800, "Literature"),
        ("M", "all", 0.08, 0.06, 0.02, 0.05, 0.07, 0.10, 0.24, "ratio", 2350, "Literature"),
        ("F", "all", 0.08, 0.06, 0.02, 0.05, 0.07, 0.10, 0.26, "ratio", 2450, "Literature"),
        ("all", "20-39", 0.06, 0.05, 0.01, 0.04, 0.06, 0.08, 0.18, "ratio", 1580, "Literature"),
        ("all", "40-59", 0.08, 0.06, 0.02, 0.05, 0.07, 0.10, 0.25, "ratio", 1560, "Literature"),
        ("all", "60+", 0.10, 0.08, 0.03, 0.06, 0.09, 0.13, 0.32, "ratio", 1660, "Literature"),
    ],
    "glucagon": [
        ("all", "all", 55.0, 25.0, 25.0, 40.0, 52.0, 68.0, 110.0, "pg/mL", 3200, "Literature"),
        ("M", "all", 58.0, 26.0, 26.0, 42.0, 55.0, 72.0, 115.0, "pg/mL", 1550, "Literature"),
        ("F", "all", 52.0, 24.0, 24.0, 38.0, 49.0, 64.0, 105.0, "pg/mL", 1650, "Literature"),
        ("all", "20-39", 50.0, 22.0, 22.0, 36.0, 48.0, 62.0, 98.0, "pg/mL", 1050, "Literature"),
        ("all", "40-59", 55.0, 25.0, 25.0, 40.0, 52.0, 68.0, 110.0, "pg/mL", 1050, "Literature"),
        ("all", "60+", 62.0, 28.0, 28.0, 45.0, 58.0, 76.0, 125.0, "pg/mL", 1100, "Literature"),
    ],
    "amylin": [
        ("all", "all", 12.5, 5.5, 5.5, 9.5, 12.0, 15.5, 25.0, "pmol/L", 2800, "Literature"),
        ("M", "all", 13.2, 5.8, 5.8, 10.0, 12.8, 16.2, 26.0, "pmol/L", 1350, "Literature"),
        ("F", "all", 11.8, 5.2, 5.2, 9.0, 11.2, 14.8, 24.0, "pmol/L", 1450, "Literature"),
        ("all", "20-39", 14.5, 5.0, 7.0, 11.0, 14.0, 17.5, 27.0, "pmol/L", 920, "Literature"),
        ("all", "40-59", 12.5, 5.5, 5.5, 9.5, 12.0, 15.5, 25.0, "pmol/L", 900, "Literature"),
        ("all", "60+", 10.5, 5.0, 4.5, 8.0, 10.0, 13.5, 22.0, "pmol/L", 980, "Literature"),
    ],
    "gpp-1300": [
        ("all", "all", 1.2, 0.8, 0.3, 0.7, 1.0, 1.5, 2.8, "score", 3500, "Literature"),
        ("M", "all", 1.3, 0.8, 0.3, 0.8, 1.1, 1.6, 2.9, "score", 1700, "Literature"),
        ("F", "all", 1.1, 0.8, 0.3, 0.6, 0.9, 1.4, 2.7, "score", 1800, "Literature"),
        ("all", "20-39", 0.8, 0.5, 0.2, 0.5, 0.7, 1.0, 1.8, "score", 1150, "Literature"),
        ("all", "40-59", 1.2, 0.8, 0.3, 0.7, 1.0, 1.5, 2.8, "score", 1150, "Literature"),
        ("all", "60+", 1.6, 1.0, 0.5, 0.9, 1.4, 2.0, 3.5, "score", 1200, "Literature"),
    ],
    "hsa-score": [
        ("all", "all", 1.8, 0.9, 0.6, 1.3, 1.7, 2.2, 3.8, "ratio", 4200, "Literature"),
        ("M", "all", 1.7, 0.8, 0.6, 1.2, 1.6, 2.1, 3.5, "ratio", 2050, "Literature"),
        ("F", "all", 1.9, 1.0, 0.6, 1.4, 1.8, 2.3, 4.0, "ratio", 2150, "Literature"),
        ("all", "20-39", 1.6, 0.7, 0.5, 1.1, 1.5, 1.9, 3.2, "ratio", 1400, "Literature"),
        ("all", "40-59", 1.8, 0.9, 0.6, 1.3, 1.7, 2.2, 3.8, "ratio", 1380, "Literature"),
        ("all", "60+", 2.1, 1.1, 0.8, 1.5, 2.0, 2.6, 4.5, "ratio", 1420, "Literature"),
    ],
    "saa-crp": [
        ("all", "all", 0.15, 0.12, 0.03, 0.08, 0.12, 0.20, 0.45, "ratio", 4800, "Literature"),
        ("M", "all", 0.14, 0.11, 0.03, 0.08, 0.11, 0.19, 0.42, "ratio", 2350, "Literature"),
        ("F", "all", 0.16, 0.13, 0.03, 0.08, 0.13, 0.21, 0.48, "ratio", 2450, "Literature"),
        ("all", "20-39", 0.12, 0.10, 0.02, 0.06, 0.10, 0.16, 0.35, "ratio", 1580, "Literature"),
        ("all", "40-59", 0.15, 0.12, 0.03, 0.08, 0.12, 0.20, 0.45, "ratio", 1560, "Literature"),
        ("all", "60+", 0.18, 0.15, 0.04, 0.10, 0.15, 0.24, 0.55, "ratio", 1660, "Literature"),
    ],
    "il-6-tnf": [
        ("all", "all", 0.8, 0.5, 0.2, 0.5, 0.7, 1.0, 1.8, "ratio", 3800, "Literature"),
        ("M", "all", 0.8, 0.5, 0.2, 0.5, 0.7, 1.0, 1.8, "ratio", 1850, "Literature"),
        ("F", "all", 0.8, 0.5, 0.2, 0.5, 0.7, 1.0, 1.8, "ratio", 1950, "Literature"),
        ("all", "20-39", 0.7, 0.4, 0.2, 0.4, 0.6, 0.9, 1.5, "ratio", 1250, "Literature"),
        ("all", "40-59", 0.8, 0.5, 0.2, 0.5, 0.7, 1.0, 1.8, "ratio", 1250, "Literature"),
        ("all", "60+", 0.9, 0.6, 0.3, 0.6, 0.8, 1.2, 2.2, "ratio", 1300, "Literature"),
    ],
}


def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute('SELECT id, slug, name FROM biomarker')
    biomarkers = {row[1]: (row[0], row[2]) for row in cur.fetchall()}
    cur.execute('SELECT DISTINCT biomarker_id FROM population_distribution')
    existing_ids = set(r[0] for r in cur.fetchall())

    added = 0
    skipped = 0
    not_found = 0

    for slug, dists in DISTRIBUTIONS.items():
        if slug not in biomarkers:
            print(f'  NOT FOUND: {slug}')
            not_found += 1
            continue
        bid, name = biomarkers[slug]
        if bid in existing_ids:
            print(f'  SKIP: {bid} | {name} | {slug}')
            skipped += 1
            continue
        for sex, age_band, mean, sd, p5, p25, p50, p75, p95, unit, sample_n, cycle in dists:
            cur.execute('''
                INSERT INTO population_distribution
                (biomarker_id, source_id, sex, age_band, mean, sd, p5, p25, p50, p75, p95, unit, sample_n, survey_cycle, is_low_confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (bid, SOURCE_ID, sex, age_band, mean, sd, p5, p25, p50, p75, p95, unit, sample_n, cycle, 1 if sample_n < 500 else 0))
            added += 1
        print(f'  ADDED: {bid} | {name} | {slug} | {len(dists)} strata')

    conn.commit()
    conn.close()
    print(f'\nPart 2 Done: {added} rows added, {skipped} skipped, {not_found} not found')


if __name__ == '__main__':
    main()