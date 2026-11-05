/*
 * Parkkarte Innovationspark Jüchen
 *
 * Stilisierte Karte im Design der Website: Teilprojekte als Sechsecke,
 * Autobahnen als Linien und die bilanziellen Energieflüsse als laufende
 * Chevrons. Klassisches Skript ohne Abhängigkeiten – im Browser stehen die
 * Funktionen global zur Verfügung, unter Node (Test) über module.exports.
 */

const PARK_MAP_VIEWBOX = { width: 800, height: 900 };

// Teilprojekte als Sechsecke (Spitze oben); Positionen am Website-Screenshot ausgerichtet.
// tx verschiebt den Text, wo die A44n durch das Sechseck läuft.
const PARK_NODES = {
  solar: { cx: 143, cy: 250, r: 95, title: ["Solarautobahn"], short: "Solar", role: "producer" },
  js: { cx: 454, cy: 185, r: 85, title: ["Stadtteilentwicklung", "Jüchen Süd"], short: "Jüchen Süd", role: "consumer" },
  industry: { cx: 632, cy: 155, r: 85, title: ["Industriegebiet", "Elsbachtal"], short: "Industrie", role: "consumer" },
  landscape: { cx: 454, cy: 457, r: 175, tx: 490, title: ["Energielandschaft"], short: "Landschaft", role: "producer" },
  hub: { cx: 226, cy: 730, r: 95, title: ["Green Energy Hub", "Autohof der Zukunft"], short: "GEH", role: "consumer" },
  grid: { cx: 660, cy: 775, r: 80, title: ["Stromnetz"], short: "Netz", role: "grid" },
};

const PARK_NODE_NAMES = {
  solar: "Solarautobahn",
  landscape: "Energielandschaft",
  hub_pv: "PV am Green Energy Hub",
  industry: "Industriegebiet Elsbachtal",
  js: "Stadtteilentwicklung Jüchen Süd",
  hub: "Green Energy Hub",
  grid: "Stromnetz",
};

// Chevron-Routen: Start/Ende am Sechseckrand, optional ein Kontrollpunkt (quadratische Bézierkurve).
// kind: "self" = Eigenstrom Erzeuger → Verbraucher, "export" = Park → Netz, "import" = Netz → Park.
const PARK_ROUTES = [
  { id: "solar-js", kind: "self", from: "solar", to: "js", start: [242, 215], end: [374, 215] },
  { id: "solar-industry", kind: "self", from: "solar", to: "industry", start: [214, 196], ctrl: [420, -40], end: [574, 104] },
  { id: "solar-hub", kind: "self", from: "solar", to: "hub", start: [168, 352], end: [168, 652] },
  { id: "landscape-js", kind: "self", from: "landscape", to: "js", start: [372, 314], end: [410, 252] },
  { id: "landscape-industry", kind: "self", from: "landscape", to: "industry", start: [532, 322], end: [588, 220] },
  { id: "landscape-hub", kind: "self", from: "landscape", to: "hub", start: [336, 566], end: [282, 656] },
  { id: "export", kind: "export", from: "landscape", to: "grid", start: [548, 578], end: [600, 729] },
  { id: "import", kind: "import", from: "grid", to: "landscape", start: [650, 701], end: [600, 548] },
];

const PARK_CHEVRON_SPACING = 16; // Abstand der Chevrons in viewBox-Einheiten
const PARK_WAVE_STEP_S = 0.1; // Versatz der Helligkeitswelle je Chevron → gleiche Geschwindigkeit für alle Routen
const PARK_WAVE_PERIOD_S = 1.5;

