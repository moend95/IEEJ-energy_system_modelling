import streamlit as st
import folium
from streamlit_folium import st_folium
import json

import numpy as np

from core.io_types import GuiInput, SimOutput
from Simulation import Simulator, run_simulation, industry_csv_mapping
from core.module_green_energy_hub import GEH_VARIANTS
from core.module_juechen_sued import JS_CONCEPTS
from core.module_industrial_area import ELSBACHTAL_BASIS_COMPANIES, INDUSTRY_COMPANY_OPTIONS
from core.module_energy_landscape import (
    LANDSCAPE_PV_TYPE_OPTIONS,
    LANDSCAPE_TRACTOR_LENGTH_M,
    LANDSCAPE_TRACTOR_TURN_RADIUS_M,
    LANDSCAPE_TRACTOR_WIDTH_M,
)
from core.js_profiles import build_js_profiles


@st.cache_data
def cached_js_profiles():
    """Bedarfsprofile Jüchen Süd für die Vorschau (unabhängig vom Konzept)."""
    weather_df = Simulator().weather_df
    return build_js_profiles(weather_df.index, weather_df["temp_air"].to_numpy())
from core.functions_web_support import *
from core.functions_plot import *



# Mapping: PV type name to id
pv_name_to_id = {
    "Windschutzwand": 0,
    "Lärmschutzwand": 1,
    "Dach": 2,
    "Böschung": 3,
}


# Industry columns order
industry_order_all = [industry_csv_mapping[i] for i in INDUSTRY_COMPANY_OPTIONS]



# create data objects for in- and output
Input = GuiInput()
Output = SimOutput()

# Streamlit layout
st.set_page_config(layout="centered")

# Logos as base64 for accurate placement in html wrapper
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


# Initial st.session.state variables definition
# Resistant to rerun of site, only changing with actual Simulation (button)
if "simulation_ran" not in st.session_state:
    st.session_state.simulation_ran = False
if "sim_output" not in st.session_state:
    st.session_state.sim_output = Output

# Title
st.write("\n")
st.title("Energiesystem Modellierung - Innovationspark Jüchen")
st.write("### Erzeugung Eingabewerte")

# ---------------- Generation Input ----------------
with st.container(key="Erzeugung", width=1000, height='content'):

    # Tabs within Generation container
    tab1, tab2 = st.tabs(["Solarautobahn", "Energielandschaft"])

    # ---------------- Solar highway ----------------
    with tab1:
        col1_tab1, col2_tab1 = st.columns(2)
        script_dir = os.path.dirname(os.path.abspath(__file__))

        # Input multiselects
        with col1_tab1:
            Input.h_highways = st.multiselect("Autobahn auswählen", ["A44", "A46"])
            h_selected_names = st.multiselect("PV-Typ", ["Lärmschutzwand", "Windschutzwand", "Dach", "Böschung"])
            Input.h_pv_types = [pv_name_to_id[name] for name in h_selected_names]

            # dynamic info box
            st.write('\n')
            if not Input.h_highways or not Input.h_pv_types:
                st.info("Solarautobahn deaktiviert.")
            else:
                st.info("Solarautobahn aktiv.")

        # Dynamic Input visualization via folium
        with col2_tab1:
            pv_geojson_mapping_col2_tab1 = {
                "A44": "a44_beide.geojson",
                "A46": "a46_beide.geojson",
            }

            m = folium.Map(location=[51.06280, 6.49554], zoom_start=12)

            for highway in Input.h_highways:
                selected_file = pv_geojson_mapping_col2_tab1[highway]
                geojson_path = os.path.join(script_dir,"data", "inputs", "geometry", selected_file)

                with open(geojson_path, "r", encoding="utf-8") as f:
                    geojson_data = json.load(f)

                folium.GeoJson(
                    geojson_data,
                    name=f"{highway}"
                ).add_to(m)

            folium.LayerControl().add_to(m)
            st_data = st_folium(m, width=400, height=400)

    # ---------------- Energy landscape ----------------
    with tab2:
        col1_tab2, col2_tab2 = st.columns(2)

        # Input segments and selectbox
        with col1_tab2:
            Input.el_build_state = st.segmented_control(
                "Ausbaugrad der Energielandschaft in %",
                options=[0, 50, 100],
                default=0,
                format_func=lambda x: f"{x:.0f}%"
            )

            Input.el_pv_type = st.selectbox(
                "PV-Typ",
                list(LANDSCAPE_PV_TYPE_OPTIONS),
                format_func=lambda pv_type: LANDSCAPE_PV_TYPE_OPTIONS[pv_type],
            )

            Input.el_tractor_width = LANDSCAPE_TRACTOR_WIDTH_M
            Input.el_tractor_length = LANDSCAPE_TRACTOR_LENGTH_M
            Input.el_tractor_turn_radius = LANDSCAPE_TRACTOR_TURN_RADIUS_M
            st.caption(
                f"Die Reihenabstände sind für landwirtschaftliche Maschinen mit "
                f"{LANDSCAPE_TRACTOR_WIDTH_M:.0f} m Arbeitsbreite ausgelegt (Länge "
                f"{LANDSCAPE_TRACTOR_LENGTH_M:.0f} m, Wenderadius "
                f"{LANDSCAPE_TRACTOR_TURN_RADIUS_M:.2f} m)".replace(".", ",") + "."
            )

            # dynamic info box
            Input.el_build_state = 0 if Input.el_build_state is None else Input.el_build_state
            if Input.el_build_state == 0:
                st.info("Energielandschaft deaktiviert.")
            else:
                st.info("Energielandschaft aktiv.")


        # Dynamic Input visualization via folium
        with col2_tab2:
            # Geometrien aus core/auxiliary/export_landscape_geometries.py (27-m-Auslegung)
            pv_geojson_name = {5: "vertical", 4: "tracking"}

            if Input.el_build_state != 0 and Input.el_build_state is not None:
                selected_file = f"landscape_{pv_geojson_name[Input.el_pv_type]}_{Input.el_build_state}.geojson"
                geojson_path = os.path.join(script_dir, "web_frontend", "geometries", selected_file)

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


