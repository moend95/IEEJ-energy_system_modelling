# Run Skript für die Solar-Autobahn in Jüchen - führt alle Funktionskripte aus

#----------------------- Wetterdatenfunktion starten ---------------------------------

from Solarautobahn.functions_weather_data import fetch_weather_data

df = fetch_weather_data(
    coords=(51.08579, 6.47554),                # Solarautobahn-Koordinaten
    start="2022-01-01",
    end="2022-12-31",
    station_id=None,                           # station_id=None, auto_select=False = eigene Stationswahl;  station_id=None, auto_select=True = Automatische Stationswahl; oder direkt station Id angeben
    auto_select=True,
    min_quality=0.95,
    save_path=r"/Input/wetterdaten_solarautobahn_2022.csv",
    plot_date="2022-06-21"                     # Optionaler Plot für einen bestimmten Tag
)

print("Wetterdaten erfolgreich geladen und gespeichert.")

#----------------------- Geometriefunktion skript starten: -----------------------------------------

from Solarautobahn.functions_geometrie import run_autobahn_geometrie

# Geometrie erzeugen und speichern
run_autobahn_geometrie(
    base_path=r"/Input"
)


# ---------------------- Azimut-Funktion starten ----------------------

from Solarautobahn.functions_PV_Modul_und_Azimuth import run_azimut_berechnung

run_azimut_berechnung(
    base_path=r"/Input"
)

# ---------------------- PV-Ertragssimulation starten ----------------------
from Solarautobahn.functions_pv_simulation import simulate_pv_yield

simulate_pv_yield(
    weather_csv_path=r"/Input/wetterdaten_solarautobahn_2022.csv",
    points_csv_path=r"/Input/punkte_mit_azimut.csv",
    save_results_to=r"C:\Users\sarah\Documents\GitHub\IEEJ-energy_system_modelling\Input\pv_ertrag_ergebnisse.csv"
)


# PV-Modul- und Inverter-Daten laden
temperature_model_parameters = pvlib.temperature.TEMPERATURE_MODEL_PARAMETERS['sapm']['open_rack_glass_glass']
sandia_modules = pvlib.pvsystem.retrieve_sam('cecmod')
cec_inverters = pvlib.pvsystem.retrieve_sam('cecinverter')

sandia_module = sandia_modules['Jinko_Solar__Co___Ltd_JKM400M_72L']
cec_inverter = cec_inverters['ABB__UNO_2_0_I_OUTD_S_US__277V_']

# Punkte und Ausrichtungen laden
# Reihenfolge (Latitude (Breitengrad), Longitude (Längengrad), Ausrichtung (Azimut)
# Punkte und Ausrichtungen aus CSV laden
punkte_df = pd.read_csv(r"C:\Users\sarah\OneDrive\Dokumenty\GitHub\IEEJ-energy_system_modelling\Input\punkte_mit_azimut.csv")
punkte = list(punkte_df.itertuples(index=False, name=None))

# PV-System an jedem Punkt simulieren
# Liste für alle Energieergebnisse
annual_energies = []

for idx, (latitude, longitude, azimut) in tqdm(enumerate(punkte), total=len(punkte), desc="Simuliere PV-Punkte"):

    # Standort definieren
    location = Location(latitude=latitude, longitude=longitude, tz="Europe/Berlin", altitude=80)

    # PVSystem definieren
    system = PVSystem(
        surface_tilt=20,
        surface_azimuth=azimut,
        module_parameters=sandia_module,
        inverter_parameters=cec_inverter,
        temperature_model_parameters=temperature_model_parameters,
        modules_per_string=4,
        strings_per_inverter=1
    )

    # ModelChain aufbauen
    mc = ModelChain(system, location, aoi_model='physical', spectral_model='no_loss', temperature_model='sapm')

    # Simulation ausführen
    mc.run_model(weather_data)

    # Ergebnisse speichern
    results = mc.results.ac

    # Jahresertrag berechnen
    annual_energy_kwh = (results.sum() * (10/60)) / 1000  # 10min Daten in kWh
    annual_energies.append(annual_energy_kwh)

 # Fortschritt ausgeben (nur alle 100 Punkte)
    if idx % 100 == 0:
        print(f"{idx}/{len(punkte)} Punkte verarbeitet...")

# Am Ende alle Einzelresultate aufsummieren:
total_energy_kwh = sum(annual_energies)
print(f"\nGesamter erwarteter Energieertrag entlang der Solarautobahn für das Jahr: {total_energy_kwh:.2f} kWh")
