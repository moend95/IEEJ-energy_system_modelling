# Code um CSV-Dateien zusammenzuführen und zu formatieren

import pandas as pd

# CSV-Datei einlesen
file_path = r'c:\Users\johan\TH_Koeln_Masterprojekt\IEEJ-energy_system_modelling\Projekt_04_Industriegebiet\Projekt_04_Lastgaenge_Unternehmen\LoadProfile_20IPs_2016.csv'
df = pd.read_csv(file_path, sep=';', skiprows=1)  # Überspringe die erste Kommentarzeile

# Spalten filtern: Zeitreihen-Spalte und LG 15, LG 9, LG 12, LG 6, LG 2
columns_to_keep = ['Time stamp', 'LG 2', 'LG 6', 'LG 9', 'LG 12', 'LG 15']
df_filtered = df[columns_to_keep]

# Zeitspalte zu datetime konvertieren
df_filtered['Time stamp'] = df_filtered['Time stamp'].str.strip().str.replace(r'\s*b$', '', regex=True)
df_filtered['Time stamp'] = pd.to_datetime(df_filtered['Time stamp'], dayfirst=True)

# Setze Zeit als Index
df_filtered.set_index('Time stamp', inplace=True)

# Resample zu stündlichen Werten und summiere
df_hourly = df_filtered.resample('H').sum()

# Reset Index, um Zeitspalte zurückzubringen
df_hourly.reset_index(inplace=True)

# Optional: Speichere die bearbeitete Datei
output_path = r'c:\Users\johan\TH_Koeln_Masterprojekt\IEEJ-energy_system_modelling\Projekt_04_Industriegebiet\Projekt_04_Lastgaenge_Unternehmen\LoadProfile_20IPs_2016_hourly.csv'
df_hourly.to_csv(output_path, sep=';', index=False)

print("Bearbeitete Datei gespeichert unter:", output_path)

