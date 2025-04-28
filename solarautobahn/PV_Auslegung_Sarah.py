import pandas as pd
import pvlib
from pvlib.pvsystem import PVSystem
from pvlib.location import Location
from pvlib.modelchain import ModelChain
from shapely.geometry import LineString
import matplotlib.pyplot as plt
import os
import math
from tqdm import tqdm


# Wetterdaten importieren
base_dir = os.path.dirname(os.path.abspath(__file__))
weather_data_path = os.path.join(base_dir, '..', 'Input', 'dwd_data_solar_10min_koeln_2020-2023.csv')
weather_data = pd.read_csv(weather_data_path, index_col='datetime', parse_dates=True)
weather_data = weather_data.loc["2022-01-01 00:00:00":"2022-12-31 23:50:00"]

# PV-Modul- und Inverter-Daten laden
temperature_model_parameters = pvlib.temperature.TEMPERATURE_MODEL_PARAMETERS['sapm']['open_rack_glass_glass']
sandia_modules = pvlib.pvsystem.retrieve_sam('cecmod')
cec_inverters = pvlib.pvsystem.retrieve_sam('cecinverter')

sandia_module = sandia_modules['Jinko_Solar__Co___Ltd_JKM400M_72L']
cec_inverter = cec_inverters['ABB__UNO_2_0_I_OUTD_S_US__277V_']

# Punkte und Ausrichtungen laden
# Reihenfolge (Latitude (Breitengrad), Longitude (Längengrad), Ausrichtung (Azimut)
# Punkte und Ausrichtungen aus CSV laden
punkte_df = pd.read_csv(os.path.join(base_dir, '..', 'Input', 'punkte_mit_azimut.csv'))
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
        modules_per_string=5,
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
print(f"\nGesamterwarteter Energieertrag entlang der Solarautobahn: {total_energy_kwh:.2f} kWh")
