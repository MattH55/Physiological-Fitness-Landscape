import json, math, sqlite3, os

db = os.path.join(os.path.dirname(__file__), "..", "data", "mortality_biomarkers.db")
c = sqlite3.connect(db)

# All distribution_fit rows: check whether mass outside [domain_min, domain_max]
# is large enough to matter (i.e. whether truncating & re-normalizing would
# visibly change the plotted distribution).
problems = []
for row in c.execute("""
    SELECT id, biomarker_id, sex, age_band, fit_type, parameters, domain_min, domain_max
    FROM distribution_fit
"""):
    _id, bid, sex, band, ftype, params_json, dmin, dmax = row
    p = json.loads(params_json) if params_json else {}
    mu = p.get("mean", p.get("mu"))
    sigma = p.get("sd", p.get("sigma"))
    if ftype == "lognormal":
        if dmin is None or dmax is None or sigma is None or sigma <= 0:
            continue
        if dmin > 0:
            z0 = (math.log(max(dmin, 1e-12)) - mu) / sigma
        else:
            z0 = float("-inf")
        z1 = (math.log(max(dmax, 1e-12)) - mu) / sigma
    elif ftype == "normal":
        if dmin is None or dmax is None or sigma is None or sigma <= 0:
            continue
        z0 = (dmin - mu) / sigma
        z1 = (dmax - mu) / sigma
    else:
        continue

    def cdf(z):
        return 0.5 * (1 + math.erf(z / math.sqrt(2)))

    if math.isinf(z0):
        prob_outside = max(0.0, 1.0 - cdf(z1))
    elif math.isinf(z1):
        prob_outside = max(0.0, cdf(z0))
    else:
        prob_outside = max(0.0, 1.0 - (cdf(z1) - cdf(z0)))
    if prob_outside > 0.01:  # >1% of mass outside plotted domain
        problems.append((prob_outside, bid, sex, band, ftype, dmin, dmax, p))

problems.sort(reverse=True)
print(f"Total fit rows with >1% mass outside domain: {len(problems)}")
for prob, bid, sex, band, ftype, dmin, dmax, p in problems[:15]:
    print(f"  bid={bid} {sex}/{band} {ftype} domain=[{dmin},{dmax}] "
          f"params_mean={p.get('mean', p.get('mu'))} mass_outside={prob*100:.1f}%")
