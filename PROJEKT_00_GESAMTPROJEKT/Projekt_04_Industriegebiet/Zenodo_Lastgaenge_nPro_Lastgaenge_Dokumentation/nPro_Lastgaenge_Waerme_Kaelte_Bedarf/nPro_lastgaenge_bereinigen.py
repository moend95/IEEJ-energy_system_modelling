# nPro Lastgänge bereinigen
# Pro Branche/Unternehmen werden die Verbräuche aufsummiert und in eine neue Datei geschrieben

import pandas as pd

def sum_columns():
    # 1. Dateinamen definieren
    input_file = r'C:\Users\johan\TH_Koeln_Masterprojekt\IEEJ-energy_system_modelling\PROJEKT_00_GESAMTPROJEKT\Projekt_04_Industriegebiet\Zenodo_Lastgaenge_nPro_Lastgaenge_Dokumentation\nPro_Lastgaenge_Waerme_Kaelte_Bedarf\nPro_lastgaenge_waerme_kaelte.csv'
    output_file = 'summierte_lastgaenge_nPro.csv'

    try:
        # 2. CSV-Datei laden
        # Hinweis: Falls die Datei Semikolons statt Kommas nutzt, ändere sep=',' zu sep=';'
        df = pd.read_csv(input_file)
        
        # Sicherstellen, dass die Zeit-Spalte existiert
        time_col = 'Zeit (TT-MM hh:mm)'
        if time_col not in df.columns:
            print(f"Warnung: Spalte '{time_col}' nicht gefunden. Überprüfe den Dateikopf.")
            return

        # 3. Definition der Gruppen und ihrer zugehörigen Spalten
        # Hier werden die exakten Namen aus deiner Anforderung gemappt
        groups = {
            "Entsorgung": [
                "Entsorgung-Raumwärme (kW)", "Entsorgung-Trinkwarmwasser (kW)", 
                "Entsorgung-Klimatisierung (kW)", "Entsorgung-Prozesskälte (kW)", 
                "Entsorgung-Nutzerstrom (kW)", "Entsorgung-Elektromobilität (kW)"
            ],
            "Stahl_1": [
                "Stahl_1-Raumwärme (kW)", "Stahl_1-Trinkwarmwasser (kW)", 
                "Stahl_1-Klimatisierung (kW)", "Stahl_1-Prozesskälte (kW)", 
                "Stahl_1-Nutzerstrom (kW)", "Stahl_1-Elektromobilität (kW)"
            ],
            "Logistik und Lagerung": [
                "Logistik und Lagerung-Raumwärme (kW)", "Logistik und Lagerung-Trinkwarmwasser (kW)", 
                "Logistik und Lagerung-Klimatisierung (kW)", "Logistik und Lagerung-Prozesskälte (kW)", 
                "Logistik und Lagerung-Nutzerstrom (kW)", "Logistik und Lagerung-Elektromobilität (kW)"
            ],
            "Logistik Lebensmittel": [
                "Logistik Lebensmittel-Raumwärme (kW)", "Logistik Lebensmittel-Trinkwarmwasser (kW)", 
                "Logistik Lebensmittel-Klimatisierung (kW)", "Logistik Lebensmittel-Prozesskälte (kW)", 
                "Logistik Lebensmittel-Nutzerstrom (kW)", "Logistik Lebensmittel-Elektromobilität (kW)"
            ],
            "Buero": [
                "Buero-Raumwärme (kW)", "Buero-Trinkwarmwasser (kW)", 
                "Buero-Klimatisierung (kW)", "Buero-Prozesskälte (kW)", 
                "Buero-Nutzerstrom (kW)", "Buero-Elektromobilität (kW)"
            ],
            "Schrott Metallhandel": [
                "Schrott Metallhandel-Raumwärme (kW)", "Schrott Metallhandel-Trinkwarmwasser (kW)", 
                "Schrott Metallhandel-Klimatisierung (kW)", "Schrott Metallhandel-Prozesskälte (kW)", 
                "Schrott Metallhandel-Nutzerstrom (kW)", "Schrott Metallhandel-Elektromobilität (kW)"
            ],
            "Lagerung": [
                "Lagerung-Raumwärme (kW)", "Lagerung-Trinkwarmwasser (kW)", 
                "Lagerung-Klimatisierung (kW)", "Lagerung-Prozesskälte (kW)", 
                "Lagerung-Nutzerstrom (kW)", "Lagerung-Elektromobilität (kW)"
            ],
            "Stahl_2": [
                "Stahl_2-Raumwärme (kW)", "Stahl_2-Trinkwarmwasser (kW)", 
                "Stahl_2-Klimatisierung (kW)", "Stahl_2-Prozesskälte (kW)", 
                "Stahl_2-Nutzerstrom (kW)", "Stahl_2-Elektromobilität (kW)"
            ]
        }

        # 4. Neues DataFrame für den Output erstellen
        output_df = pd.DataFrame()
        output_df[time_col] = df[time_col]

        # 5. Iteration durch die Gruppen und Berechnung der Summen
        print("Berechne Summen...")
        for new_col_name, columns_to_sum in groups.items():
            # Überprüfen, welche Spalten tatsächlich in der Datei vorhanden sind
            existing_cols = [c for c in columns_to_sum if c in df.columns]
            missing_cols = [c for c in columns_to_sum if c not in df.columns]
            
            if missing_cols:
                print(f"  Hinweis für '{new_col_name}': {len(missing_cols)} Spalten nicht gefunden (werden als 0 gewertet).")

            # Summe bilden (axis=1 summiert über die Zeile)
            if existing_cols:
                output_df[new_col_name] = df[existing_cols].sum(axis=1)
            else:
                output_df[new_col_name] = 0.0

        # 6. Ergebnis speichern
        output_df.to_csv(output_file, index=False)
        print(f"Erfolg! Datei wurde gespeichert unter: {output_file}")

    except FileNotFoundError:
        print(f"Fehler: Die Datei '{input_file}' wurde nicht gefunden. Bitte stelle sicher, dass sie im gleichen Ordner liegt.")
    except Exception as e:
        print(f"Ein unerwarteter Fehler ist aufgetreten: {e}")

if __name__ == "__main__":
    sum_columns()

