#Übergabefertig kommentiertJB
import os
import numpy as np
import pandas as pd

#Functions
from core.io_types import GuiInput, SimOutput
from core.module_industrial_area import IndustryLoadAggregator
from core.module_pv_modulator import PV_System, PV_TYPEN
from core.module_energy_landscape import main
from core.module_battery_storage import BatteryStorage
from core.module_green_energy_hub import (
    GEHParams,
    resolve_geh_variant,
    run_geh_dispatch,
    simulate_geh_pv,
)
from core.geh_profiles import build_geh_load_profiles
from core.js_profiles import build_js_profiles
from core.module_juechen_sued import JSParams, concept_cops, resolve_js_concept, run_js_heat_dispatch

#TYPE MAPPING
industry_csv_mapping = {
    0: "Entsorgung",
    1: "Stahl_1",
    2: "Logistik und Lagerung",
    3: "Schrott Metallhandel",
    4: "Lagerung",
    5: "Buero",
    6: "Logistik Lebensmittel",
    7: "Stahl_2"
}
highway_geojson_mapping= {"A44": "a44_beide.geojson", "A46": "a46_beide.geojson"}
industry_heating_choice_mapping = {True: "2", False: "1"}
el_pv_type_number_text_mapping = {4:"horizontal_tracking", 5:"vertical", 6:"horizontal"}

#GLOBAL VARIABLES
script_dir = os.path.dirname(os.path.abspath(__file__))
base_input = os.path.join(script_dir, "data", "inputs")
weather_csv = os.path.join(base_input,"wetter_daten_2021_15min.csv")
output_dir = os.path.join(script_dir,"data", "outputs")
os.makedirs(output_dir, exist_ok=True)

# Green Energy Hub: Profilspalte → Spalte in res_df
GEH_LOAD_COLUMNS = {
    "mcs_kw": "Last_GEH_MCS [kW]",
    "ccs_kw": "Last_GEH_CCS [kW]",
    "hpc_kw": "Last_GEH_HPC [kW]",
    "ac_kw": "Last_GEH_AC [kW]",
    "building_kw": "Last_GEH_Gebaeude [kW]",
}
GEH_GENERATION_COLUMNS = [
    "Erzeugung_Solarautobahn [kW]",
    "Erzeugung_Energielandschaft [kW]",
    "Erzeugung_GEH_PV [kW]",
]
GEH_PARK_LOAD_COLUMNS = ["Last_Industrie [kW]", "Last_Juechen_Sued [kW]", *GEH_LOAD_COLUMNS.values()]
DT_H = 0.25

# Jüchen Süd: elektrische Teillasten, Summe in Last_Juechen_Sued [kW]
JS_LOAD_COLUMNS = [
    "Last_JS_Nutzerstrom [kW]",
    "Last_JS_EMob [kW]",
    "Last_JS_Waermepumpe [kW]",
    "Last_JS_Heizstab [kW]",
    "Last_JS_Kaelte [kW]",
]