# Separation line
col1, col2, col3 = st.columns([0.05, 0.9, 0.05])
with col2:
    st.divider()


# ---------------- Consumption Input ----------------
st.write("### Verbrauch Eingabewerte")

with st.container(key="Verbrauch", width=1500, height='content'):

    tab4, tab5, tab6 = st.tabs(["Industriegebiet", "Green Energy Hub", "Neubaugebiet Jüchen Süd"])

    # ---------------- Industrial Area ----------------
    with tab4:
        col1_tab4, col2_tab4 = st.columns(2)

        with col1_tab4:
            industry_mode = st.segmented_control(
                "Unternehmensauswahl",
                options=["Basis-Variante Elsbachtal", "Unternehmen selbst zusammenstellen"],
                default="Basis-Variante Elsbachtal",
                key="industry_mode",
            )

            if industry_mode == "Unternehmen selbst zusammenstellen":
                st.write("Wähle bis zu 5 Unternehmen (Duplikate möglich):")
                slot_options = [None] + list(INDUSTRY_COMPANY_OPTIONS.keys())
                Input.i_companies = []
                for i in range(5):
                    choice = st.selectbox(
                        f"Unternehmen {i + 1}",
                        options=slot_options,
                        index=slot_options.index(ELSBACHTAL_BASIS_COMPANIES[i]),
                        format_func=lambda x: "Keine" if x is None else INDUSTRY_COMPANY_OPTIONS[x],
                        key=f"selection_{i}"
                    )
                    if choice is not None:
                        Input.i_companies.append(choice)
            else:
                Input.i_companies = list(ELSBACHTAL_BASIS_COMPANIES)
                st.write("Je ein Unternehmen jedes Typs:")
                st.markdown("\n".join(f"- {INDUSTRY_COMPANY_OPTIONS[i]}" for i in ELSBACHTAL_BASIS_COMPANIES))

        # Explanation expander
        with col2_tab4:
            Input.i_heat_cooling_electric = st.toggle("Mit Wärme/Kälte Stromverbrauch?", value=True)
            expander = st.expander("Erklärung Wärme/Kälte")
            expander.write('''
    Bei Auswahl "ohne Wärme/Kälte Stromverbrauch" werden fossiler Energiequellen für Wärme benutzt und es gibt keine Kälte

    Bei Auswahl "mit Wärme/Kälte Stromverbrauch" werden reversible Luftwärmepumpen und Geothermie-Sonden verwendet
            ''')

            # Dynamic info box
            st.write('\n')
            if not Input.i_companies:
                st.info("Industriegebiet deaktiviert.")
            else:
                st.info("Industriegebiet aktiv.")

        preview_csv_path = os.path.join(
            script_dir,
            "data",
            "inputs",
            "Projekt_04_Lastgaenge_Industriegebiet_und_nPro_Waerme_Kaelte.csv"
        )

        expander = st.expander("Erklärung Unternehmen")
        with expander:

            st.markdown('''
    1. **Entsorgung:**  
    5 1/2 Tage Woche, Kein Schichtbetrieb  
                        Jahresbedarf: 7,1 GWh, Anlehnung an Schönmackers Umweltdienste

    2. **Stahl:**  
    5 Tage Woche, 3-Schicht-Betrieb  
                        Jahresbedarf: 4,5 GWh, Anlehnung an TecPro

    3. **Logistik und Lagerung:**  
    5 Tage Woche, Teilweise Samstag und Sonntag Betrieb, Kein Schichtbetrieb  
                        Jahresbedarf: 1,2 GWh, Anlehnung an CTJ Janssen

    4. **Schrott- und Metallhandel:**  
    5 Tage Woche, Kein Schichtbetrieb  
                        Jahresbedarf: 1,5 GWh, Anlehnung an Willi Jenner

    5. **Büro:**  
    5 Tage Woche, Kein Schichtbetrieb  
                        Jahresbedarf: 0,6 GWh, Anlehnung an Marvin Wickenhäuser
            ''')

            fig_annual_all = plot_industry_annual_energy(
                preview_csv_path,
                ordered_columns=industry_order_all,
                title="Jahresenergiebedarf aller Unternehmensprofile (inkl. Wärme & Kälte)"
            )
            st.pyplot(fig_annual_all)

        selected_columns = [industry_csv_mapping[i] for i in Input.i_companies if i in industry_csv_mapping]
        selected_columns = list(dict.fromkeys(selected_columns))

        # Plot example week of selected companies
        if selected_columns:
            st.write("#### Beispielhafte Wochenlastgänge der ausgewählten Unternehmen (inkl. Wärme & Kälte)")

            fig_preview = plot_industry_preview(
                preview_csv_path,
                selected_columns=selected_columns,
                start="2017-03-05"
            )
            st.pyplot(fig_preview)

    # ---------------- Green energy hub ----------------
    with tab5:
        # Explanation expander
        expander = st.expander("Erklärung")
        with expander:
            st.write("""
    Green Energy Hub am Autobahnkreuz Jackerath nach der Machbarkeitsstudie
    **„Green Energy Hub – Autohof der Zukunft“** (inno2grid / PRSch, 10/2025, Zieljahr 2035).

    - Ladecluster: Lkw MCS, Lkw Overnight CCS, Pkw HPC und (nur Erweiterung) Pkw-Parkhaus AC
    - Gebäude, PV auf Dächern und Carports, Batteriespeicher
    - H₂-Tankstelle mit Elektrolyseur und H₂-Speicher
    - **Basis:** ohne Parkhaus · **Erweiterung:** mit Parkhaus (AC-Laden, zusätzliche PV)

    **Betriebsführung (regelbasiert)**
    - Der Elektrolyseur nutzt Strom-Überschuss des Parks. Fällt der H₂-Speicher unter den
      Mindestfüllstand, läuft er mit voller Leistung, notfalls mit Netz- oder Batteriestrom.
    - Die Batterie nimmt verbleibenden Überschuss auf und deckt Defizite.
    - Restlicher Überschuss wird eingespeist, Fehlmengen werden aus dem Netz bezogen.
    - Ladeprofile sind synthetisch (Tagesform × Wochentag), skaliert auf die Jahresenergie der Studie.
            """)

        geh_variant = st.segmented_control(
            "Variante",
            options=["Keine", "Basis", "Erweiterung"],
            default="Basis",
        )
        Input.geh_variant = "Keine" if geh_variant is None else geh_variant

        if Input.geh_variant == "Keine":
            st.info("Green Energy Hub ist deaktiviert.")
        else:
            geh_v = GEH_VARIANTS[Input.geh_variant]

            with st.expander("Anlagenparameter (Machbarkeitsstudie)"):
                st.table(geh_variant_table(geh_v))

            # Widget-Keys je Variante, damit die Vorbelegung beim Variantenwechsel mitwechselt
            k = Input.geh_variant
            with st.expander("Parameter anpassen"):
                col_geh1, col_geh2 = st.columns(2)
                with col_geh1:
                    Input.geh_pv_kwp = float(st.number_input(
                        "PV am Hub [kWp]", min_value=0.0, max_value=20_000.0,
                        value=float(geh_v["pv_kwp"]), step=50.0, key=f"geh_pv_kwp_{k}",
                    ))
                    Input.geh_battery_kwh = float(st.number_input(
                        "Batteriekapazität [kWh]", min_value=0.0, max_value=100_000.0,
                        value=float(geh_v["battery_kwh"]), step=100.0, key=f"geh_battery_kwh_{k}",
                    ))
                    Input.geh_battery_kw = float(st.number_input(
                        "Batterieleistung [kW]", min_value=0.0, max_value=50_000.0,
                        value=float(geh_v["battery_kw"]), step=100.0, key=f"geh_battery_kw_{k}",
                    ))
                    Input.geh_h2_demand_t_per_a = float(st.number_input(
                        "H₂-Nachfrage Tankstelle [t/a]", min_value=0.0, max_value=5_000.0,
                        value=float(geh_v["h2_demand_t_per_a"]), step=5.0, key=f"geh_h2_demand_{k}",
                    ))
                with col_geh2:
                    Input.geh_electrolyzer_power_kw = float(st.number_input(
                        "Elektrolyseur-Leistung [kW]", min_value=0.0, max_value=50_000.0,
                        value=float(geh_v["electrolyzer_kw"]), step=100.0, key=f"geh_el_kw_{k}",
                        help="Nennleistung des Elektrolyseurs. 0 = deaktiviert.",
                    ))
                    Input.geh_electrolyzer_efficiency = float(st.slider(
                        "System-Wirkungsgrad Elektrolyseur", min_value=0.50, max_value=0.85,
                        value=float(geh_v["electrolyzer_eff"]), step=0.01, key=f"geh_el_eff_{k}",
                        help="LHV-bezogener Systemwirkungsgrad (typisch 65–75 %).",
                    ))
                    Input.geh_storage_capacity_kwh = float(st.number_input(
                        "H₂-Speicherkapazität [kWh_H₂]", min_value=0.0, max_value=1_000_000.0,
                        value=float(geh_v["h2_storage_kwh"]), step=1_000.0, key=f"geh_h2_storage_{k}",
                    ))
                    Input.geh_h2_min_soc = float(st.slider(
                        "Mindestfüllstand H₂-Speicher", min_value=0.0, max_value=1.0,
                        value=float(geh_v["h2_min_soc"]), step=0.05, key=f"geh_h2_min_soc_{k}",
                        help="Unterhalb läuft der Elektrolyseur mit voller Leistung, auch mit Netzstrom.",
                    ))


        # ---------------- Jüchen Süd ----------------
        with tab6:
            expander = st.expander("Erklärung")
            with expander:
                st.write("""
    Stadtteilentwicklung Jüchen Süd nach dem **Energiekonzept des Fraunhofer IEG**
    (Abschlussveranstaltung 16.10.2026, vorläufige Ergebnisse), Basis-Variante:
    Bedarfsszenario „moderat“, 3 Quartiere.

    - **Warmes Netz:** zentrale Luft-Wärmepumpe speist ein Wärmenetz mit 40–50 °C,
      Tankspeicher in der Energiezentrale, Heizstab zur Warmwasser-Nachheizung.
    - **Kaltes Netz:** Anergienetz mit 10–25 °C verteilt Umweltwärme, Booster-Wärmepumpen
      in den Gebäuden heben auf Heiz- und Warmwassertemperatur.
    - **Dezentral:** jedes Gebäude hat eine eigene Grundwasser-Wärmepumpe.

    Modelliert werden Nutzerstrom, E-Mobilität und der Strombedarf der Wärme- und
    Kälteversorgung. Wärmeprofile entstehen aus den Wetterdaten, die Wärmepumpen-
    Effizienz hängt von Quell- und Zieltemperatur ab. Die Agri-PV der Studie (5,56 MW)
    ist Teil der Energielandschaft und wird hier nicht doppelt gezählt.
                """)

            js_concept = st.segmented_control(
                "Versorgungskonzept",
                options=["Aus", "Warmes Netz", "Kaltes Netz", "Dezentral"],
                default="Aus",
            )
            Input.js_concept = "Aus" if js_concept is None else js_concept

            if Input.js_concept == "Aus":
                st.info("Jüchen Süd ist deaktiviert.")
            else:
                js_c = JS_CONCEPTS[Input.js_concept]

                with st.expander("Anlagenparameter (Energiekonzept, Basis-Variante)"):
                    st.table(js_concept_table(js_c))

                # Widget-Keys je Konzept, damit die Vorbelegung beim Wechsel mitwechselt
                k = Input.js_concept
                with st.expander("Parameter anpassen"):
                    col_js1, col_js2 = st.columns(2)
                    with col_js1:
                        Input.js_hp_kw = float(st.number_input(
                            f"{js_c['hp_label']} [kW_th]", min_value=0.0, max_value=20_000.0,
                            value=float(js_c["hp_kw"]), step=50.0, key=f"js_hp_kw_{k}",
                        ))
                        Input.js_heater_kw = float(st.number_input(
                            "Heizstab dezentral [kW]", min_value=0.0, max_value=20_000.0,
                            value=float(js_c["heater_kw"]), step=50.0, key=f"js_heater_kw_{k}",
                        ))
                    with col_js2:
                        Input.js_tank_kwh = float(st.number_input(
                            "Tankspeicher [kWh_th]", min_value=0.0, max_value=100_000.0,
                            value=float(js_c["tank_kwh"]), step=100.0, key=f"js_tank_kwh_{k}",
                            help="Thermischer Speicher, puffert Spitzen oberhalb der Wärmepumpenleistung.",
                        ))

                st.write("#### Beispielwoche der Bedarfe Jüchen Süd")
                st.pyplot(plot_js_weekly_profile(cached_js_profiles()))


