import sys
from pathlib import Path


# UNBEDINGT RAUS DAMIT NUR EIN WORKAROUND FÜR DIE VERWENDUNG VON ÜBERGELAGERTEN MODULEN
sys.path.append(str(Path(__file__).resolve().parent.parent))

import streamlit as st
import os
import folium
from streamlit_folium import st_folium
import json

import matplotlib.pyplot as plt
import numpy as np

from core.io_types import GuiInput, SimOutput
from Simulation import run_simulation
from functions.plot_functions import (
    plot_industry_preview,
    plot_industry_annual_energy,
    plot_green_hub_weekly_profiles,
    plot_green_hub_annual_energy,
    plot_js_weekly_profile,
)

from functions.web_support_functions import *


pv_name_to_id = {
    "Windschutzwand": 0,
    "Lärmschutzwand": 1,
    "Dach": 2,
    "Böschung": 3,
    "Vertikal (Zaun, Nord-Süd)": 5,
    "Horizontal (aufgeständert, Ost-West)": 6,
    "Horizontal mit Single-Axis-Tracking (aufgeständert, Nord-Süd)": 4
}

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

industry_order_all = [
    "Entsorgung",
    "Stahl_1",
    "Logistik und Lagerung",
    "Schrott Metallhandel",
    "Lagerung",
    "Buero",
    "Logistik Lebensmittel",
    "Stahl_2"
]





st.set_page_config(layout="centered")

Input = GuiInput()
Output = SimOutput()


#Logo als base64
th_logo_path = os.path.join(icon_dir, "logo.png")
iee_logo_path = os.path.join(icon_dir, "IEE_Logo.png")
th_logo_b64 = image_to_base64(th_logo_path)
iee_logo_b64 = image_to_base64(iee_logo_path)
st.markdown(
    f"""
    <div style="display:flex; justify-content:center; align-items:center; gap:70px;">
        <img src="data:image/png;base64,{iee_logo_b64}" style="height:50px; border-radius:0;">
        <img src="data:image/png;base64,{th_logo_b64}" style="height:50px; border-radius:0;">
    </div>
    """,
    unsafe_allow_html=True
)


if "simulation_ran" not in st.session_state:
    st.session_state.simulation_ran = False

if "sim_output" not in st.session_state:
    st.session_state.sim_output = Output

# Überschrift
st.write("\n")
st.title("Energiesystem Modellierung - Innovationspark Jüchen")
st.write("### Erzeugung Eingabewerte")

