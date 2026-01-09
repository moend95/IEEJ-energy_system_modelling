# Projekt 04 Industriegebiet - Gesamtstromverbrauch

import pandas as pd
import matplotlib.pyplot as plt
import os
from datetime import datetime

# Pfad zur CSV-Datei
csv_file = r"c:\Users\johan\TH_Koeln_Masterprojekt\IEEJ-energy_system_modelling\Projekt_04_Industriegebiet\Projekt_04_Industriegebiet\2026-01-09-Masterprojekt_Waermebedarf_Industriegebiet_2-Lastprofile.csv"

# CSV-Datei als DataFrame einlesen
df = pd.read_csv(csv_file)
# Spalten entfernen
df = df.drop(columns=["Wärme gesamt (kW)", "Kälte gesamt (kW)", "Strom gesamt (kW)"])

# Definition der Verbraucher und ihrer zugehörigen Spalten
verbraucher = {
    'Stahlindustrie': [
        'Stahl-Raumwärme (kW)', 'Stahl-Trinkwarmwasser (kW)', 'Stahl-Klimatisierung (kW)',
        'Stahl-Prozesskälte (kW)', 'Stahl-Nutzerstrom (kW)', 'Stahl-Elektromobilität (kW)'
    ],
    'Entsorgungswirtschaft': [
        'Entsorgung-Raumwärme (kW)', 'Entsorgung-Trinkwarmwasser (kW)', 'Entsorgung-Klimatisierung (kW)',
        'Entsorgung-Prozesskälte (kW)', 'Entsorgung-Nutzerstrom (kW)', 'Entsorgung-Elektromobilität (kW)'
    ],
    'Lebensmittel-Einzelhandel': [
        'Lebensmittel-Raumwärme (kW)', 'Lebensmittel-Trinkwarmwasser (kW)', 'Lebensmittel-Klimatisierung (kW)',
        'Lebensmittel-Prozesskälte (kW)', 'Lebensmittel-Nutzerstrom (kW)', 'Lebensmittel-Elektromobilität (kW)'
    ],
    'Immobilien-Entwicklung': [
        'Immobilien-Raumwärme (kW)', 'Immobilien-Trinkwarmwasser (kW)', 'Immobilien-Klimatisierung (kW)',
        'Immobilien-Prozesskälte (kW)', 'Immobilien-Nutzerstrom (kW)', 'Immobilien-Elektromobilität (kW)'
    ],
    'Logistikdienstleistung': [
        'Logistik-Raumwärme (kW)', 'Logistik-Trinkwarmwasser (kW)', 'Logistik-Klimatisierung (kW)',
        'Logistik-Prozesskälte (kW)', 'Logistik-Nutzerstrom (kW)', 'Logistik-Elektromobilität (kW)'
    ]
}

# Neue DataFrame mit Zeit-Spalte erstellen
df_aggregiert = df[['Zeit (TT-MM hh:mm)']].copy()

# Verbräuche pro Verbraucher aggregieren
for verbraucher_name, spalten in verbraucher.items():
    df_aggregiert[verbraucher_name] = df[spalten].sum(axis=1)

# Alte Spalten entfernen und nur aggregierte Spalten behalten
df = df_aggregiert
# User-Abfrage für Unternehmensauswahl
unternehmen_liste = list(verbraucher.keys())
print("\nVerfügbare Unternehmen:")
for i, unternehmen in enumerate(unternehmen_liste, 1):
    print(f"{i}. {unternehmen}")

# Benutzer wählt Unternehmen aus
while True:
    auswahl_input = input("\nWählen Sie Unternehmen (1-5), getrennt durch Kommas (z.B. '1,3,5'). Max. 5 Auswahl: ").strip()
    
    try:
        auswahl_indizes = [int(x.strip()) for x in auswahl_input.split(",")]
        
        # Validierung
        if len(auswahl_indizes) > 5:
            print("Fehler: Maximal 5 Unternehmen auswählen!")
            continue
        
        if not all(1 <= idx <= len(unternehmen_liste) for idx in auswahl_indizes):
            print(f"Fehler: Bitte nur Nummern zwischen 1 und {len(unternehmen_liste)} eingeben!")
            continue
        
        # Ausgewählte Unternehmen
        ausgewahlte_unternehmen = [unternehmen_liste[idx - 1] for idx in auswahl_indizes]
        print(f"\nAusgewählte Unternehmen: {', '.join(ausgewahlte_unternehmen)}")
        break
        
    except ValueError:
        print("Fehler: Bitte geben Sie gültige Nummern ein!")

# DataFrame mit nur ausgewählten Unternehmen
spalten_behalten = ['Zeit (TT-MM hh:mm)'] + ausgewahlte_unternehmen
df = df[spalten_behalten]

# Verbräuche der ausgewählten Unternehmen pro Zeitschritt addieren
df['Gesamtverbrauch (kW)'] = df[ausgewahlte_unternehmen].sum(axis=1)

# Ordner des Skripts ermitteln
script_dir = os.path.dirname(os.path.abspath(__file__))

# CSV-Datei speichern mit Namen der ausgewählten Unternehmen
unternehmen_name = "_".join([u.replace("-", "").replace(" ", "") for u in ausgewahlte_unternehmen])
csv_output_filename = os.path.join(script_dir, f"Gesamtverbrauch_{unternehmen_name}.csv")
df_output = df[['Zeit (TT-MM hh:mm)', 'Gesamtverbrauch (kW)']].copy()
df_output.to_csv(csv_output_filename, index=False, sep=",")
print(f"\nCSV-Datei gespeichert: {csv_output_filename}")

# Plot des Gesamtverbrauchs als Säulendiagramm
plt.figure(figsize=(16, 6))
plt.bar(range(len(df)), df['Gesamtverbrauch (kW)'], width=1.0, color='steelblue', edgecolor='none')
plt.xlabel('Zeitschritt (Stunden)', fontsize=12)
plt.ylabel('Gesamtverbrauch (kW)', fontsize=12)
plt.title(f"Jahresgang Gesamtverbrauch: {', '.join(ausgewahlte_unternehmen)}", fontsize=14, fontweight='bold')
plt.grid(axis='y', alpha=0.3)
plt.tight_layout()

# Plot speichern
plot_filename = os.path.join(script_dir, f"Gesamtverbrauch_{unternehmen_name}.png")
plt.savefig(plot_filename, dpi=300, bbox_inches='tight')
print(f"Plot gespeichert: {plot_filename}")
plt.show()

