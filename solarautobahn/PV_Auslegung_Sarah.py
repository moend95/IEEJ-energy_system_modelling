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

# Wetterdaten über "Wetterdienst" importieren, hierfür muss "wetterdienst" mit "pip install wetterdienst" installiert werden
from wetterdienst import DwdObservationRequest, Resolution, Period, Parameter
import pandas as pd

# DWD-Request vorbereiten
request = DwdObservationRequest(
    parameter=[
        Parameter.SOLAR.GLOBAL,           # Globalstrahlung (W/m²)
        Parameter.SOLAR.DIRECT_NORMAL,    # Direktstrahlung
        Parameter.SOLAR.DIFFUSE,          # Diffusstrahlung
        Parameter.CLIMATE.TEMPERATURE_AIR_200,
        Parameter.WIND.WIND_SPEED
    ],
    resolution=Resolution.MINUTE_10,
    period=Period.HISTORICAL
)

# Stationsauswahl (nach Name oder ID, hier mit Name)
stations = request.filter_by_name("Koeln")
values = stations.values.all().df

# Index setzen
values["date"] = pd.to_datetime(values["date"])
values.set_index("date", inplace=True)

# Optional: Nach Jahr 2022 filtern
weather_data = values.loc["2022-01-01 00:00:00":"2022-12-31 23:50:00"]

# Breite aufbereitete Strukturierung notwendig, ggf. Umbenennung und Aufbereitung der Spalten:
weather_data = weather_data.pivot(columns="parameter", values="value")
weather_data.columns.name = None

# Spaltennamen für Wetterdaten
weather_data.rename(columns={
    "solar_global": "ghi",
    "solar_direct_normal": "dni",
    "solar_diffuse": "dhi",
    "temperature_air_200": "temp_air",
    "wind_speed": "wind_speed"
}, inplace=True)

# Wetterdaten importieren (BACKUP)
#base_dir = os.path.dirname(os.path.abspath(__file__))
#weather_data_path = os.path.join(base_dir, '..', 'Input', 'dwd_data_solar_10min_koeln_2020-2023.csv')
#weather_data = pd.read_csv(weather_data_path, index_col='datetime', parse_dates=True)
#weather_data = weather_data.loc["2022-01-01 00:00:00":"2022-12-31 23:50:00"]

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