# Fester Container für Darstellung der Erzeugungseingabe
with st.container(key="Erzeugung", width=1000, height='content'):

    tab1, tab2 = st.tabs(["Solarautobahn", "Energielandschaft"])

    # SOLARAUTOBAHN
    with tab1:
        col1_tab1, col2_tab1 = st.columns(2)

        script_dir = os.path.dirname(os.path.abspath(__file__))

        with col1_tab1:
            Input.h_highways = st.multiselect("Autobahn auswählen", ["A44", "A46"])
            h_selected_names = st.multiselect("PV-Typ", ["Lärmschutzwand", "Windschutzwand", "Dach", "Böschung"])
            Input.h_pv_types = [pv_name_to_id[name] for name in h_selected_names]

            st.write('\n')
            if not Input.h_highways or not Input.h_pv_types:
                st.info("Solarautobahn deaktiviert.")
            else:
                st.info("Solarautobahn aktiv.")

        with col2_tab1:
            pv_geojson_mapping_col2_tab1 = {
                "A44": "a44_beide.geojson",
                "A46": "a46_beide.geojson",
            }

            m = folium.Map(location=[51.06280, 6.49554], zoom_start=12)

            for highway in Input.h_highways:
                selected_file = pv_geojson_mapping_col2_tab1[highway]
                geojson_path = os.path.join(script_dir, "geometry", selected_file)

                with open(geojson_path, "r", encoding="utf-8") as f:
                    geojson_data = json.load(f)

                folium.GeoJson(
                    geojson_data,
                    name=f"{highway}"
                ).add_to(m)

            folium.LayerControl().add_to(m)
            st_data = st_folium(m, width=400, height=400)

    # ENERGIELANDSCHAFT
    with tab2:
        col1_tab2, col2_tab2 = st.columns(2)

        with col1_tab2:
            Input.el_build_state = st.segmented_control(
                "Ausbaugrad der Energielandschaft in %",
                options=[0, 50, 100],
                default=0,
                format_func=lambda x: f"{x:.0f}%"
            )


            el_selected_names = st.selectbox(
                "PV-Typ",
                [
                    "Vertikal (Zaun, Nord-Süd)",
                    "Horizontal (aufgeständert, Ost-West)",
                    "Horizontal mit Single-Axis-Tracking (aufgeständert, Nord-Süd)"
                ]
            )
            Input.el_pv_type = pv_name_to_id[el_selected_names]

            Input.el_tractor_width = st.segmented_control(
                "Traktorbreite",
                options=[9.0, 12.0, 15.0],
                default=12.0,
                format_func=lambda x: f"{x:.0f}m"
            )

            Input.el_tractor_length = st.segmented_control(
                "Traktorlänge",
                options=[12.0, 15.0, 18.0],
                default=15.0,
                format_func=lambda x: f"{x:.0f}m"
            )

            Input.el_tractor_turn_radius = st.segmented_control(
                "Traktor-Wenderadius",
                options=[6.0, 9.0, 12.0],
                default=9.0,
                format_func=lambda x: f"{x:.0f}m"
            )

            Input.el_build_state = 0 if Input.el_build_state is None else Input.el_build_state
            if Input.el_build_state == 0:
                st.info("Energielandschaft deaktiviert.")
            else:
                st.info("Energielandschaft aktiv.")

        with col2_tab2:
            pv_geojson_mapping_col2_tab2 = {
                "Vertikal (Zaun, Nord-Süd)": {
                    50: "Geometry_Vertikal_50_Prozent_20m.geojson",
                    100: "Geometry_Vertikal_Traktorbreite_20m.geojson",
                },
                "Horizontal (aufgeständert, Ost-West)": {
                    50: "Geometry_Horizontal_50_Prozent_20m.geojson",
                    100: "Geometry_Horizontal_Traktorbreite_20m.geojson",
                },
                "Horizontal mit Single-Axis-Tracking (aufgeständert, Nord-Süd)": {
                    50: "Geometry_Horizontal_50_Prozent_20m.geojson",
                    100: "Geometry_Horizontal_Traktorbreite_20m.geojson",
                },
            }

            if Input.el_build_state != 0 and Input.el_build_state is not None:
                selected_file = pv_geojson_mapping_col2_tab2[el_selected_names][Input.el_build_state]
                geojson_path = os.path.join(script_dir, "geometry", selected_file)

                with open(geojson_path, "r", encoding="utf-8") as f:
                    geojson_data = json.load(f)

            m = folium.Map(location=[51.07596, 6.48599], zoom_start=14)

            if Input.el_build_state != 0 and Input.el_build_state is not None:
                folium.GeoJson(
                    geojson_data,
                    name=f"{Input.el_pv_type}{Input.el_tractor_width}"
                ).add_to(m)

            folium.LayerControl().add_to(m)
            st_data = st_folium(m, width=400, height=400)


col1, col2, col3 = st.columns([0.05, 0.9, 0.05])
with col2:
    st.divider()


st.write("### Verbrauch Eingabewerte")

