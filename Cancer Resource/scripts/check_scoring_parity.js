/* Parity check: frontend/js/scoring-client.js against the Python engine
   (synlethality/scoring.py) on fixtures from scripts/parity_fixtures.py.

   Usage: python scripts/parity_fixtures.py %TEMP%/parity.json
          node scripts/check_scoring_parity.js %TEMP%/parity.json

   Bliss/HSA are exact arithmetic -> must match to 1e-12. Loewe/ZIP fit Hill
   curves (scipy TRF vs our Nelder-Mead) -> scores must agree to 1e-4 and
   classifications must be identical. */

const fs = require("fs");
const { scoreMatrixClient } = require("../frontend/js/scoring-client.js");

const fixtures = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
let failures = 0;

for (const f of fixtures) {
    const got = scoreMatrixClient(f.doses_a, f.doses_b, f.viability, null, f.scale);
    for (const [name, exp] of Object.entries(f.expected.models)) {
        const g = got.models[name];
        let maxDiff = 0, cells = 0;
        exp.scores.forEach((row, i) => row.forEach((v, j) => {
            if (v === null) {
                if (g.scores[i][j] !== null) {
                    failures++;
                    console.log(`FAIL ${f.name}/${name}[${i}][${j}]: expected null, got ${g.scores[i][j]}`);
                }
                return;
            }
            cells++;
            if (g.scores[i][j] === null) {
                failures++;
                console.log(`FAIL ${f.name}/${name}[${i}][${j}]: expected ${v}, got null`);
                return;
            }
            maxDiff = Math.max(maxDiff, Math.abs(v - g.scores[i][j]));
        }));
        const clsOK = g.summary.classification === exp.summary.classification;
        const ciDiff = exp.meta && exp.meta.mean_ci != null
            ? Math.abs((g.meta.mean_ci ?? NaN) - exp.meta.mean_ci) : 0;
        const tol = (name === "bliss" || name === "hsa") ? 1e-12 : 1e-4;
        const ok = maxDiff <= tol && clsOK && ciDiff <= 1e-4;
        if (!ok) failures++;
        console.log(`${ok ? "PASS" : "FAIL"} ${f.name}/${name}: max|dscore|=${maxDiff.toExponential(2)} `
            + `(${cells} cells), class ${g.summary.classification}==${exp.summary.classification}, `
            + `|dmean_ci|=${ciDiff.toExponential(2)}`);
    }
}
console.log(failures ? `${failures} FAILURE(S)` : "ALL PARITY CHECKS PASSED");
process.exit(failures ? 1 : 0);
