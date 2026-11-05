// Katalog des aktuellen Modellstands (generate_all_scenarios.py schreibt ihn am Laufende);
// für Probeläufe per ?catalog=./precomputed_test/catalog.json überschreibbar
const CATALOG_PATH = "./precomputed_v2/catalog.json";
const CATALOG_OVERRIDE_PATTERN = /^\.\/[\w-]+(\/[\w-]+)*\.json$/;

// Einbettung per iframe (?embed=1): ohne eigenen Header, Höhe an die Elternseite melden
const PAGE_PARAMS = new URLSearchParams(window.location.search);
const EMBED_MODE = PAGE_PARAMS.get("embed") === "1";
const EMBED_MESSAGE_TYPE = "ieej-height";

// Hinweis, wenn abhängige Felder automatisch angepasst wurden
const SNAP_HINT_MS = 5000;
const FIELD_LABELS = {
  h_highways: "Autobahnen",
  h_pv_types: "PV-Flächen",
  el_build_state: "Ausbaugrad",
  el_pv_type: "PV-Typ",
};

// Feste Auslegung der Landmaschinen (wie LANDSCAPE_TRACTOR_* in core/module_energy_landscape.py)
const LANDSCAPE_TRACTOR_WIDTH_M = 27;
const LANDSCAPE_TRACTOR_LENGTH_M = 15;
const LANDSCAPE_TRACTOR_TURN_RADIUS_M = 20.25;

// Basis-Variante Elsbachtal: je ein Unternehmen jedes Typs (wie ELSBACHTAL_BASIS_COMPANIES in Python)
const ELSBACHTAL_BASIS_COMPANIES = [0, 1, 2, 3, 5];

// Karte und Kennzahlen aktualisieren sich bei jeder Änderung, leicht entprellt
const UPDATE_DEBOUNCE_MS = 150;

const GEOJSON_PATHS = {
  A44: "./geometries/a44_beide.geojson",
  A46: "./geometries/a46_beide.geojson",
  // erzeugt mit core/auxiliary/export_landscape_geometries.py (27-m-Auslegung)
  landscape_vertical_50: "./geometries/landscape_vertical_50.geojson",
  landscape_vertical_100: "./geometries/landscape_vertical_100.geojson",
  landscape_tracking_50: "./geometries/landscape_tracking_50.geojson",
  landscape_tracking_100: "./geometries/landscape_tracking_100.geojson",
};

const LANDSCAPE_LAYER_KEYS = [
  "landscape_vertical_50",
  "landscape_vertical_100",
  "landscape_tracking_50",
  "landscape_tracking_100",
];

// PV-Typ der Energielandschaft → Geometrie und Bezeichnung im Lageplan
const LANDSCAPE_PV_TYPES = {
  5: { geo: "vertical", label: "Vertikal" },
  4: { geo: "tracking", label: "Tracking" },
};

const catalogIndex = new Map();
const payloadCache = new Map();
const viewState = {
  updateTimer: null,
  updateSeq: 0,
  lastInput: null,
  hasRendered: false,
};
const mapState = {
  map: null,
  geojsonCache: {},
  activeLayers: {},
  defaultView: { center: [51.0628, 6.49554], zoom: 12 },
};

// ---------------- Kanonischer Szenarioschlüssel (muss zu generate_all_scenarios.py passen) ----------------

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
  return {
    h_highways: sortUniqueStrings(rawInput.h_highways || []),
    h_pv_types: sortUniqueInts(rawInput.h_pv_types || []),
    el_build_state: Number.parseInt(String(rawInput.el_build_state || 0), 10) || 0,
    el_pv_type: Number.parseInt(String(rawInput.el_pv_type || 0), 10) || 0,
    el_tractor_width: LANDSCAPE_TRACTOR_WIDTH_M,
    el_tractor_length: LANDSCAPE_TRACTOR_LENGTH_M,
    el_tractor_turn_radius: roundFloat(LANDSCAPE_TRACTOR_TURN_RADIUS_M, 3),
    i_heat_cooling_electric: true,
    i_companies: sortUniqueInts(rawInput.i_companies || []),
    geh_variant: String(rawInput.geh_variant || "Keine"),
    bs_energy_kwh: null,
    bs_efficiency: null,
    bs_c_rate: null,
    js_concept: String(rawInput.js_concept || "Aus"),
  };
}

