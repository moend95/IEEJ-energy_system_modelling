import os
from pvlib.location import Location
from pvlib.pvsystem import PVSystem
from pvlib.modelchain import ModelChain
import pandas as pd
import matplotlib.pyplot as plt
import geopandas as gpd

from Projekt_01_Solarautobahn.old_skripts.old_pv_baukasten_ohne_bifazialität import PV_System, PV_TYPEN, sandia_modules, cec_inverters, temp_models_sapm
from functions_weather_data import DWDWeatherConfig, DWDWeatherFetcher
import functions_geometrie as fg


if __name__ == "__main__":

    # --- Pfade einstellen ---
    base_input = "./Input"
    geojson_path = os.path.join(base_input, "geometrien", "pv_reihen_sued.geojson")
    # HIER anpassen: nimm die GeoJSON-Datei, die du wirklich testen willst

    output_dir = os.path.join(base_input, "punkte")
    os.makedirs(output_dir, exist_ok=True)

    # --- Wetterdaten holen ---
    cfg = DWDWeatherConfig(
        coords=(51.08579, 6.47554),  # Solarautobahn-Koordinaten
        start="2022-01-01",
        end="2022-12-31",
        station_id=None,
        auto_select=True,
        min_quality=0.95,
        save_path="../Input/wetterdaten_solarautobahn_2022.csv",
        plot_date=None,
        plot_range=None,
    )

    fetcher = DWDWeatherFetcher(cfg)
    weather_df = fetcher.run()   # <— hier heißt es jetzt weather_df

    print("Wetterdaten erfolgreich geladen und gespeichert.")

    # --- PV-System anlegen ---
    pv_system = PV_System(
        geojson_path=geojson_path,
        pvtypes=[PV_TYPEN[0]],  # 0 = ID 1 Windschutzwand, 1 = ID 2 Schallschutzwand, 2 = ID 3 Schallschutzwand_Dach, 3 = ID 4 Böschung, 4 = ID 5 Freifläche_bzw_Agri_geneigt, 5 = ID 6 Agri_vertikal, 6 = ID 7 Haus_Dach
        step_size=200,                        # Punktabstand = Modul Abstand zueinander in Metern
        weather_df=weather_df,
        base_output_dir=output_dir,
    )

    # --- Punkte & Azimut generieren ---
    results = pv_system.generate_pv_points()

    # --- Geometrie der PV Punkte als GEOJASON aus dem GDF extrahieren  ---
    df = results[1]
    gdf_pv_points = gpd.GeoDataFrame(
        df,
        geometry=df["geometry"],
        crs="EPSG:4326"
    )

    # --- Geometrie (Linie) auf der Karte darstellen ---
    gh_linie = fg.GeometryHandler(gdf=gpd.read_file(geojson_path), base_path=base_input)
    gh_linie.plot_geometry_on_map(map_filename="linien_karte.html")

    # --- Geometrie PV Punkte auf der Karte darstellen ---
    gh_punkte = fg.GeometryHandler(gdf=gdf_pv_points, base_path=base_input)
    gh_punkte.plot_geometry_on_map(map_filename="punkte_karte.html")

    # kleine Kontrolle in der Konsole
    print("Berechnete PV-Typen:")
    for pv_type in pv_system.pvtypes:
        print(" -", pv_type)

    print("\nAnzahl Punkte pro Typ:")
    for type_id, gdf_points in results.items():
        print(f"  Typ-ID {type_id}: {len(gdf_points)} Punkte")


    # --- Hilfsfunktion: Jahresenergie für einen PV-Typ berechnen ---
    def simulate_pv_type_energy(pv_type, points_csv_path, weather_df):
        df_points = pd.read_csv(points_csv_path)

        total_ac = None  # hier summieren wir die AC-Leistungen aller Punkte

        for _, row in df_points.iterrows():
            module_params = sandia_modules[pv_type.module]
            inverter_params = cec_inverters[pv_type.inverter]
            temp_params = temp_models_sapm[pv_type.temp_model]

            loc = Location(row["latitude"], row["longitude"], tz="Europe/Berlin")

            system = PVSystem(
                surface_tilt=row["tilt"],
                surface_azimuth=row["azimut"],
                module_parameters=module_params,
                inverter_parameters=inverter_params,
                temperature_model_parameters=temp_params,
                modules_per_string=pv_type.modules_per_string,
                strings_per_inverter=pv_type.strings_per_inverter,
            )

            mc = ModelChain(system, loc)
            mc.run_model(weather_df)
            ac = mc.results.ac  # Zeitreihe in W

            if total_ac is None:
                total_ac = ac
            else:
                total_ac = total_ac + ac

        # Zeitschritt in Stunden (z. B. 0.25 h bei 15-Minuten-Daten)
        dt_hours = (weather_df.index[1] - weather_df.index[0]).total_seconds() / 3600.0

        # Energie in kWh: Summe(Leistung [W] * dt[h]) / 1000
        energy_kwh = (total_ac * dt_hours).sum()

        return energy_kwh, total_ac


    print("\nJahresenergie je PV-Typ:")
    for pv_type in pv_system.pvtypes:
        csv_name = f"punkte_{pv_type.id}_{pv_type.name}.csv".replace(" ", "_")
        csv_path = os.path.join(output_dir, csv_name)

        # HIER: total_ac wirklich entgegennehmen
        energy_kwh, total_ac = simulate_pv_type_energy(pv_type, csv_path, weather_df)
        print(f"  {pv_type.name}: {energy_kwh:.1f} kWh")

        # Jahresplot
        plt.figure(figsize=(15, 5))
        plt.plot(total_ac.index, total_ac.values, linewidth=0.5)
        plt.title(f"Jahresverlauf AC-Leistung – {pv_type.name}")
        plt.xlabel("Datum")
        plt.ylabel("AC-Leistung [W]")
        plt.grid(True)
        plt.tight_layout()
        plt.show()
