"""
A46 Autobahnabschnitt - PV-Lärmschutzwand Jahressimulation
Segment: 51.096375, 6.497125 → 51.096800, 6.502436 (~350m)

OUTPUT:
- Installierbare Leistung (kWp)
- Jahresenergierzeugung (kWh)
- Spezifische Energieerzeugung (kWh/kWp)
- Anzahl PV-Module
- Jahresverlauf-Diagramm
- Tagesgang-Diagramm
- OSM-Kartenplot mit Segment
"""

import os
import sys
import pandas as pd
import json
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import folium
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.module_pv_modulator import PV_System, PV_TYPEN
import pvlib

# ============================================
# KONFIGURATION
# ============================================

# GeoJSON für A46-Segment (350m)
geojson_data = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [6.497125, 51.096375],
                    [6.502436, 51.096800]
                ]
            },
            "properties": {"name": "A46_segment_350m"}
        }
    ]
}

# Speichere GeoJSON
geojson_file = "a46_segment.geojson"
geojson_path = os.path.join(
    os.path.dirname(__file__),
    "data", "inputs", "geometry",
    geojson_file
)
os.makedirs(os.path.dirname(geojson_path), exist_ok=True)

with open(geojson_path, 'w') as f:
    json.dump(geojson_data, f)

# Wetterdaten
weather_csv = os.path.join(
    os.path.dirname(__file__),
    "data", "inputs", "wetter_daten_2021_15min.csv"
)

# Ausgabeverzeichnis
output_dir = os.path.join(
    os.path.dirname(__file__),
    "data", "outputs", "a46_segment"
)
os.makedirs(output_dir, exist_ok=True)

# Simulationsparameter
step_size = 50  # 50m Schrittweite
pv_type_index = 1  # Schallschutzwand (Index 1)
face_offset_deg = 90  # Wand-Normale = Straßenrichtung + 90°

# ============================================
# SIMULATION STARTEN
# ============================================

print("\n" + "=" * 85)
print("A46-SEGMENT: PV-LÄRMSCHUTZWAND - UMFASSENDE JAHRESSIMULATION")
print("=" * 85)
print(f"\nSegment-Information:")
print(f"  Start:      51.096375, 6.497125")
print(f"  Ende:       51.096800, 6.502436")
print(f"  Distanz:    ~350m")

# Wetterdaten laden
print(f"\n✓ Wetterdaten laden...")
weather_df = pd.read_csv(weather_csv, index_col=0, parse_dates=True)
weather_df.index = pd.to_datetime(weather_df.index, utc=True).tz_convert(None)
print(f"  Zeitraum: {weather_df.index[0].date()} bis {weather_df.index[-1].date()}")

# PV-Typ
pv_type = PV_TYPEN[pv_type_index]
print(f"\n✓ PV-Typ: {pv_type.name}")
print(f"  Modul: {pv_type.module}")
print(f"  Neigung: {pv_type.tilt}° (vertikal)")
print(f"  Ausrichtung: variabel (folgt Straße)")

# Modul-Leistung auslesen
sandia_modules = pvlib.pvsystem.retrieve_sam('SandiaMod')
module_params = sandia_modules[pv_type.module]
module_power_w = module_params['Vmpo'] * module_params['Impo']  # Nennleistung in W (Vmpo * Impo)
print(f"  Modul-Leistung: {module_power_w}W")
print(f"  Module/String: {pv_type.modules_per_string}, Strings/Inverter: {pv_type.strings_per_inverter}")

# PV-System initialisieren
pv_system = PV_System(
    geojson_path=geojson_path,
    pvtypes=[pv_type],
    step_size=step_size,
    weather_df=weather_df,
    base_output_dir=output_dir,
)

# Punkte generieren
print(f"\n✓ PV-Punkte generieren...")
results = pv_system.generate_pv_points()
num_points = len(results[pv_type.id])
print(f"  {num_points} Punkte erzeugt (Abstand: {step_size}m)")

# CSV-Pfad
geo_name = "a46_segment"
csv_name = f"{geo_name}_punkte_{pv_type.id}_{pv_type.name}.csv".replace(" ", "_")
csv_path = os.path.join(output_dir, csv_name)

# Azimut von Straßenrichtung auf Wand-Normale drehen
df_points_for_az = pd.read_csv(csv_path)
df_points_for_az["azimut"] = (df_points_for_az["azimut"] + face_offset_deg) % 360
df_points_for_az.to_csv(csv_path, index=False)
print(f"  Azimut-Korrektur: +{face_offset_deg}° (Wand-Normale statt Straßenrichtung)")

# Simulation durchführen
print(f"\n✓ Energiesimulation für {num_points} Punkte...")
energy_kwh, ac_timeseries = pv_system.simulate_pv_type_energy(pv_type, csv_path)

