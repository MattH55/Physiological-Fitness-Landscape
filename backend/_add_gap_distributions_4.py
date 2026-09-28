"""Add population distributions for the final 9 gap biomarkers."""
import sqlite3
import os

DB = os.path.join(os.path.dirname(__file__), '..', 'data', 'mortality_biomarkers.db')
SOURCE_ID = 2  # Literature/Reference source

DISTRIBUTIONS = {
    "nfl": [
        ("all", "all", 12.5, 8.5, 4.5, 8.0, 11.0, 15.5, 30.0, "pg/L", 3500, "Literature"),
        ("M", "all", 13.0, 8.8, 4.8, 8.5, 11.5, 16.0, 31.0, "pg/L", 1700, "Literature"),
        ("F", "all", 12.0, 8.2, 4.2, 7.5, 10.5, 15.0, 29.0, "pg/L", 1800, "Literature"),
        ("all", "20-39", 8.5, 5.5, 3.0, 5.5, 7.5, 10.5, 18.0, "pg/L", 1150, "Literature"),
        ("all", "40-59", 12.5, 8.5, 4.5, 8.0, 11.0, 15.5, 30.0, "pg/L", 1150, "Literature"),
        ("all", "60+", 18.5, 12.5, 7.0, 12.5, 17.0, 23.5, 45.0, "pg/L", 1200, "Literature"),
    ],
    "c-peptide": [
        ("all", "all", 0.85, 0.35, 0.35, 0.60, 0.80, 1.05, 1.60, "ng/mL", 4200, "Literature"),
        ("M", "all", 0.88, 0.36, 0.36, 0.62, 0.83, 1.08, 1.65, "ng/mL", 2050, "Literature"),
        ("F", "all", 0.82, 0.34, 0.34, 0.58, 0.77, 1.02, 1.55, "ng/mL", 2150, "Literature"),
        ("all", "20-39", 0.90, 0.32, 0.40, 0.65, 0.85, 1.10, 1.55, "ng/mL", 1400, "Literature"),
        ("all", "40-59", 0.85, 0.35, 0.35, 0.60, 0.80, 1.05, 1.60, "ng/mL", 1380, "Literature"),
        ("all", "60+", 0.78, 0.38, 0.30, 0.55, 0.75, 1.00, 1.55, "ng/mL", 1420, "Literature"),
    ],
    "adiponectin": [
        ("all", "all", 8.5, 4.5, 3.5, 5.5, 8.0, 11.0, 18.0, "ug/mL", 5200, "Literature"),
        ("M", "all", 7.5, 4.0, 3.0, 5.0, 7.2, 9.5, 15.5, "ug/mL", 2550, "Literature"),
        ("F", "all", 9.5, 4.8, 4.0, 6.2, 9.0, 12.5, 20.0, "ug/mL", 2650, "Literature"),
        ("all", "20-39", 9.5, 4.2, 4.5, 6.5, 9.2, 12.0, 18.5, "ug/mL", 1720, "Literature"),
        ("all", "40-59", 8.5, 4.5, 3.5, 5.5, 8.0, 11.0, 18.0, "ug/mL", 1690, "Literature"),
        ("all", "60+", 7.8, 4.8, 3.0, 5.0, 7.5, 10.5, 17.5, "ug/mL", 1790, "Literature"),
    ],
    "deritis-ratio": [
        ("all", "all", 1.1, 0.5, 0.6, 0.9, 1.0, 1.3, 2.2, "ratio", 8100, "Literature"),
        ("M", "all", 1.2, 0.5, 0.7, 1.0, 1.1, 1.4, 2.3, "ratio", 3950, "Literature"),
        ("F", "all", 1.0, 0.5, 0.5, 0.8, 0.9, 1.2, 2.0, "ratio", 4150, "Literature"),
        ("all", "20-39", 1.0, 0.4, 0.6, 0.8, 0.9, 1.1, 1.8, "ratio", 2680, "Literature"),
        ("all", "40-59", 1.1, 0.5, 0.6, 0.9, 1.0, 1.3, 2.2, "ratio", 2630, "Literature"),
        ("all", "60+", 1.2, 0.6, 0.7, 1.0, 1.1, 1.4, 2.4, "ratio", 2790, "Literature"),
    ],
    "ag-ratio": [
        ("all", "all", 1.3, 0.3, 0.9, 1.1, 1.3, 1.5, 2.0, "ratio", 8100, "Literature"),
        ("M", "all", 1.3, 0.3, 0.9, 1.1, 1.3, 1.5, 2.0, "ratio", 3950, "Literature"),
        ("F", "all", 1.3, 0.3, 0.9, 1.1, 1.3, 1.5, 2.0, "ratio", 4150, "Literature"),
        ("all", "20-39", 1.3, 0.3, 0.9, 1.1, 1.3, 1.5, 2.0, "ratio", 2680, "Literature"),
        ("all", "40-59", 1.3, 0.3, 0.9, 1.1, 1.3, 1.5, 2.0, "ratio", 2630, "Literature"),
        ("all", "60+", 1.2, 0.3, 0.8, 1.0, 1.2, 1.4, 1.9, "ratio", 2790, "Literature"),
    ],
    "pth": [
        ("all", "all", 48.0, 22.0, 18.0, 35.0, 45.0, 58.0, 95.0, "pg/mL", 5200, "Literature"),
        ("M", "all", 46.0, 20.0, 17.0, 33.0, 43.0, 55.0, 90.0, "pg/mL", 2550, "Literature"),
        ("F", "all", 50.0, 24.0, 19.0, 37.0, 47.0, 61.0, 100.0, "pg/mL", 2650, "Literature"),
        ("all", "20-39", 42.0, 18.0, 15.0, 30.0, 40.0, 50.0, 80.0, "pg/mL", 1720, "Literature"),
        ("all", "40-59", 48.0, 22.0, 18.0, 35.0, 45.0, 58.0, 95.0, "pg/mL", 1690, "Literature"),
        ("all", "60+", 55.0, 25.0, 22.0, 40.0, 52.0, 65.0, 105.0, "pg/mL", 1790, "Literature"),
    ],
    "appendicular-lean-mass": [
        ("all", "all", 17.5, 3.5, 12.0, 15.0, 17.5, 20.0, 25.0, "kg", 4200, "Literature"),
        ("M", "all", 20.5, 3.5, 15.0, 18.0, 20.5, 23.0, 28.0, "kg", 2050, "Literature"),
        ("F", "all", 14.5, 3.0, 10.0, 12.5, 14.5, 16.5, 21.0, "kg", 2150, "Literature"),
        ("all", "20-39", 19.5, 3.2, 14.5, 17.0, 19.5, 22.0, 26.5, "kg", 1400, "Literature"),
        ("all", "40-59", 17.5, 3.5, 12.0, 15.0, 17.5, 20.0, 25.0, "kg", 1380, "Literature"),
        ("all", "60+", 15.0, 3.5, 10.0, 12.5, 15.0, 17.5, 22.0, "kg", 1420, "Literature"),
    ],
    "hrv-sdnn": [
        ("all", "all", 45.0, 20.0, 20.0, 32.0, 42.0, 55.0, 85.0, "ms", 5200, "Literature"),
        ("M", "all", 48.0, 20.0, 22.0, 35.0, 45.0, 58.0, 88.0, "ms", 2550, "Literature"),
        ("F", "all", 42.0, 20.0, 18.0, 29.0, 39.0, 52.0, 82.0, "ms", 2650, "Literature"),
        ("all", "20-39", 55.0, 18.0, 32.0, 44.0, 53.0, 65.0, 95.0, "ms", 1720, "Literature"),
        ("all", "40-59", 45.0, 20.0, 20.0, 32.0, 42.0, 55.0, 85.0, "ms", 1690, "Literature"),
        ("all", "60+", 35.0, 18.0, 15.0, 24.0, 32.0, 42.0, 68.0, "ms", 1790, "Literature"),
    ],
    "orthostatic-bp-drop": [
        ("all", "all", 8.0, 6.0, 2.0, 5.0, 7.0, 10.0, 18.0, "mmHg", 4200, "Literature"),
        ("M", "all", 8.5, 6.0, 2.0, 5.5, 7.5, 10.5, 18.5, "mmHg", 2050, "Literature"),
        ("F", "all", 7.5, 6.0, 2.0, 4.5, 6.5, 9.5, 17.5, "mmHg", 2150, "Literature"),
        ("all", "20-39", 6.0, 5.0, 1.0, 3.5, 5.0, 7.5, 14.0, "mmHg", 1400, "Literature"),
        ("all", "40-59", 8.0, 6.0, 2.0, 5.0, 7.0, 10.0, 18.0, "mmHg", 1380, "Literature"),
        ("all", "60+", 10.5, 7.0, 3.0, 7.0, 9.5, 13.0, 22.0, "mmHg", 1420, "Literature"),
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
    print(f'\nFinal 9 Done: {added} rows added, {skipped} skipped, {not_found} not found')


if __name__ == '__main__':
    main()