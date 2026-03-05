# nPro Lastgänge in 15-Minuten-Werten extrahieren

import pandas as pd
import numpy as np

# 1. Datei laden
file_path = r'C:\Users\johan\TH_Koeln_Masterprojekt\IEEJ-energy_system_modelling\PROJEKT_00_GESAMTPROJEKT\Projekt_04_Industriegebiet\Zenodo_Lastgaenge_nPro_Lastgaenge_Dokumentation\nPro_Lastgaenge_Waerme_Kaelte_Bedarf\summierte_lastgaenge_nPro.csv'
df = pd.read_csv(file_path)

# 2. Zeitstempel in Datetime-Objekte umwandeln
# Da kein Jahr angegeben ist, ergänzen wir ein fiktives Jahr (z.B. 2024), 
# damit pandas die Zeitreihen-Funktionen nutzen kann.
df['Zeit (TT-MM hh:mm)'] = pd.to_datetime(df['Zeit (TT-MM hh:mm)'] + '-2024', format='%d-%m %H:%M-%Y')

# Zeitstempel als Index setzen
df.set_index('Zeit (TT-MM hh:mm)', inplace=True)

# 3. Resampling auf 15 Minuten
# 'asfreq' erstellt die neuen Zeilen (00:15, 00:30, 00:45), die zunächst leer (NaN) sind.
df_15min = df.resample('15min').asfreq()

# 4. Werte auffüllen und durch 4 teilen
# Wir nutzen 'ffill' (forward fill), um den Stundenwert in die 15-Min-Slots zu kopieren,
# und teilen dann alles durch 4.
df_15min = df_15min.ffill() / 4

# 5. Formatierung zurück anpassen
# Wir wandeln den Index zurück in das ursprüngliche String-Format TT-MM hh:mm
df_15min.index = df_15min.index.strftime('%d-%m %H:%M')

# 6. Speichern der neuen Datei
output_path = 'summierte_lastgaenge_nPro_15min.csv'
df_15min.to_csv(output_path)

print(f"Datei erfolgreich erstellt: {output_path}")
print(df_15min.head(8)) # Zeigt die ersten zwei Stunden zur Kontrolle
