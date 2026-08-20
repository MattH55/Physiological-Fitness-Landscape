/**
 * Physiological Fitness Landscape — Mortality Biomarker Dashboard
 * Main Application Logic & Plotly Visualizations Engine
 */

// Application State
const AppState = {
    biomarkers: [],
    selectedBiomarker: null,
    selectedBiomarkerDetail: null,
    selectedBiomarkerDiseases: [],
    diseases: [],
    selectedDisease: null,
    sources: [],
    stats: null,
    activeTab: 'biomarkers',
    activeSubTab: 'landscape',
    activeDiseaseModalTab: 'all',
    groupBy: 'flat', // 'flat' | 'primary_organ' | 'bodily_fluid' | 'tissue_origin'
    compareSlugs: new Set(['high_sensitivity_crp', 'hba1c', 'estimated_gfr_ckd_epi', 'serum_albumin', 'rdw', 'resting_heart_rate']),
    filters: {
        search: '',
        category: '',
        specimen: '',
        organ: '',
        fluid: '',
        tissue: ''
    },
    diseaseFilters: {
        search: '',
        category: '',
        sortBy: 'name'
    },
    sourceSearch: ''
};

// API Endpoints
const API = {
    stats: '/api/stats',
    biomarkers: '/api/biomarkers',
    biomarkerDetail: (slugOrId) => `/api/biomarkers/${encodeURIComponent(slugOrId)}`,
    biomarkerDiseases: (slugOrId) => `/api/biomarkers/${encodeURIComponent(slugOrId)}/diseases`,
    hrDistribution: (slugOrId) => `/api/biomarkers/${encodeURIComponent(slugOrId)}/hr-distribution`,
    popDistribution: (slugOrId) => `/api/biomarkers/${encodeURIComponent(slugOrId)}/population-distribution`,
    compare: (slugs) => `/api/compare?ids=${encodeURIComponent(slugs.join(','))}`,
    diseases: (params) => `/api/diseases${params ? '?' + new URLSearchParams(params).toString() : ''}`,
    diseaseDetail: (slugOrId) => `/api/diseases/${encodeURIComponent(slugOrId)}`,
    sources: '/api/sources'
};

// Common Plotly Layout Defaults
const plotlyDarkTheme = {
    paper_bgcolor: '#0f172a',
    plot_bgcolor: '#0f172a',
    font: {
        family: 'ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
        color: '#94a3b8',
        size: 11
    },
    margin: { l: 50, r: 40, t: 30, b: 40 },
    xaxis: {
        gridcolor: '#1e293b',
        zerolinecolor: '#334155',
        tickfont: { color: '#94a3b8' }
    },
    yaxis: {
        gridcolor: '#1e293b',
        zerolinecolor: '#334155',
        tickfont: { color: '#94a3b8' }
    }
};

const plotlyConfig = {
    responsive: true,
    displayModeBar: false
};

// DOM Initialization
document.addEventListener('DOMContentLoaded', async () => {
    setupNavigation();
    setupFilters();
    setupComparisonControls();
    setupDiseaseControls();
    
    // Load initial data
    await loadStats();
    await loadBiomarkers();
    await loadDiseases();
    await loadSources();
});

// Setup Main Tab Navigation
function setupNavigation() {
    const tabs = [
        { btn: 'tab-biomarkers', view: 'view-biomarkers' },
        { btn: 'tab-diseases', view: 'view-diseases' },
        { btn: 'tab-compare', view: 'view-compare' },
        { btn: 'tab-sources', view: 'view-sources' }
    ];

    tabs.forEach(({ btn, view }) => {
        const el = document.getElementById(btn);
        if (el) {
            el.addEventListener('click', () => {
                tabs.forEach(t => {
                    const b = document.getElementById(t.btn);
                    const v = document.getElementById(t.view);
                    if (b) {
                        b.classList.remove('bg-indigo-600', 'text-white', 'shadow');
                        b.classList.add('text-slate-400');
                    }
                    if (v) v.classList.add('hidden');
                });
                
                el.classList.add('bg-indigo-600', 'text-white', 'shadow');
                el.classList.remove('text-slate-400');
                const activeView = document.getElementById(view);
                if (activeView) activeView.classList.remove('hidden');

                if (view === 'view-compare') {
                    renderCompareView();
                }
            });
        }
    });

    // Sub-Tabs for Biomarker Deep Dive
    const subtabs = [
        { btn: 'subtab-landscape', view: 'subview-landscape' },
        { btn: 'subtab-forest', view: 'subview-forest' },
        { btn: 'subtab-interventions', view: 'subview-interventions' },
        { btn: 'subtab-demographics', view: 'subview-demographics' },
        { btn: 'subtab-diseases', view: 'subview-diseases' }
    ];

    subtabs.forEach(({ btn, view }) => {
        const el = document.getElementById(btn);
        if (el) {
            el.addEventListener('click', () => {
                subtabs.forEach(t => {
                    const b = document.getElementById(t.btn);
                    const v = document.getElementById(t.view);
                    if (b) {
                        b.classList.remove('bg-indigo-600', 'text-white');
                        b.classList.add('text-slate-400');
                    }
                    if (v) v.classList.add('hidden');
                });

                el.classList.add('bg-indigo-600', 'text-white');
                el.classList.remove('text-slate-400');
                const targetView = document.getElementById(view);
                if (targetView) targetView.classList.remove('hidden');

                // Re-render plotly charts to adjust to viewport
                if (view === 'subview-landscape' && AppState.selectedBiomarkerDetail) {
                    renderLandscapePlot(AppState.selectedBiomarkerDetail);
                } else if (view === 'subview-forest' && AppState.selectedBiomarkerDetail) {
                    renderForestPlot(AppState.selectedBiomarkerDetail);
                } else if (view === 'subview-demographics' && AppState.selectedBiomarkerDetail) {
                    renderDemographicsPlot(AppState.selectedBiomarkerDetail);
                } else if (view === 'subview-diseases' && AppState.selectedBiomarkerDetail) {
                    renderBiomarkerDiseasesView(AppState.selectedBiomarkerDetail);
                }
            });
        }
    });
}

// Setup Filters & Search Listeners
function setupFilters() {
    const searchInput = document.getElementById('biomarker-search');
    const categorySelect = document.getElementById('filter-category');
    const specimenSelect = document.getElementById('filter-specimen');
    const organSelect = document.getElementById('filter-organ');
    const fluidSelect = document.getElementById('filter-fluid');
    const tissueSelect = document.getElementById('filter-tissue');
    const sourceSearchInput = document.getElementById('source-search');

    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            AppState.filters.search = e.target.value.toLowerCase().trim();
            renderBiomarkerList();
        });
    }

    if (categorySelect) {
        categorySelect.addEventListener('change', (e) => {
            AppState.filters.category = e.target.value;
            renderBiomarkerList();
        });
    }

    if (specimenSelect) {
        specimenSelect.addEventListener('change', (e) => {
            AppState.filters.specimen = e.target.value;
            renderBiomarkerList();
        });
    }

    if (organSelect) {
        organSelect.addEventListener('change', (e) => {
            AppState.filters.organ = e.target.value;
            renderBiomarkerList();
        });
    }

    if (fluidSelect) {
        fluidSelect.addEventListener('change', (e) => {
            AppState.filters.fluid = e.target.value;
            renderBiomarkerList();
        });
    }

    if (tissueSelect) {
        tissueSelect.addEventListener('change', (e) => {
            AppState.filters.tissue = e.target.value;
            renderBiomarkerList();
        });
    }

    // Grouping Toggle Buttons
    const groupBtns = document.querySelectorAll('.group-by-btn');
    groupBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            groupBtns.forEach(b => {
                b.classList.remove('active', 'bg-indigo-600', 'text-white', 'shadow-sm');
                b.classList.add('text-slate-400');
            });
            btn.classList.add('active', 'bg-indigo-600', 'text-white', 'shadow-sm');
            btn.classList.remove('text-slate-400');

            AppState.groupBy = btn.getAttribute('data-group');
            const labelMap = {
                flat: 'None',
                primary_organ: 'Organ / System',
                bodily_fluid: 'Bodily Fluid',
                tissue_origin: 'Tissue Origin'
            };
            const indicator = document.getElementById('group-active-indicator');
            if (indicator) {
                indicator.textContent = `Grouped: ${labelMap[AppState.groupBy] || 'None'}`;
            }
            renderBiomarkerList();
        });
    });

    if (sourceSearchInput) {
        sourceSearchInput.addEventListener('input', (e) => {
            AppState.sourceSearch = e.target.value.toLowerCase().trim();
            renderSourcesView();
        });
    }

    // Add to compare button in detail view
    const btnAddCompare = document.getElementById('btn-add-compare');
    if (btnAddCompare) {
        btnAddCompare.addEventListener('click', () => {
            if (AppState.selectedBiomarker) {
                const slug = AppState.selectedBiomarker.slug;
                if (AppState.compareSlugs.has(slug)) {
                    AppState.compareSlugs.delete(slug);
                } else {
                    AppState.compareSlugs.add(slug);
                }
                updateCompareButtonState();
            }
        });
    }
}