// ---------------- Eingaben lesen ----------------

function getCheckedValues(name) {
  return Array.from(document.querySelectorAll(`input[name="${name}"]:checked`)).map((el) => el.value);
}

function getRadioValue(name, fallback) {
  return document.querySelector(`input[name="${name}"]:checked`)?.value ?? fallback;
}

function isIndustryCustomMode() {
  return getRadioValue("i_mode", "basis") === "custom";
}

function getIndustryCompanyValues() {
  if (!isIndustryCustomMode()) {
    return [...ELSBACHTAL_BASIS_COMPANIES];
  }
  return getCheckedValues("i_company").map((v) => Number.parseInt(v, 10));
}

function collectRawInput() {
  return {
    h_highways: getCheckedValues("h_highways"),
    h_pv_types: getCheckedValues("h_pv_types"),
    el_build_state: Number(getRadioValue("el_build_state", 50)),
    el_pv_type: Number(getRadioValue("el_pv_type", 5)),
    i_companies: getIndustryCompanyValues(),
    geh_variant: getRadioValue("geh_variant", "Keine"),
    js_concept: getRadioValue("js_concept", "Aus"),
  };
}

function syncSidebarDisplay(cInput) {
  const custom = isIndustryCustomMode();
  document.getElementById("i-custom").hidden = !custom;
  document.getElementById("note-industry-basis").hidden = custom;
  document.getElementById("note-industry-none").hidden = !custom || cInput.i_companies.length > 0;
  document.getElementById("note-solar").hidden = cInput.h_highways.length > 0 && cInput.h_pv_types.length > 0;
}

// ---------------- Akkordeons und Reiter ----------------

function setAccordionOpen(button, open) {
  const panel = document.getElementById(button.getAttribute("aria-controls"));
  button.setAttribute("aria-expanded", open ? "true" : "false");
  if (panel) panel.classList.toggle("is-open", open);
}

function setupAccordions() {
  document.querySelectorAll(".acc-btn").forEach((button) => {
    setAccordionOpen(button, button.getAttribute("aria-expanded") === "true");
    button.addEventListener("click", () => {
      setAccordionOpen(button, button.getAttribute("aria-expanded") !== "true");
    });
  });
}

// Reiter: Ansicht (Energieflüsse | Lageplan) und Teilprojekte in der Seitenleiste
function setupTabs(tablist, onActivate) {
  const tabs = Array.from(tablist.querySelectorAll('[role="tab"]'));

  const activate = (tab, focus) => {
    tabs.forEach((t) => {
      const active = t === tab;
      t.setAttribute("aria-selected", active ? "true" : "false");
      t.tabIndex = active ? 0 : -1;
      document.getElementById(t.getAttribute("aria-controls")).hidden = !active;
    });
    if (focus) tab.focus();
    if (onActivate) onActivate(tab);
  };

  tabs.forEach((tab, idx) => {
    tab.addEventListener("click", () => activate(tab, false));
    tab.addEventListener("keydown", (event) => {
      if (!["ArrowRight", "ArrowLeft", "Home", "End"].includes(event.key)) return;
      event.preventDefault();
      let next = idx;
      if (event.key === "ArrowRight") next = (idx + 1) % tabs.length;
      if (event.key === "ArrowLeft") next = (idx - 1 + tabs.length) % tabs.length;
      if (event.key === "Home") next = 0;
      if (event.key === "End") next = tabs.length - 1;
      activate(tabs[next], true);
    });
  });
}

function setupExplainToggles() {
  document.querySelectorAll(".explain-toggle").forEach((button) => {
    const body = document.getElementById(button.getAttribute("aria-controls"));
    button.addEventListener("click", () => {
      const open = button.getAttribute("aria-expanded") !== "true";
      button.setAttribute("aria-expanded", open ? "true" : "false");
      body.hidden = !open;
    });
  });
}

function isSitePlanVisible() {
  return !document.getElementById("view-map").hidden;
}

