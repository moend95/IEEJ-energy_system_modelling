# Run Skript für die Solar-Autobahn in Jüchen - führt alle Funktionskripte aus

#----------------------- Wetterdatenfunktion starten ---------------------------------

from Solarautobahn.functions_weather_data import fetch_weather_data

df = fetch_weather_data(
    coords=(51.08579, 6.47554),                # Solarautobahn-Koordinaten
    start="2022-01-01",
    end="2022-12-31",
    station_id=None,                           # station_id=None, auto_select=False = eigene Stationswahl;  station_id=None, auto_select=True = Automatische Stationswahl; oder direkt station Id angeben
    auto_select=False,
    min_quality=0.95,
    save_path = "./Input/wetterdaten_solarautobahn_2022.csv",
    plot_date=None,                    # Optionaler Plot für einen bestimmten Tag
    plot_range=("2022-01-01", "2022-12-31")                            # (start, end) z.B. ("2022-01-01", "2022-12-31")
)

print("Wetterdaten erfolgreich geladen und gespeichert.")

#----------------------- Geometriefunktion skript starten: -----------------------------------------

from Solarautobahn.functions_geometrie import run_autobahn_geometrie

# Geometrie erzeugen und speichern
run_autobahn_geometrie(
    base_path="./Input"
)


# ---------------------- Azimut-Funktion starten ----------------------

from Solarautobahn.functions_PV_Modul_und_Azimuth import run_azimut_berechnung

run_azimut_berechnung(
    base_path="./Input"
)

# ---------------------- PV-Ertragssimulation starten ----------------------
from Solarautobahn.functions_PV_Auslegung import simulate_pv_yield

# nötige gespeicherte Daten aus Input Ordner laden:
simulate_pv_yield(
    weather_csv_path="./Input/wetterdaten_solarautobahn_2022.csv",
    points_csv_path="./Input/punkte_mit_azimut.csv",
    save_results_to="./Input/pv_ertrag_ergebnisse.csv"
)