// Setup Comparison View Controls
function setupComparisonControls() {
    const btnClear = document.getElementById('btn-compare-clear');
    const btnPreset = document.getElementById('btn-compare-preset-all');

    if (btnClear) {
        btnClear.addEventListener('click', () => {
            AppState.compareSlugs.clear();
            renderCompareView();
        });
    }

    if (btnPreset) {
        btnPreset.addEventListener('click', () => {
            AppState.compareSlugs = new Set(['serum_crp', 'hba1c', 'estimated_gfr_ckd_epi', 'serum_albumin', 'rdw', 'resting_heart_rate']);
            renderCompareView();
        });
    }
}

// Helper to populate select dropdowns
function populateSelect(selectId, items, defaultLabel) {
    const select = document.getElementById(selectId);
    if (select && items) {
        select.innerHTML = `<option value="">${defaultLabel}</option>`;
        items.forEach(item => {
            if (item) {
                const opt = document.createElement('option');
                opt.value = item;
                opt.textContent = item;
                select.appendChild(opt);
            }
        });
    }
}

// Load Global Metrics
async function loadStats() {
    try {
        const res = await fetch(API.stats);
        if (!res.ok) throw new Error('Failed to fetch platform stats');
        const stats = await res.json();
        AppState.stats = stats;

        if (document.getElementById('stat-total-biomarkers')) document.getElementById('stat-total-biomarkers').textContent = stats.biomarkers_total || 0;
        if (document.getElementById('stat-total-associations')) document.getElementById('stat-total-associations').textContent = stats.mortality_associations_total || 0;
        if (document.getElementById('stat-total-distributions')) document.getElementById('stat-total-distributions').textContent = stats.population_distributions_total || 0;
        if (document.getElementById('stat-total-interventions')) document.getElementById('stat-total-interventions').textContent = stats.interventions_total || 0;
        if (document.getElementById('stat-total-sources')) document.getElementById('stat-total-sources').textContent = stats.sources_total || 0;
        if (document.getElementById('stat-total-diseases')) document.getElementById('stat-total-diseases').textContent = stats.diseases_total || 0;
        if (document.getElementById('stat-total-alterations')) document.getElementById('stat-total-alterations').textContent = stats.disease_alterations_total || 0;
        if (document.getElementById('stat-total-biomarker-matches')) document.getElementById('stat-total-biomarker-matches').textContent = stats.disease_biomarker_matches_total || 0;

        // Populate Category and Anatomical Filters
        populateSelect('filter-category', stats.categories, 'All Categories');
        populateSelect('filter-specimen', stats.specimen_types, 'All Specimens');
        populateSelect('filter-organ', stats.primary_organs, 'All Organs & Systems');
        populateSelect('filter-fluid', stats.bodily_fluids, 'All Bodily Fluids');
        populateSelect('filter-tissue', stats.tissue_origins, 'All Tissues of Origin');
        populateSelect('disease-filter-category', stats.disease_categories, 'All Disease Categories');
    } catch (err) {
        console.error('Error loading stats:', err);
    }
}

// Load Biomarkers
async function loadBiomarkers() {
    try {
        const res = await fetch(API.biomarkers);
        if (!res.ok) throw new Error('Failed to fetch biomarkers');
        const list = await res.json();
        AppState.biomarkers = list;

        renderBiomarkerList();

        // Select first biomarker by default
        if (list.length > 0) {
            selectBiomarker(list[0].slug);
        }
    } catch (err) {
        console.error('Error loading biomarkers:', err);
        const container = document.getElementById('biomarker-list-container');
        if (container) {
            container.innerHTML = `<div class="p-4 text-center text-rose-400 text-xs">Failed to load biomarker registry. Check database connection.</div>`;
        }
    }
}

// Icon mapping helper for anatomical groups
function getGroupIcon(groupBy, groupName) {
    if (groupBy === 'primary_organ') {
        if (groupName.includes('Cardiovascular')) return 'fa-heart-pulse text-rose-400';
        if (groupName.includes('Liver')) return 'fa-vial-circle-check text-amber-400';
        if (groupName.includes('Renal')) return 'fa-droplet text-blue-400';
        if (groupName.includes('Pancreas')) return 'fa-dna text-emerald-400';
        if (groupName.includes('Immune')) return 'fa-shield-halved text-purple-400';
        if (groupName.includes('Musculoskeletal')) return 'fa-lungs text-cyan-400';
        return 'fa-network-wired text-indigo-400';
    } else if (groupBy === 'bodily_fluid') {
        if (groupName.includes('Serum') || groupName.includes('Plasma')) return 'fa-droplet text-rose-400';
        if (groupName.includes('Whole Blood')) return 'fa-circle-dot text-red-400';
        if (groupName.includes('Urine')) return 'fa-flask text-amber-400';
        return 'fa-gauge text-indigo-400';
    } else if (groupBy === 'tissue_origin') {
        if (groupName.includes('Hepatocytes')) return 'fa-cube text-amber-400';
        if (groupName.includes('Cardiomyocytes')) return 'fa-heart text-rose-400';
        if (groupName.includes('Epithelium')) return 'fa-cubes text-blue-400';
        if (groupName.includes('Beta Cells')) return 'fa-circle-nodes text-emerald-400';
        if (groupName.includes('Erythrocytes') || groupName.includes('Leukocytes')) return 'fa-shapes text-purple-400';
        return 'fa-layer-group text-indigo-400';
    }
    return 'fa-folder text-slate-400';
}

function createBiomarkerCardElement(b) {
    const isSelected = AppState.selectedBiomarker && AppState.selectedBiomarker.slug === b.slug;
    const card = document.createElement('div');
    card.className = `p-3 cursor-pointer transition flex items-center justify-between hover:bg-slate-750 border-b border-slate-800/80 ${isSelected ? 'bg-indigo-950/50 border-l-4 border-indigo-500' : ''}`;
    
    let hrBadge = '';
    if (b.max_hazard_ratio) {
        const hrVal = b.max_hazard_ratio.toFixed(2);
        let hrColor = 'bg-rose-500/20 text-rose-300 border-rose-500/30';
        if (b.primary_direction === 'protective') {
            hrColor = 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30';
        } else if (b.primary_direction === 'u_shaped') {
            hrColor = 'bg-amber-500/20 text-amber-300 border-amber-500/30';
        }
        hrBadge = `<span class="text-[10px] px-2 py-0.5 rounded border font-mono font-bold ${hrColor}">HR ${hrVal}</span>`;
    } else {
        hrBadge = `<span class="text-[10px] px-2 py-0.5 rounded bg-slate-700 text-slate-400 font-mono">HR N/A</span>`;
    }

    const organBadge = b.primary_organ ? `<span class="text-[9px] px-1.5 py-0.2 rounded bg-slate-800 text-slate-400 border border-slate-700/60 truncate max-w-[120px]"><i class="fa-solid fa-heart-pulse mr-0.5 text-[8px] text-slate-500"></i>${b.primary_organ}</span>` : '';
    const fluidBadge = b.bodily_fluid ? `<span class="text-[9px] px-1.5 py-0.2 rounded bg-slate-800 text-slate-400 border border-slate-700/60 truncate max-w-[100px]"><i class="fa-solid fa-droplet mr-0.5 text-[8px] text-slate-500"></i>${b.bodily_fluid}</span>` : '';

    card.innerHTML = `
        <div class="flex-1 min-w-0 pr-2">
            <div class="flex items-center gap-1.5 mb-1 flex-wrap">
                <span class="text-[10px] px-2 py-0.2 rounded-full font-semibold bg-slate-700/80 text-indigo-300">${b.category}</span>
                ${b.has_nhanes ? '<span class="text-[9px] px-1.5 py-0.2 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-mono">NHANES</span>' : ''}
                ${organBadge}
                ${fluidBadge}
            </div>
            <div class="text-xs font-bold text-slate-100 truncate">${b.name}</div>
            <div class="text-[11px] text-slate-400 flex items-center gap-2 mt-0.5">
                <span>${b.population_median !== null ? `Median: <strong class="text-slate-300">${b.population_median}</strong> ${b.units}` : `${b.units}`}</span>
            </div>
        </div>
        <div class="flex flex-col items-end gap-1.5 shrink-0">
            ${hrBadge}
            <span class="text-[10px] text-slate-500"><i class="fa-solid fa-dumbbell mr-1"></i>${b.interventions_count} itv</span>
        </div>
    `;

    card.addEventListener('click', () => {
        selectBiomarker(b.slug);
    });

    return card;
}

