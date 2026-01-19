# Industriegebiet - Lastgänge Unternehmen 
# Auswahl der Lastgänge für verschiedene Unternehmen im Industriegebiet

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.dates import MonthLocator, DateFormatter
import os
import collections

# Pfade zu den CSV-Dateien (im gleichen Ordner wie das Skript)
script_dir = os.path.dirname(os.path.abspath(__file__))
path_standard = os.path.join(script_dir, "Projekt_04_Lastgaenge_Industriegebiet.csv")
path_waerme_kaelte = os.path.join(script_dir, "Projekt_04_Lastgaenge_Industriegebiet_und_nPro_Waerme_Kaelte.csv")

print("Welche Daten sollen genutzt werden?")
print("1) Ohne Wärme/Kälte Stromverbrauch (Nutzung fossiler Energiequellen)")
print("2) Mit Wärme/Kälte Stromverbrauch (Nutzung reversibler Luftwärmepumpen und Geothermie-Sonden)")
wahl = input("Auswahl (1 oder 2): ")

if wahl == "2":
    path_aktiv = path_waerme_kaelte
    modus_name = "Mit_Waerme_Kaelte"
    print("Modus: Mit Wärme/Kälte ausgewählt.\n")
else:
    path_aktiv = path_standard
    modus_name = "Ohne_Waerme_Kaelte"
    print("Modus: Ohne Wärme/Kälte ausgewählt.\n")

# Einlesen der CSV-Dateien
df_2017 = pd.read_csv(path_aktiv, sep=';', decimal=',', header=0)

# Liste der verfügbaren Unternehmen
unternehmen = [
    "Entsorgung (5 1/2 Tage Woche, Kein Schichtbetrieb, Anlehnung an Schönmackers Umweltdienste)",
    "Stahl (5 Tage Woche, 3-Schicht-Betrieb, Anlehnung an TecPro)",
    "Logistik und Lagerung (5 Tage Woche, Teilweise Samstag und Sonntag Betrieb, Kein Schichtbetrieb, Anlehnung an CTJ Janssen)",
    "Schrott- und Metallhandel (5 Tage Woche, Kein Schichtbetrieb, Anlehnung an Willi Jenner)",
    "Lagerung (5 Tage Woche, Kein Schichtbetrieb, Anlehnung an Kleine Logistik)", 
    "Büro (5 Tage Woche, Kein Schichtbetrieb, Anlehnung an Marvin Wickenhäuser)", 
    "Logistik Lebensmittel (6 1/2 Tage Woche, Kein Schichtbetrieb, Anlehnung an CTJ Janssen)", 
    "Stahl (7 Tage Woche, 2-Schicht-Betrieb, Anlehnung an TecPro)"
]

# User-Input für die Auswahl der Unternehmen
print("Verfügbare Unternehmen:")
for i, u in enumerate(unternehmen, 1):
    print(f"{i}. {u}")

auswahl_input = input("Geben Sie die Nummern der Unternehmen ein, die betrachtet werden sollen (Durch Kommas trennen, Doppelauswahl möglich, Minimal 1 Unternehmen, Maximal 5 Unternehmen, z.B. 1,3,5): ")

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
    # Erstelle einen sauberen Dateinamen-Suffix (nur Zahlen und Unterstriche)
    basisname = "Projekt_04_Erzeugter_Gesamtverbrauch_Industriegebiet"
except ValueError:
    print("Ungültige Eingabe. Bitte nur Zahlen und Kommas verwenden.")
    exit()

# Zuordnung der Unternehmen zu Lastgängen
zuordnung = {
    "Entsorgung (5 1/2 Tage Woche, Kein Schichtbetrieb, Anlehnung an Schönmackers Umweltdienste)": ("Entsorgung", "2017"),
    "Stahl (5 Tage Woche, 3-Schicht-Betrieb, Anlehnung an TecPro)": ("Stahl_1", "2017"),
    "Logistik und Lagerung (5 Tage Woche, Teilweise Samstag und Sonntag Betrieb, Kein Schichtbetrieb, Anlehnung an CTJ Janssen)": ("Logistik und Lagerung", "2017"),
    "Schrott- und Metallhandel (5 Tage Woche, Kein Schichtbetrieb, Anlehnung an Willi Jenner)": ("Schrott Metallhandel", "2017"),
    "Lagerung (5 Tage Woche, Kein Schichtbetrieb, Anlehnung an Kleine Logistik)": ("Lagerung", "2017"), 
    "Büro (5 Tage Woche, Kein Schichtbetrieb, Anlehnung an Marvin Wickenhäuser)": ("Buero", "2017"),
    "Logistik Lebensmittel (6 1/2 Tage Woche, Kein Schichtbetrieb, Anlehnung an CTJ Janssen)": ("Logistik Lebensmittel", "2017"),
    "Stahl (7 Tage Woche, 2-Schicht-Betrieb, Anlehnung an TecPro)": ("Stahl_2", "2017")
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
        if year == "2017":
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
    #print("\nKombinierte Lastgänge für ausgewählte Unternehmen:")
    #print(combined_df.head())

    # Berechne die Summe der Lastgänge
    combined_df['Gesamtlast'] = combined_df.drop('Time stamp', axis=1).sum(axis=1)
    print("\nSumme der Lastgänge (kW je 15 Minuten):")
    print(combined_df[['Time stamp', 'Gesamtlast']].head(96)) # Zeige die ersten 24 Stunden (96 Intervalle)

    # Konvertiere Time stamp zu datetime für Plots
    combined_df['Time stamp'] = pd.to_datetime(combined_df['Time stamp'], errors='coerce')

    # Ausgabe als CSV-Datei
    # Formatiere Zeitstempel ohne Jahreszahl für CSV
    combined_df_csv = combined_df.copy()
    combined_df_csv['Time stamp'] = combined_df_csv['Time stamp'].dt.strftime('%d.%m %H:%M')
    output_path = os.path.join(script_dir, f"{basisname}.csv")
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
        plot_path = os.path.join(script_dir, f"{basisname}.png")
        plt.savefig(plot_path)
        print(f"Balkenplot gespeichert als: {plot_path}")

    except Exception as e:
        print(f"Fehler beim Erstellen des Plots: {e}")

else:
    print("Keine Daten zu extrahieren.")

# Überprüfung der eingelesenen Daten (optional)
# print("Daten für 2017 eingelesen:")
# print(df_2017.head())
