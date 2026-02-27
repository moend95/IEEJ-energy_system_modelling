import os
import matplotlib.pyplot as plt
import pandas as pd
from functions_weather_data import DWDWeatherConfig, DWDWeatherFetcher
from pv_baukasten import PV_System, PV_TYPEN, AzimutCalculator, AzimutVisualizer

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

    # ------------------------------------------------------------
    # 2) PV-System anlegen (Geometrie + PV-Typen + Schrittweite)
    # ------------------------------------------------------------
    base_input = "./Input"
    geojson_path = os.path.join(base_input, "geometrien", "a44_beide.geojson")
    output_dir = os.path.join(base_input, "punkte")
    os.makedirs(output_dir, exist_ok=True)

    # PV Typen übergeben, z.B. [PV_TYPEN[0], PV_TYPEN[3], ...]
    pv_system = PV_System(
        geojson_path=geojson_path,
        pvtypes=[PV_TYPEN[1]],   # 0 = Windschutzwand, 1 = Schallschutzwand
        step_size=400,             # Punktabstand in m
        weather_df=weather_df,
        base_output_dir=output_dir,
        debug=True,
    )

    # ------------------------------------------------------------
    # 3) Punkte + Azimut für alle gewählten PV-Typen generieren
    # ------------------------------------------------------------

    results = pv_system.generate_pv_points()
    number_of_points = len(results[pv_system.pvtypes[0].id])

    # ------------------------------------------------------------
    # 3b) Azimut-Plot anzeigen (Visual Debug) - optional
    # ------------------------------------------------------------
    user_input = input(
        "\nWillst du die berechneten Punkte mit Azimut plotten? [j/n]: "
    ).strip().lower()

    plot_azimut = user_input in ["j", "ja", "y", "yes"]
    if plot_azimut:
        print("\n→ Azimut-Visualisierung...")

        for pv_type in pv_system.pvtypes:
            csv_name = f"punkte_{pv_type.id}_{pv_type.name}.csv".replace(" ", "_")
            csv_path = os.path.join(output_dir, csv_name)

            calc = AzimutCalculator(
                geojson_path=geojson_path,
                step_size=pv_system.step_size,
                pv_type=pv_type,
                output_csv_path=csv_path,
            )
            calc.calculate_azimut()

            viz = AzimutVisualizer(calc)

            viz.plot(every_nth_arrow=1)
    else:
        print("→ Azimut-Plot übersprungen")

    print("Berechnete PV-Typen:")
    for pv_type in pv_system.pvtypes:
        print(" -", pv_type)

    # ------------------------------------------------------------
    # 4) Jahresenergie je PV-Typ simulieren + Zeitreihe plotten
    # ------------------------------------------------------------
    energy_kwh_sum = 0
    total_ac_sum = 0
    for pv_type in pv_system.pvtypes:
        # CSV-Name so, wie ihn generate_pv_points gespeicher hat
        csv_name = f"punkte_{pv_type.id}_{pv_type.name}.csv".replace(" ", "_")
        csv_path = os.path.join(output_dir, csv_name)

        df_one = pd.read_csv(csv_path).head(1)
        test_csv = os.path.join(output_dir, "test_single_point.csv")
        df_one.to_csv(test_csv, index=False)

        energy_kwh_pv_type, total_ac_pv_type = pv_system.simulate_pv_type_energy(pv_type, csv_path)
        print(f"Energie {pv_type.name}: {energy_kwh_pv_type:.1f} kWh" , " (Nur berechneten Punkte vor Skalierung über Schrittweite)")

        # Funktion zur Skalierung der Energie und Leistung entsprechend der Schrittweite
        scaled_energy_kwh_pv_type = 0
        if pv_system.step_size >= pv_type.row_width:
            scaling_factor = pv_system.step_size // pv_type.row_width # Ganzzahldivision -> keine halben Elemente
            print("Scaling Faktor", f"{pv_type.name}", scaling_factor)
            scaled_energy_kwh_pv_type = energy_kwh_pv_type * scaling_factor
            print(f"Skalierte Energie {pv_type.name}: {scaled_energy_kwh_pv_type:.1f} kWh")
        else:
            print("Skalierte Gesamtenergie wurde nicht berechnet da Schrittweite kleiner als PV-Typ-Modulweite")

        energy_kwh_sum += scaled_energy_kwh_pv_type
        total_ac_sum += total_ac_pv_type

    print(total_ac_sum.index, total_ac_sum.values)

    # Plot der AC-Leistung über das Jahr
    plt.figure(figsize=(15, 4))
    plt.plot(total_ac_sum.index, total_ac_sum.values, linewidth=0.6)
    plt.title(f"Jahresverlauf AC-Leistung")
    plt.xlabel("Datum")
    plt.ylabel("AC-Leistung [kW]")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()

    # ------------------------------------------------------------
    # Zusatz: Tagesplot für einen Sommertag (z. B. 21. Juni)
    # ------------------------------------------------------------
    summer_day_start = "2022-06-01"
    summer_day_end = "2022-06-07"
    day_ac = total_ac_sum.loc[summer_day_start:summer_day_end].copy()

    # Aufräumen für Plot:
    day_ac = day_ac.dropna()
    day_ac = day_ac.clip(lower=0)  # negative Werte (z.B. -0.1) auf 0 setzen

    # Optional: nur Tagesstunden anzeigen (sieht meist besser aus)
    #day_ac = day_ac.between_time("06:00", "22:00")

    plt.figure(figsize=(10, 4))
    plt.plot(day_ac.index, day_ac.values, linewidth=1.2)
    plt.title(f"Tagesverlauf AC-Leistung – ({summer_day_start}-{summer_day_end})")
    plt.xlabel("Uhrzeit")
    plt.ylabel("AC-Leistung [kW]")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()

    print(f"Gesamtenergie PV-System = {energy_kwh_sum:.1f} kWh ")