with st.container(key="Verbrauch", width=1500, height='content'):

    tab4, tab5, tab6 = st.tabs(["Industriegebiet", "Green Energy Hub", "Neubaugebiet Jüchen Süd"])

    # INDUSTRIEGEBIET
    with tab4:
        col1_tab4, col2_tab4 = st.columns(2)

        with col1_tab4:
            options = {
                0: "Entsorgung",
                1: "Stahl, 5-Tage-Woche, 3-Schicht",
                2: "Logistik und Lagerung",
                3: "Schrott- und Metallhandel",
                4: "Lagerung",
                5: "Büro",
                6: "Logistik Lebensmittel",
                7: "Stahl, 7-Tage-Woche, 2-Schicht"
            }

            st.write("Wähle bis zu 5 Unternehmen (Duplikate möglich):")

            Input.i_companies = []
            for i in range(5):
                choice = st.selectbox(
                    f"Unternehmen {i + 1}",
                    options=[None] + list(options.keys()),
                    format_func=lambda x: "Keine" if x is None else options[x],
                    key=f"selection_{i}"
                )
                if choice is not None:
                    Input.i_companies.append(choice)

        with col2_tab4:
            Input.i_heat_cooling_electric = st.toggle("Mit Wärme/Kälte Stromverbrauch?")
            expander = st.expander("Erklärung Wärme/Kälte")
            expander.write('''
    Bei Auswahl "ohne Wärme/Kälte Stromverbrauch" werden fossiler Energiequellen für Wärme benutzt und es gibt keine Kälte

    Bei Auswahl "mit Wärme/Kälte Stromverbrauch" werden reversible Luftwärmepumpen und Geothermie-Sonden verwendet
            ''')

            st.write('\n')
            if not Input.i_companies:
                st.info("Industriegebiet deaktiviert.")
            else:
                st.info("Industriegebiet aktiv.")

        preview_csv_path = os.path.join(
            script_dir,
            "functions",
            "inputs",
            "Projekt_04_Lastgaenge_Industriegebiet_und_nPro_Waerme_Kaelte.csv"
        )

        expander = st.expander("Erklärung Unternehmen")
        with expander:
            #einzelne markdowns??
            st.markdown('''
    1. Entsorgung:  
    5 1/2 Tage Woche, Kein Schichtbetrieb, &nbsp; Anlehnung an Schönmackers Umweltdienste

    2. Stahl:  
    5 Tage Woche, 3-Schicht-Betrieb, &emsp; Anlehnung an TecPro

    3. Logistik und Lagerung:  
    5 Tage Woche, Teilweise Samstag und Sonntag Betrieb, Kein Schichtbetrieb, 
    Anlehnung an CTJ Janssen

    4. Schrott- und Metallhandel:  
    5 Tage Woche, Kein Schichtbetrieb, 
    
    Anlehnung an Willi Jenner

    5. Lagerung:  
    5 Tage Woche, Kein Schichtbetrieb, Anlehnung an Kleine Logistik

    6. Büro:  
    5 Tage Woche, Kein Schichtbetrieb, Anlehnung an Marvin Wickenhäuser

    7. Logistik Lebensmittel:  
    6 1/2 Tage Woche, Kein Schichtbetrieb, Anlehnung an CTJ Janssen

    8. Stahl:  
    7 Tage Woche, 2-Schicht-Betrieb, Anlehnung an TecPro
            ''')

            fig_annual_all = plot_industry_annual_energy(
                preview_csv_path,
                ordered_columns=industry_order_all,
                title="Jahresenergie aller Unternehmensprofile"
            )
            st.pyplot(fig_annual_all)

        selected_columns = [industry_csv_mapping[i] for i in Input.i_companies if i in industry_csv_mapping]
        selected_columns = list(dict.fromkeys(selected_columns))

        if selected_columns:
            st.write("#### Beispielhafte Wochenlastgänge der ausgewählten Unternehmen")

            fig_preview = plot_industry_preview(
                preview_csv_path,
                selected_columns=selected_columns,
                start="2017-03-05"
            )
            st.pyplot(fig_preview)

    # GREEN ENERGY HUB
    with tab5:
        green_hub_base_dir = os.path.join(
            script_dir,
            "functions",
            "inputs",
            "green_energy_hub"
        )

        expander = st.expander("Erklärung")
        with expander:
            st.write("""
    **Allgemeine Daten**
    - Elektrolyseur Wirkungsgrad 70%
    - Wasserstoffspeicher (Gas) 10 MWh Kapazität
    - keine PV- oder Windanlagen
    - Ladepunkt Berechnung ohne Wartezeiten
    - BEV Ladesäulen mit 200 kW Leistung
    - Darstellung des Strombedarfs des Elektrolyseurs und der BEV-Ladesäulen
    - Anteil der Anzahl an FCEVs für jedes Jahr: PKW 92.77% , LKW 7.07% , Busse 0.16%

    **Szenario 2022**
    - 5 BEV-Ladesäulen
    - 3 Wasserstoff-Ladesäulen
    - Elektrolyseur mit einer Leistung von ca. 8 MW um H2 Bedarf zu decken
    - Anzahl BEV-Ladevorgänge: 10.381

    **Szenario 2030**
    - 6 BEV-Ladesäulen
    - 8 Wasserstoff-Ladesäulen
    - Elektrolyseur mit einer Leistung von ca. 30 MW
    - Anzahl an FCEVs: 1.800.000
    - Anzahl BEV-Ladevorgänge: 12.154

    **Szenario 2050**
    - 6 BEV-Ladesäulen
    - 8 Wasserstoff-Ladesäulen
    - Elektrolyseur mit einer Leistung von ca. 18 MW
    - Anzahl an FCEVs: 4.560.000
    - Anzahl BEV-Ladevorgänge: 16.587

    **Einordnung der geringeren Elektrolyseurleistung im Jahr 2050**
    Die geringere Elektrolyseurleistung im Vergleich zum Szenario 2030 ist modellseitig dadurch begründet,
    dass nicht allein die Anzahl der Ladepunkte entscheidend ist, sondern vor allem die angenommene
    Wasserstoffnachfrage und deren zeitliche Spitzenlast am betrachteten Standort. Im 2050-Szenario verteilt
    sich die Nachfrage auf eine stärker ausgebaute Infrastruktur, sodass an diesem Standort trotz ausgebauter
    Tankstellenstruktur eine geringere Elektrolyseurleistung ausreicht.
            """)

            fig_green_hub_bar = plot_green_hub_annual_energy(
                green_hub_base_dir,
                years=("2022", "2030", "2050")
            )
            st.pyplot(fig_green_hub_bar)

        scenario_options = ["Keine", "2022", "2030", "2050"]

        Input.geh_h2_load_scenario = st.segmented_control(
            "Wasserstoff-Bedarf Szenario",
            options=scenario_options,
            default="Keine",
        )
        Input.geh_h2_load_scenario = "Keine" if Input.geh_h2_load_scenario is None else Input.geh_h2_load_scenario

        Input.geh_e_load_scenario = st.segmented_control(
            "Elektro-Bedarf Szenario",
            options=scenario_options,
            default="Keine",
        )
        Input.geh_e_load_scenario = "Keine" if Input.geh_e_load_scenario is None else Input.geh_e_load_scenario

        geh_h2_active = Input.geh_h2_load_scenario != "Keine"
        geh_e_active = Input.geh_e_load_scenario != "Keine"
        green_hub_active = geh_h2_active or geh_e_active

        if green_hub_active:
            st.write("#### Beispielhafte Wochenlastprofile der ausgewählten Green-Energy-Hub-Szenarien")

            fig_green_hub_week = plot_green_hub_weekly_profiles(
                green_hub_base_dir,
                h2_year=Input.geh_h2_load_scenario,
                e_year=Input.geh_e_load_scenario,
                start="2022-03-05"
            )
            st.pyplot(fig_green_hub_week)
        else:
            st.info("Green Energy Hub ist deaktiviert.")


        # JÜCHEN SÜD
        with tab6:
            st.write("Wähle das Szenario für das Neubaugebiet Jüchen Süd:")

            js_options = {
                "Aus": 0,
                "1000 Bewohner": 1,
                "2000 Bewohner": 2,
                "3000 Bewohner": 3
            }

            Input.js_scenario = st.segmented_control(
                "Szenario",
                options=list(js_options.keys()),
                default="Aus"
            )

            Input.js_scenario = "Aus" if Input.js_scenario is None else Input.js_scenario

            js_factor = js_options[Input.js_scenario]

            if js_factor == 0:
                st.info("Jüchen Süd ist deaktiviert.")
            else:
                st.info(
                    f"""
                    **Jüchen Süd aktiv:**  
                    Szenario: **{Input.js_scenario}**  
                    Skalierungsfaktor Lastgang: **x{js_factor}**
                    """
                )

                # 👉 Plot
                js_csv_path = os.path.join(
                    script_dir,
                    "functions",
                    "inputs",
                    "Strombezug_Stadtentwicklung_15min.csv"
                )

                st.write("#### Beispielhafte Wochenlastprofile Jüchen Süd")

                fig_js = plot_js_weekly_profile(
                    js_csv_path,
                    scale_factor=js_factor,
                    start="2022-03-05"
                )

                st.pyplot(fig_js)


