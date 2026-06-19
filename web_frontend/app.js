const ICON_PATHS = {
  solar: "./icons/solar_highway.png",
  landscape: "./icons/energy_landscape.png",
  industry: "./icons/industrial_area.png",
  hub: "./icons/green_energy_hub.png",
  grid: "./icons/grid_supply.png",
  battery: "./icons/battery_storage.png",
  js: "./icons/juechen_sued.png",
};

const CATALOG_PATH = "./catalog.json";
const PRECOMPUTED_BASE = "./precomputed";

const LANDSCAPE_TRACTOR_LENGTH_M = 15;
const LANDSCAPE_TRACTOR_WIDTH_OPTIONS = {
  12: 9,
  18: 13.5,
  24: 18,
  27: 20.25,
};

const NODE_ICON_BY_ID = {
  solar: "solar",
  landscape: "landscape",
  grid: "grid",
  battery: "battery",
  industry: "industry",
  hub: "hub",
  js: "js",
};

const GEOJSON_PATHS = {
  A44: "./geometries/a44_beide.geojson",
  A46: "./geometries/a46_beide.geojson",
  landscape_vertical_50: "./geometries/Geometry_Vertikal_50_Prozent_20m.geojson",
  landscape_vertical_100: "./geometries/Geometry_Vertikal_Traktorbreite_20m.geojson",
  landscape_horizontal_50: "./geometries/Geometry_Horizontal_50_Prozent_20m.geojson",
  landscape_horizontal_100: "./geometries/Geometry_Horizontal_Traktorbreite_20m.geojson",
};

const LANDSCAPE_LAYER_KEYS = [
  "landscape_vertical_50",
  "landscape_vertical_100",
  "landscape_horizontal_50",
  "landscape_horizontal_100",
];

const EDGE_COLOR_FALLBACK = "#10B35A";

let catalogEntries = [];
const mapState = {
  map: null,
  geojsonCache: {},
  activeLayers: {},
  defaultView: { center: [51.0628, 6.49554], zoom: 12 },
};

function setStatus(text, match = "") {
  const statusText = document.getElementById("status-text");
  const statusMatch = document.getElementById("status-match");
  if (statusText) statusText.textContent = text;
  if (statusMatch) statusMatch.textContent = match;
}

function getNumberValue(id, fallback = 0) {
  const element = document.getElementById(id);
  const value = Number(element?.value);
  return Number.isFinite(value) ? value : fallback;
}

function roundFloat(value, digits = 3, fallback = 0) {
  const num = Number(value);
  if (!Number.isFinite(num)) {
    return fallback;
  }
  const factor = 10 ** digits;
  return Math.round(num * factor) / factor;
}

function sortUniqueStrings(values) {
  const set = new Set((values || []).filter((v) => v !== null && v !== undefined).map((v) => String(v)));
  return Array.from(set).sort();
}

function sortUniqueInts(values) {
  const out = [];
  for (const value of values || []) {
    const parsed = Number.parseInt(String(value), 10);
    if (Number.isFinite(parsed)) {
      out.push(parsed);
    }
  }
  return Array.from(new Set(out)).sort((a, b) => a - b);
}

function stableStringify(value) {
  if (value === null || typeof value !== "object") {
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    return `[${value.map((item) => stableStringify(item)).join(",")}]`;
  }
  const keys = Object.keys(value).sort();
  const body = keys.map((key) => `${JSON.stringify(key)}:${stableStringify(value[key])}`).join(",");
  return `{${body}}`;
}

