"""One-shot repair: align skewed-marker domains with the catalog convention.

`generate_population_distribution` builds its grid as
`[max(valid_min, mean - 4.5 SD), min(valid_max, mean + 4.5 SD)]`, so a
`valid_domain_min` pinned at (or near) the absolute floor of a heavily
right-skewed marker stretches the representable range far past the population
and swamps any population-SD shift: the shift is clipped back to the tiny
region where density actually lives, and the resulting 1-SD relative hazard
reduction collapses to ~0 rather than describing an effect.

The seeded catalog never does this — its lower bounds sit near `mean - 5 SD`
(SBP 85 vs mean 124.6, hs-CRP 0.1 vs mean 3.42).  This script applies the same
convention to the gap markers whose published lower bound is an assay floor
rather than a physiological one.  Upper bounds are left alone: `mean + 4.5 SD`
already caps the grid there, so they cannot distort it.
"""

import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.mortalitypredictors_gap_data import BIOMARKERS, DISTRIBUTIONS  # noqa: E402

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "mortalitypredictors_gap_data.py")


def main():
    changes = []
    for slug, cfg in sorted(BIOMARKERS.items()):
        lo = cfg.get("valid_domain_min")
        if lo is None or lo <= 0:
            continue
        mean, sd = DISTRIBUTIONS[slug][2][0][2], DISTRIBUTIONS[slug][2][0][3]
        if sd <= 0:
            continue
        floor = mean - 5.0 * sd
        # Only markers whose declared floor is an assay floor far below the
        # population are affected; a physiological floor (weight 30 kg is a
        # real value, not a detection limit) leaves the grid inside the domain.
        if floor > lo + 0.25 * sd:
            new_lo = round(floor, 4)
            changes.append((slug, lo, new_lo, mean, sd))

    if not changes:
        print("No skewed domains require repair.")
        return

    print(f"{len(changes)} markers with an assay-floor lower bound:")
    for slug, lo, new_lo, mean, sd in changes:
        print(f"  {slug:<34} valid_min {lo:<9} -> {new_lo:<9} "
              f"(mean {mean:.3f}, SD {sd:.3f})")

    src = open(PATH, encoding="utf-8").read()
    changed = 0
    for slug, lo, new_lo, _mean, _sd in changes:
        pat = re.compile(
            r'("' + re.escape(slug) + r'"\s*:\s*dict\(.*?\n\s*\),)',
            re.S,
        )
        m = pat.search(src)
        if not m:
            print(f"  !! could not locate entry for {slug}")
            continue
        block = m.group(1)
        new_block, n = re.subn(
            r"valid_domain_min=" + re.escape(repr(lo)) + r"\b",
            f"valid_domain_min={new_lo!r}",
            block,
        )
        if n != 1:
            print(f"  !! expected 1 valid_domain_min in {slug}, found {n}")
            continue
        src = src[:m.start(1)] + new_block + src[m.end(1):]
        changed += 1

    open(PATH, "w", encoding="utf-8", newline="").write(src)
    print(f"\n  rewrote {changed} entries in {os.path.basename(PATH)}")


if __name__ == "__main__":
    main()