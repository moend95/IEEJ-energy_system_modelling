"""
A46 PV-Lärmschutzwand - Saubere Jahresverteilung

Erstellt ein Monatsdiagramm der Energieerzeugung auf Basis der
Monatsanteile der Wetterdaten 2021 und normiert auf die festgelegte
Jahresenergie.

Annahmen:
- Segmentlänge: 350m
- Module: 370
- Gesamtleistung: 155.4 kWp
- Spez. Energieertrag: 820 kWh/kWp
- Jahresenergie: 127,428 kWh/Jahr
"""

import os
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

# ============================================
# ANNAHMEN
# ============================================

segment_length_m = 350
num_modules = 370
total_power_kwp = 155.4
specific_yield_kwh_per_kwp = 820.0
annual_energy_kwh = total_power_kwp * specific_yield_kwh_per_kwp

base_dir = Path(__file__).resolve().parent
weather_csv = base_dir / "data" / "inputs" / "wetter_daten_2021_15min.csv"
output_dir = base_dir / "data" / "outputs" / "a46_segment"
output_dir.mkdir(parents=True, exist_ok=True)

# ============================================
# WETTERDATEN AUSWERTEN
# ============================================

weather_df = pd.read_csv(weather_csv, index_col=0, parse_dates=True)
weather_df.index = pd.to_datetime(weather_df.index, utc=True).tz_convert(None)
weather_df["month"] = weather_df.index.month

monthly_ghi = weather_df.groupby("month")["ghi"].sum()
monthly_fraction = monthly_ghi / monthly_ghi.sum()
monthly_energy_kwh = monthly_fraction * annual_energy_kwh

months_de = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]
monthly_energy_kwh = monthly_energy_kwh.reindex(range(1, 13))
monthly_energy_kwh.index = months_de

# ============================================
# AUSGABE
# ============================================

print("\n" + "=" * 85)
print("A46 PV-LÄRMSCHUTZWAND - SAUBERE JAHRESVERTEILUNG")
print("=" * 85)
print(f"Segmentlänge:        {segment_length_m} m")
print(f"Module:              {num_modules}")
print(f"Gesamtleistung:      {total_power_kwp:.1f} kWp")
print(f"Spez. Ertrag:        {specific_yield_kwh_per_kwp:.0f} kWh/kWp")
print(f"Jahresenergie:       {annual_energy_kwh:,.0f} kWh/Jahr")
print("\nMonatliche Verteilung basiert auf den GHI-Monatsanteilen der Wetterdaten 2021.")
print(f"Maximaler Monat:     {monthly_energy_kwh.idxmax()} ({monthly_energy_kwh.max():,.0f} kWh)")
print(f"Minimaler Monat:     {monthly_energy_kwh.idxmin()} ({monthly_energy_kwh.min():,.0f} kWh)")

# ============================================
# DIAGRAMM: MONATLICHE VERTEILUNG
# ============================================

fig, ax = plt.subplots(figsize=(14, 8))
colors = plt.cm.YlOrRd(np.linspace(0.35, 0.9, 12))

bars = ax.bar(
    monthly_energy_kwh.index,
    monthly_energy_kwh.values,
    color=colors,
    edgecolor="black",
    linewidth=1.2,
    width=0.72,
)

for bar, value in zip(bars, monthly_energy_kwh.values):
    ax.text(
        bar.get_x() + bar.get_width() / 2,
        value + annual_energy_kwh * 0.008,
        f"{value:,.0f}",
        ha="center",
        va="bottom",
        fontsize=10,
        fontweight="bold",
    )

ax.set_title(
    "A46 PV-Lärmschutzwand: Monatsverteilung der Jahreserzeugung\n"
    f"{total_power_kwp:.1f} kWp | {specific_yield_kwh_per_kwp:.0f} kWh/kWp | {annual_energy_kwh:,.0f} kWh/Jahr",
    fontsize=14,
    fontweight="bold",
    pad=18,
)
ax.set_xlabel("Monat", fontsize=12, fontweight="bold")
ax.set_ylabel("Energieerzeugung [kWh]", fontsize=12, fontweight="bold")
ax.grid(axis="y", linestyle="--", alpha=0.35)
ax.set_axisbelow(True)
ax.set_ylim(0, monthly_energy_kwh.max() * 1.18)

plt.tight_layout()

output_file = output_dir / "a46_jahresverlauf_monatlich_sauber.png"
plt.savefig(output_file, dpi=180, bbox_inches="tight")
plt.close()

print(f"\nGespeichert: {output_file}")
print("Fertig.")