function canonicalizeInput(rawInput) {
  const tractorWidth = Number.parseInt(String(rawInput.el_tractor_width || 12), 10) || 12;
  const tractorTurnRadius = LANDSCAPE_TRACTOR_WIDTH_OPTIONS[tractorWidth] ?? LANDSCAPE_TRACTOR_WIDTH_OPTIONS[12];

  return {
    h_highways: sortUniqueStrings(rawInput.h_highways || []),
    h_pv_types: sortUniqueInts(rawInput.h_pv_types || []),
    el_build_state: Number.parseInt(String(rawInput.el_build_state || 0), 10) || 0,
    el_pv_type: Number.parseInt(String(rawInput.el_pv_type || 0), 10) || 0,
    el_tractor_width: tractorWidth,
    el_tractor_length: LANDSCAPE_TRACTOR_LENGTH_M,
    el_tractor_turn_radius: roundFloat(tractorTurnRadius, 3),
    i_heat_cooling_electric: true,
    i_companies: sortUniqueInts(rawInput.i_companies || []),
    geh_h2_load_scenario: String(rawInput.geh_h2_load_scenario || "Keine"),
    geh_e_load_scenario: String(rawInput.geh_e_load_scenario || "Keine"),
    bs_energy_kwh: null,
    bs_efficiency: null,
    bs_c_rate: null,
    js_scenario: String(rawInput.js_scenario || "Aus"),
  };
}

function canonicalKey(rawInput) {
  return stableStringify(canonicalizeInput(rawInput));
}

function getCheckedValues(name) {
  return Array.from(document.querySelectorAll(`input[name="${name}"]:checked`)).map((el) => el.value);
}

function getSelectedValues(selectId) {
  const element = document.getElementById(selectId);
  if (!element) {
    return [];
  }
  return Array.from(element.selectedOptions).map((opt) => opt.value);
}

function getIndustryCompanyValues() {
  const values = [];
  for (let slot = 1; slot <= 5; slot += 1) {
    const el = document.getElementById(`i-company-${slot}`);
    const raw = String(el?.value || "").trim();
    if (raw === "") continue;
    const parsed = Number.parseInt(raw, 10);
    if (Number.isFinite(parsed)) {
      values.push(parsed);
    }
  }
  return values;
}

function collectRawInput() {
  return {
    h_highways: getCheckedValues("h_highways"),
    h_pv_types: getCheckedValues("h_pv_types"),
    el_build_state: getNumberValue("el-build-state", 50),
    el_pv_type: getNumberValue("el-pv-type", 5),
    el_tractor_width: getNumberValue("el-tractor-width", 12),
    i_companies: getIndustryCompanyValues(),
    geh_h2_load_scenario: document.getElementById("geh-h2")?.value || "Keine",
    geh_e_load_scenario: document.getElementById("geh-e")?.value || "Keine",
    js_scenario: document.getElementById("js-scenario")?.value || "Aus",
  };
}

function getLandscapeTractorRadius(width) {
  const parsedWidth = Number.parseInt(String(width || 12), 10) || 12;
  return LANDSCAPE_TRACTOR_WIDTH_OPTIONS[parsedWidth] ?? LANDSCAPE_TRACTOR_WIDTH_OPTIONS[12];
}

function syncLandscapeTractorDisplay() {
  const widthElement = document.getElementById("el-tractor-width");
  const displayElement = document.getElementById("el-tractor-turn-radius-value");
  if (!displayElement) return;

  const radius = getLandscapeTractorRadius(widthElement?.value);
  const formattedRadius = Number.isInteger(radius * 10) ? radius.toFixed(1) : radius.toFixed(2);
  displayElement.textContent = `${formattedRadius} m`;
}

function findCatalogMatch(selectedCanonicalKey) {
  for (const entry of catalogEntries) {
    if ((entry?.canonical_key_normalized || entry?.canonical_key) === selectedCanonicalKey) {
      return entry;
    }
  }
  return null;
}

function setInfoHidden(id, isHidden) {
  const element = document.getElementById(id);
  if (!element) return;
  element.hidden = isHidden;
}

function updateModuleFeedback(cInput) {
  const solarActive = cInput.h_highways.length > 0 && cInput.h_pv_types.length > 0;
  const landscapeActive = Number(cInput.el_build_state) > 0;
  const industryActive = cInput.i_companies.length > 0;
  const gehActive = cInput.geh_h2_load_scenario !== "Keine" || cInput.geh_e_load_scenario !== "Keine";
  const jsActive = cInput.js_scenario !== "Aus";

  setInfoHidden("info-solar", solarActive);
  setInfoHidden("info-industry", industryActive);
  setInfoHidden("info-geh", gehActive);
  setInfoHidden("info-js", jsActive);
}

