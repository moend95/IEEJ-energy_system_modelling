# Einlesen und Analyse der Metadaten von Zenodo-Datensätzen
# Summe der Spalten(Unternehmen), durchschnittliche Größe

import pandas as pd
import os
from pathlib import Path
import matplotlib.pyplot as plt

# Pfad zum Datenverzeichnis
data_dir = Path(__file__).parent

# CSV-Dateien einlesen
csv_files = list(data_dir.glob("*.csv"))

if not csv_files:
    print("Keine CSV-Dateien im Verzeichnis gefunden.")
else:
    print(f"Gefundene CSV-Dateien: {len(csv_files)}\n")

    # Alle CSV-Dateien verarbeiten
    for csv_file in csv_files:
        print(f"{'='*60}")
        print(f"Datei: {csv_file.name}")
        print(f"{'='*60}")

        try:
            df = pd.read_csv(csv_file, skiprows=1, sep=';')

            # Numerische Spalten identifizieren (für Energiewerte)
            numeric_cols = df.select_dtypes(include=['number']).columns

            # Energiesummen pro Spalte (Unternehmen) berechnen
            # 15-Minuten-Intervalle: durch 4 teilen für Stundenwerte
            energy_sums = df[numeric_cols].sum() / 4

            print("\nEnergiesummen pro Unternehmen (kWh):")
            for company, energy in energy_sums.items():
                print(f"  {company}: {energy:.2f} kWh")
            print(f"\nGesamt-Energiesumme: {energy_sums.sum():.2f} kWh\n")

            # Balkendiagramm erstellen
            plt.figure(figsize=(12, 6))
            energy_sums.plot(kind='bar', color='steelblue')
            plt.title(f"Energiesummen - {csv_file.stem}", fontsize=14, fontweight='bold')
            plt.xlabel("Unternehmen", fontsize=12)
            plt.ylabel("Energie (kWh)", fontsize=12)
            plt.xticks(rotation=45, ha='right')
            plt.grid(axis='y', alpha=0.3)
            plt.tight_layout()

            # Plot speichern
            plot_file = csv_file.with_suffix('.png')
            plt.savefig(plot_file, dpi=150)
            print(f"Plot gespeichert: {plot_file.name}\n")
            plt.close()

        except Exception as e:
            print(f"Fehler beim Verarbeiten der Datei: {e}\n")