col1, col2, col3 = st.columns([0.05, 0.9, 0.05])
with col2:
    st.divider()


st.write("### Batterie Eingabewerte")

with st.container(key="Batterie", width=1500, height='content'):

    #tab7 = st.tabs(["Batterie"])
    # Batterie
    #with tab7:

    capacity_mode = st.radio(
        "Kapazität wählen über",
        options=["Standardwert", "Eigene Eingabe"],
        horizontal=True
    )

    if capacity_mode == "Standardwert":
        Input.bs_energy_kwh = st.segmented_control(
            "Kapazität",
            options=[0, 10000, 50000, 100000, 235000],
            default=0,
            format_func=lambda x: f"{x / 1000:.0f} MWh"
        )
    else:
        custom_mwh = st.number_input(
            "Eigene Kapazität [MWh]",
            min_value=0.0,
            value=42.0,
            step=1.0,
            max_value = 100000.0
        )
        Input.bs_energy_kwh = int(custom_mwh * 1000)

    Input.bs_energy_kwh = 0 if Input.bs_energy_kwh is None else Input.bs_energy_kwh

    st.write("\n")

    Input.bs_efficiency = st.select_slider(
        "Roundtrip Effizienz",
        options=[round(x, 3) for x in list(np.arange(0.8, 1.01, 0.01))],
        value=1.0,
        format_func=lambda x: f"{x:.0%}"
    )

    bat_active = (
            Input.bs_energy_kwh > 0
    )

    Input.bs_c_rate = st.select_slider(
        "C-Rate",
        options=[0.25, 0.5, 1.0, 2.0],
        value=1.0,
        format_func=lambda x: f"{x:.2g} C"
    )


    if bat_active:
        st.info(
            f"""
            **Batterie aktiv:**

            Kapazität: **{Input.bs_energy_kwh / 1000:.0f} MWh**  
            Roundtrip Effizienz: **{Input.bs_efficiency:.0%}**  
            C-Rate: **{Input.bs_c_rate:.2g} C**
            """
        )
    else:
        st.info("Batterie deaktiviert.")



