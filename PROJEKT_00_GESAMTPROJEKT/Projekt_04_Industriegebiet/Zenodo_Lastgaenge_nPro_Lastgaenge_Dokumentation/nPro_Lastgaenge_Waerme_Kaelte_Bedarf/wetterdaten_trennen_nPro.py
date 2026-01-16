# Wetterdaten trennen, auf Stundenwerte aggregieren und nur reine Werte speichern
import pandas as pd
import os

# 1. Datei einlesen
script_dir = os.path.dirname(os.path.abspath(__file__))
file_path = os.path.join(script_dir, 'wetterdaten_2022_nPro.csv')

try:
    # Einlesen und Datum konvertieren
    df = pd.read_csv(file_path)
    print("Datei erfolgreich geladen.")
    
    # Datum in Index umwandeln für die Aggregation
    df['date'] = pd.to_datetime(df['date'], utc=True)
    df.set_index('date', inplace=True)
    
    # Aggregation auf Stundenwerte (Mittelwert)
    df = df.resample('h').mean()

    # Auf 1 Nachkommastelle runden
    df = df.round(1)
    print("Daten aggregiert und gerundet.")
    
except FileNotFoundError:
    print(f"Datei nicht gefunden: {file_path}")
    exit()

# 2. Zielordner erstellen
output_dir = os.path.join(script_dir, 'einzelspalten_nur_werte')
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# 3. Jede Spalte einzeln speichern (ohne Index und ohne Header)
for column in df.columns:
    clean_col_name = "".join([c if c.isalnum() else "_" for c in column])
    file_name = f"{output_dir}/{clean_col_name}.csv"
    
    # index=False entfernt das Datum
    # header=False entfernt die Spaltenüberschrift
    df[column].to_csv(file_name, index=False, header=False)
    print(f"Gespeichert (nur Werte): {file_name}")

print(f"\nFertig! Die Dateien in '{output_dir}' enthalten jetzt nur noch die reinen Zahlenwerte.")
