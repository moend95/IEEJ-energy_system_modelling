import os
import sys

import numpy as np
import pandas as pd

#Functions
from core.io_types import GuiInput, SimOutput
from functions.Industriegebiet import IndustryLoadAggregator
from functions.pv_baukasten import PV_System, PV_TYPEN
from functions.Energielandschaft import main
from functions.battery_storage_eff import BatteryStorage


#TYPE MAPPING
highway_geojson_mapping= {"A44": "a44_beide.geojson", "A46": "a46_beide.geojson"}
industrie_heating_choice_mapping = {True: "2", False: "1"}
el_pv_type_number_text_mapping = {4:"horizontal_tracking", 5:"vertical", 6:"horizontal"}
#GLOBAL VARIABLES
script_dir = os.path.dirname(os.path.abspath(__file__))
weather_csv = os.path.join(script_dir,"functions", "inputs","wetter_daten_2021_15min.csv")
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
    h_selected_pv_types =  [PV_TYPEN[i] for i in inp.h_pv_types] if inp.h_pv_types else []#[next(pv for pv in PV_TYPEN if pv.id == i) for i in inp.h_pv_types] if inp.h_pv_types else []

    # ------------------------------------------------------------
    # 1) Solarautobahn
    # ------------------------------------------------------------
    out.h_sum_energy_kwh = 0
    out.h_number_of_points = 0
    all_ac_series = []

    if not inp.h_highways:
        out.h_error_text = "SOLARAUTOBAHN --- Keine Autobahnen ausgewählt."
    elif not inp.h_pv_types:
        out.h_error_text = "SOLARAUTOBAHN --- Keine PV-Typen ausgewählt."
    else:
        out.h_error_text = ""

        for highway in inp.h_highways:
            selected_file = highway_geojson_mapping[highway]
            geojson_path = os.path.join(script_dir, "geometry", selected_file)

            h_pv_system = PV_System(
                geojson_path=geojson_path,
                pvtypes=h_selected_pv_types,
                step_size=800,
                weather_df=weather_df,
                base_output_dir=output_dir,
            )

            results = h_pv_system.generate_pv_points()

            # Punkte aller PV-Typen dieser Autobahn aufsummieren
            for pv_type in h_pv_system.pvtypes:
                if pv_type.id in results:
                    out.h_number_of_points += len(results[pv_type.id])

            # Energie je PV-Typ berechnen und aufaddieren
            for pv_type in h_pv_system.pvtypes:
                geo_name = os.path.splitext(os.path.basename(geojson_path))[0]
                csv_name = f"{geo_name}_punkte_{pv_type.id}_{pv_type.name}.csv".replace(" ", "_")
                csv_path = os.path.join(output_dir, csv_name)

                if not os.path.exists(csv_path):
                    print(f"Datei nicht gefunden: {csv_path}")
                    continue

                energy_type_kWh, total_type_ac_w = h_pv_system.simulate_pv_type_energy(pv_type, csv_path)
                #print(f"Energie {highway} | {pv_type.name}: {energy_type_kWh:.1f} kWh (nur berechnete Punkte vor Skalierung)")

                scaled_energy_kwh_pv_type = 0
                scaled_total_type_ac_w = 0

                if h_pv_system.step_size >= pv_type.row_width:
                    scaling_factor = h_pv_system.step_size // pv_type.row_width
                    #print(f"Scaling Faktor {highway} | {pv_type.name}: {scaling_factor}")

                    scaled_energy_kwh_pv_type = energy_type_kWh * scaling_factor
                    scaled_total_type_ac_w = total_type_ac_w * scaling_factor

                    #print(f"Skalierte Energie {highway} | {pv_type.name}: {scaled_energy_kwh_pv_type:.1f} kWh")
                else:
                    print(f"Keine Skalierung für {highway} | {pv_type.name}, da Schrittweite kleiner als Modulbreite")

                out.h_sum_energy_kwh += scaled_energy_kwh_pv_type

                ac_kw = scaled_total_type_ac_w / 1000
                all_ac_series.append(ac_kw)

        # Alle Zeitreihen addieren
        if all_ac_series:
            total_sys_ac_kw = all_ac_series[0].copy()
            for s in all_ac_series[1:]:
                total_sys_ac_kw = total_sys_ac_kw.add(s, fill_value=0)

            out.res_df["Erzeugung_Solarautobahn [kW]"] = total_sys_ac_kw.clip(lower=0).values

            out.res_df["Erzeugung_Solarautobahn [kW]"] = out.res_df["Erzeugung_Solarautobahn [kW]"].fillna(0)
        else:
            out.res_df["Erzeugung_Solarautobahn [kW]"] = 0
        out.h_max_power_kw = out.res_df["Erzeugung_Solarautobahn [kW]"].max()

    print('Solarautobahn \t\t- abgeschlossen')


    # ------------------------------------------------------------
    # 2) Energielandschaft
    # ------------------------------------------------------------

    # agri PV code für geojson und agri pv länge
    if inp.el_pv_type is not None:
        agri_result = main(
            interactive=False,
            output_dir="./outputs",
            pv_ausrichtung=el_pv_type_number_text_mapping[inp.el_pv_type],
            tractor_width_m=inp.el_tractor_width,
            tractor_length_m=inp.el_tractor_length,
            tractor_turn_radius_m=inp.el_tractor_turn_radius,
        )
        out.el_pv_length = agri_result.get("metadata").get('total_rows_length_m')


        el_selected_pv_type = PV_TYPEN[inp.el_pv_type]

        # INPUT für PV Baukasten - ENERGIELANDSCHAFT
        geojson_file_2 = "Agri_PV_Centroid.geojson"
        geojson_path_2 = os.path.join(base_input, "geometrien", geojson_file_2)
        step_size_default = 1000

        el_pv_system = PV_System(
            geojson_path=geojson_path_2,
            pvtypes=[el_selected_pv_type],  # [PV_TYPEN[0],PV_TYPEN[3]],
            step_size=step_size_default,  # Punktabstand in m
            weather_df=weather_df,
            base_output_dir=output_dir,
        )

        # CSV-Name so, wie ihn generate_pv_points gespeicher hat
        el_csv_name = f"punkte_{el_selected_pv_type.id}_{el_selected_pv_type.name}.csv".replace(" ", "_")
        el_csv_path = os.path.join(output_dir, el_csv_name)
        #print(el_csv_path)

        # UNBEDINGT ÜBERPRÜFEN
        el_energy_type_kWh, el_total_type_ac_w = el_pv_system.simulate_pv_type_energy(el_selected_pv_type, el_csv_path)

        el_energy_sys_kWh = el_energy_type_kWh * out.el_pv_length  * (inp.el_build_state/100)
        el_total_sys_ac_kw = el_total_type_ac_w * out.el_pv_length  * (inp.el_build_state/100) /1000

        out.el_max_power_kw = el_total_sys_ac_kw.max()
        el_total_sys_ac_kw.index_no_year = el_total_sys_ac_kw.index.strftime("%m-%d %H:%M")
        out.res_df["Erzeugung_Energielandschaft [kW]"] = el_total_sys_ac_kw.clip(lower=0).values
        out.res_df["Erzeugung_Energielandschaft [kW]"] = out.res_df["Erzeugung_Energielandschaft [kW]"].fillna(0)
        out.el_sum_energy_kwh = el_energy_sys_kWh


    else:
        out.el_pv_length = 0

    print('Energielandschaft \t- abgeschlossen')


    # ------------------------------------------------------------
    # 3) Industriegebiet
    # ------------------------------------------------------------
    #df_industrie = pd.DataFrame()
    industry_aggregator = IndustryLoadAggregator()

    if inp.i_companies is []:
        out.i_error_text = "INDUSTRIEGEBIET --- Kein Unternehmen ausgewählt."
    elif inp.i_companies:
        out.i_error_text = "Hier könnte ihre Industriegebiet Fehlermeldung stehen!"

        df_industrie, csv_path_industrie, plot_path_industrie = industry_aggregator.run(
            mode_choice=industrie_heating_choice_mapping[inp.i_heat_cooling_electric],
            selection_indices=inp.i_companies,

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

    # Default: nichts aktiv -> Nullprofil
    out.res_df["Last_Green_Energy_Hub [kW]"] = 0.0
    out.geh_max_power_kw = 0.0
    out.geh_sum_energy_kwh = 0.0

    if inp.geh_h2_load_scenario not in [None, "Keine"] or inp.geh_e_load_scenario not in [None, "Keine"]:
        geh_series = pd.Series(0.0, index=out.res_df.index)

        # H2-Last separat laden, falls gewählt
        if inp.geh_h2_load_scenario not in [None, "Keine"]:
            h2_load_path = os.path.join(hub_dir, inp.geh_h2_load_scenario, "Electrolyzer_output.csv")
            df_h2_load = pd.read_csv(h2_load_path)
            df_h2_load["timestamp"] = pd.to_datetime(
                df_h2_load["timestamp"],
                format="%d-%m %H:%M",
                errors="coerce"
            )
            df_h2_load.set_index("timestamp", inplace=True)

            h2_series = df_h2_load["power_kW"].clip(lower=0).reset_index(drop=True)
            h2_series.index = out.res_df.index[:len(h2_series)]
            geh_series = geh_series.add(h2_series.reindex(out.res_df.index, fill_value=0.0), fill_value=0.0)

        # Elektro-Last separat laden, falls gewählt
        if inp.geh_e_load_scenario not in [None, "Keine"]:
            el_load_path = os.path.join(hub_dir, inp.geh_e_load_scenario, "BEV_load_el_15min.csv")
            df_el_load = pd.read_csv(el_load_path)
            df_el_load["timestamp"] = pd.to_datetime(
                df_el_load["timestamp"],
                format="%d-%m %H:%M",
                errors="coerce"
            )
            df_el_load.set_index("timestamp", inplace=True)

            el_series = df_el_load["power_kW"].clip(lower=0).reset_index(drop=True)
            el_series.index = out.res_df.index[:len(el_series)]
            geh_series = geh_series.add(el_series.reindex(out.res_df.index, fill_value=0.0), fill_value=0.0)

        out.res_df["Last_Green_Energy_Hub [kW]"] = geh_series
        out.geh_max_power_kw = out.res_df["Last_Green_Energy_Hub [kW]"].max()
        out.geh_sum_energy_kwh = (out.res_df["Last_Green_Energy_Hub [kW]"] * 0.25).sum()

    print('Green Energy Hub \t- abgeschlossen')

    # ------------------------------------------------------------
    # 5) Stadtentwicklung Jüchen Süd
    # ------------------------------------------------------------
    out.res_df["Last_Juechen_Sued [kW]"] = 0.0
    out.js_max_power_kw = 0.0
    out.js_sum_energy_kwh = 0.0
    out.js_error_text = ""

    js_scale_map = {
        "Aus": 0,
        "1000 Bewohner": 1,
        "2000 Bewohner": 2,
        "3000 Bewohner": 3,
    }

    js_factor = js_scale_map.get(inp.js_scenario, 0)

    if js_factor > 0:
        js_path = os.path.join(
            script_dir,
            "functions",
            "inputs",
            "Strombezug_Stadtentwicklung_15min.csv"
        )

        if os.path.exists(js_path):
            try:
                df_js = pd.read_csv(js_path, sep=",")
                df_js.columns = df_js.columns.str.strip()

                if "Timestamp" not in df_js.columns or "Strombezug (kW)" not in df_js.columns:
                    raise ValueError(
                        f"Unerwartete Spalten in Jüchen-Süd-Datei: {list(df_js.columns)}"
                    )

                df_js["timestamp"] = pd.to_datetime(
                    "2022 " + df_js["Timestamp"].astype(str).str.strip(),
                    format="%Y %d.%m. %H:%M",
                    errors="coerce"
                )

                df_js["Strombezug (kW)"] = pd.to_numeric(
                    df_js["Strombezug (kW)"].astype(str).str.replace(",", ".", regex=False),
                    errors="coerce"
                ).fillna(0)

                df_js = df_js.set_index("timestamp").sort_index()

                js_series = df_js["Strombezug (kW)"].clip(lower=0) * js_factor

                if len(js_series) == len(out.res_df.index):
                    js_series = pd.Series(js_series.to_numpy(), index=out.res_df.index)
                else:
                    js_series = js_series.reset_index(drop=True)
                    js_series.index = out.res_df.index[:len(js_series)]
                    js_series = js_series.reindex(out.res_df.index, fill_value=0.0)

                out.res_df["Last_Juechen_Sued [kW]"] = js_series
                out.js_max_power_kw = out.res_df["Last_Juechen_Sued [kW]"].max()
                out.js_sum_energy_kwh = (out.res_df["Last_Juechen_Sued [kW]"] * 0.25).sum()

            except Exception as e:
                out.js_error_text = f"JÜCHEN SÜD --- Fehler beim Laden: {e}"
        else:
            out.js_error_text = f"JÜCHEN SÜD --- Datei nicht gefunden: {js_path}"



    # ------------------------------------------------------------
    # 6) Bilanz
    # ------------------------------------------------------------

    sign_map = {
        "Erzeugung_Solarautobahn [kW]": 1,
        "Erzeugung_Energielandschaft [kW]": 1,
        "Last_Industrie [kW]": -1,
        "Last_Green_Energy_Hub [kW]": -1,
        "Last_Juechen_Sued [kW]": -1,
    }

    balance = 0

    for col, sign in sign_map.items():
        if col in out.res_df.columns:
            balance = balance + out.res_df[col] * sign

    out.res_df["Bilanz [kW]"] = balance

    h_energy = out.h_sum_energy_kwh or 0
    el_energy = out.el_sum_energy_kwh or 0
    geh_energy = out.geh_sum_energy_kwh or 0
    i_energy = out.i_sum_energy_kwh or 0
    js_energy = out.js_sum_energy_kwh or 0

    out.bal_energy_kwh = h_energy + el_energy - geh_energy - i_energy - js_energy

    # für coverage_rate
    total_generation = h_energy + el_energy
    total_demand = geh_energy + i_energy + js_energy

    if total_demand > 0:
        out.bal_coverage_rate = min(total_generation / total_demand, 1.0)
    else:
        out.bal_coverage_rate = 0.0

    out.bal_power_max_kw = out.res_df["Bilanz [kW]"].max()
    out.bal_power_min_kw = out.res_df["Bilanz [kW]"].min()

    print('Bilanzierung \t\t- abgeschlossen')



    # ------------------------------------------------------------
    # 7) Battery
    # ------------------------------------------------------------


    # Mit Effizienz von 95% beim Laden und Entladen
    if inp.bs_energy_kwh is not None and inp.bs_energy_kwh > 0:
        storage = BatteryStorage(
            capacity_kwh=inp.bs_energy_kwh,
            initial_soc_kwh=0,
            charge_efficiency=np.sqrt(inp.bs_efficiency),
            discharge_efficiency=np.sqrt(inp.bs_efficiency),
            max_charge_c=inp.bs_c_rate,
            max_discharge_c=inp.bs_c_rate,
        )

        out.bs_df = storage.simulate(out.res_df["Bilanz [kW]"], timestep_hours=0.25)
        out.bs_stats = storage.get_stats(out.bs_df, timestep_hours=0.25)

        out.bal_power_max_kw = out.bs_df["new_balance_kw"].max()
        out.bal_power_min_kw = out.bs_df["new_balance_kw"].min()

    print('Batterie \t\t\t- abgeschlossen')




    print('\nInput Daten:\n',inp)
    print('\nOutput Daten:\n', out)
    return out