class Simulator:
    def __init__(self):
        self.weather_df = self.weather_prep() #Read weather data from csv
        self.geh_h2_demand_kwh = np.zeros(0)  # H2-Nachfrage Tankstelle je Zeitschritt [kWh_H2]

    def weather_prep(self):
        """
        Prepares the weather data used for all PV simulations.
        """
        weather_df = pd.read_csv(weather_csv, index_col=0, parse_dates=True)
        weather_df.index = pd.to_datetime(weather_df.index, utc=True).tz_convert(None)

        return weather_df

    def run_pv_modulator(self, inp: GuiInput, out: SimOutput) -> SimOutput:
        """
        This function generates PV points along selected geometry, simulates the
        photovoltaic generation for each selected PV type, and aggregates the
        resulting time series and energy values.
        The results are written to the output object and added to the overall
        simulation result DataFrame.
        """
        h_selected_pv_types = [PV_TYPEN[i] for i in inp.h_pv_types] if inp.h_pv_types else []
        out.h_error_text = "Hier könnte ihre Autobahn Fehlermeldung stehen!"
        out.h_sum_energy_kwh = 0
        out.h_number_of_points = 0
        all_ac_series = []

        # Errortext conditions
        if not inp.h_highways:
            out.h_error_text = "SOLARAUTOBAHN --- Keine Autobahnen ausgewählt."
        elif not inp.h_pv_types:
            out.h_error_text = "SOLARAUTOBAHN --- Keine PV-Typen ausgewählt."
        else:
            out.h_error_text = ""

            # highways are simulated
            for highway in inp.h_highways:
                selected_file = highway_geojson_mapping[highway]
                geojson_path = os.path.join(base_input, "geometry", selected_file)

                h_pv_system = PV_System(
                    geojson_path=geojson_path,
                    pvtypes=h_selected_pv_types,
                    step_size=800,
                    weather_df=self.weather_df,
                    base_output_dir=os.path.join(output_dir, "highway"),
                )

                results = h_pv_system.generate_pv_points()

                # Add up all points of all pv types of the highway
                for pv_type in h_pv_system.pvtypes:
                    if pv_type.id in results:
                        out.h_number_of_points += len(results[pv_type.id])

                # Calcuate energy per pv type and add up
                for pv_type in h_pv_system.pvtypes:
                    geo_name = os.path.splitext(os.path.basename(geojson_path))[0]
                    csv_name = f"{geo_name}_punkte_{pv_type.id}_{pv_type.name}.csv".replace(" ", "_")
                    csv_path = os.path.join(output_dir, "highway", csv_name)

                    if not os.path.exists(csv_path):
                        print(f"Datei nicht gefunden: {csv_path}")
                        continue

                    energy_type_kWh, total_type_ac_w = h_pv_system.simulate_pv_type_energy(pv_type, csv_path)

                    scaled_energy_kwh_pv_type = 0
                    scaled_total_type_ac_w = 0

                    if h_pv_system.step_size >= pv_type.row_width:
                        scaling_factor = h_pv_system.step_size // pv_type.row_width
                        scaled_energy_kwh_pv_type = energy_type_kWh * scaling_factor
                        scaled_total_type_ac_w = total_type_ac_w * scaling_factor

                    else:
                        print(f"Keine Skalierung für {highway} | {pv_type.name}, da Schrittweite kleiner als Modulbreite")

                    out.h_sum_energy_kwh += scaled_energy_kwh_pv_type

                    ac_kw = scaled_total_type_ac_w / 1000
                    all_ac_series.append(ac_kw)

            # Add up all time series
            if all_ac_series:
                total_sys_ac_kw = all_ac_series[0].copy()
                for s in all_ac_series[1:]:
                    total_sys_ac_kw = total_sys_ac_kw.add(s, fill_value=0)

                out.res_df["Erzeugung_Solarautobahn [kW]"] = total_sys_ac_kw.clip(lower=0).values

                out.res_df["Erzeugung_Solarautobahn [kW]"] = out.res_df["Erzeugung_Solarautobahn [kW]"].fillna(0)
            else:
                out.res_df["Erzeugung_Solarautobahn [kW]"] = 0
            out.h_max_power_kw = out.res_df["Erzeugung_Solarautobahn [kW]"].max()

        return out

    def run_energy_landscape(self, inp: GuiInput, out: SimOutput) -> SimOutput:
        """
        Energy landscape (Agri-PV) simulation module.
        This function generates Agri-PV layouts based on tractor parameters and
        selected PV type, simulates the resulting photovoltaic generation, and
        scales the results according to the selected build state.
        The resulting time series and energy values are written to the output object.
        """
        # Agri PV code for geojson and agri pv length
        if inp.el_pv_type is not None:
            agri_result = main(
                interactive=False,
                output_dir=os.path.join(output_dir, "energy_landscape"),
                pv_ausrichtung=el_pv_type_number_text_mapping[inp.el_pv_type],
                tractor_width_m=inp.el_tractor_width,
                tractor_length_m=inp.el_tractor_length,
                tractor_turn_radius_m=inp.el_tractor_turn_radius,
            )
            out.el_pv_length = agri_result.get("metadata").get('total_rows_length_m')

            el_selected_pv_type = PV_TYPEN[inp.el_pv_type]

            # Input for PV Modulator
            geojson_file_2 = "Agri_PV_Centroid.geojson"
            geojson_path_2 = os.path.join(base_input, "geometry", geojson_file_2)
            step_size_default = 1000

            el_pv_system = PV_System(
                geojson_path=geojson_path_2,
                pvtypes=[el_selected_pv_type],  # [PV_TYPEN[0],PV_TYPEN[3]],
                step_size=step_size_default,  # Punktabstand in m
                weather_df=self.weather_df,
                base_output_dir=os.path.join(output_dir, "energy_landscape"),
            )

            el_pv_system.generate_pv_points()

            # CSV-Name the way generate_pv_points saved it
            geo_name = os.path.splitext(os.path.basename(geojson_path_2))[0]
            el_csv_name = f"{geo_name}_punkte_{el_selected_pv_type.id}_{el_selected_pv_type.name}.csv".replace(" ", "_")
            el_csv_path = os.path.join(output_dir, "energy_landscape", el_csv_name)

            # Simulate pv and write time series
            el_energy_type_kWh, el_total_type_ac_w = el_pv_system.simulate_pv_type_energy(el_selected_pv_type, el_csv_path)

            el_energy_sys_kWh = el_energy_type_kWh * out.el_pv_length * (inp.el_build_state / 100)
            el_total_sys_ac_kw = el_total_type_ac_w * out.el_pv_length * (inp.el_build_state / 100) / 1000

            out.el_max_power_kw = el_total_sys_ac_kw.max()
            el_total_sys_ac_kw.index_no_year = el_total_sys_ac_kw.index.strftime("%m-%d %H:%M")
            out.res_df["Erzeugung_Energielandschaft [kW]"] = el_total_sys_ac_kw.clip(lower=0).values
            out.res_df["Erzeugung_Energielandschaft [kW]"] = out.res_df["Erzeugung_Energielandschaft [kW]"].fillna(0)
            out.el_sum_energy_kwh = el_energy_sys_kWh


        else:
            out.el_pv_length = 0

        return out

    def run_industry_area(self, inp: GuiInput, out: SimOutput) -> SimOutput:
        """
        Industrial area load simulation module.
        This function aggregates load profiles of selected companies, applies the
        selected heating/cooling electrification scenario, and generates the
        combined industrial load time series.
        The resulting demand profile and energy statistics are written to the output object.
        """
        industry_aggregator = IndustryLoadAggregator()

        if not inp.i_companies:
            out.i_error_text = "INDUSTRIEGEBIET --- Kein Unternehmen ausgewählt."
        elif inp.i_companies:
            out.i_error_text = "Hier könnte ihre Industriegebiet Fehlermeldung stehen!"

            # Run industry_aggregator with user inputs
            df_industrie, csv_path_industrie, plot_path_industrie = industry_aggregator.run(
                mode_choice=industry_heating_choice_mapping[inp.i_heat_cooling_electric],
                selection_indices=inp.i_companies,
            )
            # Write timeseries
            if df_industrie is None or df_industrie.empty:
                out.res_df['Last_Industrie [kW]'] = 0
            else:
                out.res_df['Last_Industrie [kW]'] = df_industrie['Gesamtlast [kW]']  # Alle Lastgänge positiv

            out.i_max_power_kw = out.res_df['Last_Industrie [kW]'].max()
            df_i_energy_kwh_profile = out.res_df['Last_Industrie [kW]'] * 0.25
            out.i_sum_energy_kwh = df_i_energy_kwh_profile.sum()

        return out

    def run_green_energy_hub(self, inp: GuiInput, out: SimOutput) -> SimOutput:
        """
        Green Energy Hub – Lasten und PV (Machbarkeitsstudie „Autohof der Zukunft“).
        Erzeugt für die gewählte Variante die synthetischen Ladeprofile je Ladecluster,
        die Gebäudelast, die H2-Tankstellennachfrage und die PV am Hub und schreibt
        sie in out.res_df. Ohne Variante sind alle Profile 0.
        Die Betriebsführung (Elektrolyseur, Batterie, Netz) folgt in run_geh_dispatch_step().
        """
        weather_index = self.weather_df.index
        if len(out.res_df.index) == 0:
            out.res_df = pd.DataFrame(index=pd.RangeIndex(len(weather_index)))
        # res_df hat einen RangeIndex → Profile werden positionsgleich über .values geschrieben
        assert len(weather_index) == len(out.res_df), (
            f"Wetterdaten ({len(weather_index)}) und res_df ({len(out.res_df)}) sind nicht gleich lang."
        )

        variant = resolve_geh_variant(inp)

        if variant is None:
            for column in GEH_LOAD_COLUMNS.values():
                out.res_df[column] = 0.0
            out.res_df["Erzeugung_GEH_PV [kW]"] = 0.0
            self.geh_h2_demand_kwh = np.zeros(len(out.res_df))
        else:
            profiles = build_geh_load_profiles(weather_index, variant)
            for profile_column, column in GEH_LOAD_COLUMNS.items():
                out.res_df[column] = profiles[profile_column].values
            self.geh_h2_demand_kwh = profiles["h2_demand_kwh"].to_numpy()

            pv_kw = simulate_geh_pv(self.weather_df, float(variant["pv_kwp"]), weather_index)
            out.res_df["Erzeugung_GEH_PV [kW]"] = pv_kw.values

        out.geh_pv_sum_energy_kwh = float(out.res_df["Erzeugung_GEH_PV [kW]"].sum() * DT_H)
        out.geh_pv_max_power_kw = float(out.res_df["Erzeugung_GEH_PV [kW]"].max())
        out.geh_charging_mcs_kwh = float(out.res_df["Last_GEH_MCS [kW]"].sum() * DT_H)
        out.geh_charging_ccs_kwh = float(out.res_df["Last_GEH_CCS [kW]"].sum() * DT_H)
        out.geh_charging_hpc_kwh = float(out.res_df["Last_GEH_HPC [kW]"].sum() * DT_H)
        out.geh_charging_ac_kwh = float(out.res_df["Last_GEH_AC [kW]"].sum() * DT_H)
        out.geh_building_kwh = float(out.res_df["Last_GEH_Gebaeude [kW]"].sum() * DT_H)
        out.geh_h2_demand_kwh = float(self.geh_h2_demand_kwh.sum())

        return out

    def run_geh_dispatch_step(self, inp: GuiInput, out: SimOutput) -> SimOutput:
        """
        Betriebsführung des Green Energy Hubs auf Basis der Park-Bilanz vor Flexibilität:
        eigener Strom zuerst (Elektrolyseur, GEH-Batterie), Überschuss ins Netz,
        Fehlmengen aus dem Netz. Läuft auch ohne Variante (mit Nullkomponenten),
        damit Netzbezug und -einspeisung immer einheitlich berechnet werden.
        """
        n = len(out.res_df)
        net_kw = np.zeros(n)
        for column in GEH_GENERATION_COLUMNS:
            if column in out.res_df.columns:
                net_kw += out.res_df[column].fillna(0.0).to_numpy()
        for column in GEH_PARK_LOAD_COLUMNS:
            if column in out.res_df.columns:
                net_kw -= out.res_df[column].fillna(0.0).to_numpy()

        params = GEHParams.from_variant(resolve_geh_variant(inp))
        r = run_geh_dispatch(net_kw, self.geh_h2_demand_kwh, params, dt_h=DT_H)

        out.res_df["Last_GEH_Elektrolyseur [kW]"] = r.electrolyzer_kw
        out.res_df["Last_GEH_Kompressor [kW]"] = r.compressor_kw
        out.res_df["GEH_Batterie_Laden [kW]"] = r.battery_charge_kw
        out.res_df["GEH_Batterie_Entladen [kW]"] = r.battery_discharge_kw
        out.res_df["Netzbezug [kW]"] = r.grid_import_kw
        out.res_df["Netzeinspeisung [kW]"] = r.grid_export_kw

        geh_load_columns = [*GEH_LOAD_COLUMNS.values(), "Last_GEH_Elektrolyseur [kW]", "Last_GEH_Kompressor [kW]"]
        out.res_df["Last_Green_Energy_Hub [kW]"] = out.res_df[geh_load_columns].sum(axis=1)
        out.geh_max_power_kw = float(out.res_df["Last_Green_Energy_Hub [kW]"].max())
        out.geh_sum_energy_kwh = float(out.res_df["Last_Green_Energy_Hub [kW]"].sum() * DT_H)

        out.geh_electrolyzer_kwh = r.electrolyzer_kwh
        out.geh_electrolyzer_full_load_hours = r.electrolyzer_full_load_hours
        out.geh_compressor_demand_kwh = r.compressor_kwh
        out.geh_h2_production_kwh = r.h2_production_kwh
        out.geh_h2_delivered_kwh = r.h2_delivered_total_kwh
        out.geh_h2_demand_kwh = r.h2_demand_kwh
        out.geh_h2_unmet_kwh = r.unmet_kwh
        out.geh_battery_charge_kwh = r.battery_charge_kwh
        out.geh_battery_discharge_kwh = r.battery_discharge_kwh
        out.geh_battery_full_cycles = r.battery_full_cycles
        out.geh_storage_soc_df = pd.DataFrame({"soc_kwh": r.h2_soc_kwh}, index=out.res_df.index)
        out.geh_battery_soc_df = pd.DataFrame({"soc_kwh": r.battery_soc_kwh}, index=out.res_df.index)

        out.grid_import_kwh = r.grid_import_kwh
        out.grid_export_kwh = r.grid_export_kwh
        out.grid_max_import_kw = r.grid_max_import_kw

        return out

    def run_juechen_sued(self, inp: GuiInput, out: SimOutput) -> SimOutput:
        """
        Jüchen Süd – Stadtteilentwicklung nach dem Energiekonzept (Fraunhofer IEG, Basis-Variante).
        Erzeugt Nutzerstrom, E-Mobilität und Wärme-/Kältebedarf, berechnet die Wärmeversorgung
        des gewählten Versorgungskonzepts (warmes Netz, kaltes Netz, dezentral) und schreibt
        alle elektrischen Lasten in out.res_df. Ohne Konzept sind alle Lasten 0.
        """
        n = len(out.res_df)
        assert len(self.weather_df.index) == n, (
            f"Wetterdaten ({len(self.weather_df.index)}) und res_df ({n}) sind nicht gleich lang."
        )
        out.js_error_text = ""
        concept = resolve_js_concept(inp)

        for column in JS_LOAD_COLUMNS:
            out.res_df[column] = 0.0
        out.js_tank_soc_df = pd.DataFrame({"soc_kwh": np.zeros(n)}, index=out.res_df.index)
        out.js_household_kwh = out.js_emob_kwh = 0.0
        out.js_space_heat_kwh = out.js_dhw_kwh = out.js_cooling_kwh = 0.0
        out.js_hp_el_kwh = out.js_heater_el_kwh = out.js_cooling_el_kwh = 0.0
        out.js_heat_unmet_kwh = out.js_hp_scop = 0.0

        if concept is not None:
            temp_air = self.weather_df["temp_air"].to_numpy()
            profiles = build_js_profiles(self.weather_df.index, temp_air)
            cop_space, cop_dhw = concept_cops(concept, temp_air)
            r = run_js_heat_dispatch(
                profiles["space_heat_kw"].to_numpy(),
                profiles["dhw_kw"].to_numpy(),
                profiles["cooling_kw"].to_numpy(),
                cop_space,
                cop_dhw,
                JSParams.from_concept(concept),
                dt_h=DT_H,
            )

            out.res_df["Last_JS_Nutzerstrom [kW]"] = profiles["household_kw"].values
            out.res_df["Last_JS_EMob [kW]"] = profiles["emob_kw"].values
            out.res_df["Last_JS_Waermepumpe [kW]"] = r.hp_el_kw
            out.res_df["Last_JS_Heizstab [kW]"] = r.heater_kw
            out.res_df["Last_JS_Kaelte [kW]"] = r.cooling_el_kw
            out.js_tank_soc_df = pd.DataFrame({"soc_kwh": r.tank_soc_kwh}, index=out.res_df.index)

            out.js_household_kwh = float(profiles["household_kw"].sum() * DT_H)
            out.js_emob_kwh = float(profiles["emob_kw"].sum() * DT_H)
            out.js_space_heat_kwh = float(profiles["space_heat_kw"].sum() * DT_H)
            out.js_dhw_kwh = float(profiles["dhw_kw"].sum() * DT_H)
            out.js_cooling_kwh = float(profiles["cooling_kw"].sum() * DT_H)
            out.js_hp_el_kwh = r.hp_el_kwh
            out.js_heater_el_kwh = r.heater_kwh
            out.js_cooling_el_kwh = r.cooling_el_kwh
            out.js_heat_unmet_kwh = r.unmet_kwh
            out.js_hp_scop = r.scop

        out.res_df["Last_Juechen_Sued [kW]"] = out.res_df[JS_LOAD_COLUMNS].sum(axis=1)
        out.js_max_power_kw = float(out.res_df["Last_Juechen_Sued [kW]"].max())
        out.js_sum_energy_kwh = float(out.res_df["Last_Juechen_Sued [kW]"].sum() * DT_H)

        return out

    def run_balance(self, out: SimOutput):
        """
        System balance calculation module.
        This function combines all generation and demand time series, calculates the
        overall power balance, and determines total generation, total demand, and
        coverage rate.
        The resulting balance time series and energy statistics are written to the
        output object and returned for further processing.
        """

        sign_map = {
            "Erzeugung_Solarautobahn [kW]": 1,
            "Erzeugung_Energielandschaft [kW]": 1,
            "Erzeugung_GEH_PV [kW]": 1,
            "Last_Industrie [kW]": -1,
            "Last_Green_Energy_Hub [kW]": -1,
            "Last_Juechen_Sued [kW]": -1,
            "GEH_Batterie_Entladen [kW]": 1,
            "GEH_Batterie_Laden [kW]": -1,
        }

        balance = 0

        for col, sign in sign_map.items():
            if col in out.res_df.columns:
                balance = balance + out.res_df[col] * sign

        # Bilanz nach GEH-Batterie (= balance_after_kw aus run_geh_dispatch)
        out.res_df["Bilanz [kW]"] = balance

        h_energy = out.h_sum_energy_kwh or 0
        el_energy = out.el_sum_energy_kwh or 0
        geh_pv_energy = out.geh_pv_sum_energy_kwh or 0
        geh_energy = out.geh_sum_energy_kwh or 0
        i_energy = out.i_sum_energy_kwh or 0
        js_energy = out.js_sum_energy_kwh or 0
        geh_battery_net = (out.geh_battery_discharge_kwh or 0) - (out.geh_battery_charge_kwh or 0)

        out.bal_energy_kwh = h_energy + el_energy + geh_pv_energy - geh_energy - i_energy - js_energy + geh_battery_net

        feed_in_kwh = out.res_df["Netzeinspeisung [kW]"].sum() * DT_H

        # For coverage_rate
        total_generation = h_energy + el_energy + geh_pv_energy
        total_demand = geh_energy + i_energy + js_energy

        if total_demand > 0:
            out.bal_coverage_rate = min(total_generation / total_demand, 1.0)
        else:
            out.bal_coverage_rate = 0.0
        # write time series
        out.bal_power_max_kw = out.res_df["Bilanz [kW]"].max()
        out.bal_power_min_kw = out.res_df["Bilanz [kW]"].min()

        return total_demand, total_generation, feed_in_kwh

    def run_battery(self, inp: GuiInput, out: SimOutput) -> SimOutput:
        """
        Battery storage simulation module.
        This function simulates battery operation based on the system balance,
        including charging and discharging behavior, state of charge, and grid
        exchange.
        The resulting adjusted balance, battery statistics, and updated energy values
        are written to the output object.
        """

        # When Battery input is given (capacity), battery class is called and storage object created
        if inp.bs_energy_kwh is not None and inp.bs_energy_kwh > 0:
            storage = BatteryStorage(
                capacity_kwh=inp.bs_energy_kwh,  # Battery capacity [kWh]
                initial_soc_kwh=0,  # Initial State of Charge [kWh]
                charge_efficiency=np.sqrt(inp.bs_efficiency),  # Charging Efficiency
                discharge_efficiency=np.sqrt(inp.bs_efficiency),  # Discharging Efficiency
                max_charge_c=inp.bs_c_rate,  # Maximum C-Rate Charging
                max_discharge_c=inp.bs_c_rate,  # Maximum C-Rate Discharging
                # Calculates max Charging/Discharging Power through capacity and C-Rate
            )

            # Calculate new energy balance (Data Frame['new_balance_kw'])
            # Input: Balance Data Frame and give timestep information, 0.25 equals 15 min
            # Output: Data Frame including: balance_kw(Input), battery_power_kw, soc_kwh, new_balance_kw
            out.bs_df = storage.simulate(out.res_df["Bilanz [kW]"], timestep_hours=0.25)

            # Calculate battery stats (dict)
            # Input: result Battery Data Frame and give timestep information, 0.25 equals 15 min
            # Output: Stats Dictionary: grid_import_kwh, grid_export_kwh, battery_charge_kwh, battery_discharge_kwh,
            #  ...final_soc_kwh, final_soc_percent, max_charge_kw, max_discharge_kw
            out.bs_stats = storage.get_stats(out.bs_df, timestep_hours=0.25)

            out.bal_energy_kwh = out.bal_energy_kwh + out.bs_stats['battery_discharge_kwh'] - out.bs_stats[
                'battery_charge_kwh']

            out.bal_power_max_kw = out.bs_df["new_balance_kw"].max()
            out.bal_power_min_kw = out.bs_df["new_balance_kw"].min()

            # Netzaustausch nach allgemeiner Batterie überschreibt die Werte aus dem GEH-Dispatch
            new_balance = out.bs_df["new_balance_kw"].to_numpy()
            out.res_df["Netzbezug [kW]"] = np.maximum(-new_balance, 0.0)
            out.res_df["Netzeinspeisung [kW]"] = np.maximum(new_balance, 0.0)
            out.grid_import_kwh = float(out.res_df["Netzbezug [kW]"].sum() * DT_H)
            out.grid_export_kwh = float(out.res_df["Netzeinspeisung [kW]"].sum() * DT_H)
            out.grid_max_import_kw = float(out.res_df["Netzbezug [kW]"].max())

        return out


