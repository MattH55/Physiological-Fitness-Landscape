"""One-shot repair: fix inverted `directionality` in the gap data module.

For each biomarker whose curated `optimal_target` sits strictly inside its
valid domain on the opposite side of the population mean from what its
`directionality` claims, the curated optimum is authoritative (it is what the
UI renders as the recommendation) while the flag is inverted.  Every such entry
also carries a published HR > 1 for its upper extreme, confirming that higher
is worse.  This script flips the flag and reports what it changed.
"""

import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.mortalitypredictors_gap_data import BIOMARKERS, DISTRIBUTIONS  # noqa: E402

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "mortalitypredictors_gap_data.py")


def offenders():
    out = []
    for slug, cfg in sorted(BIOMARKERS.items()):
        d = cfg["directionality"]
        opt = cfg.get("optimal_target")
        lo = cfg.get("valid_domain_min")
        hi = cfg.get("valid_domain_max")
        if d not in ("higher_better", "lower_better"):
            continue
        if opt is None or lo is None or hi is None or not (lo < opt < hi):
            continue
        mean = DISTRIBUTIONS[slug][2][0][2]
        want = "lower_better" if opt < mean else "higher_better"
        if want != d:
            out.append((slug, d, want, opt, mean, cfg["hr"][0]))
    return out


def main():
    bad = offenders()
    if not bad:
        print("No inverted directionality entries found.")
        return

    print(f"{len(bad)} entries with directionality inverted vs. their optimum:")
    for slug, d, want, opt, mean, hr in bad:
        print(f"  {slug:<34} {d:<14} -> {want:<14} "
              f"opt={opt:<8} mean={mean:<8} HR={hr}")

    src = open(PATH, encoding="utf-8").read()
    changed = 0
    for slug, d, want, _opt, _mean, _hr in bad:
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
            r'directionality="' + d + r'"', f'directionality="{want}"', block
        )
        if n != 1:
            print(f"  !! expected 1 directionality in {slug}, found {n}")
            continue
        src = src[:m.start(1)] + new_block + src[m.end(1):]
        changed += 1

    open(PATH, "w", encoding="utf-8", newline="").write(src)
    print(f"\n  rewrote {changed} entries in {os.path.basename(PATH)}")


if __name__ == "__main__":
    main()