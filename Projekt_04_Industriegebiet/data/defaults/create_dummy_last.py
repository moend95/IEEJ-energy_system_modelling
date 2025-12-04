# make_dummy_data.py
import pandas as pd
import numpy as np
from pathlib import Path

# -------------------- Standardunternehmen -------------------- #
STANDARD_COMPANIES = [
    {"name": "Entsorgungswirtschaft", "dachflaeche_m2": 92.0},
    {"name": "Stahl", "dachflaeche_m2": 69.01},
    {"name": "Logistik", "dachflaeche_m2": 86.34},
    {"name": "Lebensmittel (Verwaltung/Zentrale)", "dachflaeche_m2": 88.7},
    {"name": "Immobilien (Büro/Hotel/Gewerbe)", "dachflaeche_m2": 82.83},
]

#Fläche mit 90% PV (auf Gebäudedächer und über Parkplatz)

# -------------------- Dummy-Lastgang-Generator -------------------- #
def make_dummy_lastgang(days=7, base_kw=300, fluct=100):
    """Erzeugt künstlichen 15-Minuten-Lastgang für mehrere Tage."""
    idx = pd.date_range("2025-01-01", periods=96 * days, freq="15min")

    # Sinusförmiger Tagesverlauf mit leichtem Rauschen
    hours = np.linspace(0, 24 * days, len(idx))
    load = base_kw + fluct * np.sin(2 * np.pi * (hours % 24) / 24)
    load += np.random.normal(0, 10, size=len(load))  # Rauschen

    df = pd.DataFrame({"time": idx, "elec_kw": np.maximum(load, 50)})
    return df

# -------------------- CSV-Dateien generieren -------------------- #
out_dir = Path("data/lastgaenge")
out_dir.mkdir(parents=True, exist_ok=True)

for company in STANDARD_COMPANIES:
    filename = company["name"].replace("/", "-").replace(" ", "_").lower() + "_lastgang.csv"
    path = out_dir / filename

    # leicht unterschiedliche Baseline & Fluktuation pro Branche
    base = 250 + np.random.randint(0, 150)
    fluct = 60 + np.random.randint(0, 40)

    df = make_dummy_lastgang(days=30, base_kw=base, fluct=fluct)
    df.to_csv(path, index=False)
    print(f"Erstellt: {path}")

print("\n✅ Dummy-Lastgänge für Standardunternehmen erzeugt.")
