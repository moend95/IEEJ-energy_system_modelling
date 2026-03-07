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
weather_csv = os.path.join(script_dir,"functions", "inputs","wetter_daten_2022_15min.csv")
base_input = os.path.join(script_dir, "functions", "inputs")
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
    if not inp.highways:
        out.h_error_text = "SOLARAUTOBAHN --- Keine Autobahnen/PV ausgewählt."
    elif not inp.h_pv_types:
        out.h_error_text= "SOLARAUTOBAHN --- Keine Autobahn/PV ausgewählt."
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
        print(f'Anzahl Punkte ({highway}): ',out.h_number_of_points )

    #Berechnung
    out.h_sum_energy_kwh = 0
    h_total_sys_ac_kw = None
    for pv_type in h_pv_system.pvtypes if inp.h_pv_types and inp.highways else []:
        # CSV-Name so, wie ihn generate_pv_points gespeichert hat
        csv_name = f"punkte_{pv_type.id}_{pv_type.name}.csv".replace(" ", "_")
        csv_path = os.path.join(output_dir, csv_name)
        df_one = pd.read_csv(csv_path).head(1)
        test_csv = os.path.join(output_dir, "test_single_point.csv")
        df_one.to_csv(test_csv, index=False)

        h_energy_type_kWh, h_total_type_ac_w = h_pv_system.simulate_pv_type_energy(pv_type, csv_path)
        print(f"Energie {pv_type.name}: {h_energy_type_kWh:.1f} kWh"," (Nur berechneten Punkte vor Skalierung über Schrittweite)")

        # Funktion zur Skalierung der Energie und Leistung entsprechend der Schrittweite
        scaled_energy_kwh_pv_type = 0
        scaled_total_type_ac_w = 0
        if h_pv_system.step_size >= pv_type.row_width:
            scaling_factor = h_pv_system.step_size // pv_type.row_width  # Ganzzahldivision -> keine halben Elemente
            print("Scaling Faktor", f"{pv_type.name}", scaling_factor)
            scaled_energy_kwh_pv_type = h_energy_type_kWh * scaling_factor
            scaled_total_type_ac_w = h_total_type_ac_w * scaling_factor
            print(f"Skalierte Energie {pv_type.name}: {scaled_energy_kwh_pv_type:.1f} kWh")
        else:
            print("Skalierte Gesamtenergie wurde nicht berechnet da Schrittweite kleiner als PV-Typ-Modulweite")

        out.h_sum_energy_kwh += scaled_energy_kwh_pv_type
        ac_kw = scaled_total_type_ac_w / 1000

        if h_total_sys_ac_kw is None:
            h_total_sys_ac_kw = ac_kw
        else:
            h_total_sys_ac_kw = h_total_sys_ac_kw.add(ac_kw, fill_value=0)
    out.h_max_power_kw = h_total_sys_ac_kw.max()
    h_total_sys_ac_kw.index_no_year = h_total_sys_ac_kw.index.strftime("%m-%d %H:%M")
    out.res_df["Erzeugung_Solarautobahn [kW]"] = h_total_sys_ac_kw.clip(lower=0).values
    out.res_df["Erzeugung_Solarautobahn [kW]"] = out.res_df["Erzeugung_Solarautobahn [kW]"].fillna(0)

    print('Solarautobahn \t\t- abgeschlossen')


    # ------------------------------------------------------------
    # 2) Energielandschaft
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


        el_selected_pv_type = PV_TYPEN[inp.el_pv_type]

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

        # CSV-Name so, wie ihn generate_pv_points gespeicher hat
        el_csv_name = f"punkte_{el_selected_pv_type.id}_{el_selected_pv_type.name}.csv".replace(" ", "_")
        el_csv_path = os.path.join(output_dir, el_csv_name)
        print(el_csv_path)

        # UNBEDINGT ÜBERPRÜFEN
        el_energy_type_kWh, el_total_type_ac_w = el_pv_system.simulate_pv_type_energy(el_selected_pv_type, el_csv_path)

        modules_per_meter = el_selected_pv_type.modules_per_string * el_selected_pv_type.strings_per_inverter / el_selected_pv_type.row_width
        el_energy_sys_kWh = el_energy_type_kWh * out.el_pv_length * modules_per_meter
        el_total_sys_ac_kw = el_total_type_ac_w * out.el_pv_length * modules_per_meter

        out.el_max_power_kw = el_total_sys_ac_kw.max()
        el_total_sys_ac_kw.index_no_year = el_total_sys_ac_kw.index.strftime("%m-%d %H:%M")
        out.res_df["Erzeugung_Energielandschaft [kW]"] = el_total_sys_ac_kw.clip(lower=0).values
        out.res_df["Erzeugung_Energielandschaft [kW]"] = out.res_df["Erzeugung_Solarautobahn [kW]"].fillna(0)
        out.el_sum_energy_kwh = el_energy_sys_kWh


    else:
        out.el_pv_length = 0

    print('Energielandschaft \t- abgeschlossen')


    # ------------------------------------------------------------
    # 3) Industriegebiet
    # ------------------------------------------------------------
    #df_industrie = pd.DataFrame()
    industry_aggregator = IndustryLoadAggregator()

    if inp.companies is []:
        out.i_error_text = "INDUSTRIEGEBIET --- Kein Unternehmen ausgewählt."
    elif inp.companies:
        out.i_error_text = "Hier könnte ihre Industriegebiet Fehlermeldung stehen!"

        df_industrie, csv_path_industrie, plot_path_industrie = industry_aggregator.run(
            mode_choice=industrie_heating_choice_mapping[inp.is_heat_cooling_electric],
            selection_indices=inp.companies,

        )
        if df_industrie is None or df_industrie.empty:
            out.res_df['Last_Industrie [kW]'] = 0
        else:
            out.res_df['Last_Industrie [kW]'] = df_industrie['Gesamtlast [kW]'] #Alle Lastgänge positiv

        out.i_max_power_kw = out.res_df['Last_Industrie [kW]'].max()
        df_i_energy_kwh_profile = out.res_df['Last_Industrie [kW]'] * 0.25
        out.i_sum_energy_kwh = df_i_energy_kwh_profile.sum()


    print('Industriegebiet \t- abgeschlossen')


    # ------------------------------------------------------------
    # 4) Green Energy Hub
    # ------------------------------------------------------------
    hub_dir = os.path.join(script_dir, "functions", "inputs", "green_energy_hub")

    h2_load_path = os.path.join(hub_dir, inp.h2_load_scenario, "BEV_load_el_15min.csv")
    df_h2_load = pd.read_csv(h2_load_path)
    df_h2_load["timestamp"] = pd.to_datetime(df_h2_load["timestamp"], format="%d-%m %H:%M", errors="coerce")
    df_h2_load.set_index("timestamp", inplace=True)

    el_load_path = os.path.join(hub_dir, inp.e_load_scenario, "Electrolyzer_output.csv")
    df_el_load = pd.read_csv(el_load_path)
    df_el_load["timestamp"] = pd.to_datetime(df_el_load["timestamp"], format="%d-%m %H:%M", errors="coerce")
    df_el_load.set_index("timestamp", inplace=True)

    #Einzeloutputs
    #out.res_df["Last Elektrolyeur Green Energy Hub [kW]"] = df_h2_load["power_kW"].clip(lower=0).values
    #out.res_df["Last E-Ladesäulen Green Energy Hub [kW]"] = df_el_load["power_kW"].clip(lower=0).values

    #Sammeloutpus
    out.res_df["Last Green Energy Hub [kW]"] = df_h2_load["power_kW"].clip(lower=0).values + df_el_load["power_kW"].clip(lower=0).values
    out.geh_max_power_kw = out.res_df["Last Green Energy Hub [kW]"].max()
    df_geh_energy_kwh_profile = out.res_df["Last Green Energy Hub [kW]"] * 0.25
    out.geh_sum_energy_kwh = df_geh_energy_kwh_profile.sum()


    print('Green Energy Hub \t- abgeschlossen')


    # ------------------------------------------------------------
    # 5) Stadtentwicklung Jüchen Süd
    # ------------------------------------------------------------




    # ------------------------------------------------------------
    # 6) Bilanz
    # ------------------------------------------------------------


    print('Bilanzierung \t\t- abgeschlossen')



    # ------------------------------------------------------------
    # 7) Battery
    # ------------------------------------------------------------


    print('Batterie \t\t\t- abgeschlossen')






    print('\nInput Daten:\n',inp)
    print('\nOutput Daten:\n', out)
    return out