// Filter and Render Biomarker List
function renderBiomarkerList() {
    const container = document.getElementById('biomarker-list-container');
    const countEl = document.getElementById('biomarker-count');
    if (!container) return;

    let filtered = AppState.biomarkers.filter(b => {
        const matchCat = !AppState.filters.category || (b.category && b.category.toLowerCase().includes(AppState.filters.category.toLowerCase()));
        const matchSpec = !AppState.filters.specimen || b.specimen_type === AppState.filters.specimen;
        const matchOrgan = !AppState.filters.organ || b.primary_organ === AppState.filters.organ;
        const matchFluid = !AppState.filters.fluid || b.bodily_fluid === AppState.filters.fluid;
        const matchTissue = !AppState.filters.tissue || b.tissue_origin === AppState.filters.tissue;
        const matchSearch = !AppState.filters.search || 
            (b.name && b.name.toLowerCase().includes(AppState.filters.search)) ||
            (b.category && b.category.toLowerCase().includes(AppState.filters.search)) ||
            (b.primary_organ && b.primary_organ.toLowerCase().includes(AppState.filters.search)) ||
            (b.bodily_fluid && b.bodily_fluid.toLowerCase().includes(AppState.filters.search)) ||
            (b.tissue_origin && b.tissue_origin.toLowerCase().includes(AppState.filters.search)) ||
            (b.nhanes_code && b.nhanes_code.toLowerCase().includes(AppState.filters.search)) ||
            (b.notes && b.notes.toLowerCase().includes(AppState.filters.search));
        return matchCat && matchSpec && matchOrgan && matchFluid && matchTissue && matchSearch;
    });

    if (countEl) countEl.textContent = filtered.length;

    if (filtered.length === 0) {
        container.innerHTML = `<div class="p-6 text-center text-slate-500 text-xs">No biomarkers match your search / grouping filter.</div>`;
        return;
    }

    container.innerHTML = '';

    if (!AppState.groupBy || AppState.groupBy === 'flat') {
        filtered.forEach(b => {
            container.appendChild(createBiomarkerCardElement(b));
        });
    } else {
        // Group biomarkers by the selected property
        const groupProp = AppState.groupBy;
        const groups = {};
        filtered.forEach(b => {
            const key = b[groupProp] || 'Unclassified / Other';
            if (!groups[key]) groups[key] = [];
            groups[key].push(b);
        });

        // Sort group keys alphabetically
        const sortedKeys = Object.keys(groups).sort((a, b) => a.localeCompare(b));

        sortedKeys.forEach(groupName => {
            const groupList = groups[groupName];
            const groupHeader = document.createElement('div');
            groupHeader.className = 'sticky top-0 z-10 bg-slate-850/95 backdrop-blur px-3.5 py-2 border-y border-slate-700/80 flex items-center justify-between text-xs font-bold text-slate-200 shadow-sm';
            
            const iconClass = getGroupIcon(AppState.groupBy, groupName);
            groupHeader.innerHTML = `
                <div class="flex items-center gap-2 truncate">
                    <i class="fa-solid ${iconClass}"></i>
                    <span class="truncate">${groupName}</span>
                </div>
                <span class="text-[10px] px-2 py-0.5 rounded-full bg-slate-700 text-slate-300 font-mono font-normal">${groupList.length}</span>
            `;
            container.appendChild(groupHeader);

            const groupContent = document.createElement('div');
            groupContent.className = 'divide-y divide-slate-800';
            groupList.forEach(b => {
                groupContent.appendChild(createBiomarkerCardElement(b));
            });
            container.appendChild(groupContent);
        });
    }
}

// Select Biomarker and Fetch Detailed Sub-Resources
async function selectBiomarker(slugOrId) {
    try {
        const res = await fetch(API.biomarkerDetail(slugOrId));
        if (!res.ok) throw new Error('Biomarker details fetch failed');
        const detail = await res.json();
        
        AppState.selectedBiomarker = detail;
        AppState.selectedBiomarkerDetail = detail;

        renderBiomarkerDetail(detail);
        renderBiomarkerList(); // update active styling in sidebar
    } catch (err) {
        console.error('Error selecting biomarker:', err);
    }
}

// Render Biomarker Detail View & Sub-Views
function renderBiomarkerDetail(detail) {
    document.getElementById('detail-name').textContent = detail.name;
    document.getElementById('detail-category').textContent = detail.category;
    document.getElementById('detail-specimen').textContent = `Specimen: ${detail.specimen_type || 'N/A'}`;
    document.getElementById('detail-nhanes').textContent = detail.nhanes_code ? `NHANES: ${detail.nhanes_code}` : 'Reference Cohort';
    if (document.getElementById('detail-organ')) {
        document.getElementById('detail-organ').textContent = detail.primary_organ || 'Multi-Organ / Systemic';
    }
    if (document.getElementById('detail-fluid')) {
        document.getElementById('detail-fluid').textContent = detail.bodily_fluid || detail.specimen_type || 'N/A';
    }
    if (document.getElementById('detail-tissue')) {
        document.getElementById('detail-tissue').textContent = detail.tissue_origin || 'Systemic';
    }
    document.getElementById('detail-method').textContent = `Method / Assay: ${detail.measurement_method || 'Standardized Laboratory Assay'}`;
    document.getElementById('detail-notes').textContent = detail.notes || 'No description available for this biomarker.';
    document.getElementById('landscape-unit').textContent = detail.units;

    updateCompareButtonState();

    // Population percentiles benchmark table
    const overallDist = detail.population_distributions.find(d => d.sex === 'all' && d.age_band === 'all') || detail.population_distributions[0];
    if (overallDist) {
        document.getElementById('bench-p5').textContent = overallDist.p5 !== null ? `${overallDist.p5} ${detail.units}` : '--';
        document.getElementById('bench-p25').textContent = overallDist.p25 !== null ? `${overallDist.p25} ${detail.units}` : '--';
        document.getElementById('bench-p50').textContent = overallDist.p50 !== null ? `${overallDist.p50} ${detail.units}` : '--';
        document.getElementById('bench-p75').textContent = overallDist.p75 !== null ? `${overallDist.p75} ${detail.units}` : '--';
        document.getElementById('bench-p95').textContent = overallDist.p95 !== null ? `${overallDist.p95} ${detail.units}` : '--';
    } else {
        ['bench-p5', 'bench-p25', 'bench-p50', 'bench-p75', 'bench-p95'].forEach(id => {
            document.getElementById(id).textContent = '--';
        });
    }

    // Render Sub-Views
    renderLandscapePlot(detail);
    renderForestPlot(detail);
    renderInterventionsView(detail);
    renderDemographicsPlot(detail);
    renderBiomarkerDiseasesView(detail);
}

function updateCompareButtonState() {
    const btnAddCompare = document.getElementById('btn-add-compare');
    if (!btnAddCompare || !AppState.selectedBiomarker) return;
    const isAdded = AppState.compareSlugs.has(AppState.selectedBiomarker.slug);
    if (isAdded) {
        btnAddCompare.innerHTML = `<i class="fa-solid fa-check text-emerald-400"></i> Added in Compare (${AppState.compareSlugs.size})`;
        btnAddCompare.className = 'px-3.5 py-2 bg-indigo-900/60 border border-indigo-500/40 text-indigo-200 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition';
    } else {
        btnAddCompare.innerHTML = `<i class="fa-solid fa-plus"></i> Add to Compare`;
        btnAddCompare.className = 'px-3.5 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 transition';
    }
}

