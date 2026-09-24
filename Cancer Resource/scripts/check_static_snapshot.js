/* Simulates the static GitHub Pages build: loads frontend/js/common.js with
   STATIC_DATA = true and a fetch stub that reads from npxp-repo/, then walks
   every apiGet call the six pages make (including client-side filters) and
   verifies the snapshot payloads carry what the renderers expect.

   Usage (from project root, after python scripts/export_static.py):
       node scripts/check_static_snapshot.js [repoDir]            */

const fs = require("fs");
const path = require("path");

const repo = path.resolve(process.argv[2] || "npxp-repo");

global.fetch = async (url) => {
    const p = path.join(repo, decodeURIComponent(url));
    if (!fs.existsSync(p)) return { ok: false, status: 404, statusText: "Not Found", json: async () => ({}) };
    return { ok: true, status: 200, json: async () => JSON.parse(fs.readFileSync(p, "utf8")) };
};
global.STATIC_DATA = true;

// Direct eval: common.js declares its helpers (apiGet etc.) in this scope.
eval(fs.readFileSync(path.join(__dirname, "..", "frontend", "js", "common.js"), "utf8"));

let checks = 0, failures = 0;
function expect(label, cond, extra = "") {
    checks++;
    if (!cond) failures++;
    console.log(`${cond ? "PASS" : "FAIL"} ${label}${extra ? " — " + extra : ""}`);
}

(async () => {
    // home.js
    const stats = await apiGet("/stats");
    expect("stats counts", stats.cell_lines >= 8 && stats.modifiers >= 8 && stats.interaction_effects >= 11);
    const tiers = await apiGet("/evidence_tiers");
    expect("evidence tiers incl. tier_2b", "tier_2b_model_predicted" in tiers);
    expect("evidence tiers incl. tier_2c", "tier_2c_nearest_neighbor" in tiers);

    // explorer.js
    const drugs = await apiGet("/drugs");
    const withData = drugs.filter((d) => d.interaction_count > 0);
    expect("drugs with interactions", withData.length >= 4, `${withData.length} drugs`);
    for (const d of withData) {
        const mx = await apiGet("/explorer/matrix", { drug_id: d.drug_id });
        expect(`matrix ${d.drug_id}`, mx.cells.length === d.interaction_count
            && Array.isArray(mx.cell_lines) && Array.isArray(mx.modifiers)
            && !!mx.evidence_tier_definitions, `${mx.cells.length} cells`);
    }

    // cell-lines.js (list + filters + detail)
    const cls = await apiGet("/cell_lines");
    expect("cell_lines list", cls.length >= 8);
    const qMc = await apiGet("/cell_lines", { q: "mcf" });
    expect("cell_lines q=mcf", qMc.length === 2 && qMc.every((c) => /mcf/i.test(c.name)), qMc.map((c) => c.name).join(","));
    const breast = await apiGet("/cell_lines", { tissue: "Breast" });
    expect("cell_lines tissue=Breast", breast.length === 6, `${breast.length}`);
    const tp53 = await apiGet("/cell_lines", { mutation: "TP53" });
    expect("cell_lines mutation=TP53", tp53.length >= 1, tp53.map((c) => c.name).join(","));
    const cl = await apiGet(`/cell_lines/${encodeURIComponent(cls[0].cell_line_id)}`);
    expect("cell_line detail", Array.isArray(cl.signature_scores) && Array.isArray(cl.interactions));

    // modifiers.js
    const mods = await apiGet("/modifiers");
    expect("modifiers list", mods.length >= 8);
    const thermal = await apiGet("/modifiers", { modifier_type: "thermal" });
    expect("modifiers type=thermal", thermal.length === 3 && thermal.every((m) => m.modifier_type === "thermal"));
    const hyper = await apiGet("/modifiers", { q: "hyperthermia" });
    // substring match on agent: "Hyperthermic shock" does NOT contain "hyperthermia"
    expect("modifiers q=hyperthermia", hyper.length === 2 && hyper.every((m) => /hyperthermia/i.test(m.agent)),
        hyper.map((m) => m.agent).join(" | "));
    const md = await apiGet(`/modifiers/${encodeURIComponent(mods[0].modifier_id)}`);
    expect("modifier detail", !!md.protocol_parameters && Array.isArray(md.interactions));

    // interaction.js
    const ints = await apiGet("/interactions");
    expect("interactions list", ints.length >= 11);
    const t1 = await apiGet("/interactions", { evidence_tier: "tier_1_direct" });
    const t1Expected = stats.interactions_by_tier.tier_1_direct || 0;
    expect("interactions tier_1 filter", t1.length === t1Expected && t1.every((i) => i.evidence_tier === "tier_1_direct"),
        `${t1.length}/${t1Expected}`);
    const it = await apiGet(`/interactions/${ints[0].id}`);
    expect("interaction detail payload", !!it.evidence_tier_definition && Array.isArray(it.related)
        && !!it.modifier && "model_run_id" in it, `id=${ints[0].id}`);

    // scoring.js data deps
    const models = await apiGet("/scoring/models");
    expect("scoring models", models.map((m) => m.name).join(",") === "bliss,hsa,loewe,zip");
    const r = await apiGet("/prediction/readiness");
    // tier_1_quantitative_count == 5 as of 2026-09-23 (real, source-extracted
    // combined_effect_metric values -- see README's "First real Tier 1
    // quantitative labels" section); still far below required_quantitative,
    // so Stage 3 stays correctly gated either way.
    expect("readiness gated", r.ready === false && r.tier_1_quantitative_count === 5 && r.required_quantitative === 30);

    const oppCellLines = await apiGet("/opportunity/cell-lines");
    expect("opportunity cell-lines sorted + valid range", oppCellLines.length > 0
        && oppCellLines.every((c) => c.predicted_uplift >= 0 && c.predicted_uplift <= 1 && c.gap_weight > 0 && c.gap_weight <= 1)
        && oppCellLines.every((c, i) => i === 0 || oppCellLines[i - 1].opportunity_score >= c.opportunity_score));
    const oppCancerTypes = await apiGet("/opportunity/cancer-types");
    expect("opportunity cancer-types rollup", oppCancerTypes.length > 0
        && oppCancerTypes.reduce((sum, c) => sum + c.n_cell_lines, 0) === oppCellLines.length);

    console.log(`\n${checks - failures}/${checks} static-snapshot checks passed`);
    process.exit(failures ? 1 : 0);
})().catch((e) => { console.error("FATAL", e); process.exit(1); });
