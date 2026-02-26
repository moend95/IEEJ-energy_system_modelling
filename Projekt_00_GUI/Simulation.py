from core.io_types import GuiInput, SimOutput
import os
from Projekt_01_Solarautobahn.pv_baukasten import PV_System, PV_TYPEN
import pandas as pd

#GLOBAL VARIABLES
highway_geojson_mapping= {"A44": "a44_beide.geojson", "A46": "a46_beide.geojson"}
script_dir = os.path.dirname(os.path.abspath(__file__))
weather_csv = os.path.join(script_dir,"data","test_solarautobahn.csv")
output_dir = os.path.join("./Input", "punkte")
os.makedirs(output_dir, exist_ok=True)  #UNBEDINGT ANPASSEN: Speicherpfad muss der gleiche wie in run_pv_baukasten sein, da in generate pv_points gespeichert wird


def weather_prep():
    weather_df = pd.read_csv(weather_csv, index_col=0, parse_dates=True)
    weather_df.index = pd.to_datetime(weather_df.index, utc=True).tz_convert(None)

    return weather_df

def run_simulation(inp: GuiInput) -> SimOutput:

    out = SimOutput()
    out.h_number_of_points = 0
    out.error_text = "Hier könnte ihre Fehlermeldung stehen!"
    weather_df = weather_prep()         #Wetterdaten aus csv lesen
    selected_pv_types = [PV_TYPEN[i] for i in inp.h_pv_types]

    print(f"inp.highways is: {inp.highways}")
    if not inp.highways:
        out.error_text = "Keine Autobahnen ausgewählt!"
    elif not inp.h_pv_types:
        out.error_text = "Keine PV Typen ausgewählt!"
    else:   #Fall Autobahn und PV Typ ausgewählt

        for highway in inp.highways:
            selected_file = highway_geojson_mapping[highway]
            geojson_path = os.path.join(script_dir, "geometry", selected_file)

            pv_system = PV_System(
                geojson_path=geojson_path,
                pvtypes=selected_pv_types,  # 0 = Windschutzwand, 1 = Schallschutzwand
                step_size=800,  # Punktabstand in m
                weather_df=weather_df,
                base_output_dir=output_dir,
                debug=True,
            )

            results = pv_system.generate_pv_points()
            out.h_number_of_points = len(results[pv_system.pvtypes[0].id])

        #Berechnung
        out.sum_energy_kwh = 0
        out.total_ac_kw = 0
        for pv_type in pv_system.pvtypes:
            # CSV-Name so, wie ihn generate_pv_points gespeichert hat
            csv_name = f"punkte_{pv_type.id}_{pv_type.name}.csv".replace(" ", "_")
            csv_path = os.path.join(output_dir, csv_name)

            df_one = pd.read_csv(csv_path).head(1)
            test_csv = os.path.join(output_dir, "test_single_point.csv")
            df_one.to_csv(test_csv, index=False)

            energy_kwh_pv_type, total_ac_pv_type = pv_system.simulate_pv_type_energy(pv_type, csv_path)
            print(f"Energie {pv_type.name}: {energy_kwh_pv_type:.1f} kWh",
                  " (Nur berechneten Punkte vor Skalierung über Schrittweite)")

            # Funktion zur Skalierung der Energie und Leistung entsprechend der Schrittweite
            scaled_energy_kwh_pv_type = 0
            if pv_system.step_size >= pv_type.row_width:
                scaling_factor = pv_system.step_size // pv_type.row_width  # Ganzzahldivision -> keine halben Elemente
                print("Scaling Faktor", f"{pv_type.name}", scaling_factor)
                scaled_energy_kwh_pv_type = energy_kwh_pv_type * scaling_factor
                print(f"Skalierte Energie {pv_type.name}: {scaled_energy_kwh_pv_type:.1f} kWh")
            else:
                print("Skalierte Gesamtenergie wurde nicht berechnet da Schrittweite kleiner als PV-Typ-Modulweite")

            out.sum_energy_kwh += scaled_energy_kwh_pv_type
            out.total_ac_kw += total_ac_pv_type

    return out