// Leaflet erst beim ersten Öffnen des Lageplans starten (im verborgenen Reiter hätte die Karte keine Größe)
function showSitePlan() {
  if (!mapState.map) initLeafletMap();
  if (!mapState.map) return;
  mapState.map.invalidateSize();
  if (viewState.lastInput) updateMapHighlights(viewState.lastInput);
}

// ---------------- Szenario laden und anzeigen ----------------

function setScenarioHint(text) {
  const hint = document.getElementById("scenario-hint");
  hint.textContent = text;
  hint.hidden = !text;
}

function getCatalogPath() {
  const override = PAGE_PARAMS.get("catalog");
  return override && CATALOG_OVERRIDE_PATTERN.test(override) ? override : CATALOG_PATH;
}

async function loadCatalog() {
  const res = await fetch(getCatalogPath());
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }
  const entries = await res.json();
  for (const entry of entries) {
    let normalized = String(entry?.canonical_key || "");
    try {
      normalized = stableStringify(JSON.parse(normalized || "{}"));
    } catch {
      // Schlüssel unverändert übernehmen
    }
    catalogIndex.set(normalized, entry);
  }
  window.__IEEJ_CATALOG__ = entries;
  buildGroupIndex(entries);
}

// ---------------- Nicht vorberechnete Optionen deaktivieren ----------------

// Felder je Teilprojekt. Eine Option bleibt wählbar, wenn ein Katalogeintrag existiert, der sich vom
// aktuellen Szenario nur in diesem Feld unterscheidet. Beim führenden Feld eines Teilprojekts (erstes
// Feld der Liste) darf er zusätzlich in den übrigen Feldern des Teilprojekts abweichen; diese werden
// dann mitgezogen (z. B. Energielandschaft 100 % → PV-Typ horizontal).
const FIELD_GROUPS = {
  solar: ["h_highways", "h_pv_types"],
  landscape: ["el_build_state", "el_pv_type", "el_tractor_width", "el_tractor_length", "el_tractor_turn_radius"],
  industry: ["i_companies"],
  geh: ["geh_variant"],
  js: ["js_concept"],
};

// Name des Eingabefelds → Feld im kanonischen Schlüssel
const INPUT_FIELDS = {
  h_highways: "h_highways",
  h_pv_types: "h_pv_types",
  el_build_state: "el_build_state",
  el_pv_type: "el_pv_type",
  i_mode: "i_companies",
  i_company: "i_companies",
  geh_variant: "geh_variant",
  js_concept: "js_concept",
};

const UNAVAILABLE_TEXT = "nicht vorberechnet";
const groupIndex = new Map();

function groupOfField(field) {
  return Object.keys(FIELD_GROUPS).find((group) => FIELD_GROUPS[group].includes(field));
}

function restKey(key, group) {
  const rest = { ...key };
  for (const field of FIELD_GROUPS[group]) delete rest[field];
  return stableStringify(rest);
}

function buildGroupIndex(entries) {
  for (const group of Object.keys(FIELD_GROUPS)) {
    const byRest = new Map();
    for (const entry of entries) {
      let key;
      try {
        key = JSON.parse(entry.canonical_key);
      } catch {
        continue;
      }
      const rk = restKey(key, group);
      if (!byRest.has(rk)) byRest.set(rk, []);
      byRest.get(rk).push(key);
    }
    groupIndex.set(group, byRest);
  }
}

// Katalogschlüssel mit gleichem Wert in `field`, der sonst höchstens im eigenen Teilprojekt abweicht
// (nur beim führenden Feld); bei mehreren der mit den wenigsten Abweichungen
function findClosestKey(cInput, field) {
  const group = groupOfField(field);
  const candidates = groupIndex.get(group)?.get(restKey(cInput, group)) || [];
  const wanted = stableStringify(cInput[field]);
  let best = null;
  let bestDiff = FIELD_GROUPS[group][0] === field ? Infinity : 1;
  for (const key of candidates) {
    if (stableStringify(key[field]) !== wanted) continue;
    const diff = FIELD_GROUPS[group].filter((f) => stableStringify(key[f]) !== stableStringify(cInput[f])).length;
    if (diff < bestDiff) {
      best = key;
      bestDiff = diff;
    }
  }
  return best;
}