# Separation line
col1, col2, col3 = st.columns([0.05, 0.9, 0.05])
with col2:
    st.divider()


# ---------------- Battery input ----------------
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
        options=[0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0],
        value=1.0,
        format_func=lambda x: f"{x:.2g} C"
    )

    # Dynamic info box
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


# ---------------- Run simulation ----------------
with col2:
    run = st.button(
        "⚡ Simulation starten",
        type="primary",
        use_container_width=True
    )
st.space(size='small')

# if button is pressed, actual simulation is started
if run:
    with st.spinner("Simulation läuft..."):
        Output = run_simulation(Input)          # Simulation call

    st.success("Simulation abgeschlossen.")

    # Safe simulation state and output in session state
    st.session_state.simulation_ran = True
    st.session_state.sim_output = Output
    #print('\nOutput Daten:\n', Output)     #debug
    #st.write(Output.res_df.columns)        #debug





# ---------------- Support function: KPIs and Energy flow visualization ----------------
st.write("### Ergebnisse")
with st.spinner("Visualisierung wird erstellt..."):
    fig_synergy = build_synergy_diagram(Input, st.session_state.sim_output)
    st.plotly_chart(fig_synergy, width="stretch")



# ---------------- Additional Results (if Sim ran) ----------------
if st.session_state.get("simulation_ran") and "sim_output" in st.session_state:

    sim_output = st.session_state.sim_output

    # Drop zero columns
    protected_cols = ["Bilanz [kW]"]
    zero_cols = [
        col for col in sim_output.res_df.columns
        if col not in protected_cols and sim_output.res_df[col].fillna(0).eq(0).all()
    ]

    sim_output.res_df = sim_output.res_df.drop(columns=zero_cols)


    # ---------------- Net balance Plot ----------------
    st.write("### Bilanzverlauf")

    # Balance from res_df (no battery) or bs_df (if battery)
    fig0 = plot_balance(sim_output)
    st.pyplot(fig0)


    # ---------------- Detailed information expander ----------------
    with st.expander("Lastgang Infos anzeigen", expanded=False):
        desc_stats = sim_output.res_df
        desc = desc_stats.describe().loc[["mean", "min", "max"]].round(0)
        desc.loc["sum [kWh]"] = desc_stats.sum()/4
        desc.loc["sum [kWh]"] = desc.loc["sum [kWh]"].round(0)
        desc = desc.loc[["sum [kWh]", "mean", "min", "max"]]
        st.dataframe(desc)

        # Plot 1: Generation
        fig = plot_generation(sim_output)
        st.pyplot(fig)

        # Plot 2: Consumption
        fig2 = plot_consumption(sim_output)
        st.pyplot(fig2)



    # ---------------- Battery details expander ----------------
    if not sim_output.bs_df.empty:

        with st.expander("Batterieergebnisse anzeigen", expanded=False):

            # Stats
            bs_desc_stats = sim_output.bs_df.drop(columns=['soc_kwh'])
            bs_desc = bs_desc_stats.describe().loc[["mean", "min", "max"]].round(0)
            bs_desc.loc["sum [kWh]"] = bs_desc_stats.sum()/4
            bs_desc.loc["sum [kWh]"] = bs_desc.loc["sum [kWh]"].round(0)
            bs_desc = bs_desc.loc[["sum [kWh]", "mean", "min", "max"]]

            bs_desc = bs_desc.rename(columns={
                "balance_kw": "Bilanz ohne Batterie [kW]",
                "new_balance_kw": "Bilanz mit Batterie [kW]",
                "battery_power_kw": "Batterieleistung [kW]",
            })
            st.dataframe(bs_desc)


            # Battery Plots
            fig3, fig4 = plot_battery_comparison(sim_output)
            # Plot 1: Balance with battery storage
            st.pyplot(fig3)
            # Plot 2: Balance withOUT battery storage
            st.pyplot(fig4)


            # Plot 3: State of charge
            fig5 = plot_soc(Input, sim_output)
            st.pyplot(fig5)
