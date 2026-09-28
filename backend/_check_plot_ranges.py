"""
Check plotting ranges for population distributions and mortality HRs.
Ensures both can be observed in the landscape plot.
"""
import sqlite3
import os
import sys
import io

# Force UTF-8 output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "mortality_biomarkers.db")

def check_plot_ranges():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("=" * 100)
    print("PLOT RANGE ANALYSIS: Population Distributions vs Mortality HRs")
    print("=" * 100)
    
    # Get all biomarkers with HR functions and population distributions
    cursor.execute("""
        SELECT b.id, b.name, b.units,
               h.fit_type, h.domain_min, h.domain_max, h.reference_value,
               pd.mean, pd.sd, pd.p5, pd.p50, pd.p95
        FROM biomarker b
        LEFT JOIN hr_function h ON b.id = h.biomarker_id AND h.sex = 'all' AND h.age_band = 'all'
        LEFT JOIN population_distribution pd ON b.id = pd.biomarker_id AND pd.sex = 'all' AND pd.age_band = 'all'
        WHERE h.id IS NOT NULL
        ORDER BY b.name
    """)
    
    rows = cursor.fetchall()
    
    print(f"\n{'Biomarker':<35} {'HR Domain':<20} {'Pop Dist Range':<25} {'Overlap':<10} {'Status'}")
    print("-" * 100)
    
    issues = []
    
    for row in rows:
        bm_id, name, units, fit_type, dom_min, dom_max, ref_val, mean, sd, p5, p50, p95 = row
        
        # Calculate population distribution range (mean ± 3*sd or p5-p95)
        if mean and sd:
            pop_min = max(0, mean - 3 * sd)
            pop_max = mean + 3 * sd
            pop_range_str = f"{pop_min:.1f}-{pop_max:.1f}"
        elif p5 and p95:
            pop_min = p5
            pop_max = p95
            pop_range_str = f"{p5:.1f}-{p95:.1f}"
        else:
            pop_min = None
            pop_max = None
            pop_range_str = "N/A"
        
        # Check overlap between HR domain and population distribution
        if dom_min is not None and dom_max is not None and pop_min is not None and pop_max is not None:
            # Check if population range is within HR domain
            pop_in_domain = pop_min >= dom_min and pop_max <= dom_max
            # Check if there's any overlap
            has_overlap = not (pop_max < dom_min or pop_min > dom_max)
            
            if not has_overlap:
                status = "NO OVERLAP"
                issues.append(f"{name}: HR domain [{dom_min}, {dom_max}] does not overlap with pop dist [{pop_min:.1f}, {pop_max:.1f}]")
            elif not pop_in_domain:
                status = "PARTIAL"
                issues.append(f"{name}: Pop dist [{pop_min:.1f}, {pop_max:.1f}] extends beyond HR domain [{dom_min}, {dom_max}]")
            else:
                status = "OK"
        else:
            status = "N/A"
        
        hr_domain_str = f"{dom_min:.1f}-{dom_max:.1f}" if dom_min is not None else "N/A"
        
        print(f"{name[:34]:<35} {hr_domain_str:<20} {pop_range_str:<25} {status:<10}")
    
    conn.close()
    
    print("\n" + "=" * 100)
    print("ISSUES FOUND:")
    print("=" * 100)
    
    if issues:
        for issue in issues:
            print(f"  ⚠ {issue}")
    else:
        print("  ✓ No issues found. All population distributions overlap with HR domains.")
    
    print(f"\nTotal biomarkers checked: {len(rows)}")
    print(f"Issues found: {len(issues)}")

if __name__ == "__main__":
    check_plot_ranges()