// Kanonische Eingabe, wenn die Option `input` gewählt (Radio) bzw. umgeschaltet (Checkbox) würde
function inputWithOption(input) {
  const raw = collectRawInput();
  if (input.name === "i_mode") {
    raw.i_companies = input.value === "basis"
      ? [...ELSBACHTAL_BASIS_COMPANIES]
      : getCheckedValues("i_company").map((v) => Number.parseInt(v, 10));
  } else if (input.name === "i_company") {
    const values = new Set(getCheckedValues("i_company"));
    if (values.has(input.value)) values.delete(input.value);
    else values.add(input.value);
    raw.i_companies = Array.from(values);
  } else if (input.type === "checkbox") {
    const values = new Set(raw[input.name]);
    if (values.has(input.value)) values.delete(input.value);
    else values.add(input.value);
    raw[input.name] = Array.from(values);
  } else {
    raw[input.name] = input.value;
  }
  return canonicalizeInput(raw);
}

function setOptionAvailable(input, available) {
  input.disabled = !available;
  const label = input.closest(".opt");
  if (available) {
    input.removeAttribute("aria-description");
    label?.removeAttribute("title");
  } else {
    input.setAttribute("aria-description", UNAVAILABLE_TEXT);
    label?.setAttribute("title", UNAVAILABLE_TEXT);
  }
}

function refreshOptionAvailability() {
  const inputs = document.querySelectorAll(".sidebar input[name]");
  const currentValid = catalogIndex.has(stableStringify(canonicalizeInput(collectRawInput())));
  inputs.forEach((input) => {
    const field = INPUT_FIELDS[input.name];
    // Ist die aktuelle Auswahl selbst nicht vorberechnet, bleibt alles wählbar, damit man herausfindet
    if (!field || !currentValid || (input.type === "radio" && input.checked)) {
      setOptionAvailable(input, true);
      return;
    }
    setOptionAvailable(input, findClosestKey(inputWithOption(input), field) !== null);
  });
}

// Übrige Felder eines Teilprojekts im Formular auf den gefundenen Katalogschlüssel setzen;
// liefert die Felder, die sich dabei geändert haben
function applyKeyToForm(key, group, cInput) {
  const changed = [];
  for (const field of FIELD_GROUPS[group]) {
    if (stableStringify(key[field]) !== stableStringify(cInput[field])) changed.push(field);
    document.querySelectorAll(`.sidebar input[name="${field}"]`).forEach((input) => {
      input.checked = input.type === "checkbox"
        ? key[field].map(String).includes(input.value)
        : Number(input.value) === Number(key[field]);
    });
  }
  return changed;
}

let snapHintTimer = null;

function hideSnapHint() {
  clearTimeout(snapHintTimer);
  const hint = document.getElementById("snap-hint");
  hint.textContent = "";
  hint.hidden = true;
}

// Kurzer Hinweis direkt unter der geänderten Auswahl
function showSnapHint(target, fields) {
  const hint = document.getElementById("snap-hint");
  const labels = fields.map((f) => FIELD_LABELS[f]).filter(Boolean);
  if (!labels.length) return;
  target.closest(".opt-group")?.after(hint);
  hint.hidden = false;
  hint.textContent = `${labels.join(", ")} angepasst – nur diese Kombination ist berechnet.`;
  snapHintTimer = setTimeout(hideSnapHint, SNAP_HINT_MS);
}

function onSidebarChange(event) {
  hideSnapHint();
  const field = INPUT_FIELDS[event.target?.name];
  if (field && catalogIndex.size > 0) {
    const cInput = canonicalizeInput(collectRawInput());
    if (!catalogIndex.has(stableStringify(cInput))) {
      const key = findClosestKey(cInput, field);
      if (key) showSnapHint(event.target, applyKeyToForm(key, groupOfField(field), cInput));
    }
    refreshOptionAvailability();
  }
  syncSidebarDisplay(canonicalizeInput(collectRawInput()));
  scheduleUpdate();
}

async function loadFlowPayload(flowPath) {
  if (payloadCache.has(flowPath)) return payloadCache.get(flowPath);
  const res = await fetch(flowPath);
  if (!res.ok) {
    throw new Error(`flow_data fetch failed (${res.status})`);
  }
  const payload = await res.json();
  payloadCache.set(flowPath, payload);
  return payload;
}