# ============================================
# BERECHNUNGEN
# ============================================

# Installierte Leistung pro Punkt
modules_per_point = pv_type.modules_per_string * pv_type.strings_per_inverter
power_per_point_kw = (modules_per_point * module_power_w) / 1000

# Geometrische Hochrechnung von 1 Modulreihe auf Schrittweite
segment_scaling_factor = step_size / pv_type.row_width
power_per_step_kw = power_per_point_kw * segment_scaling_factor

# Gesamtleistung der simulierten Anlage (alle Schritte entlang des Segments)
total_installed_power_kw = power_per_step_kw * num_points

# Gesamtmodule
total_modules = num_points * modules_per_point * segment_scaling_factor

# Jahresenergiezeugung
total_energy_kwh = energy_kwh * segment_scaling_factor

# Spezifische Energieerzeugung
specific_energy_kwh_per_kwp = total_energy_kwh / total_installed_power_kw

# Zeitreihe in kW umrechnen und geometrisch hochrechnen
total_ac_kw = ac_timeseries * segment_scaling_factor / 1000

# ============================================
# ERGEBNISSE AUSGEBEN
# ============================================

print("\n" + "=" * 85)
print("INSTALLIERTE LEISTUNG")
print("=" * 85)
print(f"Leistung pro PV-Reihe (4m):     {power_per_point_kw:.3f} kWp")
print(f"Leistung pro Schritt (50m):     {power_per_step_kw:.3f} kWp")
print(f"╔ GESAMT INSTALLIERT:           {total_installed_power_kw:.2f} kWp ╗")

print(f"\n" + "=" * 85)
print("JAHRESENERGIEZEUGUNG")
print("=" * 85)
print(f"Jahresenergie (GESAMT):         {total_energy_kwh:,.0f} kWh/Jahr")
print(f"Durchschn. täglich:             {total_energy_kwh/365:,.0f} kWh/Tag")
print(f"Max. Leistung:                  {total_ac_kw.max():.2f} kW")
print(f"Ø Leistung:                     {total_ac_kw.mean():.3f} kW")

print(f"\n" + "=" * 85)
print("SPEZIFISCHE ENERGIEERZEUGUNG")
print("=" * 85)
print(f"╔ kWh/kWp/Jahr:                 {specific_energy_kwh_per_kwp:.1f} kWh/kWp ╗")

print(f"\n" + "=" * 85)
print("MODULANZAHL")
print("=" * 85)
print(f"Module pro Punkt:               {modules_per_point} Stück")
print(f"╔ GESAMT MODULE:                {int(round(total_modules))} Stück ╗")

# ============================================
# ZEITREIHE SPEICHERN
# ============================================

output_timeseries = os.path.join(output_dir, "timeseries_kw.csv")
df_ts_export = pd.DataFrame(index=ac_timeseries.index)
df_ts_export['power_kw'] = total_ac_kw.values
df_ts_export.to_csv(output_timeseries)

# ============================================
# DIAGRAMME ERSTELLEN
# ============================================

# 1. Jahresverlauf (Monatssummen)
print(f"\n✓ Erstelle Jahresverlauf-Diagramm...")
df_monthly = pd.DataFrame({
    'power_kw': total_ac_kw,
})
df_monthly['month'] = df_monthly.index.month
monthly_energy = df_monthly.groupby('month')['power_kw'].sum() * 0.25  # 15min zu kWh

fig, ax = plt.subplots(figsize=(14, 7))
months = ['Jan', 'Feb', 'Mär', 'Apr', 'Mai', 'Jun', 'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dez']
bars = ax.bar(range(1, 13), monthly_energy.values, color='#1f77b4', alpha=0.8, edgecolor='black', linewidth=1.5)

# Werte auf den Balken
for i, bar in enumerate(bars):
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., height,
            f'{height:,.0f}\nkWh', ha='center', va='bottom', fontsize=10, fontweight='bold')

ax.set_xlabel('Monat', fontsize=12, fontweight='bold')
ax.set_ylabel('Energieerzeugung [kWh]', fontsize=12, fontweight='bold')
ax.set_title(f'A46 PV-Lärmschutzwand: Monatliche Energieerzeugung\n({total_installed_power_kw:.2f} kWp, {specific_energy_kwh_per_kwp:.1f} kWh/kWp/Jahr)', 
             fontsize=13, fontweight='bold')
ax.set_xticks(range(1, 13))
ax.set_xticklabels(months)
ax.grid(axis='y', alpha=0.4, linestyle='--')
plt.tight_layout()
plot_monthly = os.path.join(output_dir, "jahresverlauf_monatlich.png")
plt.savefig(plot_monthly, dpi=150, bbox_inches='tight')
plt.close()
print(f"  Gespeichert: jahresverlauf_monatlich.png")

