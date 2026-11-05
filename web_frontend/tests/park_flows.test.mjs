// Prüft die bilanzielle Zuordnung computeParkFlows() an echten Szenarien.
// Node:    node web_frontend/tests/park_flows.test.mjs
// Browser: web_frontend/tests/run_in_browser.html (ohne Node, über python -m http.server)
const SCENARIOS = ["s_auto_0001", "s_auto_1253", "s_auto_1296"];
const isBrowser = typeof window !== "undefined";

// Im Browser gibt es node:assert nicht – minimaler Ersatz mit gleicher Schnittstelle
const assert = isBrowser
  ? {
      ok(value, msg) {
        if (!value) throw new Error(msg);
      },
      equal(actual, expected, msg) {
        if (actual !== expected) throw new Error(`${msg}: ${actual} !== ${expected}`);
      },
    }
  : (await import("node:assert/strict")).default;

let computeParkFlows = globalThis.computeParkFlows;
if (!computeParkFlows) {
  const { createRequire } = await import("node:module");
  computeParkFlows = createRequire(import.meta.url)("../park_map.js").computeParkFlows;
}

async function loadSummary(id) {
  const rel = `../precomputed/${id}/flow_data.json`;
  if (isBrowser) return (await (await fetch(rel)).json()).annual_summary;
  const { readFile } = await import("node:fs/promises");
  return JSON.parse(await readFile(new URL(rel, import.meta.url), "utf-8")).annual_summary;
}

function log(line) {
  console.log(line);
  if (isBrowser) document.getElementById("out").textContent += `${line}\n`;
}

function close(actual, expected, tol, msg) {
  const ok = Math.abs(actual - expected) <= tol * Math.max(Math.abs(expected), 1);
  assert.ok(ok, `${msg}: ${actual} != ${expected}`);
}

let failed = 0;
for (const id of SCENARIOS) {
  try {
    const summary = await loadSummary(id);
    const r = computeParkFlows(summary);
    const t = r.totals;
    const sumFlows = r.flows.reduce((a, f) => a + f.kwh, 0);
    const sumGridImport = Object.values(r.consumers).reduce((a, c) => a + c.gridImport, 0);
    const sumExport = Object.values(r.producers).reduce((a, p) => a + p.export, 0);

    close(sumFlows + sumGridImport, t.demand, 0.001, "Σ Flüsse + Σ Netzbezug = Bedarf");
    // Σ Flüsse = min(S, D); entspricht G − (G − E − S) aus dem Prompt, solange S ≤ D
    close(sumFlows + sumExport, Math.min(t.selfUse, t.demand) + t.gridExport, 0.001, "Σ Flüsse + Σ Einspeisung");
    close(sumExport, t.gridExport, 0.001, "Σ Einspeisung = grid.export");

    const values = [
      ...r.flows.map((f) => f.kwh),
      ...Object.values(r.consumers).flatMap((c) => [c.covered, c.gridImport]),
      ...Object.values(r.producers).map((p) => p.export),
    ];
    assert.ok(values.every((v) => v >= 0), "keine negativen Werte");

    if (summary.green_energy_hub?.variant === "Keine") {
      const hub = r.consumers.hub;
      assert.equal(hub.demand + hub.covered + hub.gridImport, 0, "GEH „Keine“: Verbraucher hub = 0");
      assert.ok(r.flows.filter((f) => f.to === "hub" || f.from === "hub_pv").every((f) => f.kwh === 0), "GEH „Keine“: keine Flüsse");
    }

    log(
      `ok   ${id}  G=${(t.generation / 1e6).toFixed(2)} GWh  D=${(t.demand / 1e6).toFixed(2)} GWh  ` +
        `Autarkie=${(t.autarky * 100).toFixed(1)} %  Import Σc=${(sumGridImport / 1e6).toFixed(2)} vs grid=${(t.gridImport / 1e6).toFixed(2)} GWh`
    );
  } catch (err) {
    failed += 1;
    log(`FAIL ${id}: ${err.message}`);
  }
}

log(failed ? `${failed} Szenario(s) fehlgeschlagen` : "alle Tests bestanden");
if (!isBrowser && failed) process.exit(1);
