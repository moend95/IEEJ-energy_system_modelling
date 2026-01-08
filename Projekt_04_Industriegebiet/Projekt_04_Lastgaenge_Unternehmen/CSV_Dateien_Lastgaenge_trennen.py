# Skript um CSV-Dateien zu trennen und in einzelne Dateien zu speichern

import pandas as pd

# CSV-Datei einlesen
file_path = r'c:\Users\johan\TH_Koeln_Masterprojekt\IEEJ-energy_system_modelling\Projekt_04_Industriegebiet\Projekt_04_Industriegebiet\LoadProfile_20IPs_2016_hourly.csv'
df = pd.read_csv(file_path, sep=';')

# Spalten außer 'Time stamp' durchgehen
columns_to_export = [col for col in df.columns if col != 'Time stamp']

# Für jede Spalte eine separate CSV-Datei erstellen
for col in columns_to_export:
    # Nur die Werte der Spalte extrahieren
    values = df[col]
    # Dateiname basierend auf dem Spaltennamen
    output_filename = f"{col}.csv"
    output_path = rf'c:\Users\johan\TH_Koeln_Masterprojekt\IEEJ-energy_system_modelling\Projekt_04_Industriegebiet\Projekt_04_Lastgaenge_Unternehmen\{output_filename}'
    # Speichere nur die Werte, ohne Header oder Index
    values.to_csv(output_path, index=False, header=False)

print("Einzelne CSV-Dateien für jeden Lastgang wurden erstellt.")

