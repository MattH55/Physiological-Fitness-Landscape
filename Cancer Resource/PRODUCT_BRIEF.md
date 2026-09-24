# Product brief: PAVS Hub on Vaccine Data Navigator

**Working title:** Post-Acute Vaccination Syndromes (PAVS) Hub  
**Host:** https://vaccinedatanavigator.org/  
**Proposed URL:** https://vaccinedatanavigator.org/pavs.html  
**Owner:** Open Source Medicine Foundation (OSMF)  
**Status:** Draft product brief (2026-09-21)  
**Related network:** Research Tracker (PACVS), Evidence Desk, PACVS Research Summit, opensourcemed.info

---

## 1. Problem

People researching persistent illness after vaccination today hit fragmented surfaces:

- Per-vaccine pages on VDN (schedules, trial AE tables, VAERS/lot context)
- Evidence dossiers (vaccine–AE pairs, causality framework)
- OSMF PACVS tools (Tracker feeds, Summit, Desk claims) that don’t yet frame **Hep B / HPV / anthrax** as siblings of PACVS

There is no single VDN entry point that says: *these are the post-acute vaccination syndrome clusters we track, how they relate, what evidence exists, and where to go next* — without implying that every report equals proven causation.

---

## 2. Opportunity

VDN already has strong building blocks:

| Asset | Role for PAVS |
|-------|----------------|
| `hepatitis-b-vaccine.html` | Hep B product/schedule/AE substrate |
| `hpv-vaccine.html` | HPV substrate |
| `covid-vaccine.html` | COVID / PACVS-adjacent substrate |
| `evidence-dossiers/` | Literature mapped to causality nodes |
| `openpv/` | Signal exploration |
| OSMF Tracker / Desk / Summit | PACVS depth outside VDN |

A **PAVS hub** turns those into a cross-vaccine program page: umbrella framing + four syndrome cards + honest epistemology + outbound links.

---

## 3. Product vision

**One sentence:**  
A VDN hub page that introduces post-acute vaccination syndromes (PAVS) as a research category, featuring PACVS plus Hep B–, HPV–, and anthrax vaccine–associated clusters, and routes users to the right vaccine pages, dossiers, and OSMF tools.

**Not this product:**  
A diagnostic tool, a causation verdict engine, a replacement for per-vaccine pages, or a full second Research Tracker.

---

## 4. Goals (MVP)

1. Define **PAVS** clearly on VDN (post-acute = persistent multi-system illness weeks–months+ after vaccination; umbrella, not one disease).
2. Feature **four clusters:** PACVS, Hep B–associated, HPV–associated, anthrax vaccine–associated (with GWI adjacency called out).
3. Link each cluster to **existing VDN pages** (and dossiers where they exist); link PACVS also to Tracker / Desk / Summit.
4. State epistemology up front: signal ≠ syndrome ≠ proven causation; not medical advice.
5. Give anthrax a **honest stub** (no full VDN vaccine page yet) rather than omitting it.

### Non-goals (MVP)
- New automated PubMed feeds for Hep B/HPV/anthrax PAVS
- New Desk entities for non-PACVS clusters
- Anthrax full vaccine page (can be a follow-on ticket)
- Changing dossier scoring methodology

---

## 5. Audience

| Audience | Job to be done |
|----------|----------------|
| Researchers / clinicians | Find the PAVS framing + jump to literature/dossiers/vaccine AE data |
| Informed patients / advocates | Understand scope and limits; find PACVS program links |
| OSMF collaborators | Shared vocabulary across COVID / Hep B / HPV / anthrax clusters |
| Journalists / policymakers | One citable landing page with disclaimers and sources |

---

## 6. Information architecture

### Placement on VDN
- **Primary:** `/pavs.html` (top-level hub)
- **Nav:** Add “PAVS” (or “Post-acute syndromes”) near About / major tools — keep label short
- **Inbound from:** homepage (featured card or under pharmacovigilance tools), Hep B / HPV / COVID vaccine pages (cross-link “See also: PAVS hub”), evidence-dossiers index (optional filter/tag later)
- **Outbound to:** vaccine pages, dossiers, OpenPV, Tracker PACVS, Desk PACVS entity, Summit

### Page outline

