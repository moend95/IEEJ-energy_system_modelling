# Industriegebiet - Lastgänge Unternehmen 
# Auswahl der Lastgänge für verschiedene Unternehmen im Industriegebiet

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.dates import MonthLocator, DateFormatter
import os
import collections

# Pfade zu den CSV-Dateien (im gleichen Ordner wie das Skript)
script_dir = os.path.dirname(os.path.abspath(__file__))
path_2016 = os.path.join(script_dir, "LoadProfile_20IPs_2016.csv")
path_2017 = os.path.join(script_dir, "LoadProfile_30IPs_2017.csv")

# Einlesen der CSV-Dateien
df_2016 = pd.read_csv(path_2016, sep=';', decimal=',', header=1)
df_2017 = pd.read_csv(path_2017, sep=';', decimal=',', header=1)

# Liste der verfügbaren Unternehmen
unternehmen = [
    "Stahlindustrie",
    "Entsorgungswirtschaft",
    "Lebensmittel-Einzelhandel",
    "Immobilien-Entwicklung",
    "Logistikdienstleistung"
]

# User-Input für die Auswahl der Unternehmen
print("Verfügbare Unternehmen:")
for i, u in enumerate(unternehmen, 1):
    print(f"{i}. {u}")

auswahl_input = input("Geben Sie die Nummern der Unternehmen ein, die betrachtet werden sollen (mehrere durch Kommas trennen, Doppelauswahl möglich, z.B. 1,3,5): ")

# Parsen der Eingabe
try:
    auswahl_indices = [int(x.strip()) - 1 for x in auswahl_input.split(',') if x.strip().isdigit()]
    if len(auswahl_indices) > 5:
        print("Maximal 5 Auswahlen erlaubt.")
        exit()
    ausgewahlte_unternehmen = [unternehmen[i] for i in auswahl_indices if 0 <= i < len(unternehmen)]
    if not ausgewahlte_unternehmen:
        print("Keine gültige Auswahl getroffen. Programm beendet.")
        exit()
    print(f"Ausgewählte Unternehmen: {ausgewahlte_unternehmen}")
    name_suffix = "_".join(ausgewahlte_unternehmen)
except ValueError:
    print("Ungültige Eingabe. Bitte nur Zahlen und Kommas verwenden.")
    exit()

# Zuordnung der Unternehmen zu Lastgängen
zuordnung = {
    "Stahlindustrie": ("LG 15", "2016"),
    "Entsorgungswirtschaft": ("LG 9", "2016"),
    "Lebensmittel-Einzelhandel": ("LG 12", "2016"),
    "Immobilien-Entwicklung": ("LG 6", "2016"),
    "Logistikdienstleistung": ("LG 2", "2016")
}

# Extrahiere die relevanten Lastgänge basierend auf der Auswahl
selected_columns = ['Time stamp']
selected_data = {}
unternehmen_counts = collections.defaultdict(int)

for idx in auswahl_indices:
    if 0 <= idx < len(unternehmen):
        u = unternehmen[idx]
        unternehmen_counts[u] += 1
        key = f"{u}_{unternehmen_counts[u]}"
        lg, year = zuordnung[u]
        if year == "2016":
            selected_columns.append(lg)
            selected_data[key] = df_2016[['Time stamp', lg]].copy()
            selected_data[key].rename(columns={lg: key}, inplace=True)
            selected_data[key][key] = pd.to_numeric(selected_data[key][key], errors='coerce')
        elif year == "2017":
            selected_columns.append(lg)
            selected_data[key] = df_2017[['Time stamp', lg]].copy()
            selected_data[key].rename(columns={lg: key}, inplace=True)
            selected_data[key][key] = pd.to_numeric(selected_data[key][key], errors='coerce')

# Kombiniere die Daten in einem DataFrame
if selected_data:
    combined_df = pd.DataFrame()
    for df in selected_data.values():
        if combined_df.empty:
            combined_df = df
        else:
            combined_df = pd.merge(combined_df, df, on='Time stamp', how='outer')
    print("\nKombinierte Lastgänge für ausgewählte Unternehmen:")
    print(combined_df.head())

    # Berechne die Summe der Lastgänge
    combined_df['Gesamtlast'] = combined_df.drop('Time stamp', axis=1).sum(axis=1)
    print("\nSumme der Lastgänge:")
    print(combined_df[['Time stamp', 'Gesamtlast']].head())

    # Konvertiere Time stamp zu datetime für Plots
    combined_df['Time stamp'] = pd.to_datetime(combined_df['Time stamp'], format='%d.%m.%Y %H:%M:%S', errors='coerce')

    # Ausgabe als CSV-Datei
    # Formatiere Zeitstempel ohne Jahreszahl für CSV
    combined_df_csv = combined_df.copy()
    combined_df_csv['Time stamp'] = combined_df_csv['Time stamp'].dt.strftime('%d.%m %H:%M')
    output_path = os.path.join(script_dir, f"combined_load_profiles_{name_suffix}.csv")
    combined_df_csv[['Time stamp', 'Gesamtlast']].to_csv(output_path, sep=';', decimal=',', index=False)
    print(f"\nKombinierte Lastgänge gespeichert in: {output_path}")

    # Erstelle ein Balkendiagramm der Gesamtlast
    try:
        combined_df_plot = combined_df.copy()
        # Aggregiere auf tägliche Summen für bessere Darstellung
        combined_df_plot = combined_df_plot.set_index('Time stamp').resample('D').sum().reset_index()
        plt.figure(figsize=(20, 10))
        plt.bar(combined_df_plot['Time stamp'], combined_df_plot['Gesamtlast'], width=1)  # Breite 1 Tag
        plt.xlabel('Zeit')
        plt.ylabel('Tägliche Gesamtlast (kW)')
        plt.title('Tägliche Gesamtlast über das Jahr')
        plt.xticks(rotation=45)
        ax = plt.gca()
        ax.xaxis.set_major_locator(MonthLocator())
        ax.xaxis.set_major_formatter(DateFormatter('%B'))  # %B für vollen Monatsnamen (Januar, Februar, etc.)
        plt.xlim(combined_df_plot['Time stamp'].min(), combined_df_plot['Time stamp'].max())
        plot_path = os.path.join(script_dir, f"gesamtlast_plot_{name_suffix}.png")
        plt.savefig(plot_path)
        print(f"Balkenplot gespeichert als: {plot_path}")

    except Exception as e:
        print(f"Fehler beim Erstellen des Plots: {e}")

else:
    print("Keine Daten zu extrahieren.")

# Überprüfung der eingelesenen Daten (optional)
print("Daten für 2016 eingelesen:")
print(df_2016.head())
print("\nDaten für 2017 eingelesen:")
print(df_2017.head())