const PARK_NF0 = new Intl.NumberFormat("de-DE", { maximumFractionDigits: 0 });
const PARK_NF1 = new Intl.NumberFormat("de-DE", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

function parkAbs(value) {
  return Math.abs(Number(value) || 0);
}

function parkSum(obj) {
  return Object.values(obj).reduce((acc, v) => acc + v, 0);
}

function parkFormatEnergy(kwh, perYear = true) {
  const v = parkAbs(kwh);
  const unit = v >= 1_000_000 ? `${PARK_NF1.format(v / 1_000_000)} GWh` : `${PARK_NF0.format(v / 1_000)} MWh`;
  return perYear ? `${unit}/a` : unit;
}

function parkFormatPower(kw) {
  return `${PARK_NF1.format(parkAbs(kw) / 1_000)} MW`;
}

function parkFormatPercent(share) {
  return `${PARK_NF0.format(Math.max(0, share) * 100)} %`;
}

function parkEscape(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/**
 * Bilanzielle Zuordnung der Jahresenergie: Jeder Verbraucher erhält den im Park
 * genutzten Strom anteilig zu seinem Bedarf, jeder Erzeuger liefert anteilig zu
 * seiner Erzeugung. Reine Funktion, nur annual_summary als Eingabe.
 */
function computeParkFlows(annualSummary) {
  const summary = annualSummary || {};
  const gen = summary.generation || {};
  const dem = summary.demand || {};
  const grid = summary.grid || {};

  const generation = {
    solar: parkAbs(gen.solar_highway_kwh),
    landscape: parkAbs(gen.energy_landscape_kwh),
    hub_pv: parkAbs(gen.green_energy_hub_pv_kwh),
  };
  const demand = {
    industry: parkAbs(dem.industry_kwh),
    js: parkAbs(dem.juechen_sued_kwh),
    hub: parkAbs(dem.green_energy_hub_kwh),
  };

  const G = parkSum(generation);
  const D = parkSum(demand);
  const E = parkAbs(grid.export_kwh);
  const I = parkAbs(grid.import_kwh);
  const S = Math.max(G - E, 0);

  const consumers = {};
  for (const [c, d] of Object.entries(demand)) {
    const covered = D > 0 ? Math.min(d, (S * d) / D) : 0;
    consumers[c] = { demand: d, covered, gridImport: d - covered, selfShare: d > 0 ? covered / d : 0 };
  }

  const producers = {};
  for (const [p, g] of Object.entries(generation)) {
    producers[p] = { generation: g, export: G > 0 ? (E * g) / G : 0 };
  }

  const flows = [];
  for (const p of Object.keys(generation)) {
    for (const c of Object.keys(demand)) {
      flows.push({ from: p, to: c, kwh: G > 0 ? (consumers[c].covered * generation[p]) / G : 0 });
    }
  }

  const covered = parkSum(Object.fromEntries(Object.entries(consumers).map(([c, v]) => [c, v.covered])));
  return {
    totals: {
      generation: G,
      demand: D,
      selfUse: S,
      covered,
      gridImport: I,
      gridExport: E,
      maxImportKw: parkAbs(grid.max_import_kw),
      maxExportKw: parkAbs(grid.max_export_kw),
      autarky: D > 0 ? covered / D : 0,
      selfConsumption: G > 0 ? Math.min(S, D) / G : 0,
    },
    producers,
    consumers,
    flows,
  };
}

/**
 * Statischer Kartenhintergrund (Landflächen, Autobahnen, Schilder, Städte-Hinweise)
 * als Inhalt eines <svg viewBox="0 0 800 900">.
 *
 * Austauschbar: Eine Original-Grafik der Website kann entweder hier eingesetzt oder
 * über renderParkMap(stage, payload, { background: "<g>…</g>" }) übergeben werden.
 * Sechsecke und Flüsse liegen immer darüber und hängen nicht von diesem Inhalt ab.
 */
function parkMapBackground() {
  const roads = [
    // A46 (oben, von West nach Ost über das Kreuz)
    "M -10 58 C 70 96 180 100 270 94 C 400 84 520 60 620 38 C 690 22 740 10 790 -6",
    // A44n (vom Kreuz diagonal nach Süden)
    "M 268 -10 C 268 60 270 120 250 175 C 238 214 300 282 340 360 C 390 460 442 560 436 660 C 430 752 362 830 322 910",
    // A61 (unten links)
    "M -10 792 L 46 748 L 150 860",
  ];
  const roadSvg = roads
    .map((d) => `<path class="park-road-casing" d="${d}"/><path class="park-road-core" d="${d}"/>`)
    .join("");

  const signs = [
    { label: "A46", x: 150, y: 97 },
    { label: "A44n", x: 306, y: 305 },
    { label: "A61", x: 108, y: 800 },
  ]
    .map(
      (s) =>
        `<g class="park-sign"><rect x="${s.x - 28}" y="${s.y - 14}" width="56" height="28" rx="6"/>` +
        `<text x="${s.x}" y="${s.y + 5}" text-anchor="middle">${s.label}</text></g>`
    )
    .join("");

  const cities = [
    { label: "↑ Mönchengladbach", x: 58, y: 38, w: 170 },
    { label: "→ Düsseldorf", x: 652, y: 238, w: 112 },
    { label: "↓ Köln", x: 704, y: 636, w: 66 },
  ]
    .map(
      (c) =>
        `<g class="park-city"><rect x="${c.x}" y="${c.y}" width="${c.w}" height="28"/>` +
        `<text x="${c.x + 8}" y="${c.y + 19}">${c.label}</text></g>`
    )
    .join("");

  return (
    `<rect class="park-bg" x="0" y="0" width="800" height="900"/>` +
    // Landflächen (dunkleres Grün) oben, rechts und unten rechts
    `<path class="park-land" d="M 0 0 H 800 V 92 C 700 100 600 96 470 102 C 330 108 150 126 0 142 Z"/>` +
    `<path class="park-land" d="M 800 88 C 760 96 738 112 744 160 C 752 232 650 252 655 330 C 660 420 694 470 640 540 C 590 610 520 624 430 700 C 362 760 318 830 292 900 H 800 Z"/>` +
    roadSvg +
    signs +
    cities
  );
}

function parkHexPoints(cx, cy, r) {
  const pts = [];
  for (let k = 0; k < 6; k += 1) {
    const a = ((-90 + 60 * k) * Math.PI) / 180;
    pts.push(`${(cx + r * Math.cos(a)).toFixed(1)},${(cy + r * Math.sin(a)).toFixed(1)}`);
  }
  return pts.join(" ");
}

function parkRoutePoint(route, t) {
  const [x0, y0] = route.start;
  const [x1, y1] = route.end;
  const [cx, cy] = route.ctrl || [(x0 + x1) / 2, (y0 + y1) / 2];
  const u = 1 - t;
  return {
    x: u * u * x0 + 2 * u * t * cx + t * t * x1,
    y: u * u * y0 + 2 * u * t * cy + t * t * y1,
  };
}

// Gleichmäßig verteilte Positionen (mit Richtung) entlang der Route
function parkChevronPositions(route, spacing) {
  const samples = 96;
  const pts = [];
  const lengths = [0];
  for (let i = 0; i <= samples; i += 1) {
    pts.push(parkRoutePoint(route, i / samples));
    if (i > 0) {
      lengths.push(lengths[i - 1] + Math.hypot(pts[i].x - pts[i - 1].x, pts[i].y - pts[i - 1].y));
    }
  }
  const total = lengths[samples];
  const positions = [];
  let j = 1;
  for (let s = spacing / 2; s <= total - spacing / 3; s += spacing) {
    while (j < samples && lengths[j] < s) j += 1;
    const a = pts[j - 1];
    const b = pts[j];
    const f = (s - lengths[j - 1]) / Math.max(lengths[j] - lengths[j - 1], 1e-9);
    const len = Math.hypot(b.x - a.x, b.y - a.y) || 1;
    positions.push({ x: a.x + (b.x - a.x) * f, y: a.y + (b.y - a.y) * f, dx: (b.x - a.x) / len, dy: (b.y - a.y) / len });
  }
  return positions;
}

function parkRouteSvgPath(route) {
  const [x0, y0] = route.start;
  const [x1, y1] = route.end;
  if (!route.ctrl) return `M ${x0} ${y0} L ${x1} ${y1}`;
  return `M ${x0} ${y0} Q ${route.ctrl[0]} ${route.ctrl[1]} ${x1} ${y1}`;
}

function parkChevronsSvg(route, strokeWidth) {
  const arm = 4 + strokeWidth * 0.9;
  const depth = arm * 0.85;
  return parkChevronPositions(route, PARK_CHEVRON_SPACING)
    .map((p, i) => {
      const nx = -p.dy;
      const ny = p.dx;
      const bx = p.x - (p.dx * depth) / 2;
      const by = p.y - (p.dy * depth) / 2;
      const tipX = p.x + (p.dx * depth) / 2;
      const tipY = p.y + (p.dy * depth) / 2;
      const points = [
        [bx + nx * arm, by + ny * arm],
        [tipX, tipY],
        [bx - nx * arm, by - ny * arm],
      ]
        .map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`)
        .join(" ");
      // Negative Verzögerung: Welle läuft sofort, Spitze wandert mit i in Flussrichtung
      const delay = ((i * PARK_WAVE_STEP_S) % PARK_WAVE_PERIOD_S) - PARK_WAVE_PERIOD_S;
      return `<polyline class="park-chevron" points="${points}" style="animation-delay:${delay.toFixed(2)}s"/>`;
    })
    .join("");
}

function parkStrokeWidth(kwh, maxKwh) {
  if (maxKwh <= 0) return 1.5;
  return 1.5 + 4.5 * Math.sqrt(kwh / maxKwh);
}

function parkRouteValues(parkFlows) {
  const byPair = {};
  for (const f of parkFlows.flows) byPair[`${f.from}-${f.to}`] = f.kwh;
  const values = {};
  for (const route of PARK_ROUTES) {
    if (route.kind === "export") values[route.id] = parkFlows.totals.gridExport;
    else if (route.kind === "import") values[route.id] = parkFlows.totals.gridImport;
    else values[route.id] = byPair[`${route.from}-${route.to}`] || 0;
  }
  return values;
}

function parkRouteLabel(route, kwh) {
  if (route.kind === "export") return `Park → Stromnetz (Einspeisung): ${parkFormatEnergy(kwh)}`;
  if (route.kind === "import") return `Stromnetz → Park (Netzbezug): ${parkFormatEnergy(kwh)}`;
  return `${PARK_NODE_NAMES[route.from]} → ${PARK_NODE_NAMES[route.to]}: ${parkFormatEnergy(kwh)} (bilanziell)`;
}

function parkIsActive(id, summary, parkFlows) {
  if (id === "grid") return true;
  if (id === "solar" || id === "landscape") return parkFlows.producers[id].generation > 0;
  if (id === "hub") {
    const variant = summary?.green_energy_hub?.variant;
    return variant !== "Keine" && parkFlows.consumers.hub.demand > 0;
  }
  return parkFlows.consumers[id].demand > 0;
}

function parkNodeTooltip(id, summary, parkFlows) {
  const name = PARK_NODE_NAMES[id];
  if (id === "grid") {
    const t = parkFlows.totals;
    return [
      name,
      `Bezug: ${parkFormatEnergy(t.gridImport)}`,
      `Einspeisung: ${parkFormatEnergy(t.gridExport)}`,
      `max. Bezug: ${parkFormatPower(t.maxImportKw)}`,
      `max. Einspeisung: ${parkFormatPower(t.maxExportKw)}`,
    ].join("\n");
  }
  if (!parkIsActive(id, summary, parkFlows)) return `${name}: nicht aktiv`;

  if (id === "solar" || id === "landscape") {
    const p = parkFlows.producers[id];
    return [
      name,
      `Erzeugung: ${parkFormatEnergy(p.generation)}`,
      `im Park genutzt (bilanziell): ${parkFormatEnergy(p.generation - p.export)}`,
      `Einspeisung (bilanziell): ${parkFormatEnergy(p.export)}`,
    ].join("\n");
  }

  const c = parkFlows.consumers[id];
  const lines = [
    name,
    `Bedarf: ${parkFormatEnergy(c.demand)}`,
    `Eigenstrom: ${parkFormatEnergy(c.covered)} (${parkFormatPercent(c.selfShare)})`,
    `Netzbezug: ${parkFormatEnergy(c.gridImport)}`,
  ];
  if (id === "hub") {
    const h = summary?.green_energy_hub || {};
    const pv = parkFlows.producers.hub_pv;
    lines.push(
      `Variante: ${h.variant || "-"}`,
      `Laden MCS / CCS / HPC / AC: ${[h.charging_mcs_kwh, h.charging_ccs_kwh, h.charging_hpc_kwh, h.charging_ac_kwh]
        .map((v) => parkFormatEnergy(v, false))
        .join(" / ")}`,
      `PV am Hub: ${parkFormatEnergy(pv.generation)} (im Eigenstrom enthalten)`,
      `Batterie: ${PARK_NF0.format(parkAbs(h.battery_full_cycles))} Vollzyklen`,
      `H₂ produziert / geliefert: ${parkFormatEnergy(h.h2_production_kwh, false)} / ${parkFormatEnergy(h.h2_delivered_kwh, false)}`,
      `Elektrolyseur: ${PARK_NF0.format(parkAbs(h.electrolyzer_full_load_hours))} Volllaststunden`
    );
  }
  return lines.join("\n");
}

function parkText(x, y, text, cls) {
  return `<text class="${cls}" x="${x}" y="${y}" text-anchor="middle">${parkEscape(text)}</text>`;
}

function parkNodeSvg(id, summary, parkFlows) {
  const node = PARK_NODES[id];
  const { cx, cy, r } = node;
  const tx = node.tx ?? cx;
  const active = parkIsActive(id, summary, parkFlows);
  const tip = parkNodeTooltip(id, summary, parkFlows);
  const hexClass = id === "grid" ? "park-hex park-hex-grid" : active ? "park-hex" : "park-hex park-hex-inactive";

  const parts = [`<polygon class="${hexClass}" points="${parkHexPoints(cx, cy, r)}"/>`];
  const titleTop = id === "landscape" ? cy - 70 : id === "hub" ? cy - 46 : cy - 38;
  node.title.forEach((line, i) => parts.push(parkText(tx, titleTop + i * 17, line, "park-title")));
  parts.push(parkText(tx, cy + 8, node.short, "park-short"));

  const detail = [];
  if (!active) {
    detail.push(parkText(tx, cy + 10, "nicht aktiv", "park-label"));
  } else if (node.role === "producer") {
    const p = parkFlows.producers[id];
    const base = id === "landscape" ? cy - 20 : cy + 2;
    detail.push(parkText(tx, base, "Erzeugung", "park-label"));
    detail.push(parkText(tx, base + 21, parkFormatEnergy(p.generation), "park-value"));
    detail.push(parkText(tx, base + 39, `davon Einspeisung ${parkFormatEnergy(p.export, false)}`, "park-label"));
  } else if (node.role === "consumer") {
    const c = parkFlows.consumers[id];
    const base = id === "hub" ? cy - 8 : cy;
    detail.push(parkText(tx, base, "Bedarf", "park-label"));
    detail.push(parkText(tx, base + 19, parkFormatEnergy(c.demand), "park-value"));
    detail.push(parkText(tx, base + 35, `Eigenstrom ${parkFormatPercent(c.selfShare)}`, "park-label"));
    const barW = 96;
    const barX = tx - barW / 2;
    const barY = base + 42;
    const coveredW = barW * Math.min(Math.max(c.selfShare, 0), 1);
    detail.push(`<rect class="park-bar-grid" x="${barX}" y="${barY}" width="${barW}" height="6" rx="3"/>`);
    if (coveredW > 0) {
      detail.push(`<rect class="park-bar-self" x="${barX}" y="${barY}" width="${coveredW.toFixed(1)}" height="6" rx="3"/>`);
    }
    if (id === "hub") {
      const h = summary?.green_energy_hub || {};
      const badges = [
        parkAbs(h.pv_kwh) > 0 ? "PV" : null,
        parkAbs(h.battery_charge_kwh) > 0 ? "Batterie" : null,
        parkAbs(h.electrolyzer_kwh) > 0 ? "H₂" : null,
      ].filter(Boolean);
      const widths = badges.map((b) => 14 + b.length * 6);
      let bx = tx - (widths.reduce((a, w) => a + w, 0) + 4 * (badges.length - 1)) / 2;
      badges.forEach((b, i) => {
        detail.push(`<rect class="park-badge" x="${bx.toFixed(1)}" y="${barY + 12}" width="${widths[i]}" height="16" rx="8"/>`);
        detail.push(parkText((bx + widths[i] / 2).toFixed(1), barY + 24, b, "park-badge-text"));
        bx += widths[i] + 4;
      });
    }
  } else {
    const t = parkFlows.totals;
    detail.push(parkText(tx, cy - 12, `Bezug ${parkFormatEnergy(t.gridImport, false)}`, "park-label park-label-strong"));
    detail.push(parkText(tx, cy + 6, `Einspeisung ${parkFormatEnergy(t.gridExport, false)}`, "park-label park-label-strong"));
    detail.push(parkText(tx, cy + 24, `max. Bezug ${parkFormatPower(t.maxImportKw)}`, "park-label"));
  }
  parts.push(`<g class="park-detail">${detail.join("")}</g>`);

  return (
    `<g class="park-node" data-node="${id}" tabindex="0" data-tip="${parkEscape(tip)}" aria-label="${parkEscape(tip)}">` +
    parts.join("") +
    `</g>`
  );
}

function parkFlowTableHtml(parkFlows, routeValues) {
  const rows = PARK_ROUTES.filter((route) => routeValues[route.id] > 0).map((route) => {
    const label = parkRouteLabel(route, routeValues[route.id]).split(": ");
    return `<tr><th scope="row">${parkEscape(label[0])}</th><td>${parkEscape(label.slice(1).join(": "))}</td></tr>`;
  });
  for (const id of ["industry", "js", "hub"]) {
    const c = parkFlows.consumers[id];
    if (c.demand > 0) {
      rows.push(
        `<tr><th scope="row">${parkEscape(PARK_NODE_NAMES[id])}</th><td>Bedarf ${parkFormatEnergy(c.demand)}, Eigenstrom ${parkFormatPercent(c.selfShare)}</td></tr>`
      );
    }
  }
  return `<table class="park-table"><caption>Energieflüsse im Park (bilanziell, Jahreswerte)</caption><tbody>${rows.join("")}</tbody></table>`;
}

function parkSetupInteraction(stage) {
  if (stage.dataset.parkInteractive === "1") return;
  stage.dataset.parkInteractive = "1";

  const tip = document.createElement("div");
  tip.className = "park-tip";
  tip.hidden = true;
  stage.appendChild(tip);

  const show = (target) => {
    tip.textContent = target.getAttribute("data-tip");
    tip.hidden = false;
    const box = target.getBoundingClientRect();
    const host = stage.getBoundingClientRect();
    const left = Math.min(Math.max(box.left + box.width / 2 - host.left, 110), host.width - 110);
    tip.style.left = `${left}px`;
    tip.style.top = `${Math.max(box.top - host.top, 0)}px`;
  };
  const hide = () => {
    tip.hidden = true;
  };
  const findTarget = (event) => event.target.closest?.("[data-tip]");

  stage.addEventListener("pointerover", (event) => {
    const target = findTarget(event);
    if (target && event.pointerType === "mouse") show(target);
  });
  stage.addEventListener("pointerout", (event) => {
    if (event.pointerType === "mouse" && findTarget(event)) hide();
  });
  stage.addEventListener("focusin", (event) => {
    const target = findTarget(event);
    if (target) show(target);
  });
  stage.addEventListener("focusout", hide);
  // Touch: Tippen zeigt den Tooltip, Tippen daneben schließt ihn
  stage.addEventListener("click", (event) => {
    const target = findTarget(event);
    if (target) show(target);
    else hide();
  });

  // Animation nur laufen lassen, wenn die Karte sichtbar ist
  if (typeof IntersectionObserver !== "undefined") {
    const observer = new IntersectionObserver((entries) => {
      for (const entry of entries) stage.classList.toggle("park-paused", !entry.isIntersecting);
    });
    observer.observe(stage);
  }
}

/**
 * Zeichnet die Parkkarte für ein Szenario (flow_data.json) in das Element stage.
 * options.background ersetzt den Kartenhintergrund (SVG-Markup im viewBox 0 0 800 900).
 */
function renderParkMap(stage, payload, options = {}) {
  if (!stage) return;
  const summary = payload?.annual_summary || {};
  const parkFlows = computeParkFlows(summary);
  const routeValues = parkRouteValues(parkFlows);
  const maxKwh = Math.max(...Object.values(routeValues), 0);

  const routeSvg = PARK_ROUTES.filter((route) => routeValues[route.id] > 0)
    .map((route) => {
      const kwh = routeValues[route.id];
      const width = parkStrokeWidth(kwh, maxKwh);
      const faint = kwh < 0.01 * maxKwh ? " park-route-faint" : "";
      const label = parkRouteLabel(route, kwh);
      return (
        `<g class="park-route park-route-${route.kind}${faint}" tabindex="0" data-tip="${parkEscape(label)}" aria-label="${parkEscape(label)}" style="stroke-width:${width.toFixed(2)}">` +
        `<path class="park-route-hit" d="${parkRouteSvgPath(route)}"/>` +
        parkChevronsSvg(route, width) +
        `</g>`
      );
    })
    .join("");

  const nodeSvg = Object.keys(PARK_NODES)
    .map((id) => parkNodeSvg(id, summary, parkFlows))
    .join("");

  const background = options.background ?? parkMapBackground();
  const t = parkFlows.totals;
  const desc =
    `Erzeugung ${parkFormatEnergy(t.generation)}, Bedarf ${parkFormatEnergy(t.demand)}, ` +
    `Eigenstromanteil ${parkFormatPercent(t.autarky)}, Netzbezug ${parkFormatEnergy(t.gridImport)}, Einspeisung ${parkFormatEnergy(t.gridExport)}.`;

  const svg =
    `<svg class="park-svg" viewBox="0 0 ${PARK_MAP_VIEWBOX.width} ${PARK_MAP_VIEWBOX.height}" xmlns="http://www.w3.org/2000/svg" role="group" aria-labelledby="park-map-title park-map-desc">` +
    `<title id="park-map-title">Energieflüsse im Innovationspark Jüchen</title>` +
    `<desc id="park-map-desc">${parkEscape(desc)}</desc>` +
    `<g class="park-background" aria-hidden="true">${background}</g>` +
    `<g class="park-nodes">${nodeSvg}</g>` +
    `<g class="park-routes">${routeSvg}</g>` +
    `</svg>`;

  const tip = stage.querySelector(".park-tip");
  stage.innerHTML = svg + parkFlowTableHtml(parkFlows, routeValues);
  if (tip) {
    tip.hidden = true;
    stage.appendChild(tip);
  }
  stage.classList.add("park-map");
  parkSetupInteraction(stage);
  return parkFlows;
}

function renderParkKpis(container, payload) {
  if (!container) return;
  const t = computeParkFlows(payload?.annual_summary || {}).totals;
  const cards = [
    { label: "Erzeugung", value: parkFormatEnergy(t.generation) },
    { label: "Bedarf", value: parkFormatEnergy(t.demand) },
    { label: "Eigenstromanteil am Bedarf (Autarkie)", value: parkFormatPercent(t.autarky) },
    { label: "Genutzter Anteil der Erzeugung (Eigenverbrauch)", value: parkFormatPercent(t.selfConsumption) },
    { label: "Netzbezug", value: parkFormatEnergy(t.gridImport) },
    { label: "Einspeisung", value: parkFormatEnergy(t.gridExport) },
  ];
  container.innerHTML = cards
    .map(
      (c) =>
        `<div class="park-kpi"><div class="park-kpi-value">${parkEscape(c.value)}</div><div class="park-kpi-label">${parkEscape(c.label)}</div></div>`
    )
    .join("");
}

function parkMapLegendHtml() {
  const chevron = (cls) =>
    `<svg class="park-legend-icon ${cls}" viewBox="0 0 40 16" aria-hidden="true">` +
    [6, 18, 30].map((x) => `<polyline points="${x},3 ${x + 6},8 ${x},13"/>`).join("") +
    `</svg>`;
  return (
    `<ul class="park-legend">` +
    `<li>${chevron("park-legend-self")}Eigenstrom aus dem Park</li>` +
    `<li>${chevron("park-legend-import")}Bezug aus dem Stromnetz</li>` +
    `<li><span class="park-legend-width" aria-hidden="true"><i></i><i></i><i></i></span>Strichstärke = Jahresenergie</li>` +
    `</ul>` +
    `<p class="park-footnote">Die Pfeile zeigen eine bilanzielle Zuordnung: Jeder Verbraucher erhält den im Park erzeugten Strom anteilig zu seinem Bedarf. Grundlage ist eine Simulation in 15-Minuten-Auflösung für ein Wetterjahr.</p>`
  );
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { computeParkFlows, parkMapBackground, PARK_ROUTES, PARK_NODES };
}
