import os
import pandas as pd
import matplotlib.pyplot as plt

#PV IMPORTS
from merge_teilprojekte_test.functions.functions_weather_data import DWDWeatherConfig, DWDWeatherFetcher
from merge_teilprojekte_test.functions.pv_baukasten import PV_System, PV_TYPEN

#INDUSTRIE IMPORT
from merge_teilprojekte_test.functions.Industriegebiet import IndustryLoadAggregator

#ENERGIELANDSCHAFT IMPORT
from merge_teilprojekte_test.functions.Energielandschaft import main



#WETTERDATEN CSV
USE_EXISTING_WEATHER = True
weather_csv = "./functions/inputs/wetter_daten.csv"

#SOLARAUTOBAHN
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
    base_input = "./functions/inputs"
    geojson_path = os.path.join(base_input, "geometrien", "a44_beide.geojson")
    output_dir = os.path.join(base_input, "punkte")
    os.makedirs(output_dir, exist_ok=True)

    # hier kannst du auch mehrere Typen übergeben, z.B. [PV_TYPEN[0], PV_TYPEN[3], ...]
    #0 = Windschutzwand, 1 = Schallschutzwand, 2 = Schallschutzwand_Dach, 3 = Böschung
    pv_system = PV_System(
        geojson_path=geojson_path,
        pvtypes=[PV_TYPEN[0],PV_TYPEN[3]],
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





#INDUSTRIEGEBIET
if __name__ == "__main__":
    IndustryLoadAggregator().run_interactive()



#ENERGIELANDSCHAFT
if __name__ == "__main__":
	try:
		result = main(interactive=True, output_dir="./outputs")
		if result.get("success"):
			print("✓ Verarbeitung erfolgreich abgeschlossen!")
		else:
			print(f"✗ Verarbeitung abgebrochen: {result.get('error')}")
	except Exception as e:
		print(f"✗ Kritischer Fehler: {e}")
		import traceback
		traceback.print_exc()

