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

    sandia_modules = pvlib.pvsystem.retrieve_sam('SandiaMod')
    cec_inverters = pvlib.pvsystem.retrieve_sam('CECInverter')



    # Modul-Zuweisung je nach Typ (genau Modulwahl muss noch erfolgen)
    module_mapping = {
        "aufgesetzt": sandia_modules['Canadian_Solar_CS6X_300M__2013_'],
        "senkrecht": sandia_modules['Canadian_Solar_CS6X_300M__2013_'],
        "bifazial": sandia_modules['LONGi_Green_Energy_Technology_Co___Ltd__LR6_72HBD_370M'],
        "böschung": sandia_modules['Canadian_Solar_Inc__CS6X_300M__2013_']  # Beispiel: klassisches Glas-Glas-Modul
    }

    inverter_mapping = {
        # unterschiedliche Inverter je Typ, nochmal anpassen!:
        # "aufgesetzt": klassische String-Inverter, mittlere Leistung
        "aufgesetzt": cec_inverters['SMA_America__SB5000TL_US__240V_'],
        # "senkrecht": ggf. Mikro- oder kleine String-Inverter bei hoher Segmentierung
        "senkrecht": cec_inverters['ABB__MICRO_0_25_I_OUTD_US_208__208V_'],
        # "bifazial": passende Inverter für beidseitig einspeisende Module wählen
        "bifazial": cec_inverters['Fronius__Symo_10_0_3_M__208_240V_'],
        # "böschung": größere String-Inverter für Freiflächenanlagen (hohe Gesamtleistung)
        "böschung": cec_inverters['ABB__PVI_12_5_OUTD_S__480V_']
    }

    temp_models = {
        # "aufgesetzt": Typische Aufdach- oder aufgeständerte Montage (z.B. auf Masten/Wänden),
        # mit freier Luftzirkulation. Daher geringere Modultemperatur → gutes Modell: "open_rack_glass_glass"
        "aufgesetzt": pvlib.temperature.TEMPERATURE_MODEL_PARAMETERS['sapm']['open_rack_glass_glass'],
        # "senkrecht": Vertikal montierte Module (z.B. an Lärmschutzwänden), meist mit freier Rückseite,
        # daher ebenfalls gute Belüftung → gleiches Modell wie "aufgesetzt"
        "senkrecht": pvlib.temperature.TEMPERATURE_MODEL_PARAMETERS['sapm']['open_rack_glass_glass'],
        # "bifazial": Leichte bifaziale Module, oft mit Polymerrückseite, hängen z.B. in Wind- oder Lärmschutzkassetten.
        # Hier etwas geringere Wärmeabfuhr als bei Glas/Glas → Modell für bifaziale Glas-Polymer-Konstruktionen
        "bifazial": pvlib.temperature.TEMPERATURE_MODEL_PARAMETERS['sapm']['open_rack_glass_polymer'],
        # "böschung": Module flach am Boden oder mit geringer Bodenfreiheit montiert (z.B. Modultische),
        # daher schlechtere Wärmeabfuhr, höhere Zelltemperatur → konservatives Modell mit erhöhter Temperatur
        "böschung": pvlib.temperature.TEMPERATURE_MODEL_PARAMETERS['sapm']['close_mount_glass_glass']
    }

    # Technisch sinnvolle Anzahl Module pro String je nach PV-Typ
    # (z.B. abhängig von Modulspannung, Umgebungstemperatur und Anlagenform)
    modules_per_string_config = {
        "aufgesetzt": 10,  # gut belüftet → meist höhere Strings möglich
        "senkrecht": 8,  # abhängig vom Senkrechtendesign
        "bifazial": 9,  # abhängig vom bifazialen Design
        "böschung": 12  # flache Böschungen → oft mehr Module pro String möglich
    }

    strings_per_inverter_config = {
        "aufgesetzt": 2,
        "senkrecht": 1,
        "bifazial": 2,
        "böschung": 3
    }

    # 4. Simulation starten
    all_results = []

    for idx, row in tqdm(df_points.iterrows(), total=len(df_points), desc="Simuliere PV-Punkte"):
        latitude = row["latitude"]
        longitude = row["longitude"]
        azimut = row["azimut"]
        tilt = row["tilt"]
        typ = row["pv_typ"]

        if pd.isna(azimut) or not isinstance(azimut, (int, float)):
            continue

        location = Location(latitude=latitude, longitude=longitude, tz="Europe/Berlin", altitude=90)

        system = PVSystem(
            surface_tilt=tilt,
            surface_azimuth=azimut,
            module_parameters=module_mapping[typ],
            inverter_parameters=inverter_mapping[typ],
            temperature_model_parameters=temp_models[typ],
            modules_per_string=modules_per_string_config[typ],                               # Wie viele PV-Module werden in Reihe geschaltet (also wie viele in einem String)?
            strings_per_inverter=strings_per_inverter_config[typ]                              # Wie viele solcher Strings (Reihenschaltungen) werden dann parallel an einen Wechselrichter angeschlossen?
        )

        mc = ModelChain(system, location)
        mc.run_model(weather_data)
        results = mc.results.ac

        result_df = pd.DataFrame({
            "datetime": results.index,
            "ac_power": results.values,
            "point_id": idx
        })
        all_results.append(result_df)

    if save_results_to:
        df_time_series = pd.concat(all_results)
        zeitverlauf_path = save_results_to.replace(".csv", "_zeitverlauf.csv")
        df_time_series.to_csv(zeitverlauf_path, index=False)
        print(f" Zeitreihen gespeichert unter: {zeitverlauf_path}")

        # Summierte Erzeugung über alle Punkte pro Zeitstempel
        df_time_series["energy_kwh"] = df_time_series["ac_power"] * (10 / 60) / 1000
        df_sum = df_time_series.groupby("datetime")["energy_kwh"].sum().reset_index()

        plt.figure(figsize=(16, 9))
        plt.plot(df_sum["datetime"], df_sum["energy_kwh"], label="Summierte Erzeugung")
        plt.title("Summierte PV-Erzeugung über das Jahr (alle Punkte)")
        plt.xlabel("Datum")
        plt.ylabel("Erzeugte Energie [kWh]")
        plt.grid(True)
        plt.tight_layout()
        plt.legend()
        plt.show()


# ------------------ Lokale Testausführung ------------------
if __name__ == "__main__":
    simulate_pv_yield(
        weather_csv_path=r"C:\Users\sarah\Documents\GitHub\IEEJ-energy_system_modelling\Input\wetterdaten_solarautobahn_2022.csv",
        points_csv_path=r"C:\Users\sarah\Documents\GitHub\IEEJ-energy_system_modelling\Input\punkte_mit_azimut.csv",
        save_results_to=r"C:\Users\sarah\Documents\GitHub\IEEJ-energy_system_modelling\Input\pv_ertrag_ergebnisse.csv"
    )
