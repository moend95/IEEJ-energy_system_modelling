# Industriegebiet - Lastgänge Unternehmen 
# Auswahl der Lastgänge für verschiedene Unternehmen im Industriegebiet

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.dates import MonthLocator, DateFormatter

# Pfade zu den CSV-Dateien
path_2016 = r"c:\Users\johan\TH_Koeln_Masterprojekt\IEEJ-energy_system_modelling\Projekt_04_Industriegebiet\Projekt_04_Lastgaenge_Unternehmen\LoadProfile_20IPs_2016.csv"
path_2017 = r"c:\Users\johan\TH_Koeln_Masterprojekt\IEEJ-energy_system_modelling\Projekt_04_Industriegebiet\Projekt_04_Lastgaenge_Unternehmen\LoadProfile_30IPs_2017.csv"

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

auswahl_input = input("Geben Sie die Nummern der Unternehmen ein, die betrachtet werden sollen (mehrere durch Kommas trennen, z.B. 1,3,5): ")

# Parsen der Eingabe
try:
    auswahl_indices = [int(x.strip()) - 1 for x in auswahl_input.split(',') if x.strip().isdigit()]
    ausgewahlte_unternehmen = [unternehmen[i] for i in auswahl_indices if 0 <= i < len(unternehmen)]
    if not ausgewahlte_unternehmen:
        print("Keine gültige Auswahl getroffen. Programm beendet.")
        exit()
    print(f"Ausgewählte Unternehmen: {ausgewahlte_unternehmen}")
except ValueError:
    print("Ungültige Eingabe. Bitte nur Zahlen und Kommas verwenden.")
    exit()

# Zuordnung der Unternehmen zu Lastgängen
zuordnung = {
    "Stahlindustrie": ("LG 15", "2016"),
    "Entsorgungswirtschaft": ("LG 9", "2016"),
    "Lebensmittel-Einzelhandel": ("LG 12", "2016"),
    "Immobilien-Entwicklung": ("LG 10", "2017"),
    "Logistikdienstleistung": ("LG 2", "2016")
}

# Extrahiere die relevanten Lastgänge basierend auf der Auswahl
selected_columns = ['Time stamp']
selected_data = {}

for unternehmen in ausgewahlte_unternehmen:
    lg, year = zuordnung[unternehmen]
    if year == "2016":
        selected_columns.append(lg)
        selected_data[unternehmen] = df_2016[['Time stamp', lg]].copy()
        selected_data[unternehmen].rename(columns={lg: unternehmen}, inplace=True)
        selected_data[unternehmen][unternehmen] = pd.to_numeric(selected_data[unternehmen][unternehmen], errors='coerce')
    elif year == "2017":
        selected_columns.append(lg)
        selected_data[unternehmen] = df_2017[['Time stamp', lg]].copy()
        selected_data[unternehmen].rename(columns={lg: unternehmen}, inplace=True)
        selected_data[unternehmen][unternehmen] = pd.to_numeric(selected_data[unternehmen][unternehmen], errors='coerce')

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
    output_path = r"c:\Users\johan\TH_Koeln_Masterprojekt\IEEJ-energy_system_modelling\Projekt_04_Industriegebiet\Projekt_04_Lastgaenge_Unternehmen\combined_load_profiles.csv"
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
        plot_path = r"c:\Users\johan\TH_Koeln_Masterprojekt\IEEJ-energy_system_modelling\Projekt_04_Industriegebiet\Projekt_04_Lastgaenge_Unternehmen\gesamtlast_plot.png"
        plt.savefig(plot_path)
        print(f"Balkenplot gespeichert als: {plot_path}")

        # Zweiter Plot: Balkendiagramm für 15-Minuten-Intervalle (beispielhaft für Januar)
        plt.figure(figsize=(20, 10))
        # Filter für Januar zur besseren Darstellung (ca. 3000 Punkte statt 35000)
        januar_data = combined_df[combined_df['Time stamp'].dt.month == 1]
        plt.bar(januar_data['Time stamp'], januar_data['Gesamtlast'], width=0.01)
        plt.xlabel('Zeit')
        plt.ylabel('Gesamtlast (kW)')
        plt.title('Gesamtlast über 15-Minuten-Intervalle (Januar)')
        plt.xticks(rotation=45)
        ax2 = plt.gca()
        ax2.xaxis.set_major_locator(MonthLocator())
        ax2.xaxis.set_major_formatter(DateFormatter('%d.%m'))
        plt.xlim(januar_data['Time stamp'].min(), januar_data['Time stamp'].max())
        plot_path2 = r"c:\Users\johan\TH_Koeln_Masterprojekt\IEEJ-energy_system_modelling\Projekt_04_Industriegebiet\Projekt_04_Lastgaenge_Unternehmen\gesamtlast_15min_plot.png"
        plt.savefig(plot_path2)
        print(f"Balkendiagramm für 15-Minuten-Intervalle (Januar) gespeichert als: {plot_path2}")
    except Exception as e:
        print(f"Fehler beim Erstellen des Plots: {e}")

else:
    print("Keine Daten zu extrahieren.")

# Überprüfung der eingelesenen Daten (optional)
print("Daten für 2016 eingelesen:")
print(df_2016.head())
print("\nDaten für 2017 eingelesen:")
print(df_2017.head())