function setAccordionOpen(accordion, open) {
  if (!accordion) return;
  const toggle = accordion.querySelector(".accordion-toggle");
  const wrap = accordion.querySelector(".accordion-content-wrap");
  accordion.classList.toggle("open", open);
  if (toggle) {
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
  }
  if (wrap) {
    wrap.style.gridTemplateRows = open ? "1fr" : "0fr";
  }
}

function setupTabGroup(config) {
  const buttons = Array.from(document.querySelectorAll(config.buttonSelector));
  const panels = Array.from(document.querySelectorAll(config.panelSelector));
  if (!buttons.length) return;

  const setActiveTab = (targetId) => {
    buttons.forEach((btn) => {
      const isActive = btn.dataset.tabTarget === targetId;
      btn.classList.toggle("active", isActive);
      btn.setAttribute("aria-selected", isActive ? "true" : "false");
      btn.setAttribute("tabindex", isActive ? "0" : "-1");
    });

    panels.forEach((panel) => {
      const isActive = panel.id === targetId;
      panel.classList.toggle("active", isActive);
      panel.hidden = !isActive;
      panel.setAttribute("aria-hidden", isActive ? "false" : "true");
    });

    if (typeof config.onChange === "function") {
      config.onChange(targetId);
    }
  };

  buttons.forEach((btn, idx) => {
    btn.addEventListener("click", () => {
      const target = btn.dataset.tabTarget;
      if (target) setActiveTab(target);
    });

    btn.addEventListener("keydown", (event) => {
      if (!["ArrowRight", "ArrowLeft", "Home", "End"].includes(event.key)) {
        return;
      }
      event.preventDefault();
      let nextIndex = idx;
      if (event.key === "ArrowRight") nextIndex = (idx + 1) % buttons.length;
      if (event.key === "ArrowLeft") nextIndex = (idx - 1 + buttons.length) % buttons.length;
      if (event.key === "Home") nextIndex = 0;
      if (event.key === "End") nextIndex = buttons.length - 1;
      buttons[nextIndex].focus();
      const target = buttons[nextIndex].dataset.tabTarget;
      if (target) setActiveTab(target);
    });
  });

  const activeBtn = buttons.find((btn) => btn.classList.contains("active"));
  const initialTarget = activeBtn?.dataset.tabTarget || buttons[0]?.dataset.tabTarget;
  if (initialTarget) setActiveTab(initialTarget);
}

function setupGenerationTabs() {
  setupTabGroup({
    buttonSelector: ".tab-btn-generation",
    panelSelector: ".generation-tab-panel",
  });
}

function setupConsumptionTabs() {
  setupTabGroup({
    buttonSelector: ".tab-btn-consumption",
    panelSelector: ".consumption-tab-panel",
    onChange: (targetId) => {
      const panel = document.getElementById(targetId);
      if (!panel) return;

      const allPanels = Array.from(document.querySelectorAll(".consumption-tab-panel"));
      allPanels.forEach((p) => {
        if (p !== panel) {
          p.querySelectorAll(".accordion").forEach((accordion) => setAccordionOpen(accordion, false));
        }
      });

      const firstAccordion = panel.querySelector(".accordion");
      if (firstAccordion) {
        setAccordionOpen(firstAccordion, true);
      }
    },
  });
}

function setupAccordions() {
  const accordions = Array.from(document.querySelectorAll(".accordion"));
  accordions.forEach((accordion) => {
    const toggle = accordion.querySelector(".accordion-toggle");
    const wrap = accordion.querySelector(".accordion-content-wrap");
    if (!toggle || !wrap) return;

    const isOpen = accordion.classList.contains("open");
    setAccordionOpen(accordion, isOpen);

    toggle.addEventListener("click", () => {
      const open = !accordion.classList.contains("open");
      setAccordionOpen(accordion, open);
    });
  });
}