// -----------------------------------------------------------------------------------------
// Plotly Chart 1: Physiological Fitness Landscape Overlay
// -----------------------------------------------------------------------------------------
function renderLandscapePlot(detail) {
    const plotDiv = document.getElementById('plot-landscape');
    if (!plotDiv) return;

    const overallDist = detail.population_distributions.find(d => d.sex === 'all' && d.age_band === 'all') || detail.population_distributions[0];
    const assoc = detail.associations[0];

    // Compute synthetic distribution curve domain based on percentiles or mean/SD
    let p5 = overallDist ? (overallDist.p5 || 10) : 10;
    let p50 = overallDist ? (overallDist.p50 || 50) : 50;
    let p95 = overallDist ? (overallDist.p95 || 100) : 100;
    let mean = overallDist ? (overallDist.mean || p50) : p50;
    let sd = overallDist ? (overallDist.sd || (p95 - p5) / 3.29) : (p95 - p5) / 3.29;
    if (sd <= 0) sd = 1.0;

    let minX = Math.max(0, p5 - 1.5 * sd);
    let maxX = p95 + 1.8 * sd;
    if (minX === 0 && p5 > 50) minX = p5 * 0.5;

    const points = 150;
    const step = (maxX - minX) / (points - 1);
    const xVals = [];
    const densityVals = [];
    const hrVals = [];

    // Direction and hazard ratio behavior
    const hrVal = assoc ? assoc.hazard_ratio : 1.5;
    const direction = assoc ? assoc.direction : 'positive';

    for (let i = 0; i < points; i++) {
        const x = minX + i * step;
        xVals.push(x);

        // Gaussian density estimate
        const z = (x - mean) / sd;
        const density = (1 / (sd * Math.sqrt(2 * Math.PI))) * Math.exp(-0.5 * z * z);
        densityVals.push(density);

        // Model Hazard Ratio curve according to physiological association
        let computedHR = 1.0;
        if (direction === 'positive') {
            // Higher is riskier: HR increases with standard deviations above p50
            const zRisk = (x - p50) / sd;
            computedHR = Math.exp(Math.log(hrVal) * (zRisk));
        } else if (direction === 'inverse' || direction === 'protective') {
            // Lower is riskier (e.g., eGFR, Albumin)
            const zRisk = (p50 - x) / sd;
            computedHR = Math.exp(Math.log(hrVal) * (zRisk));
        } else if (direction === 'u_shaped') {
            // U-shaped / J-shaped risk curve
            const zRisk = Math.abs(x - p50) / sd;
            computedHR = 1.0 + (hrVal - 1.0) * Math.pow(zRisk / 1.5, 2);
        } else {
            const zRisk = (x - p50) / sd;
            computedHR = Math.exp(Math.log(Math.max(1.1, hrVal)) * zRisk);
        }
        hrVals.push(Math.max(0.2, Math.min(8.0, computedHR)));
    }

    const densityTrace = {
        x: xVals,
        y: densityVals,
        type: 'scatter',
        mode: 'lines',
        name: 'NHANES Population Density',
        line: { color: '#38bdf8', width: 2.5 },
        fill: 'tozeroy',
        fillcolor: 'rgba(56, 189, 248, 0.12)',
        yaxis: 'y1',
        hovertemplate: `Level: %{x:.2f} ${detail.units}<br>Density: %{y:.4f}<extra></extra>`
    };

    const hrTrace = {
        x: xVals,
        y: hrVals,
        type: 'scatter',
        mode: 'lines',
        name: 'Mortality Hazard Ratio (HR)',
        line: { color: '#f43f5e', width: 3, dash: 'solid' },
        yaxis: 'y2',
        hovertemplate: `Level: %{x:.2f} ${detail.units}<br>Hazard Ratio: %{y:.2f}x<extra></extra>`
    };

    const baselineHrLine = {
        type: 'line',
        xref: 'paper',
        x0: 0,
        x1: 1,
        yref: 'y2',
        y0: 1.0,
        y1: 1.0,
        line: {
            color: '#64748b',
            width: 1.5,
            dash: 'dot'
        }
    };

    const layout = {
        ...plotlyDarkTheme,
        title: false,
        showlegend: true,
        legend: {
            orientation: 'h',
            x: 0,
            y: 1.15,
            font: { color: '#cbd5e1', size: 11 }
        },
        xaxis: {
            ...plotlyDarkTheme.xaxis,
            title: { text: `${detail.name} (${detail.units})`, font: { color: '#cbd5e1', size: 11 } }
        },
        yaxis: {
            ...plotlyDarkTheme.yaxis,
            title: { text: 'Population Density', font: { color: '#38bdf8', size: 11 } },
            showgrid: true,
            zeroline: false
        },
        yaxis2: {
            title: { text: 'All-Cause Mortality HR', font: { color: '#f43f5e', size: 11 } },
            overlaying: 'y',
            side: 'right',
            gridcolor: 'transparent',
            zeroline: false,
            tickfont: { color: '#f43f5e' }
        },
        shapes: [baselineHrLine]
    };

    Plotly.newPlot(plotDiv, [densityTrace, hrTrace], layout, plotlyConfig);
}

// -----------------------------------------------------------------------------------------
// Plotly Chart 2: Hazard Ratio Forest Plot
// -----------------------------------------------------------------------------------------
function renderForestPlot(detail) {
    const plotDiv = document.getElementById('plot-forest');
    const tableContainer = document.getElementById('forest-table-container');
    if (!plotDiv) return;

    const assocs = detail.associations || [];

    if (assocs.length === 0) {
        plotDiv.innerHTML = `<div class="p-8 text-center text-slate-500 text-xs">No prospective hazard ratio associations documented for this biomarker.</div>`;
        if (tableContainer) tableContainer.innerHTML = '';
        return;
    }

    const studyNames = [];
    const hrs = [];
    const errorsX = [];
    const errorsMinus = [];
    const hoverTexts = [];

    // Sort by study or effect size
    assocs.forEach(a => {
        const title = a.cohort_description || (a.notes ? a.notes.substring(0, 35) : `Association ID #${a.id}`);
        studyNames.push(title);
        hrs.push(a.hazard_ratio);
        errorsX.push(a.ci_upper !== null ? (a.ci_upper - a.hazard_ratio) : 0);
        errorsMinus.push(a.ci_lower !== null ? (a.hazard_ratio - a.ci_lower) : 0);
        hoverTexts.push(`Study: ${title}<br>HR: ${a.hazard_ratio} (95% CI: ${a.ci_lower || '--'} - ${a.ci_upper || '--'})<br>N: ${a.n ? a.n.toLocaleString() : 'N/A'}<br>Covariates: ${a.adjustment_covariates || 'Fully adjusted'}`);
    });

    const forestTrace = {
        type: 'scatter',
        mode: 'markers',
        x: hrs,
        y: studyNames,
        error_x: {
            type: 'data',
            symmetric: false,
            array: errorsX,
            arrayminus: errorsMinus,
            color: '#10b981',
            thickness: 2,
            width: 6
        },
        marker: {
            color: '#10b981',
            size: 10,
            symbol: 'square'
        },
        hoverinfo: 'text',
        hovertext: hoverTexts
    };

    const layout = {
        ...plotlyDarkTheme,
        margin: { l: 200, r: 40, t: 20, b: 40 },
        xaxis: {
            ...plotlyDarkTheme.xaxis,
            title: { text: 'Hazard Ratio (95% Confidence Interval)', font: { color: '#cbd5e1', size: 11 } },
            zeroline: false
        },
        yaxis: {
            ...plotlyDarkTheme.yaxis,
            automargin: true,
            autorange: 'reversed'
        },
        shapes: [{
            type: 'line',
            x0: 1.0,
            x1: 1.0,
            y0: -0.5,
            y1: studyNames.length - 0.5,
            line: {
                color: '#f43f5e',
                width: 1.5,
                dash: 'dash'
            }
        }]
    };

    Plotly.newPlot(plotDiv, [forestTrace], layout, plotlyConfig);

    // Forest Plot Details Table
    if (tableContainer) {
        let tableHtml = `
            <table class="w-full text-left text-xs border-collapse">
                <thead>
                    <tr class="border-b border-slate-700 text-slate-400 uppercase text-[10px]">
                        <th class="py-2 px-3">Cohort / Comparison</th>
                        <th class="py-2 px-3">Hazard Ratio (95% CI)</th>
                        <th class="py-2 px-3">Sample Size (N)</th>
                        <th class="py-2 px-3">Adjustments</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-slate-800 text-slate-300">
        `;

        assocs.forEach(a => {
            tableHtml += `
                <tr class="hover:bg-slate-750">
                    <td class="py-2 px-3 font-medium text-slate-200">${a.cohort_description || a.hr_type || 'Prospective cohort'}</td>
                    <td class="py-2 px-3 font-mono font-bold text-emerald-400">${a.hazard_ratio} <span class="text-slate-500 font-normal">(${a.ci_lower || '--'} - ${a.ci_upper || '--'})</span></td>
                    <td class="py-2 px-3 text-slate-400 font-mono">${a.n ? a.n.toLocaleString() : 'N/A'}</td>
                    <td class="py-2 px-3 text-slate-400 text-[11px] truncate max-w-xs">${a.adjustment_covariates || 'Age, sex, smoking, comorbidities'}</td>
                </tr>
            `;
        });

        tableHtml += `</tbody></table>`;
        tableContainer.innerHTML = tableHtml;
    }
}

// -----------------------------------------------------------------------------------------
// Sub-View C: Evidence-Graded Interventions
// -----------------------------------------------------------------------------------------
function renderInterventionsView(detail) {
    const favContainer = document.getElementById('favorable-interventions-list');
    const unfavContainer = document.getElementById('unfavorable-interventions-list');
    if (!favContainer || !unfavContainer) return;

    const interventions = detail.interventions || [];
    const favorable = interventions.filter(i => i.direction === 'favorable');
    const unfavorable = interventions.filter(i => i.direction === 'unfavorable');

    const renderCard = (itv, isFav) => {
        let evidenceBadge = 'bg-slate-700 text-slate-300';
        if (itv.evidence_grade === 'rct' || itv.evidence_grade === 'meta-analysis') {
            evidenceBadge = 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/30';
        } else if (itv.evidence_grade === 'cohort') {
            evidenceBadge = 'bg-purple-500/20 text-purple-300 border border-purple-500/30';
        }

        const effectColor = isFav ? 'text-emerald-400' : 'text-rose-400';

        return `
            <div class="bg-slate-900/80 p-3.5 rounded-lg border border-slate-700/70 space-y-1.5 shadow-sm">
                <div class="flex items-center justify-between">
                    <div class="flex items-center gap-1.5">
                        <span class="text-[10px] px-2 py-0.5 rounded font-semibold uppercase ${evidenceBadge}">${itv.evidence_grade.replace('_', ' ')}</span>
                        <span class="text-[10px] px-2 py-0.5 rounded bg-slate-800 text-slate-400 font-medium">${itv.intervention_type}</span>
                    </div>
                    <span class="text-xs font-mono font-bold ${effectColor}">${itv.effect_size || 'Modulating'}</span>
                </div>
                <div class="text-xs font-bold text-slate-100">${itv.intervention_name}</div>
                <p class="text-[11px] text-slate-400 leading-relaxed">${itv.notes || 'Documented physiological effect on marker levels.'}</p>
                <div class="text-[10px] text-slate-500 flex items-center justify-between pt-1 border-t border-slate-800">
                    <span>Duration: ${itv.duration || 'Variable'}</span>
                    ${itv.source_id ? '<span class="text-indigo-400 hover:underline cursor-pointer"><i class="fa-solid fa-link mr-1"></i>Evidence Ref</span>' : ''}
                </div>
            </div>
        `;
    };

    if (favorable.length === 0) {
        favContainer.innerHTML = `<p class="text-xs text-slate-500 p-2">No favorable interventions recorded yet.</p>`;
    } else {
        favContainer.innerHTML = favorable.map(i => renderCard(i, true)).join('');
    }

    if (unfavorable.length === 0) {
        unfavContainer.innerHTML = `<p class="text-xs text-slate-500 p-2">No adverse/aggravating factors recorded yet.</p>`;
    } else {
        unfavContainer.innerHTML = unfavorable.map(i => renderCard(i, false)).join('');
    }
}