def run_simulation(inp: GuiInput) -> SimOutput:
        """
        Main simulation function
        Each of the five modules are implemented (PV-modulator, energy landscape, industrial area, green energy hub and battery storage)
        The function gets the Input Object and returns the output object defined in io_types.py.
        During standard procedure the Input object is filled via website user inputs and the outputs are visualized on the website.
        """
        sim = Simulator()
        out = SimOutput()

        sim.run_pv_modulator(inp, out)
        print('Solarautobahn \t\t- abgeschlossen')

        sim.run_energy_landscape(inp, out)
        print('Energielandschaft \t- abgeschlossen')

        sim.run_industry_area(inp, out)
        print('Industriegebiet \t- abgeschlossen')

        sim.run_green_energy_hub(inp, out)   # Ladeprofile, Gebäude, H2-Nachfrage, PV am Hub
        print('Green Energy Hub \t- abgeschlossen')

        sim.run_juechen_sued(inp, out)
        print('Juechen-Sued \t\t- abgeschlossen')

        # GEH-Betriebsführung: Elektrolyseur, H2-Speicher, GEH-Batterie, Netz
        sim.run_geh_dispatch_step(inp, out)
        print('GEH-Dispatch \t\t- abgeschlossen')

        total_demand, total_generation, feed_in_kwh = sim.run_balance(out)

        sim.run_battery(inp, out)
        print('Batterie \t\t- abgeschlossen')

        feed_in_kwh = out.res_df["Netzeinspeisung [kW]"].sum() * DT_H

        if total_generation > 0:
            out.ee_self_consumption = (total_generation - feed_in_kwh) / total_generation
        else:
            out.ee_self_consumption = 0
        if total_demand > 0:
            out.autarky = (total_generation - feed_in_kwh) / total_demand
        else:
            out.autarky = 0

        print('\nInput Daten:\n', inp)
        #print('\nOutput Daten:\n', out)    # only enable for website use, causes large console output in sensitivity_analysis.py
        return out