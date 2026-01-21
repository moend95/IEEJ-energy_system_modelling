# CSV-Dateien zusammenführen
# Industriegebiet + nPro Wärme/Kälte Lastgänge

import pandas as pd

def add_load_profiles(file_industrie, file_waerme_kaelte, output_file):
    # 1. Daten einlesen
    # Wir setzen 'Time stamp' als Index, um die Zeilen automatisch korrekt zuzuordnen
    df_ind = pd.read_csv(file_industrie, sep=';', index_col='Time stamp')
    df_wk = pd.read_csv(file_waerme_kaelte, sep=';', index_col='Time stamp')

    # Sicherstellen, dass der Index als Datetime vorliegt (für robusten Abgleich)
    df_ind.index = pd.to_datetime(df_ind.index)
    df_wk.index = pd.to_datetime(df_wk.index)

    # 2. Addition der DataFrames
    # Da beide DataFrames den gleichen Index und die gleichen Spaltennamen haben,
    # addiert pandas automatisch die Werte, die an der gleichen Stelle (Zeit & Firma) stehen.
    # .fillna(0) stellt sicher, dass keine Fehler entstehen, falls ein Zeitstempel in einer Datei fehlt.
    df_gesamt = df_ind.add(df_wk, fill_value=0)

    # 3. Ergebnis speichern
    # Index wieder in Spalte umwandeln für das ursprüngliche Format
    df_gesamt.reset_index(inplace=True)
    
    # Speichern als CSV mit dem ursprünglichen Trennzeichen
    df_gesamt.to_csv(output_file, sep=';', index=False)
    
    print(f"Erfolgreich! Die summierte Datei wurde als '{output_file}' gespeichert.")

# Dateinamen definieren
file_1 = r'C:\Users\johan\TH_Koeln_Masterprojekt\IEEJ-energy_system_modelling\PROJEKT_00_GESAMTPROJEKT\Projekt_04_Industriegebiet\Projekt_04_Lastgaenge_Industriegebiet.csv'
file_2 = r'C:\Users\johan\TH_Koeln_Masterprojekt\IEEJ-energy_system_modelling\PROJEKT_00_GESAMTPROJEKT\Projekt_04_Industriegebiet\Projekt_04_Lastgaenge_nPro_Waerme_Kaelte.csv'
output = 'Projekt_04_Lastgaenge_Industriegebiet_und_nPro_Waerme_Kaelte.csv'

# Skript ausführen
if __name__ == "__main__":
    add_load_profiles(file_1, file_2, output)

