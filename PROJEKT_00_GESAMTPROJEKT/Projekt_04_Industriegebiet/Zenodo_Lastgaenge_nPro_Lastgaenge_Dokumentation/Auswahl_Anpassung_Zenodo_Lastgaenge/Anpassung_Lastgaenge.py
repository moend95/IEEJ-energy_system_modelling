# Anpassung Lastgaenge für Industriegebiet

import pandas as pd

# 1. Daten laden
file_path = r"C:\Users\johan\TH_Koeln_Masterprojekt\IEEJ-energy_system_modelling\PROJEKT_00_GESAMTPROJEKT\Projekt_04_Industriegebiet\Zenodo_Lastgaenge_nPro_Lastgaenge_Dokumentation\Auswahl_Anpassung_Zenodo_Lastgaenge\LoadProfile_30IPs_2017.csv"
df = pd.read_csv(file_path, header=1, delimiter=';')

# 2. Definition der gewünschten Spalten und ihrer Faktoren
columns_and_factors = {
    'LG 16': 115,
    'LG 30': 7.5,
    'LG 08': 19,
    'LG 27': 3.2,
    'LG 26': 0.054,
    'LG 20': 0.069,
    'LG 24': 3.6,
    'LG 06': 67
}

# 3. Extraktion der Zeitspalte und der oben definierten Lastgang-Spalten
columns_to_keep = ['Time stamp'] + list(columns_and_factors.keys())
df_processed = df[columns_to_keep].copy()

# --- NEU: 3.5 Bereinigung der Zeitstempel (Sommer-/Winterzeit Korrektur) ---
# Das " b" wird entfernt, damit das Datumsformat wieder stimmt
df_processed['Time stamp'] = df_processed['Time stamp'].str.replace(' b', '', regex=False)

# 4. Multiplikation der Werte mit den Faktoren
for col, factor in columns_and_factors.items():
    df_processed[col] = pd.to_numeric(df_processed[col], errors='coerce') * factor

# 5. Zeitstempel umwandeln
df_processed['Time stamp'] = pd.to_datetime(df_processed['Time stamp'], format='%d.%m.%Y %H:%M:%S')

# 5. Spalten umbenennen
# Hier kannst du alle Namen festlegen, die du ändern möchtest
rename_dict = {
    'LG 16': 'Entsorgung',
    'LG 30': 'Stahl_1',
    'LG 08': 'Logistik und Lagerung',
    'LG 27': 'Schrott Metallhandel',
    'LG 26': 'Lagerung',
    'LG 20': 'Buero',
    'LG 24': 'Logistik Lebensmittel',
    'LG 06': 'Stahl_2',
    'Time stamp': 'Time stamp'  # Optional: Auch die Zeitspalte eindeutschen
}

df_processed = df_processed.rename(columns=rename_dict)

# 6. Ergebnis anzeigen und speichern
print("Verarbeitung abgeschlossen. Hier sind die ersten Zeilen:")
print(df_processed.head())

# Kannst du auch den absoluten Pfad nutzen (damit es im gleichen Ordner liegt wie die Eingabe):
import os
output_folder = os.path.dirname(file_path)
output_path = os.path.join(output_folder, 'Projekt_04_Lastgaenge_Industriegebiet.csv')
df_processed.to_csv(output_path, index=False, sep=';')