function scheduleUpdate() {
  clearTimeout(viewState.updateTimer);
  viewState.updateTimer = setTimeout(updateScenario, UPDATE_DEBOUNCE_MS);
}

async function updateScenario() {
  const seq = ++viewState.updateSeq;
  const cInput = canonicalizeInput(collectRawInput());
  viewState.lastInput = cInput;
  syncSidebarDisplay(cInput);
  if (isSitePlanVisible()) updateMapHighlights(cInput);

  const results = document.getElementById("results");
  const entry = catalogIndex.get(stableStringify(cInput));
  if (!entry) {
    setScenarioHint(
      viewState.hasRendered
        ? "Diese Kombination ist nicht vorberechnet. Angezeigt wird weiterhin das zuletzt verfügbare Szenario."
        : "Diese Kombination ist nicht vorberechnet. Bitte eine andere Auswahl treffen."
    );
    results.classList.add("is-stale");
    return;
  }

  try {
    const payload = await loadFlowPayload(entry.flow_path);
    if (seq !== viewState.updateSeq) return; // inzwischen neuere Auswahl
    renderParkKpis(document.getElementById("park-kpis"), payload);
    renderParkMap(document.getElementById("park-stage"), payload);
    document.getElementById("scenario-meta").textContent = `Szenario ${entry.scenario_id}`;
    viewState.hasRendered = true;
    setScenarioHint("");
    results.classList.remove("is-stale");
  } catch (err) {
    if (seq === viewState.updateSeq) setScenarioHint(`Szenario konnte nicht geladen werden (${err.message}).`);
  }
}

// ---------------- Lageplan (Leaflet) ----------------

function getLandscapeGeoKey(cInput) {
  const buildState = Number(cInput.el_build_state || 0);
  if (buildState !== 50 && buildState !== 100) {
    return null;
  }

  const pvType = LANDSCAPE_PV_TYPES[Number(cInput.el_pv_type)] || LANDSCAPE_PV_TYPES[5];
  return `landscape_${pvType.geo}_${buildState}`;
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
    const pvType = LANDSCAPE_PV_TYPES[Number(cInput.el_pv_type)] || LANDSCAPE_PV_TYPES[5];
    active.push(`Energielandschaft ${Number(cInput.el_build_state)} % (${pvType.label})`);
  }

  mapHint.textContent = active.length
    ? `Hervorgehoben: ${active.join(", ")}`
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
    document.getElementById("map-active-hint").textContent = `Lageplan konnte nicht aktualisiert werden (${err.message}).`;
  }
}

// ---------------- Einbettung ----------------

// Meldet die Dokumenthöhe an die einbettende Seite (siehe docs/einbettung.md)
function setupEmbedMode() {
  if (!EMBED_MODE) return;
  document.documentElement.classList.add("is-embed");
  if (window.parent === window) return;

  let lastHeight = 0;
  const report = () => {
    // Höhe des Inhalts (scrollHeight des Dokuments wird nie kleiner als der iframe selbst)
    const height = Math.ceil(document.body.getBoundingClientRect().height);
    if (height === lastHeight) return;
    lastHeight = height;
    window.parent.postMessage({ type: EMBED_MESSAGE_TYPE, height }, "*");
  };
  window.addEventListener("load", report);
  if (typeof ResizeObserver !== "undefined") {
    new ResizeObserver(report).observe(document.body);
  }
  report();
}

// ---------------- Start ----------------

async function init() {
  setupEmbedMode();
  setupAccordions();
  document.querySelectorAll('[role="tablist"]').forEach((tablist) => {
    setupTabs(tablist, (tab) => {
      if (tab.id === "tab-map") showSitePlan();
    });
  });
  setupExplainToggles();
  document.getElementById("park-legend").innerHTML = parkMapLegendHtml();
  document.querySelector(".sidebar").addEventListener("change", onSidebarChange);

  try {
    await loadCatalog();
  } catch (err) {
    setScenarioHint(`Szenariokatalog konnte nicht geladen werden (${err.message}).`);
    return;
  }
  refreshOptionAvailability();
  await updateScenario();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => {
    init();
  });
} else {
  init();
}
