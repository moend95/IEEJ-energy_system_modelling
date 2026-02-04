import os
import matplotlib.pyplot as plt
import pandas as pd

from functions_weather_data import DWDWeatherConfig, DWDWeatherFetcher
from pv_baukasten import PV_System, PV_TYPEN

# Ausgabe Punkte die man auf der linienbasierten Karte sehen kann

USE_EXISTING_WEATHER = True
weather_csv = "./Input/test_solarautobahn.csv"




if __name__ == "__main__":
    # ------------------------------------------------------------
    # 1) Wetterdaten laden (CSV ODER DWD)
    # ------------------------------------------------------------
    if USE_EXISTING_WEATHER:
        print("→ Verwende vorhandene Wetterdaten-CSV")
        weather_df = pd.read_csv(weather_csv, index_col=0, parse_dates=True)
        weather_df.index = pd.to_datetime(weather_df.index, utc=True).tz_convert(None)
    else:
        print("→ Hole Wetterdaten neu vom DWD")
        cfg = DWDWeatherConfig(
            coords=(51.08579, 6.47554),
            start="2022-01-01",
            end="2022-12-31",
            station_id=None,
            auto_select=False,
            min_quality=0.95,
            save_path=weather_csv,
        )
        weather_df = DWDWeatherFetcher(cfg).run()

# if __name__ == "__main__":
#     # ------------------------------------------------------------
#     # 1) Wetterdaten vom DWD holen
#     # ------------------------------------------------------------
#     cfg = DWDWeatherConfig(
#         coords=(51.08579, 6.47554),
#         start="2022-01-01",
#         end="2022-12-31",
#         station_id=None,
#         auto_select=False,
#         min_quality=0.95,
#         save_path="./Input/wetterdaten_solarautobahn_2022.csv",
#     )
#     weather_df = DWDWeatherFetcher(cfg).run()

    # ------------------------------------------------------------
    # 2) PV-System anlegen (Geometrie + PV-Typen + Schrittweite)
    # ------------------------------------------------------------
    base_input = "./Input"
    geojson_path = os.path.join(base_input, "geometrien", "P_02_Agri_PV_Breite25.0_Laenge3.0_Wenderadius4.0_Vertikal_Centroid.geojson")
    output_dir = os.path.join(base_input, "punkte")
    os.makedirs(output_dir, exist_ok=True)

    # hier kannst du auch mehrere Typen übergeben, z.B. [PV_TYPEN[0], PV_TYPEN[3], ...]
    pv_system = PV_System(
        geojson_path=geojson_path,
        pvtypes=[PV_TYPEN[0]],   # 0 = Windschutzwand
        step_size=50,             # Punktabstand in m
        weather_df=weather_df,
        base_output_dir=output_dir,
    )

    # ------------------------------------------------------------
    # 3) Punkte + Azimut für alle gewählten PV-Typen generieren
    # ------------------------------------------------------------
    results = pv_system.generate_pv_points()

    print("Berechnete PV-Typen:")
    for pv_type in pv_system.pvtypes:
        print(" -", pv_type)

    # ------------------------------------------------------------
    # 4) Jahresenergie je PV-Typ simulieren + Zeitreihe plotten
    # ------------------------------------------------------------
    print("\nJahresenergie je PV-Typ:")
    for pv_type in pv_system.pvtypes:
        # CSV-Name so, wie ihn generate_pv_points gespeicher hat
        csv_name = f"punkte_{pv_type.id}_{pv_type.name}.csv".replace(" ", "_")
        csv_path = os.path.join(output_dir, csv_name)

        energy_kwh, total_ac = pv_system.simulate_pv_type_energy(pv_type, csv_path)
        print(f"  {pv_type.name}: {energy_kwh:.1f} kWh")

        # Plot der AC-Leistung über das Jahr
        plt.figure(figsize=(15, 4))
        plt.plot(total_ac.index, total_ac.values, linewidth=0.6)
        plt.title(f"Jahresverlauf AC-Leistung – {pv_type.name}")
        plt.xlabel("Datum")
        plt.ylabel("AC-Leistung [W]")
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.show()

        # ------------------------------------------------------------
        # Zusatz: Tagesplot für einen Sommertag (z. B. 21. Juni)
        # ------------------------------------------------------------
        summer_day_start = "2022-06-21"
        summer_day_end = "2022-06-24"
        day_ac = total_ac.loc[summer_day_start:summer_day_end].copy()

        # Aufräumen für Plot:
        day_ac = day_ac.dropna()
        day_ac = day_ac.clip(lower=0)  # negative Werte (z.B. -0.1) auf 0 setzen

        # Optional: nur Tagesstunden anzeigen (sieht meist besser aus)
        #day_ac = day_ac.between_time("06:00", "22:00")

        plt.figure(figsize=(10, 4))
        plt.plot(day_ac.index, day_ac.values, linewidth=1.2)
        plt.title(f"Tagesverlauf AC-Leistung – {pv_type.name} ({summer_day_start}-{summer_day_end})")
        plt.xlabel("Uhrzeit")
        plt.ylabel("AC-Leistung [W]")
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.show()