// -----------------------------------------------------------------------------------------
// Plotly Chart 3: Demographics Stratification
// -----------------------------------------------------------------------------------------
function renderDemographicsPlot(detail) {
    const plotDiv = document.getElementById('plot-demographics');
    const tableContainer = document.getElementById('demographics-table-container');
    if (!plotDiv) return;

    const strata = detail.population_distributions || [];

    if (strata.length === 0) {
        plotDiv.innerHTML = `<div class="p-8 text-center text-slate-500 text-xs">No demographic stratification data available for this biomarker.</div>`;
        if (tableContainer) tableContainer.innerHTML = '';
        return;
    }

    // Filter out strata
    const ageStrata = strata.filter(s => s.sex === 'all' && s.age_band !== 'all');
    const displayStrata = ageStrata.length > 0 ? ageStrata : strata;

    const labels = displayStrata.map(s => `${s.sex.toUpperCase()} (${s.age_band})`);
    const p25s = displayStrata.map(s => s.p25 || 0);
    const p50s = displayStrata.map(s => s.p50 || 0);
    const p75s = displayStrata.map(s => s.p75 || 0);

    const traceP50 = {
        x: labels,
        y: p50s,
        name: 'Median (P50)',
        type: 'bar',
        marker: { color: '#6366f1' },
        hovertemplate: `Stratum: %{x}<br>Median: %{y:.2f} ${detail.units}<extra></extra>`
    };

    const traceP75 = {
        x: labels,
        y: p75s,
        name: '75th Percentile',
        type: 'bar',
        marker: { color: '#a855f7' },
        hovertemplate: `Stratum: %{x}<br>75th %ile: %{y:.2f} ${detail.units}<extra></extra>`
    };

    const layout = {
        ...plotlyDarkTheme,
        barmode: 'group',
        xaxis: {
            ...plotlyDarkTheme.xaxis,
            title: { text: 'Demographic Stratum', font: { color: '#cbd5e1', size: 11 } }
        },
        yaxis: {
            ...plotlyDarkTheme.yaxis,
            title: { text: `${detail.name} (${detail.units})`, font: { color: '#cbd5e1', size: 11 } }
        }
    };

    Plotly.newPlot(plotDiv, [traceP50, traceP75], layout, plotlyConfig);

    // Demographic Data Table
    if (tableContainer) {
        let tableHtml = `
            <table class="w-full text-left text-xs border-collapse">
                <thead>
                    <tr class="border-b border-slate-700 text-slate-400 uppercase text-[10px]">
                        <th class="py-2 px-3">Sex</th>
                        <th class="py-2 px-3">Age Band</th>
                        <th class="py-2 px-3 text-right">P5</th>
                        <th class="py-2 px-3 text-right">P25</th>
                        <th class="py-2 px-3 text-right text-indigo-400 font-bold">Median (P50)</th>
                        <th class="py-2 px-3 text-right">P75</th>
                        <th class="py-2 px-3 text-right">P95</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-slate-800 text-slate-300">
        `;

        strata.forEach(s => {
            tableHtml += `
                <tr class="hover:bg-slate-750">
                    <td class="py-2 px-3 capitalize">${s.sex}</td>
                    <td class="py-2 px-3 font-mono">${s.age_band}</td>
                    <td class="py-2 px-3 text-right font-mono text-slate-400">${s.p5 ?? '--'}</td>
                    <td class="py-2 px-3 text-right font-mono text-slate-400">${s.p25 ?? '--'}</td>
                    <td class="py-2 px-3 text-right font-mono font-bold text-indigo-300">${s.p50 ?? '--'}</td>
                    <td class="py-2 px-3 text-right font-mono text-slate-400">${s.p75 ?? '--'}</td>
                    <td class="py-2 px-3 text-right font-mono text-slate-400">${s.p95 ?? '--'}</td>
                </tr>
            `;
        });

        tableHtml += `</tbody></table>`;
        tableContainer.innerHTML = tableHtml;
    }
}

// -----------------------------------------------------------------------------------------
// View 2: Multi-Biomarker Side-by-Side Comparison
// -----------------------------------------------------------------------------------------
async function renderCompareView() {
    const chipsContainer = document.getElementById('compare-selection-chips');
    const tableContainer = document.getElementById('compare-table-container');
    const plotDiv = document.getElementById('plot-compare-forest');
    if (!chipsContainer || !tableContainer || !plotDiv) return;

    // Render Selection Chips for All Biomarkers
    chipsContainer.innerHTML = '';
    AppState.biomarkers.forEach(b => {
        const isSelected = AppState.compareSlugs.has(b.slug);
        const chip = document.createElement('button');
        chip.className = `px-2.5 py-1 rounded-full text-xs font-semibold flex items-center gap-1.5 transition ${
            isSelected 
                ? 'bg-indigo-600 text-white shadow' 
                : 'bg-slate-800 text-slate-400 hover:bg-slate-700 hover:text-slate-200 border border-slate-700'
        }`;
        chip.innerHTML = `
            <span>${b.name}</span>
            <i class="fa-solid ${isSelected ? 'fa-circle-check text-indigo-200' : 'fa-plus text-slate-500'} text-[10px]"></i>
        `;
        chip.addEventListener('click', () => {
            if (AppState.compareSlugs.has(b.slug)) {
                AppState.compareSlugs.delete(b.slug);
            } else {
                if (AppState.compareSlugs.size >= 8) {
                    alert('You can compare up to 8 biomarkers simultaneously.');
                    return;
                }
                AppState.compareSlugs.add(b.slug);
            }
            renderCompareView();
        });
        chipsContainer.appendChild(chip);
    });

    const selectedSlugs = Array.from(AppState.compareSlugs);
    if (selectedSlugs.length === 0) {
        plotDiv.innerHTML = `<div class="p-8 text-center text-slate-500 text-xs">No biomarkers selected for comparison. Click chips above to add.</div>`;
        tableContainer.innerHTML = '';
        return;
    }

    try {
        const res = await fetch(API.compare(selectedSlugs));
        if (!res.ok) throw new Error('Compare API failed');
        const data = await res.json();
        const comparisons = data.comparisons || [];

        // 1. Comparative Hazard Ratio Bar/Forest Plot
        const names = [];
        const hrs = [];
        const colors = [];
        const hoverTexts = [];

        comparisons.forEach(c => {
            names.push(c.name);
            const hr = c.primary_association ? c.primary_association.hazard_ratio : 1.0;
            hrs.push(hr);
            
            let color = '#f43f5e';
            if (c.primary_association && c.primary_association.direction === 'protective') {
                color = '#10b981';
            } else if (c.primary_association && c.primary_association.direction === 'u_shaped') {
                color = '#f59e0b';
            }
            colors.push(color);

            hoverTexts.push(`<b>${c.name}</b><br>Category: ${c.category}<br>Primary HR: ${hr}x<br>Direction: ${c.primary_association ? c.primary_association.direction : 'N/A'}`);
        });

        const compareTrace = {
            type: 'bar',
            x: names,
            y: hrs,
            marker: { color: colors },
            text: hrs.map(h => `${h.toFixed(2)}x`),
            textposition: 'outside',
            textfont: { color: '#cbd5e1', size: 10 },
            hoverinfo: 'text',
            hovertext: hoverTexts
        };

        const compareLayout = {
            ...plotlyDarkTheme,
            title: false,
            xaxis: {
                ...plotlyDarkTheme.xaxis,
                tickangle: -20
            },
            yaxis: {
                ...plotlyDarkTheme.yaxis,
                title: { text: 'Primary Mortality Hazard Ratio (HR)', font: { color: '#cbd5e1', size: 11 } }
            },
            shapes: [{
                type: 'line',
                xref: 'paper',
                x0: 0,
                x1: 1,
                y0: 1.0,
                y1: 1.0,
                line: {
                    color: '#64748b',
                    width: 1.5,
                    dash: 'dash'
                }
            }]
        };

        Plotly.newPlot(plotDiv, [compareTrace], compareLayout, plotlyConfig);

        // 2. Comparison Table
        let tableHtml = `
            <table class="w-full text-left text-xs border-collapse">
                <thead>
                    <tr class="border-b border-slate-700 text-slate-400 uppercase text-[10px]">
                        <th class="py-2.5 px-3">Biomarker</th>
                        <th class="py-2.5 px-3">Category</th>
                        <th class="py-2.5 px-3 text-right">Population Median</th>
                        <th class="py-2.5 px-3 text-right">Mean &plusmn; SD</th>
                        <th class="py-2.5 px-3 text-center">Mortality HR</th>
                        <th class="py-2.5 px-3">Risk Pattern</th>
                        <th class="py-2.5 px-3">Key Interventions</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-slate-800 text-slate-300">
        `;

        comparisons.forEach(c => {
            const hr = c.primary_association ? c.primary_association.hazard_ratio : null;
            const dir = c.primary_association ? c.primary_association.direction : 'unknown';
            const favorable = c.interventions_summary ? c.interventions_summary.favorable : [];
            const topItvs = favorable.slice(0, 2).map(i => i.intervention_name).join(', ') || 'Lifestyle modifications';

            tableHtml += `
                <tr class="hover:bg-slate-750">
                    <td class="py-2.5 px-3 font-bold text-slate-100 flex items-center gap-1.5">
                        ${c.name}
                        <span class="text-[10px] text-slate-500 font-mono">(${c.units})</span>
                    </td>
                    <td class="py-2.5 px-3"><span class="text-[10px] px-2 py-0.5 rounded bg-slate-800 text-slate-300">${c.category}</span></td>
                    <td class="py-2.5 px-3 text-right font-mono text-indigo-300 font-semibold">${c.population_p50 ?? '--'}</td>
                    <td class="py-2.5 px-3 text-right font-mono text-slate-400">${c.population_mean ? `${c.population_mean.toFixed(1)} &plusmn; ${c.population_sd ? c.population_sd.toFixed(1) : '0'}` : '--'}</td>
                    <td class="py-2.5 px-3 text-center font-mono font-bold text-rose-400">${hr ? `${hr.toFixed(2)}x` : '--'}</td>
                    <td class="py-2.5 px-3 capitalize text-[11px] text-slate-300">${dir.replace('_', ' ')}</td>
                    <td class="py-2.5 px-3 text-slate-400 text-[11px] truncate max-w-xs">${topItvs}</td>
                </tr>
            `;
        });

        tableHtml += `</tbody></table>`;
        tableContainer.innerHTML = tableHtml;

    } catch (err) {
        console.error('Error rendering comparison:', err);
    }
}

