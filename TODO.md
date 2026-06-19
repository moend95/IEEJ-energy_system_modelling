# IEEJ Projekt – Offene Punkte

## Web-Frontend (Statisches Precomputed-System)

### Erledigt
- [x] Alle Szenarien vorberechnet und in `web_frontend/precomputed/` gespeichert (177 Szenarien ohne Batterie)
- [x] `catalog.json` mit korrekten Pfaden (`./precomputed/…/flow_data.json`) erstellt
- [x] Katalog-Matching (Python `json.dumps` ↔ JS `stableStringify`) funktioniert
- [x] Debug-Sektionen "Katalogvorschau" und "Icon-Pfadtest" aus `index.html` und `app.js` entfernt

### Offen – Web-Frontend

- [x] **GEH-Standardwerte in `generate_all_scenarios.py`** (Plan-Schritt 5):
  Elektrolyseur 1000 kW, Speicher 10 MWh, Dispenser 10 kg/h als feste Werte im
  Permutationsraum. Neue Szenarien enthalten jetzt H2-Prozessketten-Ergebnisse.

- [x] **GEH-Felder in `core/export_utils.py`** exportieren:
  `geh_h2_production_kwh`, `geh_h2_delivered_kwh`, `geh_h2_curtailed_kwh`,
  `geh_compressor_demand_kwh` werden jetzt in `annual_summary.green_energy_hub`
  geschrieben.

- [x] **Synergiefluss-Diagramm in `Web_Gui.py`** aktualisiert:
  `build_synergy_diagram()` in `functions_web_support.py` zeigt jetzt H2-Produktion,
  Lieferung, Überschuss und Kompressor-Strombedarf im Hover-Tooltip des GEH-Knotens.

- [ ] **Design überarbeiten** für Veröffentlichung auf innovationspark-erneuerbare-energien.de:
  - Branding / Farben anpassen
  - ggf. Iframe-Parameter für Szenario-Vorauswahl per URL implementieren
  - CORS und Cache-Control für Hosting konfigurieren

- [ ] **Energielandschaft-Szenarien** noch nicht im Katalog:
  Die Energy-Landscape-Parameter (Ausbaugrad, PV-Typ, Traktorbreite) sind aktuell
  nicht Teil des Permutationsraums in `generate_all_scenarios.py`. Entscheiden ob
  diese als weitere Achse aufgenommen werden sollen.

---

## Green Energy Hub (GEH) – Prozesskette

### Erledigt
- [x] `core/io_types.py`: GEH-Parameter in `GuiInput` und `SimOutput` ergänzt
- [x] `core/module_green_energy_hub.py`: Neues Modul (Elektrolyseur → Kompressor → Speicher → Dispenser)
- [x] `Simulation.py`: Vorläufige Bilanz vor GEH-Lauf; `run_geh_electrolyzer()` integriert
- [x] `Web_Gui.py`: Physikalische Eingabefelder statt statischer Szenario-Auswahl
- [x] Parameterweiterleitung verifiziert: 2x Leistung → exakt 2x H2-Produktion ✓

### Offen – GEH

- [ ] **Synergiefluss-Diagramm in `Web_Gui.py`** prüfen/aktualisieren:
  Zeigt `build_synergy_diagram()` in `functions_web_support.py` bereits die
  neuen H2-Felder (Produktion, Speicher-SOC, Kompressor)? Ggf. ergänzen.

- [ ] **Cleanup `core/auxiliary/`** (optional):
  `MA_Saur_GEH.py` ist nur noch Referenz, wird nicht mehr in `run_simulation()`
  eingebunden. Ggf. in README dokumentieren, damit keine Verwirrung entsteht.

---

## Hosting / Veröffentlichung

- [ ] Statisches Frontend + Precomputed-JSON auf Server hochladen
- [ ] Iframe-Einbettung auf innovationspark-erneuerbare-energien.de testen
- [ ] `schema_version` und `model_version` in `flow_data.json` etablieren (Versionierung)