function getLandscapeGeoKey(cInput) {
  const buildState = Number(cInput.el_build_state || 0);
  if (buildState !== 50 && buildState !== 100) {
    return null;
  }

  const pvType = Number(cInput.el_pv_type || 0);
  const orientation = pvType === 6 ? "horizontal" : "vertical";
  return `landscape_${orientation}_${buildState}`;
}

function getLandscapeStyle(cInput) {
  const buildState = Number(cInput.el_build_state || 0);
  if (buildState === 50) {
    return {
      color: "#16A34A",
      weight: 1.6,
      fillColor: "#86EFAC",
      fillOpacity: 0.24,
      opacity: 0.82,
      dashArray: "6 4",
    };
  }
  return {
    color: "#15803D",
    weight: 2.2,
    fillColor: "#4ADE80",
    fillOpacity: 0.38,
    opacity: 0.9,
  };
}

function deactivateLandscapeLayers(exceptKey = null) {
  for (const key of LANDSCAPE_LAYER_KEYS) {
    if (key !== exceptKey) {
      deactivateGeoLayer(key);
    }
  }
}

function setMapHint(cInput) {
  const mapHint = document.getElementById("map-active-hint");
  if (!mapHint) return;

  const active = [];
  if (cInput.h_highways.includes("A44")) active.push("A44");
  if (cInput.h_highways.includes("A46")) active.push("A46");

  const landscapeKey = getLandscapeGeoKey(cInput);
  if (landscapeKey) {
    const orientation = Number(cInput.el_pv_type || 0) === 6 ? "Horizontal" : "Vertikal";
    active.push(`Energielandschaft ${Number(cInput.el_build_state)}% (${orientation})`);
  }

  mapHint.textContent = active.length
    ? `Aktiv hervorgehoben: ${active.join(", ")}`
    : "Keine aktive Kartenhervorhebung.";
}

function initLeafletMap() {
  const mapContainer = document.getElementById("leaflet-map");
  if (!mapContainer || typeof L === "undefined") {
    return;
  }

  mapState.map = L.map(mapContainer, {
    zoomControl: true,
    scrollWheelZoom: false,
    preferCanvas: true,
  }).setView(mapState.defaultView.center, mapState.defaultView.zoom);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap-Mitwirkende",
  }).addTo(mapState.map);

  L.control.scale({ imperial: false, maxWidth: 120 }).addTo(mapState.map);
}

async function fetchGeoJsonCached(key) {
  if (mapState.geojsonCache[key]) {
    return mapState.geojsonCache[key];
  }
  const path = GEOJSON_PATHS[key];
  if (!path) {
    throw new Error(`Missing path for ${key}`);
  }
  const res = await fetch(path);
  if (!res.ok) {
    throw new Error(`GeoJSON load failed for ${key} (${res.status})`);
  }
  const data = await res.json();
  mapState.geojsonCache[key] = data;
  return data;
}

async function activateGeoLayer(key, style) {
  if (!mapState.map) return null;
  const data = await fetchGeoJsonCached(key);

  if (mapState.activeLayers[key]) {
    mapState.activeLayers[key].setStyle(style);
    if (!mapState.map.hasLayer(mapState.activeLayers[key])) {
      mapState.activeLayers[key].addTo(mapState.map);
    }
    return mapState.activeLayers[key];
  }

  const layer = L.geoJSON(data, { style });
  layer.addTo(mapState.map);
  mapState.activeLayers[key] = layer;
  return layer;
}

function deactivateGeoLayer(key) {
  if (!mapState.map) return;
  const layer = mapState.activeLayers[key];
  if (layer && mapState.map.hasLayer(layer)) {
    mapState.map.removeLayer(layer);
  }
}