st.space(size='small')
col1, col2, col3 = st.columns([0.15, 0.7, 0.15])

with col2:
    run = st.button(
        "⚡ Simulation starten",
        type="primary",
        use_container_width=True
    )
st.space(size='small')


if run:
    with st.spinner("Simulation läuft..."):
        Output = run_simulation(Input)

    st.success("Simulation abgeschlossen.")
    st.session_state.simulation_ran = True

    st.session_state.sim_output = Output
    #print('\nOutput Daten:\n', Output)     #debug
    #st.write(Output.res_df.columns)        #debug




# =========================================================
# Neue Visualisierung: Synergie-Diagramm
# =========================================================

st.write("### Ergebnisse")
#, text_alignment="center") klppt nicht     #:rainbow[Simulationsergebnisse]")
#sim_output = st.session_state.sim_output if st.session_state.simulation_ran else Output

with st.spinner("Visualisierung wird erstellt..."):
    fig_synergy = build_synergy_diagram(Input, st.session_state.sim_output)
    st.plotly_chart(fig_synergy, width="stretch")



# =========================================================
# Wenn Simulation gelaufen ist, weitere Ergebnisse darstellen
# =========================================================
if st.session_state.get("simulation_ran") and "sim_output" in st.session_state:

    sim_output = st.session_state.sim_output


    #NUll spalten entfernen
    protected_cols = ["Bilanz [kW]"]

    zero_cols = [
        col for col in sim_output.res_df.columns
        if col not in protected_cols and sim_output.res_df[col].fillna(0).eq(0).all()
    ]

    sim_output.res_df = sim_output.res_df.drop(columns=zero_cols)




    st.write("### Bilanzverlauf")

    import pandas as pd
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import streamlit as st






    if hasattr(sim_output, "bs_df") and sim_output.bs_df is not None and not sim_output.bs_df.empty:
        y = sim_output.bs_df["new_balance_kw"].copy()
        #plot_title = "Bilanz nach Batteriespeicher"
        #line_label = "Bilanz nach Batterie"
    else:
        y = sim_output.res_df["Bilanz [kW]"].copy()
        #plot_title = "Bilanzverlauf"
        #line_label = "Bilanz"

    #y = sim_output.res_df["Bilanz [kW]"].copy()

    if not isinstance(y.index, pd.DatetimeIndex):
        y.index = pd.date_range(
            start="2021-01-01 00:00:00",
            periods=len(y),
            freq="15min"
        )

    mean_val = y.mean()
    min_val = y.min()
    max_val = y.max()

    fig, ax = plt.subplots(figsize=(12, 5))

    ax.plot(y.index, y.values, label="Bilanz")

    ax.axhline(mean_val, color="red", linestyle="--", linewidth=1.5, label=f"Mittelwert: {mean_val:.1f} kW")
    ax.axhline(min_val, color="red", linestyle=":", linewidth=1.2, label=f"Minimum: {min_val:.1f} kW")
    ax.axhline(max_val, color="red", linestyle=":", linewidth=1.2, label=f"Maximum: {max_val:.1f} kW")

    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))

    ax.set_title("Bilanzverlauf")
    ax.set_xlabel("Monat")
    ax.set_ylabel("Leistung [kW]")
    ax.grid(True, alpha=0.3)
    ax.legend()

    fig.autofmt_xdate()
    st.pyplot(fig)

    with st.expander("Lastgang Infos anzeigen", expanded=False):
        desc_stats = sim_output.res_df
        desc = desc_stats.describe().loc[["mean", "min", "max"]].round(2)
        desc.loc["sum [kWh]"] = desc_stats.sum()/4
        desc.loc["sum [kWh]"] = desc.loc["sum [kWh]"].round(1)
        desc = desc.loc[["sum [kWh]", "mean", "min", "max"]]
        st.dataframe(desc)

        # Plot 1: Erzeuger
        generation_cols = [col for col in sim_output.res_df.columns if "Erzeugung" in col]
        generation = sim_output.res_df[generation_cols].sum(axis=1)
        if not isinstance(generation.index, pd.DatetimeIndex):
            generation.index = pd.date_range(
                start="2021-01-01 00:00:00",
                periods=len(generation),
                freq="15min"
            )
        mean_val = generation.mean()
        #min_val = generation.min()
        max_val = generation.max()

        fig1, ax1 = plt.subplots(figsize=(12, 4))
        ax1.plot(
            generation.index,
            generation.values,
            label="Erzeugung"
        )
        ax1.axhline(mean_val, color="red", linestyle="--", linewidth=1.5, label=f"Mittelwert: {mean_val:.1f} kW")
        #ax1.axhline(min_val, color="red", linestyle=":", linewidth=1.2, label=f"Minimum: {min_val:.1f} kW")
        ax1.axhline(max_val, color="red", linestyle=":", linewidth=1.2, label=f"Maximum: {max_val:.1f} kW")
        ax1.xaxis.set_major_locator(mdates.MonthLocator())
        ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
        ax1.set_title("Leistungsverlauf Erzeugung")
        ax1.set_xlabel("Monat")
        ax1.set_ylabel("Leistung [kW]")
        ax1.grid(True, alpha=0.3)
        ax1.legend()
        fig1.autofmt_xdate()
        st.pyplot(fig1)


        # Plot 1: Verbaucher
        demand_cols = [col for col in sim_output.res_df.columns if "Last" in col]
        demand = sim_output.res_df[demand_cols].sum(axis=1)
        if not isinstance(demand.index, pd.DatetimeIndex):
            demand.index = pd.date_range(
                start="2021-01-01 00:00:00",
                periods=len(demand),
                freq="15min"
            )
        mean_val = demand.mean()
        # min_val = demand.min()
        max_val = demand.max()

        fig1, ax1 = plt.subplots(figsize=(12, 4))
        ax1.plot(
            demand.index,
            demand.values,
            label="Verbrauch"
        )
        ax1.axhline(mean_val, color="red", linestyle="--", linewidth=1.5, label=f"Mittelwert: {mean_val:.1f} kW")
        # ax1.axhline(min_val, color="red", linestyle=":", linewidth=1.2, label=f"Minimum: {min_val:.1f} kW")
        ax1.axhline(max_val, color="red", linestyle=":", linewidth=1.2, label=f"Maximum: {max_val:.1f} kW")
        ax1.xaxis.set_major_locator(mdates.MonthLocator())
        ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
        ax1.set_title("Leistungsverlauf Verbrauch")
        ax1.set_xlabel("Monat")
        ax1.set_ylabel("Leistung [kW]")
        ax1.grid(True, alpha=0.3)
        ax1.legend()
        fig1.autofmt_xdate()
        st.pyplot(fig1)

    # =========================================================
    # Falls Batterie aktiv, Batterie Ergebnisse
    # =========================================================
    if not sim_output.bs_df.empty:

        with st.expander("Batterieergebnisse anzeigen", expanded=False):

            #Stats
            bs_desc_stats = sim_output.bs_df.drop(columns=['soc_kwh'])
            bs_desc = bs_desc_stats.describe().loc[["mean", "min", "max"]].round(2)
            bs_desc.loc["sum [kWh]"] = bs_desc_stats.sum()/4
            bs_desc.loc["sum [kWh]"] = bs_desc.loc["sum [kWh]"].round(2)
            bs_desc = bs_desc.loc[["sum [kWh]", "mean", "min", "max"]]
            st.dataframe(bs_desc)


            # Plot 1: Bilanz mit batteriespeicher
            balance_with_battery = sim_output.bs_df["new_balance_kw"].copy()
            if not isinstance(balance_with_battery.index, pd.DatetimeIndex):
                balance_with_battery.index = pd.date_range(
                    start="2021-01-01 00:00:00",
                    periods=len(balance_with_battery),
                    freq="15min"
                )
            mean_val = balance_with_battery.mean()
            min_val = balance_with_battery.min()
            max_val = balance_with_battery.max()

            fig1, ax1 = plt.subplots(figsize=(12, 4))
            ax1.plot(
                balance_with_battery.index,
                balance_with_battery.values,
                label="Bilanz MIT Batterie"
            )
            ax1.axhline(mean_val, color="red", linestyle="--", linewidth=1.5, label=f"Mittelwert: {mean_val:.1f} kW")
            ax1.axhline(min_val, color="red", linestyle=":", linewidth=1.2, label=f"Minimum: {min_val:.1f} kW")
            ax1.axhline(max_val, color="red", linestyle=":", linewidth=1.2, label=f"Maximum: {max_val:.1f} kW")
            ax1.xaxis.set_major_locator(mdates.MonthLocator())
            ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
            ax1.set_title("Netzbilanz MIT Batteriespeicher")
            ax1.set_xlabel("Monat")
            ax1.set_ylabel("Leistung [kW]")
            ax1.grid(True, alpha=0.3)
            ax1.legend()
            fig1.autofmt_xdate()
            st.pyplot(fig1)


            # Plot 2: Bilanz vor batteriespeicher
            balance_without_battery = sim_output.bs_df["balance_kw"].copy()
            if not isinstance(balance_without_battery.index, pd.DatetimeIndex):
                balance_without_battery.index = pd.date_range(
                    start="2021-01-01 00:00:00",
                    periods=len(balance_without_battery),
                    freq="15min"
                )
            mean_val = balance_without_battery.mean()
            min_val = balance_without_battery.min()
            max_val = balance_without_battery.max()

            fig1, ax1 = plt.subplots(figsize=(12, 4))
            ax1.plot(
                balance_without_battery.index,
                balance_without_battery.values,
                label="Bilanz OHNE Batterie"
            )
            ax1.axhline(mean_val, color="red", linestyle="--", linewidth=1.5, label=f"Mittelwert: {mean_val:.1f} kW")
            ax1.axhline(min_val, color="red", linestyle=":", linewidth=1.2, label=f"Minimum: {min_val:.1f} kW")
            ax1.axhline(max_val, color="red", linestyle=":", linewidth=1.2, label=f"Maximum: {max_val:.1f} kW")
            ax1.xaxis.set_major_locator(mdates.MonthLocator())
            ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
            ax1.set_title("Netzbilanz OHNE Batteriespeicher")
            ax1.set_xlabel("Monat")
            ax1.set_ylabel("Leistung [kW]")
            ax1.grid(True, alpha=0.3)
            ax1.legend()
            fig1.autofmt_xdate()
            st.pyplot(fig1)


            # Plot 2: SOC
            bs_soc = sim_output.bs_df["soc_kwh"].copy()
            bs_soc_percent = bs_soc / Input.bs_energy_kwh
            if not isinstance(bs_soc_percent.index, pd.DatetimeIndex):
                bs_soc_percent.index = pd.date_range(
                    start="2021-01-01 00:00:00",
                    periods=len(bs_soc_percent),
                    freq="15min"
                )
            
            fig3, ax3 = plt.subplots(figsize=(12, 4))
            ax3.plot(
                bs_soc_percent.index,
                bs_soc_percent.values,
                label="State of charge"
            )
            #fig3, ax3 = plt.subplots(figsize=(12, 4))
            #ax3.plot(sim_output.bs_df.index, sim_output.bs_df["soc_kwh"])
            ax3.set_title(f"State of Charge der Batterie (Kapazität: {Input.bs_energy_kwh/1000} MWh)")
            ax3.set_xlabel("Zeit")
            ax3.set_ylabel("SOC [%]  Energie [kWh]")
            ax3.grid(True)
            st.pyplot(fig3)

