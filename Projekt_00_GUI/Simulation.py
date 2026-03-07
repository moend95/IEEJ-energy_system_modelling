import os
import sys
import pandas as pd
#Functions
from core.io_types import GuiInput, SimOutput
from functions.Industriegebiet import IndustryLoadAggregator
from functions.pv_baukasten import PV_System, PV_TYPEN
from functions.Energielandschaft import main


#TYPE MAPPING
highway_geojson_mapping= {"A44": "a44_beide.geojson", "A46": "a46_beide.geojson"}
industrie_heating_choice_mapping = {True: "2", False: "1"}
el_pv_type_number_text_mapping = {4:"horizontal", 5:"vertical", 6:"horizontal_tracking"}
#GLOBAL VARIABLES
script_dir = os.path.dirname(os.path.abspath(__file__))
weather_csv = os.path.join(script_dir,"data","test_solarautobahn.csv")
base_input = "./functions/inputs"
output_dir = os.path.join(base_input, "punkte")
os.makedirs(output_dir, exist_ok=True)  #UNBEDINGT ANPASSEN: Speicherpfad muss der gleiche wie in run_pv_baukasten sein, da in generate pv_points gespeichert wird


def weather_prep():
    weather_df = pd.read_csv(weather_csv, index_col=0, parse_dates=True)
    weather_df.index = pd.to_datetime(weather_df.index, utc=True).tz_convert(None)

    return weather_df

def run_simulation(inp: GuiInput) -> SimOutput:

    out = SimOutput()
    out.h_number_of_points = 0
    out.h_error_text = "Hier könnte ihre Autobahn Fehlermeldung stehen!"
    weather_df = weather_prep()         #Wetterdaten aus csv lesen
    h_selected_pv_types = [PV_TYPEN[i] for i in inp.h_pv_types] if inp.h_pv_types else []
    # ------------------------------------------------------------
    # 1) Solarautobahn
    # ------------------------------------------------------------
    #if not inp.highways:
    #    out.h_error_text = "Keine Autobahnen ausgewählt!"
    #elif not inp.h_pv_types:
    #    out.h_error_text= "Keine PV Typen ausgewählt!"
    #else:   #Fall Autobahn und PV Typ ausgewählt

    for highway in inp.highways if inp.h_pv_types and inp.highways else []:
        selected_file = highway_geojson_mapping[highway]
        geojson_path = os.path.join(script_dir, "geometry", selected_file)

        h_pv_system = PV_System(
            geojson_path=geojson_path,
            pvtypes=h_selected_pv_types,  # 0 = Windschutzwand, 1 = Schallschutzwand
            step_size=800,  # Punktabstand in m
            weather_df=weather_df,
            base_output_dir=output_dir,
        )
        results = h_pv_system.generate_pv_points()
        out.h_number_of_points = len(results[h_pv_system.pvtypes[0].id])

    #Berechnung
    out.h_sum_energy_kwh = 0
    out.total_ac_kw = None
    for pv_type in h_pv_system.pvtypes if inp.h_pv_types and inp.highways else []:
        # CSV-Name so, wie ihn generate_pv_points gespeichert hat
        csv_name = f"punkte_{pv_type.id}_{pv_type.name}.csv".replace(" ", "_")
        csv_path = os.path.join(output_dir, csv_name)
        df_one = pd.read_csv(csv_path).head(1)
        test_csv = os.path.join(output_dir, "test_single_point.csv")
        df_one.to_csv(test_csv, index=False)

        energy_kwh_pv_type, total_ac_pv_type = h_pv_system.simulate_pv_type_energy(pv_type, csv_path)
        print(f"Energie {pv_type.name}: {energy_kwh_pv_type:.1f} kWh",
              " (Nur berechneten Punkte vor Skalierung über Schrittweite)")

        # Funktion zur Skalierung der Energie und Leistung entsprechend der Schrittweite
        scaled_energy_kwh_pv_type = 0
        if h_pv_system.step_size >= pv_type.row_width:
            scaling_factor = h_pv_system.step_size // pv_type.row_width  # Ganzzahldivision -> keine halben Elemente
            print("Scaling Faktor", f"{pv_type.name}", scaling_factor)
            scaled_energy_kwh_pv_type = energy_kwh_pv_type * scaling_factor
            print(f"Skalierte Energie {pv_type.name}: {scaled_energy_kwh_pv_type:.1f} kWh")
        else:
            print("Skalierte Gesamtenergie wurde nicht berechnet da Schrittweite kleiner als PV-Typ-Modulweite")

        out.h_sum_energy_kwh += scaled_energy_kwh_pv_type
        out.total_ac_kw = total_ac_pv_type / 1000 if out.total_ac_kw is None else out.total_ac_kw + (total_ac_pv_type / 1000)
        out.res_df["Erzeugung_Solarautobahn [kW]"] = out.total_ac_kw.clip(lower=0).values
        out.res_df["Erzeugung_Solarautobahn [kW]"] = out.res_df["Erzeugung_Solarautobahn [kW]"].fillna(0)

    # ------------------------------------------------------------
    # 2) Industriegebiet
    # ------------------------------------------------------------
    df_industrie = pd.DataFrame()
    industry_aggregator = IndustryLoadAggregator()

    if inp.companies is None:
        out.i_error_text = "Ungültige Auswahl für Industriegebiet. Skript wird beendet."
    elif inp.companies:
        out.i_error_text = "Hier könnte ihre Industriegebiet Fehlermeldung stehen!"

        df_industrie, csv_path_industrie, plot_path_industrie = industry_aggregator.run(
            mode_choice=industrie_heating_choice_mapping[inp.is_heat_cooling_electric],
            selection_indices=inp.companies,

        )
        if df_industrie is None or df_industrie.empty:
            out.res_df['Last_Industrie [kW]'] = 0
        else:
            out.res_df['Last_Industrie [kW]'] = 0 - df_industrie['Gesamtlast [kW]']

    # ------------------------------------------------------------
    # 3) Energielandschaft
    # ------------------------------------------------------------

    # agri PV code für geojson und agri pv länge
    if inp.el_pv_type:
        agri_result = main(
            interactive=False,
            output_dir="./outputs",
            pv_ausrichtung=el_pv_type_number_text_mapping[inp.el_pv_type],
            tractor_width_m=inp.tractor_width,
            tractor_length_m=inp.tractor_length,
            tractor_turn_radius_m=inp.tractor_turn_radius,
        )
        out.el_pv_length = agri_result.get("metadata").get('total_rows_length_m')


        el_selected_pv_type = [PV_TYPEN[inp.el_pv_type]]

        # INPUT für PV Baukasten - ENERGIELANDSCHAFT
        geojson_file_2 = "Agri_PV_Centroid.geojson"
        geojson_path_2 = os.path.join(base_input, "geometrien", geojson_file_2)
        step_size_default = 1000

        el_pv_system = PV_System(
            geojson_path=geojson_path_2,
            pvtypes=el_selected_pv_type,  # [PV_TYPEN[0],PV_TYPEN[3]],
            step_size=step_size_default,  # Punktabstand in m
            weather_df=weather_df,
            base_output_dir=output_dir,
        )
    else:
        out.el_pv_length = 0
    # ------------------------------------------------------------
    # 4) Green Energy Hub
    # ------------------------------------------------------------




    # ------------------------------------------------------------
    # 5) Bilanz
    # ------------------------------------------------------------




    # ------------------------------------------------------------
    # 6) Battery
    # ------------------------------------------------------------



    print(inp)
    print(out.res_df)
    return out