async function updateMapHighlights(cInput) {
  if (!mapState.map) return;

  const activeLayers = [];
  setMapHint(cInput);

  try {
    if (cInput.h_highways.includes("A44")) {
      const layer = await activateGeoLayer("A44", {
        color: "#2563EB",
        weight: 5,
        opacity: 0.95,
      });
      if (layer) activeLayers.push(layer);
    } else {
      deactivateGeoLayer("A44");
    }

    if (cInput.h_highways.includes("A46")) {
      const layer = await activateGeoLayer("A46", {
        color: "#EA580C",
        weight: 5,
        opacity: 0.95,
      });
      if (layer) activeLayers.push(layer);
    } else {
      deactivateGeoLayer("A46");
    }

    const landscapeKey = getLandscapeGeoKey(cInput);
    if (landscapeKey) {
      const layer = await activateGeoLayer(landscapeKey, getLandscapeStyle(cInput));
      if (layer) activeLayers.push(layer);
      deactivateLandscapeLayers(landscapeKey);
    } else {
      deactivateLandscapeLayers();
    }

    if (activeLayers.length > 0) {
      const group = L.featureGroup(activeLayers);
      mapState.map.fitBounds(group.getBounds(), { padding: [24, 24], maxZoom: 13 });
    } else {
      mapState.map.setView(mapState.defaultView.center, mapState.defaultView.zoom);
    }
  } catch (err) {
    setMapHint({ h_highways: [], el_build_state: 0 });
    setStatus("Karte konnte nicht aktualisiert werden", String(err));
  }
}

function setLoadButtonBusy(isBusy) {
  const btn = document.getElementById("btn-load");
  if (!btn) return;
  btn.setAttribute("aria-busy", isBusy ? "true" : "false");
  btn.disabled = isBusy;
  btn.textContent = isBusy ? "Lade Szenario..." : "Szenario laden";
}

function formatEnergy(kwh) {
  const val = Number(kwh) || 0;
  if (Math.abs(val) >= 1_000_000) return `${(val / 1_000_000).toFixed(2)} GWh`;
  if (Math.abs(val) >= 1_000) return `${(val / 1_000).toFixed(2)} MWh`;
  return `${val.toFixed(2)} kWh`;
}

function renderSummaryCards(payload) {
  const container = document.getElementById("summary-cards");
  if (!container) return;
  const summary = payload?.annual_summary || {};
  const generation = summary.generation || {};
  const demand = summary.demand || {};
  const balance = summary.balance || {};
  const grid = summary.grid || {};

  const cards = [
    { label: "Erzeugung", value: formatEnergy(generation.total_generation_kwh) },
    { label: "Verbrauch", value: formatEnergy(demand.total_demand_kwh) },
    { label: "Bilanz", value: formatEnergy(balance.bal_energy_kwh) },
    { label: "Netzimport", value: formatEnergy(grid.import_kwh) },
  ];

  container.innerHTML = "";
  for (const card of cards) {
    const cardEl = document.createElement("div");
    cardEl.className = "summary-card";
    cardEl.innerHTML = `<div class="summary-label">${card.label}</div><div class="summary-value">${card.value}</div>`;
    container.appendChild(cardEl);
  }
}

function nodePosition(node, width, height, padding) {
  const x = padding + Number(node.x || 0) * (width - 2 * padding);
  const y = padding + (1 - Number(node.y || 0)) * (height - 2 * padding);
  return { x, y };
}

function buildPolylinePath(points) {
  if (!points.length) return "";
  const [first, ...rest] = points;
  let d = `M ${first.x.toFixed(2)} ${first.y.toFixed(2)}`;
  for (const p of rest) {
    d += ` L ${p.x.toFixed(2)} ${p.y.toFixed(2)}`;
  }
  return d;
}

function computeEdgeRoute(source, target) {
  const dx = target.x - source.x;
  const dy = target.y - source.y;
  if (Math.abs(dx) >= Math.abs(dy)) {
    const mx = source.x + dx * 0.5;
    return [source, { x: mx, y: source.y }, { x: mx, y: target.y }, target];
  }
  const my = source.y + dy * 0.5;
  return [source, { x: source.x, y: my }, { x: target.x, y: my }, target];
}

