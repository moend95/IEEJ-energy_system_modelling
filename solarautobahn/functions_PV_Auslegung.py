# functions_pv_simulation.py

import pandas as pd
from pvlib.location import Location
from pvlib.pvsystem import PVSystem
from pvlib.modelchain import ModelChain
import pvlib
from tqdm import tqdm
import matplotlib.pyplot as plt
import geopandas as gpd
from shapely.geometry import Point


def simulate_pv_yield(weather_csv_path, points_csv_path, save_results_to=None):
    # 1. Wetterdaten laden
    df_weather = pd.read_csv(weather_csv_path)
    df_weather["date"] = pd.to_datetime(df_weather["date"], utc=True)
    df_weather["date"] = df_weather["date"].dt.tz_localize(None)
    df_weather.set_index("date", inplace=True)
    df_weather.index.name = "datetime"
    weather_data = df_weather

    # 2. Punkte mit Azimut, Tilt und PV-Typ laden
    df_points = pd.read_csv(points_csv_path)

    # 3. PV-Komponenten vorbereiten
    temperature_model_parameters = pvlib.temperature.TEMPERATURE_MODEL_PARAMETERS['sapm']['open_rack_glass_glass']
    sandia_modules = pvlib.pvsystem.retrieve_sam('cecmod')
    cec_inverters = pvlib.pvsystem.retrieve_sam('cecinverter')

    # Modul-Zuweisung je nach Typ
    module_mapping = {
        "dach": sandia_modules['Jinko_Solar__Co___Ltd_JKM400M_72L'],
        "senkrecht": sandia_modules['Jinko_Solar__Co___Ltd_JKM400M_72L'],
        "bifazial": sandia_modules['LONGi_Green_Energy_Technology_Co___Ltd__LR6_72HBD_370M']
    }
    inverter = cec_inverters['ABB__UNO_2_0_I_OUTD_S_US__277V_']

    # 4. Simulation starten
    energies = []

    for idx, row in tqdm(df_points.iterrows(), total=len(df_points), desc="Simuliere PV-Punkte"):
        latitude = row["latitude"]
        longitude = row["longitude"]
        azimut = row["azimut"]
        tilt = row["tilt"]
        typ = row["pv_typ"]

        if pd.isna(azimut) or not isinstance(azimut, (int, float)):
            continue

        location = Location(latitude=latitude, longitude=longitude, tz="Europe/Berlin", altitude=80)

        system = PVSystem(
            surface_tilt=tilt,
            surface_azimuth=azimut,
            module_parameters=module_mapping[typ],
            inverter_parameters=inverter,
            temperature_model_parameters=temperature_model_parameters,
            modules_per_string=4,
            strings_per_inverter=1
        )

        mc = ModelChain(system, location, aoi_model='physical', spectral_model='no_loss', temperature_model='sapm')
        mc.run_model(weather_data)
        results = mc.results.ac

        annual_energy_kwh = (results.sum() * (10 / 60)) / 1000
        energies.append(annual_energy_kwh)

    total_energy = sum(energies)
    print(f"\n Gesamter erwarteter Energieertrag: {total_energy:.2f} kWh")

    if save_results_to:
        df_points["annual_energy_kwh"] = energies + [None] * (len(df_points) - len(energies))
        df_points.to_csv(save_results_to, index=False)
        print(f" Ergebnisse gespeichert unter: {save_results_to}")

        # Visualisierung hinzufügen
        df_ertrag.plot(y="energy_kwh", x="datetime")
        plt.title("PV-Ertrag über das Jahr")
        plt.ylabel("Energieertrag [kWh]")
        plt.xlabel("Datum")
        plt.grid(True)
        plt.show()


# ------------------ Lokale Testausführung ------------------
if __name__ == "__main__":
    simulate_pv_yield(
        weather_csv_path=r"C:\Users\sarah\Documents\GitHub\IEEJ-energy_system_modelling\Input\wetterdaten_solarautobahn_2022.csv",
        points_csv_path=r"C:\Users\sarah\Documents\GitHub\IEEJ-energy_system_modelling\Input\punkte_mit_azimut.csv",
        save_results_to=r"C:\Users\sarah\Documents\GitHub\IEEJ-energy_system_modelling\Input\pv_ertrag_ergebnisse.csv"
    )