1. **Hero** — Title, one-sentence definition, not-medical-advice + non-causation banner, CTAs (Explore clusters · About methodology)
2. **What PAVS means** — Definition, time window, “shared themes ≠ identical diseases”
3. **How to read this hub** — VDN’s evidence posture (trial AE, post-licensure, dossiers, signals); link About & Methodology
4. **Four cluster cards**
   - **PACVS** — Active program; links: COVID vaccine page, Tracker `pacvs.html`, Desk PACVS entity, Summit, relevant dossiers
   - **Hep B–associated PAVS** — Links: `hepatitis-b-vaccine.html`, Hep-related dossiers, key lit accordion (MVP stub OK)
   - **HPV–associated PAVS** — Links: `hpv-vaccine.html`, HPV dossiers, key lit accordion; note controversy honestly
   - **Anthrax vaccine–associated PAVS** — Stub card; GWI-related Tracker link; “full VDN anthrax page TBD”; key lit accordion
5. **Compare at a glance** — Simple table: cluster · primary vaccine page · OSMF depth · dossier coverage · status
6. **Network / cite** — OSMF strip + citation snippet for the hub page
7. **Support** — Optional donate (same OSMF PayPal + `utm_source=vdn&utm_campaign=pavs`)

---

## 7. Content requirements (MVP copy)

| Block | Owner input needed |
|-------|-------------------|
| PAVS definition (≤120 words) | Editorial |
| Four card blurbs (≤80 words each) | Editorial |
| PACVS outbound URL list | Engineering (known) |
| Hep B / HPV / anthrax: 5–15 key citations each | Research (reviews + major series) |
| Anthrax ↔ GWI “related not equivalent” note | Editorial |
| Disclaimer banner text | Legal/editorial (align with VDN About) |

Tone: clinical-neutral, open-science, no advocacy slogans, no “vaccines are safe/unsafe” framing — evidence navigation only.

---

## 8. Success metrics

- Hub indexed and linked from VDN home + Hep B/HPV/COVID pages  
- PACVS card drives measurable outbound clicks to Tracker/Desk/Summit (UTMs)  
- Hep B/HPV cards drive clicks to existing vaccine pages / dossiers  
- Zero support burden from users mistaking the hub for a diagnosis tool (monitor corrections@ / contact)  
- Follow-on tickets opened for anthrax vaccine page + Tracker/Desk expansion if demand shows

---

## 9. Risks & mitigations

| Risk | Mitigation |
|------|------------|
| Perceived as anti-vaccine | Lead with methodology + non-causation; reuse VDN About grading language |
| Conflating four clusters into one disease | Explicit “not assumed identical” + separate cards |
| Anthrax thin content looks broken | Label status “Nascent / stub”; point to GWI Tracker as related |
| Scope creep into full Tracker | Freeze MVP to hub + links + lit stubs |
| Duplicate PACVS messaging vs Summit | Hub = map; Summit = consensus program; Tracker = feeds |

---

## 10. Delivery plan

### Milestone A — Brief locked (this doc)
Agree URL, nav label, four cluster names, disclaimer text.

### Milestone B — MVP page
Static `pavs.html` in VDN site chrome; PACVS links live; Hep B/HPV/anthrax cards with lit stubs; cross-links from Hep B/HPV/COVID pages.

### Milestone C — Deepen
Anthrax vaccine page ticket; dossier tags for PAVS-relevant AE pairs; optional OpenPV presets; coordinate Desk/Tracker entities for non-PACVS clusters (separate OSMF repos).

### Estimated MVP shape
S/M content page + light nav/cross-links — similar effort to a VDN landing section, not a new app.

---

## 11. Open decisions

1. Nav label: **PAVS** vs **Post-acute syndromes**  
2. Anthrax naming: “Anthrax vaccine–associated PAVS” vs “AVA-associated / GWI-adjacent”  
3. Whether COVID card is labeled **PACVS** only or “COVID / PACVS”  
4. Cite license for hub bibliography (match VDN dossier license)  
5. Whether homepage feature is a card or a single line under tools  

---

## 12. One-line pitch

**PAVS on Vaccine Data Navigator:** the cross-vaccine map for post-acute vaccination syndromes — PACVS, Hep B, HPV, and anthrax — linking schedules, AE data, dossiers, and OSMF research tools without claiming causation.