function renderFlowSvg(payload) {
  const stage = document.getElementById("flow-stage");
  if (!stage) return;

  const nodes = Array.isArray(payload?.flow_nodes) ? payload.flow_nodes : [];
  const edges = Array.isArray(payload?.flow_edges) ? payload.flow_edges : [];
  const width = 1200;
  const height = 680;
  const padding = 70;

  const nodeById = {};
  for (const node of nodes) {
    nodeById[node.id] = node;
  }

  const svgParts = [];
  svgParts.push(`<svg viewBox="0 0 ${width} ${height}" class="flow-svg" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Energiefluss">`);
  svgParts.push("<defs>");
  svgParts.push('<marker id="arrow-head" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto"><polygon points="0 0, 10 3.5, 0 7" fill="#475569" /></marker>');
  svgParts.push("</defs>");

  for (const edge of edges) {
    const annual = Number(edge.annual_kwh) || 0;
    if (annual <= 0) continue;

    const sourceNode = nodeById[edge.source];
    const targetNode = nodeById[edge.target];
    if (!sourceNode || !targetNode) continue;

    const source = nodePosition(sourceNode, width, height, padding);
    const target = nodePosition(targetNode, width, height, padding);
    const route = computeEdgeRoute(source, target);
    const path = buildPolylinePath(route);
    const stroke = Math.max(1.8, Number(edge.stroke_px) || 2);
    const color = String(edge.color || EDGE_COLOR_FALLBACK);

    const title = `${edge.id} | ${formatEnergy(edge.annual_kwh)} | peak ${(Number(edge.peak_kw) || 0).toFixed(2)} kW`;
    svgParts.push(`<path d="${path}" fill="none" stroke="${color}" stroke-width="${stroke.toFixed(2)}" marker-end="url(#arrow-head)"><title>${title}</title></path>`);
  }

  for (const node of nodes) {
    const pos = nodePosition(node, width, height, padding);
    const isSystem = node.id === "system";
    const label = String(node.label || node.id || "node");

    if (isSystem) {
      svgParts.push(`<circle cx="${pos.x.toFixed(2)}" cy="${pos.y.toFixed(2)}" r="16" fill="#ffffff" stroke="#475569" stroke-width="2" />`);
      svgParts.push(`<text x="${pos.x.toFixed(2)}" y="${(pos.y + 30).toFixed(2)}" text-anchor="middle" class="node-label">${label}</text>`);
      continue;
    }

    const boxW = 148;
    const boxH = 84;
    const x = pos.x - boxW / 2;
    const y = pos.y - boxH / 2;
    const iconKey = NODE_ICON_BY_ID[node.id];
    const iconPath = ICON_PATHS[iconKey];

    svgParts.push(`<rect x="${x.toFixed(2)}" y="${y.toFixed(2)}" width="${boxW}" height="${boxH}" rx="12" fill="#ffffff" stroke="#94a3b8" stroke-width="2" />`);
    if (iconPath) {
      svgParts.push(`<image href="${iconPath}" x="${(pos.x - 17).toFixed(2)}" y="${(pos.y - 17).toFixed(2)}" width="34" height="34" preserveAspectRatio="xMidYMid meet" />`);
    }
    svgParts.push(`<text x="${pos.x.toFixed(2)}" y="${(y - 10).toFixed(2)}" text-anchor="middle" class="node-label">${label}</text>`);
  }

  svgParts.push("</svg>");
  stage.innerHTML = svgParts.join("");
}

async function loadFlowPayload(flowPath) {
  const res = await fetch(flowPath);
  if (!res.ok) {
    throw new Error(`flow_data fetch failed (${res.status})`);
  }
  return res.json();
}

