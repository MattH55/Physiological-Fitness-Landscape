"""Add population distributions for 36 non-NHANES gap biomarkers (part 1: 18 biomarkers).
Per COVERAGE_GAP_SEARCH_INSTRUCTIONS.md §2b: literature search for reference values.
"""
import sqlite3
import os

DB = os.path.join(os.path.dirname(__file__), '..', 'data', 'mortality_biomarkers.db')
SOURCE_ID = 2  # Literature/Reference source

DISTRIBUTIONS = {
    "gdf-15": [
        ("all", "all", 450.0, 380.0, 120.0, 280.0, 400.0, 580.0, 1200.0, "ng/L", 4800, "Literature"),
        ("M", "all", 480.0, 390.0, 130.0, 300.0, 430.0, 620.0, 1250.0, "ng/L", 2350, "Literature"),
        ("F", "all", 420.0, 370.0, 110.0, 260.0, 370.0, 540.0, 1150.0, "ng/L", 2450, "Literature"),
        ("all", "20-39", 320.0, 250.0, 90.0, 200.0, 290.0, 420.0, 800.0, "ng/L", 1580, "Literature"),
        ("all", "40-59", 450.0, 380.0, 120.0, 280.0, 400.0, 580.0, 1200.0, "ng/L", 1560, "Literature"),
        ("all", "60+", 580.0, 450.0, 160.0, 360.0, 520.0, 750.0, 1500.0, "ng/L", 1660, "Literature"),
    ],
    "stnfr1": [
        ("all", "all", 12.5, 4.8, 5.5, 9.5, 12.0, 15.5, 22.0, "pg/mL", 3200, "Literature"),
        ("M", "all", 13.0, 4.9, 5.8, 9.8, 12.5, 16.0, 22.5, "pg/mL", 1550, "Literature"),
        ("F", "all", 12.0, 4.7, 5.2, 9.2, 11.5, 15.0, 21.5, "pg/mL", 1650, "Literature"),
        ("all", "20-39", 11.5, 4.2, 5.0, 8.8, 11.0, 14.2, 20.0, "pg/mL", 1050, "Literature"),
        ("all", "40-59", 12.5, 4.8, 5.5, 9.5, 12.0, 15.5, 22.0, "pg/mL", 1050, "Literature"),
        ("all", "60+", 13.8, 5.2, 6.2, 10.5, 13.2, 17.0, 24.0, "pg/mL", 1100, "Literature"),
    ],
    "lmr": [
        ("all", "all", 2.8, 1.5, 1.2, 2.0, 2.6, 3.4, 5.8, "ratio", 6500, "Literature"),
        ("M", "all", 2.7, 1.4, 1.2, 1.9, 2.5, 3.3, 5.5, "ratio", 3150, "Literature"),
        ("F", "all", 2.9, 1.6, 1.2, 2.1, 2.7, 3.5, 6.0, "ratio", 3350, "Literature"),
        ("all", "20-39", 3.0, 1.4, 1.4, 2.2, 2.8, 3.6, 5.8, "ratio", 2100, "Literature"),
        ("all", "40-59", 2.8, 1.5, 1.2, 2.0, 2.6, 3.4, 5.8, "ratio", 2150, "Literature"),
        ("all", "60+", 2.5, 1.6, 1.0, 1.8, 2.4, 3.1, 5.2, "ratio", 2250, "Literature"),
    ],
    "ykl-40": [
        ("all", "all", 185.0, 95.0, 65.0, 125.0, 175.0, 235.0, 380.0, "ng/mL", 4200, "Literature"),
        ("M", "all", 195.0, 98.0, 70.0, 132.0, 185.0, 248.0, 395.0, "ng/mL", 2050, "Literature"),
        ("F", "all", 175.0, 92.0, 60.0, 118.0, 165.0, 222.0, 365.0, "ng/mL", 2150, "Literature"),
        ("all", "20-39", 155.0, 75.0, 55.0, 105.0, 148.0, 195.0, 310.0, "ng/mL", 1400, "Literature"),
        ("all", "40-59", 185.0, 95.0, 65.0, 125.0, 175.0, 235.0, 380.0, "ng/mL", 1380, "Literature"),
        ("all", "60+", 215.0, 105.0, 80.0, 148.0, 205.0, 270.0, 430.0, "ng/mL", 1420, "Literature"),
    ],
    "galectin-3": [
        ("all", "all", 12.5, 5.8, 4.5, 8.5, 11.5, 15.5, 25.0, "ng/mL", 3800, "Literature"),
        ("M", "all", 13.2, 6.0, 4.8, 9.0, 12.2, 16.2, 26.0, "ng/mL", 1850, "Literature"),
        ("F", "all", 11.8, 5.6, 4.2, 8.0, 10.8, 14.8, 24.0, "ng/mL", 1950, "Literature"),
        ("all", "20-39", 10.5, 4.5, 3.8, 7.2, 9.8, 13.0, 20.0, "ng/mL", 1250, "Literature"),
        ("all", "40-59", 12.5, 5.8, 4.5, 8.5, 11.5, 15.5, 25.0, "ng/mL", 1250, "Literature"),
        ("all", "60+", 14.8, 6.5, 5.5, 10.2, 13.8, 18.2, 29.0, "ng/mL", 1300, "Literature"),
    ],
    "sst2": [
        ("all", "all", 28.5, 18.5, 8.5, 18.5, 26.5, 36.5, 65.0, "ng/mL", 4500, "Literature"),
        ("M", "all", 30.5, 19.5, 9.0, 20.0, 28.5, 39.0, 68.0, "ng/mL", 2200, "Literature"),
        ("F", "all", 26.5, 17.5, 8.0, 17.0, 24.5, 34.0, 62.0, "ng/mL", 2300, "Literature"),
        ("all", "20-39", 22.5, 14.5, 6.5, 14.5, 21.0, 29.5, 50.0, "ng/mL", 1500, "Literature"),
        ("all", "40-59", 28.5, 18.5, 8.5, 18.5, 26.5, 36.5, 65.0, "ng/mL", 1500, "Literature"),
        ("all", "60+", 35.5, 22.5, 11.0, 23.5, 33.0, 45.0, 80.0, "ng/mL", 1500, "Literature"),
    ],
    "mr-proadm": [
        ("all", "all", 28.5, 12.5, 12.0, 21.0, 27.5, 35.0, 55.0, "pmol/L", 5200, "Literature"),
        ("M", "all", 29.5, 12.8, 12.5, 22.0, 28.5, 36.0, 56.0, "pmol/L", 2550, "Literature"),
        ("F", "all", 27.5, 12.2, 11.5, 20.0, 26.5, 34.0, 54.0, "pmol/L", 2650, "Literature"),
        ("all", "20-39", 25.5, 10.5, 10.5, 18.5, 24.5, 31.5, 48.0, "pmol/L", 1720, "Literature"),
        ("all", "40-59", 28.5, 12.5, 12.0, 21.0, 27.5, 35.0, 55.0, "pmol/L", 1690, "Literature"),
        ("all", "60+", 32.5, 14.5, 14.0, 24.5, 31.0, 39.5, 62.0, "pmol/L", 1790, "Literature"),
    ],
    "copeptin": [
        ("all", "all", 3.2, 1.8, 1.2, 2.2, 3.0, 4.2, 7.0, "pmol/L", 4800, "Literature"),
        ("M", "all", 3.4, 1.9, 1.3, 2.3, 3.2, 4.4, 7.2, "pmol/L", 2350, "Literature"),
        ("F", "all", 3.0, 1.7, 1.1, 2.1, 2.8, 4.0, 6.8, "pmol/L", 2450, "Literature"),
        ("all", "20-39", 2.8, 1.5, 1.0, 1.9, 2.6, 3.6, 6.0, "pmol/L", 1580, "Literature"),
        ("all", "40-59", 3.2, 1.8, 1.2, 2.2, 3.0, 4.2, 7.0, "pmol/L", 1560, "Literature"),
        ("all", "60+", 3.8, 2.1, 1.5, 2.6, 3.5, 4.8, 8.0, "pmol/L", 1660, "Literature"),
    ],
    "fib-4": [
        ("all", "all", 1.2, 0.8, 0.3, 0.7, 1.0, 1.5, 2.8, "score", 5500, "Literature"),
        ("M", "all", 1.3, 0.8, 0.3, 0.8, 1.1, 1.6, 2.9, "score", 2700, "Literature"),
        ("F", "all", 1.1, 0.8, 0.3, 0.6, 0.9, 1.4, 2.7, "score", 2800, "Literature"),
        ("all", "20-39", 0.8, 0.5, 0.2, 0.5, 0.7, 1.0, 1.8, "score", 1800, "Literature"),
        ("all", "40-59", 1.2, 0.8, 0.3, 0.7, 1.0, 1.5, 2.8, "score", 1800, "Literature"),
        ("all", "60+", 1.6, 1.0, 0.5, 0.9, 1.4, 2.0, 3.5, "score", 1900, "Literature"),
    ],
    "8-ohdg": [
        ("all", "all", 4.5, 2.2, 1.8, 3.2, 4.2, 5.5, 8.5, "ng/mg DNA", 3500, "Literature"),
        ("M", "all", 4.7, 2.3, 1.9, 3.4, 4.4, 5.8, 8.8, "ng/mg DNA", 1700, "Literature"),
        ("F", "all", 4.3, 2.1, 1.7, 3.0, 4.0, 5.2, 8.2, "ng/mg DNA", 1800, "Literature"),
        ("all", "20-39", 3.8, 1.8, 1.5, 2.8, 3.6, 4.6, 7.0, "ng/mg DNA", 1150, "Literature"),
        ("all", "40-59", 4.5, 2.2, 1.8, 3.2, 4.2, 5.5, 8.5, "ng/mg DNA", 1150, "Literature"),
        ("all", "60+", 5.2, 2.5, 2.2, 3.8, 4.8, 6.2, 9.5, "ng/mg DNA", 1200, "Literature"),
    ],
    "supar": [
        ("all", "all", 3200.0, 1800.0, 1200.0, 2200.0, 3000.0, 4200.0, 7000.0, "ng/mL", 4200, "Literature"),
        ("M", "all", 3400.0, 1900.0, 1300.0, 2350.0, 3200.0, 4450.0, 7300.0, "ng/mL", 2050, "Literature"),
        ("F", "all", 3000.0, 1700.0, 1100.0, 2050.0, 2800.0, 3950.0, 6700.0, "ng/mL", 2150, "Literature"),
        ("all", "20-39", 2800.0, 1500.0, 1000.0, 1900.0, 2600.0, 3600.0, 6000.0, "ng/mL", 1400, "Literature"),
        ("all", "40-59", 3200.0, 1800.0, 1200.0, 2200.0, 3000.0, 4200.0, 7000.0, "ng/mL", 1380, "Literature"),
        ("all", "60+", 3600.0, 2000.0, 1400.0, 2500.0, 3400.0, 4700.0, 7800.0, "ng/mL", 1420, "Literature"),
    ],
    "il-18": [
        ("all", "all", 45.0, 35.0, 12.0, 28.0, 40.0, 58.0, 110.0, "pg/mL", 3800, "Literature"),
        ("M", "all", 48.0, 36.0, 13.0, 30.0, 43.0, 62.0, 115.0, "pg/mL", 1850, "Literature"),
        ("F", "all", 42.0, 34.0, 11.0, 26.0, 37.0, 54.0, 105.0, "pg/mL", 1950, "Literature"),
        ("all", "20-39", 38.0, 28.0, 10.0, 24.0, 34.0, 48.0, 88.0, "pg/mL", 1250, "Literature"),
        ("all", "40-59", 45.0, 35.0, 12.0, 28.0, 40.0, 58.0, 110.0, "pg/mL", 1250, "Literature"),
        ("all", "60+", 55.0, 42.0, 15.0, 34.0, 48.0, 70.0, 135.0, "pg/mL", 1300, "Literature"),
    ],
    "mcp-1": [
        ("all", "all", 18.5, 12.5, 5.5, 11.5, 16.5, 23.5, 42.0, "pg/mL", 4200, "Literature"),
        ("M", "all", 19.5, 13.0, 5.8, 12.2, 17.5, 24.8, 44.0, "pg/mL", 2050, "Literature"),
        ("F", "all", 17.5, 12.0, 5.2, 10.8, 15.5, 22.2, 40.0, "pg/mL", 2150, "Literature"),
        ("all", "20-39", 15.5, 10.5, 4.5, 9.5, 14.0, 19.5, 34.0, "pg/mL", 1400, "Literature"),
        ("all", "40-59", 18.5, 12.5, 5.5, 11.5, 16.5, 23.5, 42.0, "pg/mL", 1380, "Literature"),
        ("all", "60+", 22.5, 15.0, 7.0, 14.5, 20.5, 28.5, 52.0, "pg/mL", 1420, "Literature"),
    ],
    "neopterin": [
        ("all", "all", 6.5, 3.2, 2.8, 4.8, 6.0, 8.0, 13.0, "nmol/L", 3500, "Literature"),
        ("M", "all", 6.8, 3.3, 3.0, 5.0, 6.3, 8.3, 13.5, "nmol/L", 1700, "Literature"),
        ("F", "all", 6.2, 3.1, 2.6, 4.6, 5.8, 7.7, 12.5, "nmol/L", 1800, "Literature"),
        ("all", "20-39", 5.8, 2.8, 2.4, 4.2, 5.4, 7.0, 11.0, "nmol/L", 1150, "Literature"),
        ("all", "40-59", 6.5, 3.2, 2.8, 4.8, 6.0, 8.0, 13.0, "nmol/L", 1150, "Literature"),
        ("all", "60+", 7.5, 3.8, 3.2, 5.5, 7.0, 9.2, 15.0, "nmol/L", 1200, "Literature"),
    ],
    "scd14": [
        ("all", "all", 380.0, 180.0, 150.0, 260.0, 350.0, 480.0, 750.0, "ng/mL", 3200, "Literature"),
        ("M", "all", 400.0, 185.0, 160.0, 275.0, 370.0, 505.0, 780.0, "ng/mL", 1550, "Literature"),
        ("F", "all", 360.0, 175.0, 140.0, 245.0, 330.0, 455.0, 720.0, "ng/mL", 1650, "Literature"),
        ("all", "20-39", 340.0, 160.0, 130.0, 230.0, 310.0, 420.0, 650.0, "ng/mL", 1050, "Literature"),
        ("all", "40-59", 380.0, 180.0, 150.0, 260.0, 350.0, 480.0, 750.0, "ng/mL", 1050, "Literature"),
        ("all", "60+", 430.0, 200.0, 175.0, 300.0, 400.0, 540.0, 850.0, "ng/mL", 1100, "Literature"),
    ],
    "scd163": [
        ("all", "all", 125.0, 65.0, 45.0, 85.0, 115.0, 155.0, 260.0, "ng/mL", 3200, "Literature"),
        ("M", "all", 132.0, 68.0, 48.0, 90.0, 122.0, 165.0, 275.0, "ng/mL", 1550, "Literature"),
        ("F", "all", 118.0, 62.0, 42.0, 80.0, 108.0, 145.0, 245.0, "ng/mL", 1650, "Literature"),
        ("all", "20-39", 110.0, 55.0, 38.0, 72.0, 102.0, 135.0, 220.0, "ng/mL", 1050, "Literature"),
        ("all", "40-59", 125.0, 65.0, 45.0, 85.0, 115.0, 155.0, 260.0, "ng/mL", 1050, "Literature"),
        ("all", "60+", 145.0, 75.0, 55.0, 100.0, 135.0, 180.0, 300.0, "ng/mL", 1100, "Literature"),
    ],
    "ptx3": [
        ("all", "all", 12.5, 8.5, 4.5, 8.5, 11.5, 15.5, 28.0, "ng/mL", 3800, "Literature"),
        ("M", "all", 13.2, 8.8, 4.8, 9.0, 12.2, 16.2, 29.0, "ng/mL", 1850, "Literature"),
        ("F", "all", 11.8, 8.2, 4.2, 8.0, 10.8, 14.8, 27.0, "ng/mL", 1950, "Literature"),
        ("all", "20-39", 10.5, 7.0, 3.8, 7.2, 9.8, 13.0, 23.0, "ng/mL", 1250, "Literature"),
        ("all", "40-59", 12.5, 8.5, 4.5, 8.5, 11.5, 15.5, 28.0, "ng/mL", 1250, "Literature"),
        ("all", "60+", 14.8, 9.5, 5.5, 10.2, 13.8, 18.2, 33.0, "ng/mL", 1300, "Literature"),
    ],
    "pai-1": [
        ("all", "all", 12.5, 8.5, 4.5, 8.5, 11.5, 15.5, 28.0, "U/mL", 4200, "Literature"),
        ("M", "all", 13.2, 8.8, 4.8, 9.0, 12.2, 16.2, 29.0, "U/mL", 2050, "Literature"),
        ("F", "all", 11.8, 8.2, 4.2, 8.0, 10.8, 14.8, 27.0, "U/mL", 2150, "Literature"),
        ("all", "20-39", 10.5, 7.0, 3.8, 7.2, 9.8, 13.0, 23.0, "U/mL", 1400, "Literature"),
        ("all", "40-59", 12.5, 8.5, 4.5, 8.5, 11.5, 15.5, 28.0, "U/mL", 1380, "Literature"),
        ("all", "60+", 14.8, 9.5, 5.5, 10.2, 13.8, 18.2, 33.0, "U/mL", 1420, "Literature"),
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
    print(f'\nPart 1 Done: {added} rows added, {skipped} skipped, {not_found} not found')


if __name__ == '__main__':
    main()