// -----------------------------------------------------------------------------------------
// View 3: Evidence Sources & Full Citations
// -----------------------------------------------------------------------------------------
async function loadSources() {
    try {
        const res = await fetch(API.sources);
        if (!res.ok) throw new Error('Sources fetch failed');
        const list = await res.json();
        AppState.sources = list;
        renderSourcesView();
    } catch (err) {
        console.error('Error loading sources:', err);
    }
}

function renderSourcesView() {
    const container = document.getElementById('sources-list-container');
    if (!container) return;

    let filtered = AppState.sources.filter(s => {
        if (!AppState.sourceSearch) return true;
        const q = AppState.sourceSearch;
        return (
            (s.citation && s.citation.toLowerCase().includes(q)) ||
            (s.authors && s.authors.toLowerCase().includes(q)) ||
            (s.title && s.title.toLowerCase().includes(q)) ||
            (s.journal && s.journal.toLowerCase().includes(q)) ||
            (s.pmid && s.pmid.toLowerCase().includes(q)) ||
            (s.doi && s.doi.toLowerCase().includes(q))
        );
    });

    if (filtered.length === 0) {
        container.innerHTML = `<div class="col-span-2 p-8 text-center text-slate-500 text-xs">No citations found matching your search.</div>`;
        return;
    }

    container.innerHTML = filtered.map(s => {
        const pmidLink = s.pmid ? `https://pubmed.ncbi.nlm.nih.gov/${s.pmid}/` : null;
        const doiLink = s.doi ? `https://doi.org/${s.doi}` : null;
        const directUrl = s.url || pmidLink || doiLink;

        let badgeStyle = 'bg-slate-700 text-slate-300';
        if (s.study_type === 'rct' || s.study_type === 'meta_analysis') {
            badgeStyle = 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/30';
        } else if (s.study_type === 'prospective_cohort') {
            badgeStyle = 'bg-purple-500/20 text-purple-300 border border-purple-500/30';
        }

        return `
            <div class="bg-slate-900/90 p-4 rounded-xl border border-slate-700/80 space-y-2 flex flex-col justify-between shadow-sm">
                <div class="space-y-1.5">
                    <div class="flex items-center justify-between gap-2">
                        <span class="text-[10px] px-2 py-0.5 rounded font-semibold uppercase ${badgeStyle}">
                            ${s.study_type ? s.study_type.replace('_', ' ') : 'Peer-Reviewed'}
                        </span>
                        <span class="text-xs font-mono font-bold text-slate-400">${s.year || '2020'}</span>
                    </div>
                    <h3 class="text-xs font-bold text-slate-100 leading-snug">${s.title || s.citation}</h3>
                    <p class="text-[11px] text-slate-400 italic">${s.authors || 'Collaborative Research Consortium'}</p>
                    <p class="text-[11px] text-slate-500 font-medium">${s.journal || 'Journal Reference'}</p>
                </div>
                <div class="pt-2 border-t border-slate-800 flex items-center justify-between text-xs">
                    <div class="flex items-center gap-2">
                        ${s.pmid ? `<span class="text-[10px] text-slate-400 font-mono">PMID: ${s.pmid}</span>` : ''}
                        ${s.doi ? `<span class="text-[10px] text-slate-400 font-mono">DOI: ${s.doi}</span>` : ''}
                    </div>
                    ${directUrl ? `
                        <a href="${directUrl}" target="_blank" rel="noopener noreferrer" class="text-indigo-400 hover:text-indigo-300 font-semibold text-xs flex items-center gap-1 transition">
                            Read Paper <i class="fa-solid fa-arrow-up-right-from-square text-[10px]"></i>
                        </a>
                    ` : ''}
                </div>
            </div>
        `;
    }).join('');
}

// -----------------------------------------------------------------------------------------
// Disease Intelligence & Multi-Scale Alterations Logic
// -----------------------------------------------------------------------------------------
function setupDiseaseControls() {
    const searchInput = document.getElementById('disease-search');
    const categorySelect = document.getElementById('disease-filter-category');
    const sortSelect = document.getElementById('disease-sort-by');
    const modalCloseBtn = document.getElementById('disease-modal-close');
    const modal = document.getElementById('disease-modal');

    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            AppState.diseaseFilters.search = e.target.value.toLowerCase().trim();
            renderDiseasesView();
        });
    }

    if (categorySelect) {
        categorySelect.addEventListener('change', (e) => {
            AppState.diseaseFilters.category = e.target.value;
            renderDiseasesView();
        });
    }

    if (sortSelect) {
        sortSelect.addEventListener('change', (e) => {
            AppState.diseaseFilters.sortBy = e.target.value;
            renderDiseasesView();
        });
    }

    if (modalCloseBtn && modal) {
        modalCloseBtn.addEventListener('click', () => {
            modal.classList.add('hidden');
        });
    }

    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.classList.add('hidden');
            }
        });
    }
}

async function loadDiseases() {
    try {
        const res = await fetch(API.diseases());
        if (!res.ok) throw new Error('Failed to fetch diseases');
        const data = await res.json();
        AppState.diseases = data.diseases || [];
        renderDiseasesView();
    } catch (err) {
        console.error('Error loading diseases:', err);
    }
}

