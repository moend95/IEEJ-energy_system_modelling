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
from core.module_green_energy_hub import run_geh_h2_chain

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

class Simulator:
    def __init__(self):
        self.weather_df = self.weather_prep() #Read weather data from csv

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

        if inp.i_companies is []:
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
        Green Energy Hub load simulation module.
        This function loads selected hydrogen and electric mobility demand scenarios,
        combines them into a single load profile, and writes the resulting time series
        and energy values to the output object.
        If no scenario is selected, a zero load profile is used.
        """

        hub_dir = os.path.join(base_input, "green_energy_hub")

        # Default: not active -> Null profile
        out.res_df["Last_Green_Energy_Hub [kW]"] = 0.0
        out.geh_max_power_kw = 0.0
        out.geh_sum_energy_kwh = 0.0

        # BEV-Ladepark: externes CSV-Profil (bleibt szenariobasiert)
        geh_series = pd.Series(0.0, index=out.res_df.index)
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
        out.geh_max_power_kw = float(geh_series.max())
        out.geh_sum_energy_kwh = float((geh_series * 0.25).sum())

        # H2-Elektrolyseur: wird NACH der vorläufigen Bilanz dynamisch berechnet
        # → siehe run_geh_electrolyzer() / run_simulation()

        return out

    def run_geh_electrolyzer(self, inp: GuiInput, out: SimOutput) -> SimOutput:
        """
        Berechnet die H2-Prozesskette (Elektrolyseur → Kompressor → Speicher → Dispenser)
        auf Basis des verfügbaren Überschuss-Stroms aus der vorläufigen Bilanz.
        Ergänzt Last_Green_Energy_Hub [kW] um den Strombedarf von Elektrolyseur + Kompressor.
        """
        if not (inp.geh_electrolyzer_power_kw and inp.geh_electrolyzer_power_kw > 0):
            return out

        surplus_kw = out.res_df.get("Bilanz_vorläufig [kW]", out.res_df.get("Bilanz [kW]",
                                     pd.Series(0.0, index=out.res_df.index)))

        geh_result = run_geh_h2_chain(inp, surplus_kw, dt_h=0.25)

        # Elektrolyseur + Kompressor als elektrische Last hinzufügen
        out.res_df["Last_Green_Energy_Hub [kW]"] = (
            out.res_df["Last_Green_Energy_Hub [kW]"] + geh_result.total_el_demand_kw.values
        )

        # GEH-Jahreswerte aktualisieren
        out.geh_max_power_kw = float(out.res_df["Last_Green_Energy_Hub [kW]"].max())
        out.geh_sum_energy_kwh = float((out.res_df["Last_Green_Energy_Hub [kW]"] * 0.25).sum())

        # H2-spezifische Ergebnisse in SimOutput schreiben
        out.geh_h2_production_kwh = geh_result.h2_production_kwh
        out.geh_compressor_demand_kwh = geh_result.compressor_demand_kwh
        out.geh_h2_delivered_kwh = geh_result.h2_delivered_kwh
        out.geh_h2_curtailed_kwh = geh_result.h2_curtailed_kwh
        out.geh_storage_soc_df = geh_result.storage_soc_kwh.to_frame(name="soc_kwh")

        return out

    def run_juechen_sued(self, inp: GuiInput, out: SimOutput) -> SimOutput:
        """
        Jüchen-Süd development area load simulation module.
        This function loads the predefined residential demand profile and scales it
        according to the selected population scenario.
        The resulting load time series and energy statistics are written to the
        output object and added to the overall simulation results.
        """
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
                base_input,
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

        feed_in_kwh = out.res_df["Bilanz [kW]"].clip(lower=0).sum() / 4

        # For coverage_rate
        total_generation = h_energy + el_energy
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

        sim.run_green_energy_hub(inp, out)   # Lädt nur BEV-CSV, kein H2-CSV mehr
        print('Green Energy Hub (BEV)\t- abgeschlossen')

        sim.run_juechen_sued(inp, out)
        print('Juechen-Sued \t\t- abgeschlossen')

        # Vorläufige Bilanz – nötig damit der Elektrolyseur den verfügbaren
        # Überschuss-Strom als Input bekommt
        sim.run_balance(out)
        out.res_df["Bilanz_vorläufig [kW]"] = out.res_df["Bilanz [kW]"].copy()

        # GEH – H2-Prozesskette dynamisch berechnen (Elektrolyseur + Kompressor)
        sim.run_geh_electrolyzer(inp, out)
        print('Green Energy Hub (H2)\t- abgeschlossen')

        # Finale Bilanz inkl. Elektrolyseur- und Kompressorlast
        total_demand, total_generation, feed_in_kwh = sim.run_balance(out)

        sim.run_battery(inp, out)
        print('Batterie \t\t- abgeschlossen')

        if hasattr(out, "bs_df") and "new_balance_kw" in out.bs_df.columns:
            feed_in_kwh = out.bs_df["new_balance_kw"].clip(lower=0).sum() / 4

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