async function loadCatalog() {
  try {
    const res = await fetch(CATALOG_PATH);
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }

    catalogEntries = await res.json();
    catalogEntries = catalogEntries.map((entry) => {
      let normalized = entry?.canonical_key;
      try {
        normalized = stableStringify(JSON.parse(String(entry?.canonical_key || "{}")));
      } catch {
        normalized = String(entry?.canonical_key || "");
      }
      return {
        ...entry,
        canonical_key_normalized: normalized,
      };
    });
    setStatus("catalog.json erfolgreich geladen.", `Szenarien im Index: ${catalogEntries.length}`);

    window.__IEEJ_CATALOG__ = catalogEntries;
  } catch (err) {
    setStatus("Fehler beim Laden von catalog.json", String(err));
  }
}

async function runScenarioLoad() {
  setLoadButtonBusy(true);
  if (!Array.isArray(catalogEntries) || catalogEntries.length === 0) {
    setStatus("Noch kein Katalog geladen.", "Bitte Seite neu laden.");
    setLoadButtonBusy(false);
    return;
  }

  const rawInput = collectRawInput();
  const cInput = canonicalizeInput(rawInput);
  updateModuleFeedback(cInput);
  await updateMapHighlights(cInput);

  const key = stableStringify(cInput);
  const match = findCatalogMatch(key);

  if (!match) {
    renderSummaryCards({ annual_summary: {} });
    const flowStage = document.getElementById("flow-stage");
    if (flowStage) {
      flowStage.textContent = "Diese Kombination ist im Precomputed-Katalog noch nicht verfuegbar.";
    }
    setStatus("Kein Match im Katalog.", key);
    setLoadButtonBusy(false);
    return;
  }

  try {
    const payload = await loadFlowPayload(match.flow_path);
    renderSummaryCards(payload);
    renderFlowSvg(payload);

    // Use the payload input to keep map highlight in sync with loaded scenario.
    const payloadInput = canonicalizeInput(payload?.input || rawInput);
    await updateMapHighlights(payloadInput);

    setStatus("Szenario geladen.", `${match.scenario_id} | ${match.flow_path}`);
  } catch (err) {
    setStatus("Fehler beim Laden von flow_data.json", String(err));
  } finally {
    setLoadButtonBusy(false);
  }
}

function setupLoadButton() {
  const btn = document.getElementById("btn-load");
  if (!btn) return;
  btn.addEventListener("click", runScenarioLoad);
}

function setupReactiveInputHandlers() {
  const selectors = [
    "input[name='h_highways']",
    "input[name='h_pv_types']",
    "#el-build-state",
    "#el-pv-type",
    "#el-tractor-width",
    "#i-company-1",
    "#i-company-2",
    "#i-company-3",
    "#i-company-4",
    "#i-company-5",
    "#geh-h2",
    "#geh-e",
    "#js-scenario",
  ];

  selectors.forEach((selector) => {
    document.querySelectorAll(selector).forEach((el) => {
      el.addEventListener("change", async () => {
        const cInput = canonicalizeInput(collectRawInput());
        updateModuleFeedback(cInput);
        await updateMapHighlights(cInput);
      });
    });
  });
}

function setupKeyboardShortcuts() {
  document.addEventListener("keydown", (event) => {
    const loadShortcut = (event.ctrlKey || event.metaKey) && event.key === "Enter";
    if (!loadShortcut) return;

    const tag = (document.activeElement?.tagName || "").toLowerCase();
    const isEditable = ["input", "select", "textarea"].includes(tag);
    if (isEditable) {
      event.preventDefault();
    }

    runScenarioLoad();
  });
}

async function init() {
  setupGenerationTabs();
  setupAccordions();
  setupConsumptionTabs();
  setupLoadButton();
  setupKeyboardShortcuts();
  setupReactiveInputHandlers();
  initLeafletMap();
  syncLandscapeTractorDisplay();
  const widthElement = document.getElementById("el-tractor-width");
  if (widthElement) {
    widthElement.addEventListener("change", syncLandscapeTractorDisplay);
  }
  await loadCatalog();

  const initialInput = canonicalizeInput(collectRawInput());
  updateModuleFeedback(initialInput);
  await updateMapHighlights(initialInput);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => {
    init();
  });
} else {
  init();
}