# 2. Tagesgang (Ø pro Stunde)
print(f"✓ Erstelle Tagesgang-Diagramm...")
df_hourly = pd.DataFrame({'power_kw': total_ac_kw})
df_hourly['hour'] = df_hourly.index.hour
hourly_power = df_hourly.groupby('hour')['power_kw'].mean()

fig, ax = plt.subplots(figsize=(14, 7))
ax.plot(hourly_power.index, hourly_power.values, marker='o', linewidth=2.5, markersize=7, 
        color='#2ca02c', label='Durchschn. Leistung')
ax.fill_between(hourly_power.index, hourly_power.values, alpha=0.3, color='green')

ax.set_xlabel('Stunde des Tages', fontsize=12, fontweight='bold')
ax.set_ylabel('Durchschnittliche Leistung [kW]', fontsize=12, fontweight='bold')
ax.set_title(f'A46 PV-Lärmschutzwand: Mittlerer Tagesgang', fontsize=13, fontweight='bold')
ax.set_xticks(range(0, 24, 2))
ax.grid(alpha=0.4, linestyle='--')
plt.tight_layout()
plot_hourly = os.path.join(output_dir, "tagesgang_stundlich.png")
plt.savefig(plot_hourly, dpi=150, bbox_inches='tight')
plt.close()
print(f"  Gespeichert: tagesgang_stundlich.png")

# ============================================
# KARTENPLOT (OSM)
# ============================================

print(f"\n✓ Erstelle interaktiven Kartenplot...")

# Koordinaten
start_lat, start_lon = 51.096375, 6.497125
end_lat, end_lon = 51.096800, 6.502436
center_lat = (start_lat + end_lat) / 2
center_lon = (start_lon + end_lon) / 2

# Karte erstellen
m = folium.Map(
    location=[center_lat, center_lon],
    zoom_start=15,
    tiles='OpenStreetMap'
)

# Segment anzeichnen (Strecke)
folium.PolyLine(
    locations=[[start_lat, start_lon], [end_lat, end_lon]],
    color='red',
    weight=5,
    opacity=0.9,
    popup='A46 PV-Lärmschutzwand Segment',
    tooltip='Autobahnabschnitt mit PV-Lärmschutzwand'
).add_to(m)

# Lese Punkte aus CSV
df_points = pd.read_csv(csv_path)
for idx, row in df_points.iterrows():
    folium.CircleMarker(
        location=[row['latitude'], row['longitude']],
        radius=6,
        popup=f"Punkt {idx+1}<br>Azimuth: {row['azimut']:.1f}°<br>Leistung (50m): {power_per_step_kw:.2f} kWp",
        color='#1f77b4',
        fill=True,
        fillColor='lightblue',
        fillOpacity=0.8,
        weight=2
    ).add_to(m)

# Start- und Endpunkt
folium.Marker(
    location=[start_lat, start_lon],
    popup='Start (KM 0)',
    icon=folium.Icon(color='green', icon='play', prefix='fa'),
    tooltip='Startpunkt'
).add_to(m)

folium.Marker(
    location=[end_lat, end_lon],
    popup='Ende (KM 0.35)',
    icon=folium.Icon(color='red', icon='stop', prefix='fa'),
    tooltip='Endpunkt'
).add_to(m)

# Info-Box (popup in der Mitte)
info_html = f"""
<div style="font-family: Arial; background-color: #f0f0f0; padding: 12px; border-radius: 5px; border: 2px solid #1f77b4;">
    <h4 style="margin-top: 0; color: #1f77b4;">A46 PV-Lärmschutzwand</h4>
    <b>Segment:</b> 350m<br>
    <b>Installierte Leistung:</b> {total_installed_power_kw:.2f} kWp<br>
    <b>Jahresenergie:</b> {total_energy_kwh:,.0f} kWh<br>
    <b>Spez. Energie:</b> {specific_energy_kwh_per_kwp:.1f} kWh/kWp<br>
    <b>Module:</b> {int(total_modules)} Stück<br>
    <b>PV-Punkte:</b> {num_points}
</div>
"""

folium.Marker(
    location=[center_lat, center_lon],
    popup=folium.Popup(info_html, max_width=320),
    icon=folium.Icon(color='orange', icon='info', prefix='fa'),
    tooltip='Segment-Information'
).add_to(m)