function renderDiseasesView() {
    const container = document.getElementById('disease-cards-container');
    const countEl = document.getElementById('disease-count-display');
    if (!container) return;

    let filtered = AppState.diseases.filter(d => {
        const matchCat = !AppState.diseaseFilters.category || d.category === AppState.diseaseFilters.category;
        const matchSearch = !AppState.diseaseFilters.search ||
            d.name.toLowerCase().includes(AppState.diseaseFilters.search) ||
            (d.primary_barrier && d.primary_barrier.toLowerCase().includes(AppState.diseaseFilters.search)) ||
            (d.barrier_detail && d.barrier_detail.toLowerCase().includes(AppState.diseaseFilters.search)) ||
            (d.category && d.category.toLowerCase().includes(AppState.diseaseFilters.search));
        return matchCat && matchSearch;
    });

    const sortBy = AppState.diseaseFilters.sortBy;
    if (sortBy === 'alterations_count') {
        filtered.sort((a, b) => (b.alterations_count || 0) - (a.alterations_count || 0));
    } else if (sortBy === 'therapeutics_count') {
        filtered.sort((a, b) => (b.therapeutics_count || 0) - (a.therapeutics_count || 0));
    } else if (sortBy === 'us_dalys') {
        filtered.sort((a, b) => (parseFloat(b.us_dalys) || 0) - (parseFloat(a.us_dalys) || 0));
    } else if (sortBy === 'nih_funding') {
        filtered.sort((a, b) => (parseFloat(b.nih_funding) || 0) - (parseFloat(a.nih_funding) || 0));
    } else {
        filtered.sort((a, b) => a.name.localeCompare(b.name));
    }

    if (countEl) countEl.textContent = `${filtered.length} Diseases`;

    if (filtered.length === 0) {
        container.innerHTML = `<div class="col-span-full p-12 text-center text-slate-500 text-sm">No diseases matched your criteria.</div>`;
        return;
    }

    container.innerHTML = filtered.map(d => {
        const dalysStr = d.us_dalys ? `${d.us_dalys}` : 'N/A';
        const fundingStr = d.nih_funding ? `${d.nih_funding}` : 'N/A';
        const altCount = d.alterations_count || 0;
        const itvCount = d.therapeutics_count || 0;

        return `
            <div class="disease-card bg-slate-900/90 rounded-xl p-5 border border-slate-800 flex flex-col justify-between cursor-pointer hover:border-indigo-500/50 shadow-md transition" onclick="openDiseaseModal('${d.slug}')">
                <div class="space-y-3">
                    <div class="flex items-center justify-between gap-2">
                        <span class="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-slate-800 text-indigo-300 border border-slate-700/60">${d.category || 'General'}</span>
                        <div class="flex items-center gap-1.5 text-xs text-slate-400 font-mono">
                            <i class="fa-solid fa-dna text-indigo-400"></i>
                            <span class="font-bold text-slate-200">${altCount}</span> alterations
                        </div>
                    </div>

                    <div>
                        <h3 class="text-base font-bold text-slate-100 group-hover:text-indigo-400 transition">${d.name}</h3>
                        <p class="text-xs text-slate-400 mt-1 line-clamp-2 leading-relaxed">${d.barrier_detail || d.primary_barrier || 'Comprehensive multi-scale disease profiling available.'}</p>
                    </div>
                </div>

                <div class="mt-4 pt-3 border-t border-slate-800/80 grid grid-cols-3 gap-2 text-center">
                    <div class="bg-slate-950/60 p-2 rounded-lg border border-slate-800/60">
                        <div class="text-[9px] uppercase tracking-wider text-slate-500 font-semibold">US DALYs</div>
                        <div class="text-xs font-mono font-bold text-slate-200 truncate">${dalysStr}</div>
                    </div>
                    <div class="bg-slate-950/60 p-2 rounded-lg border border-slate-800/60">
                        <div class="text-[9px] uppercase tracking-wider text-slate-500 font-semibold">NIH Funding</div>
                        <div class="text-xs font-mono font-bold text-emerald-400 truncate">${fundingStr}</div>
                    </div>
                    <div class="bg-slate-950/60 p-2 rounded-lg border border-slate-800/60">
                        <div class="text-[9px] uppercase tracking-wider text-slate-500 font-semibold">Rx Pipeline</div>
                        <div class="text-xs font-mono font-bold text-purple-400">${itvCount}</div>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

async function openDiseaseModal(slugOrId) {
    const modal = document.getElementById('disease-modal');
    if (!modal) return;
    modal.classList.remove('hidden');

    const modalContent = document.getElementById('disease-modal-body');
    if (modalContent) {
        modalContent.innerHTML = `
            <div class="p-12 text-center text-slate-400">
                <i class="fa-solid fa-circle-notch fa-spin text-2xl text-indigo-500 mb-3"></i>
                <div>Loading comprehensive disease intelligence profile...</div>
            </div>
        `;
    }

    try {
        const res = await fetch(API.diseaseDetail(slugOrId));
        if (!res.ok) throw new Error('Failed to fetch disease details');
        const detail = await res.json();
        AppState.selectedDisease = detail;
        renderDiseaseModalContent(detail);
    } catch (err) {
        console.error('Error opening disease modal:', err);
        if (modalContent) {
            modalContent.innerHTML = `<div class="p-8 text-center text-rose-400 text-sm">Failed to load disease data.</div>`;
        }
    }
}

function renderDiseaseModalContent(detail) {
    const modalBody = document.getElementById('disease-modal-body');
    if (!modalBody) return;

    const alts = detail.alterations || [];
    const matchedCount = detail.matched_biomarkers_count || 0;

    const typeA = alts.filter(a => a.alteration_type_code === 'A' || a.alteration_type === 'Molecular');
    const typeB = alts.filter(a => a.alteration_type_code === 'B' || a.alteration_type === 'Lab/Clinical');
    const typeC = alts.filter(a => a.alteration_type_code === 'C' || a.alteration_type === 'Scales & PROs');
    const typeD = alts.filter(a => a.alteration_type_code === 'D' || a.alteration_type === 'Pathology');
    const typeE = alts.filter(a => a.alteration_type_code === 'E' || a.alteration_type === 'Functional');

    const renderAlterationRow = (alt) => {
        let dirIcon = 'fa-arrows-left-right text-slate-400';
        let dirColor = 'text-slate-300';
        if (alt.direction === 'elevated' || alt.direction === 'increased') {
            dirIcon = 'fa-arrow-trend-up text-rose-400';
            dirColor = 'text-rose-300';
        } else if (alt.direction === 'reduced' || alt.direction === 'decreased') {
            dirIcon = 'fa-arrow-trend-down text-blue-400';
            dirColor = 'text-blue-300';
        }

        let evClass = 'evidence-emerging';
        if (alt.evidence_level === 'definitive') evClass = 'evidence-definitive';
        else if (alt.evidence_level === 'strong') evClass = 'evidence-strong';
        else if (alt.evidence_level === 'moderate') evClass = 'evidence-moderate';

        let typeBadgeClass = 'badge-type-a';
        if (alt.alteration_type_code === 'B') typeBadgeClass = 'badge-type-b';
        else if (alt.alteration_type_code === 'C') typeBadgeClass = 'badge-type-c';
        else if (alt.alteration_type_code === 'D') typeBadgeClass = 'badge-type-d';
        else if (alt.alteration_type_code === 'E') typeBadgeClass = 'badge-type-e';

        const matchBadge = alt.is_biomarker_match 
            ? `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/40 flex items-center gap-1 cursor-pointer hover:bg-indigo-500/30" onclick="navigateToBiomarker('${alt.biomarker_id}')"><i class="fa-solid fa-link text-[8px]"></i> Fitness Landscape Marker</span>`
            : '';

        return `
            <div class="p-3 bg-slate-900/80 rounded-lg border border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-3 hover:border-slate-700 transition">
                <div class="flex-1 space-y-1">
                    <div class="flex items-center gap-2 flex-wrap">
                        <span class="text-[9px] uppercase px-1.5 py-0.5 rounded font-bold ${typeBadgeClass}">${alt.alteration_type || 'Type ' + alt.alteration_type_code}</span>
                        ${alt.subtype ? `<span class="text-[10px] px-1.5 py-0.2 bg-slate-800 text-slate-400 rounded">${alt.subtype}</span>` : ''}
                        ${matchBadge}
                    </div>
                    <div class="text-xs font-bold text-slate-100 flex items-center gap-1.5">
                        <i class="fa-solid ${dirIcon}"></i>
                        <span class="${dirColor}">${alt.name}</span>
                        ${alt.sub_name ? `<span class="text-slate-400 font-normal">(${alt.sub_name})</span>` : ''}
                    </div>
                    ${alt.sources ? `<div class="text-[10px] text-slate-500 truncate max-w-md"><i class="fa-solid fa-book-open mr-1"></i>${alt.sources}</div>` : ''}
                </div>
                <div class="flex items-center gap-2 shrink-0">
                    <span class="text-[10px] px-2 py-0.5 rounded font-semibold capitalize ${evClass}">${alt.evidence_level || 'Documented'}</span>
                    ${alt.frequency ? `<span class="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-400">${alt.frequency}</span>` : ''}
                </div>
            </div>
        `;
    };

    modalBody.innerHTML = `
        <div class="space-y-6">
            <!-- Disease Header Info -->
            <div class="bg-slate-900 p-6 rounded-xl border border-slate-800 space-y-4">
                <div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div>
                        <div class="flex items-center gap-2 mb-1.5">
                            <span class="text-xs uppercase font-bold tracking-wider px-2.5 py-0.5 rounded-full bg-indigo-900/60 text-indigo-300 border border-indigo-700/50">${detail.category || 'Chronic Disease'}</span>
                            <span class="text-xs px-2.5 py-0.5 rounded-full bg-slate-800 text-slate-400 font-mono">${matchedCount} Matched Landscape Markers</span>
                        </div>
                        <h2 class="text-2xl font-black text-white">${detail.name}</h2>
                    </div>
                    <div class="flex items-center gap-3">
                        <div class="text-right">
                            <div class="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">US DALYs</div>
                            <div class="text-base font-mono font-bold text-slate-200">${detail.us_dalys || 'N/A'}</div>
                        </div>
                        <div class="h-8 w-px bg-slate-800"></div>
                        <div class="text-right">
                            <div class="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">NIH Funding</div>
                            <div class="text-base font-mono font-bold text-emerald-400">${detail.nih_funding || 'N/A'}</div>
                        </div>
                    </div>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4 border-t border-slate-800 text-xs">
                    <div>
                        <span class="text-slate-500 font-semibold uppercase text-[10px]">Primary Barrier to Cure / Reversal:</span>
                        <p class="text-slate-300 font-medium mt-0.5">${detail.primary_barrier || 'Biological irreversibility and multifactorial etiology.'}</p>
                    </div>
                    <div>
                        <span class="text-slate-500 font-semibold uppercase text-[10px]">Remission & Intervention Benchmark:</span>
                        <p class="text-slate-300 font-medium mt-0.5">Spontaneous: <span class="font-mono text-indigo-300">${detail.spontaneous_remission || 'Rare'}</span> | Best Intervention: <span class="font-mono text-emerald-300">${detail.best_intervention_remission || 'Standard Care'}</span></p>
                    </div>
                </div>
            </div>

            <!-- Alteration Filter Pills -->
            <div class="flex items-center justify-between flex-wrap gap-2">
                <div class="flex items-center gap-2 overflow-x-auto pb-1" id="modal-type-tabs">
                    <button class="px-3 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600 text-white transition active-modal-tab" onclick="switchModalTab('all')">All Alterations (${alts.length})</button>
                    <button class="px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800 text-slate-400 hover:text-white transition" onclick="switchModalTab('type-a')">Type A: Molecular (${typeA.length})</button>
                    <button class="px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800 text-slate-400 hover:text-white transition" onclick="switchModalTab('type-b')">Type B: Lab / Clinical (${typeB.length})</button>
                    <button class="px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800 text-slate-400 hover:text-white transition" onclick="switchModalTab('type-c')">Type C: Scales & PROs (${typeC.length})</button>
                    <button class="px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800 text-slate-400 hover:text-white transition" onclick="switchModalTab('type-d')">Type D: Pathology (${typeD.length})</button>
                    <button class="px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800 text-slate-400 hover:text-white transition" onclick="switchModalTab('type-e')">Type E: Functional (${typeE.length})</button>
                </div>
            </div>

            <!-- Alterations Container List -->
            <div id="modal-alterations-list" class="space-y-2 max-h-[50vh] overflow-y-auto pr-1">
                ${alts.length > 0 ? alts.map(renderAlterationRow).join('') : '<div class="p-8 text-center text-slate-500 text-xs">No multi-scale alterations recorded.</div>'}
            </div>
        </div>
    `;
}

function switchModalTab(tabKey) {
    if (!AppState.selectedDisease) return;
    AppState.activeDiseaseModalTab = tabKey;
    
    // Update button styling
    const tabsContainer = document.getElementById('modal-type-tabs');
    if (tabsContainer) {
        const btns = tabsContainer.querySelectorAll('button');
        btns.forEach(b => {
            b.className = 'px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800 text-slate-400 hover:text-white transition';
        });
    }

    const alts = AppState.selectedDisease.alterations || [];
    let filtered = alts;
    if (tabKey === 'type-a') filtered = alts.filter(a => a.alteration_type_code === 'A' || a.alteration_type === 'Molecular');
    else if (tabKey === 'type-b') filtered = alts.filter(a => a.alteration_type_code === 'B' || a.alteration_type === 'Lab/Clinical');
    else if (tabKey === 'type-c') filtered = alts.filter(a => a.alteration_type_code === 'C' || a.alteration_type === 'Scales & PROs');
    else if (tabKey === 'type-d') filtered = alts.filter(a => a.alteration_type_code === 'D' || a.alteration_type === 'Pathology');
    else if (tabKey === 'type-e') filtered = alts.filter(a => a.alteration_type_code === 'E' || a.alteration_type === 'Functional');

    const listContainer = document.getElementById('modal-alterations-list');
    if (listContainer) {
        if (filtered.length === 0) {
            listContainer.innerHTML = `<div class="p-8 text-center text-slate-500 text-xs">No alterations in this category.</div>`;
        } else {
            // Render filtered list
            renderDiseaseModalContent({
                ...AppState.selectedDisease,
                alterations: filtered
            });
        }
    }
}

function navigateToBiomarker(biomarkerId) {
    const modal = document.getElementById('disease-modal');
    if (modal) modal.classList.add('hidden');
    
    const tabBiomarkers = document.getElementById('tab-biomarkers');
    if (tabBiomarkers) tabBiomarkers.click();
    
    selectBiomarker(biomarkerId);
}

// -----------------------------------------------------------------------------------------
// Biomarker Detail Subview: Disease Alterations Mapping
// -----------------------------------------------------------------------------------------
async function renderBiomarkerDiseasesView(detail) {
    const container = document.getElementById('biomarker-diseases-container');
    if (!container) return;

    container.innerHTML = `
        <div class="p-8 text-center text-slate-400">
            <i class="fa-solid fa-circle-notch fa-spin text-lg text-indigo-500 mb-2"></i>
            <div class="text-xs">Querying multi-scale chronic disease network...</div>
        </div>
    `;

    try {
        const res = await fetch(API.biomarkerDiseases(detail.slug));
        if (!res.ok) throw new Error('Biomarker diseases fetch failed');
        const data = await res.json();
        const alterations = data.alterations || [];

        if (alterations.length === 0) {
            container.innerHTML = `
                <div class="p-8 text-center bg-slate-900/50 rounded-xl border border-slate-800 text-slate-500 text-xs space-y-2">
                    <i class="fa-solid fa-dna text-2xl text-slate-600"></i>
                    <div>No direct disease perturbation mappings recorded for ${detail.name}.</div>
                </div>
            `;
            return;
        }

        let html = `
            <div class="space-y-4">
                <div class="flex items-center justify-between bg-slate-900/80 p-4 rounded-xl border border-slate-800">
                    <div>
                        <h4 class="text-xs font-bold text-slate-200">Chronic Disease Perturbation Network</h4>
                        <p class="text-[11px] text-slate-400">Diseases where altered levels of <strong class="text-indigo-300">${detail.name}</strong> serve as clinical biomarkers or pathophysiological drivers.</p>
                    </div>
                    <span class="px-2.5 py-1 rounded-full bg-indigo-500/20 text-indigo-300 text-xs font-bold font-mono border border-indigo-500/30">${alterations.length} Diseases Mapped</span>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
        `;

        alterations.forEach(alt => {
            let dirColor = 'text-slate-300';
            let dirIcon = 'fa-arrows-left-right';
            if (alt.direction === 'elevated' || alt.direction === 'increased') {
                dirColor = 'text-rose-400';
                dirIcon = 'fa-arrow-trend-up';
            } else if (alt.direction === 'reduced' || alt.direction === 'decreased') {
                dirColor = 'text-blue-400';
                dirIcon = 'fa-arrow-trend-down';
            }

            html += `
                <div class="p-3.5 bg-slate-900/90 rounded-xl border border-slate-800 space-y-2 hover:border-indigo-500/40 transition">
                    <div class="flex items-center justify-between">
                        <span class="text-[10px] font-bold uppercase px-2 py-0.5 rounded bg-slate-800 text-slate-400">${alt.alteration_type || 'Alteration'}</span>
                        <button class="text-xs font-bold text-indigo-400 hover:text-indigo-300 flex items-center gap-1 transition" onclick="openDiseaseModal('${alt.disease_slug}')">
                            ${alt.disease_name} <i class="fa-solid fa-arrow-up-right-from-square text-[9px]"></i>
                        </button>
                    </div>
                    <div class="text-xs font-bold text-slate-100 flex items-center gap-1.5">
                        <i class="fa-solid ${dirIcon} ${dirColor}"></i>
                        <span class="${dirColor}">${alt.name}</span>
                    </div>
                    <div class="flex items-center justify-between text-[10px] text-slate-500 pt-1 border-t border-slate-800/80">
                        <span>Evidence: <strong class="text-slate-300 capitalize">${alt.evidence_level || 'Strong'}</strong></span>
                        <span>US DALYs: <strong class="text-slate-300 font-mono">${alt.us_dalys || 'N/A'}</strong></span>
                    </div>
                </div>
            `;
        });

        html += `</div></div>`;
        container.innerHTML = html;

    } catch (err) {
        console.error('Error rendering biomarker diseases:', err);
        container.innerHTML = `<div class="p-6 text-center text-rose-400 text-xs">Failed to load associated disease mappings.</div>`;
    }
}