# Legende
legend_html = '''
<div style="position: fixed; 
     bottom: 50px; right: 50px; width: 250px; height: 180px; 
     background-color: white; border:2px solid grey; z-index:9999; 
     font-size: 14px; padding: 10px; border-radius: 5px;">
 <p style="margin: 5px;"><b>A46 PV-Lärmschutzwand</b></p>
 <p style="margin: 5px;">
  <i class="fa fa-stop" style="color:red"></i> Segment (350m)
 </p>
 <p style="margin: 5px;">
  <i class="fa fa-play" style="color:green"></i> Start
 </p>
 <p style="margin: 5px;">
  <i class="fa fa-stop" style="color:red"></i> Ende
 </p>
 <p style="margin: 5px;">
  <span style="background-color: #1f77b4; border-radius: 50%; width: 12px; height: 12px; display: inline-block;"></span> PV-Punkte
 </p>
 <p style="margin: 5px; font-size: 12px; color: grey;">
   © OpenStreetMap
 </p>
</div>
'''
m.get_root().html.add_child(folium.Element(legend_html))

# Karte speichern
map_file = os.path.join(output_dir, "segment_osm_karte.html")
m.save(map_file)
print(f"  Gespeichert: segment_osm_karte.html")

# ============================================
# ZUSAMMENFASSUNG SPEICHERN
# ============================================

print(f"\n✓ Speichere Zusammenfassung...")

summary_text = f"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║              A46-SEGMENT: PV-LÄRMSCHUTZWAND SIMULATIONSERGEBNISSE            ║
╚═══════════════════════════════════════════════════════════════════════════════╝

SEGMENT INFORMATION
───────────────────────────────────────────────────────────────────────────────
Autobahnabschnitt:         A46
Koordinaten Start:         51.096375, 6.497125
Koordinaten Ende:          51.096800, 6.502436
Segmentlänge:              ~350m
Schrittweite:              {step_size}m
Anzahl PV-Punkte:          {num_points}

ANLAGENKONFIGURATION
───────────────────────────────────────────────────────────────────────────────
PV-Typ:                    {pv_type.name}
PV-Modul:                  {pv_type.module}
Modul-Leistung:            {module_power_w}W
Module pro Punkt:          {modules_per_point}
Tilt:                      {pv_type.tilt}° (vertikal)
Ausrichtung:               variabel (azimuth folgt Straße)
Azimut-Offset:             +{face_offset_deg}° (Wand-Normale)
Geometrie-Skalierung:      {segment_scaling_factor:.2f}x ({step_size}m / {pv_type.row_width}m)

╔═══════════════════════════════════════════════════════════════════════════════╗
║                           SCHLÜSSELERGEBNISSE                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝

INSTALLIERTE LEISTUNG (Gesamtanlage)
───────────────────────────────────────────────────────────────────────────────
✓ Installierte Leistung:       {total_installed_power_kw:.2f} kWp

JAHRESENERGIEZEUGUNG
───────────────────────────────────────────────────────────────────────────────
✓ Jahresenergie:               {total_energy_kwh:,.0f} kWh/Jahr
  Durchschnittliche täglich:   {total_energy_kwh/365:,.0f} kWh/Tag
  Max. Leistung:               {total_ac_kw.max():.2f} kW
  Ø Leistung:                  {total_ac_kw.mean():.3f} kW

SPEZIFISCHE ENERGIEERZEUGUNG (Performance Ratio Indikator)
───────────────────────────────────────────────────────────────────────────────
✓ Spez. Energieerzeugung:      {specific_energy_kwh_per_kwp:.1f} kWh/kWp/Jahr

MODULANZAHL
───────────────────────────────────────────────────────────────────────────────
✓ Gesamt Anzahl Module:        {int(round(total_modules))} Module

AUSGABEDATEIEN & VISUALISIERUNGEN
───────────────────────────────────────────────────────────────────────────────
📊 Zeitreihe (15-min):         timeseries_kw.csv
📈 Jahresverlauf (Grafik):     jahresverlauf_monatlich.png
📈 Tagesgang (Grafik):         tagesgang_stundlich.png
🗺️  Kartenplot (OSM):           segment_osm_karte.html
📍 Punkt-Koordinaten (CSV):    a46_segment_punkte_2_Schallschutzwand.csv

ALLGEMEINE INFORMATIONEN
───────────────────────────────────────────────────────────────────────────────
Wetterdaten-Zeitraum:      {weather_df.index[0].date()} bis {weather_df.index[-1].date()}
Wetterdaten-Auflösung:     15 Minuten
Simuliert am:              {datetime.now().strftime("%d.%m.%Y %H:%M:%S")}
Output-Ordner:             data/outputs/a46_segment/

═══════════════════════════════════════════════════════════════════════════════
"""

summary_file = os.path.join(output_dir, "ERGEBNISSE_ZUSAMMENFASSUNG.txt")
with open(summary_file, 'w', encoding='utf-8') as f:
    f.write(summary_text)

print(summary_text)

# ============================================
# FERTIG
# ============================================

print("=" * 85)
print("✓ SIMULATION ERFOLGREICH ABGESCHLOSSEN")
print("=" * 85)
print(f"\nAlle Ausgaben in:\n  {output_dir}\n")
