import streamlit as st
import os
import folium
from streamlit_folium import st_folium
import json
from pathlib import Path
from core.io_types import GuiInput, SimOutput
from Simulation import run_simulation

st.set_page_config(layout="centered")

Input = GuiInput()
Output = SimOutput()

#Überschrift
st.title("Energiesystem Modelierung - Innovationspark Jüchen")
st.write("### Erzeugung Eingabewerte")


# Fester Container für Darstellung der Erzeugungseingabe -> Fixierte Größe damit nachfolgender Inhalt nicht rutscht
with st.container(key="Erzeugung", width=1000, height=500):

    tab1, tab2 = st.tabs(["Solarautobahn", "Energielandschaft"])

    # SOLARAUTOBAHN
    with tab1:
        col1_tab1, col2_tab1 = st.columns(2)

        script_dir = os.path.dirname(os.path.abspath(__file__))

        with col1_tab1:
            Input.highways = st.multiselect("Autobahn auswählen", ["A44", "A46"])
            Input.h_pv_types = st.multiselect("PV-Typ", ["Lärmschutzwand", "Windschutzwand", "Dach", "Böschung"])

        with col2_tab1:
            # Mapping Autobahn → GeoJSON
            pv_geojson_mapping_col2_tab1 = {
                "A44": "a44_beide.geojson",
                "A46": "a46_beide.geojson",
            }

            # Karte erstellen
            m = folium.Map(location=[51.06280, 6.49554], zoom_start=12)

            # Loop über ausgewählte Autobahnen
            for highway in Input.highways:
                selected_file = pv_geojson_mapping_col2_tab1[highway]
                geojson_path = os.path.join(script_dir, "geometry", selected_file)

                # GeoJSON laden
                with open(geojson_path, "r", encoding="utf-8") as f:
                    geojson_data = json.load(f)

                # Layer hinzufügen
                folium.GeoJson(
                    geojson_data,
                    name=f"{highway}"
                ).add_to(m)

            # Layer Control aktivieren
            folium.LayerControl().add_to(m)

            # Karte in Streamlit rendern
            st_data = st_folium(m, width=400, height=400)

    #ENERGIELANDSCHAFT
    with tab2:
        col1_tab2, col2_tab2 = st.columns(2)
        with col1_tab2:
            Input.el_pv_type = st.selectbox("PV-Typ", ["Vertikal (Zaun, Nord-Süd)",
                                                       "Horizontal (aufgeständert, Ost-West)",
                                                       "Horizontal mit Single-Axis-Tracking (aufgeständert, Nord-Süd)"])
            Input.tractor_width = st.segmented_control("Traktorbreite", ["9m", "12m", "15m"], default="12m")
            Input.tractor_length = st.segmented_control("Traktorlänge", ["12m", "15m", "18m"], default="15m")
            Input.tractor_turn_radius = st.segmented_control("Traktor-Wenderadius", ["6m", "9m", "12m"], default="9m")



        with col2_tab2:
            # --- Mapping PV-Typ → GeoJSON-Datei ---
            pv_geojson_mapping_col2_tab2 = {
                "Vertikal (Zaun, Nord-Süd)":
                    "Geometry_Vertikal_Traktorbreite_20m.geojson",
                "Horizontal (aufgeständert, Ost-West)":
                    "Geometry_Horizontal_Traktorbreite_20m.geojson",
                "Horizontal mit Single-Axis-Tracking (aufgeständert, Nord-Süd)":
                    "Geometry_Horizontal_Traktorbreite_20m.geojson",
            }

            selected_file = pv_geojson_mapping_col2_tab2[Input.el_pv_type]
            geojson_path = os.path.join(script_dir, "geometry", selected_file)

            # GeoJSON laden
            with open(geojson_path, "r", encoding="utf-8") as f:
                geojson_data = json.load(f)

            # Karte erstellen
            m = folium.Map(location=[51.07596, 6.48599], zoom_start=14)

            # GeoJSON Layer hinzufügen
            folium.GeoJson(
                geojson_data,
                name=f"{Input.el_pv_type}{Input.tractor_width}"
            ).add_to(m)

            # Layer Control (falls mehrere Layer kommen)
            folium.LayerControl().add_to(m)

            # Karte in Streamlit rendern
            st_data = st_folium(m, width=400, height=400)


st.write("### Verbrauch Eingabewerte")

with st.container(key="Verbrauch", width=1500, height=1000):

    tab4, tab5, tab6 = st.tabs(["Industriegebiet", "Green Energy Hub", "Neubaugebiet Jüchen Süd"])

    #INDUSTRIEGEBIET
    with tab4:
        col1_tab4, col2_tab4 = st.columns(2)

        with col1_tab4:
            options = ["Entsorgung",
                       "Stahl, 5-Tage-Woche, 3-Schicht",
                       "Logistik und Lagerung",
                       "Schrott- und Metallhandel",
                       "Lagerung",
                       "Büro",
                       "Logistik Lebensmittel",
                       "Stahl, 7-Tage-Woche, 2-Schicht" ]

            st.write("Wähle bis zu 5 Unternehmen (Duplikate möglich):")

            Input.companies = []
            for i in range(5):
                choice = st.selectbox(f"Unternehmen {i + 1}", ["Keine"] + options, key=f"selection_{i}")
                Input.companies.append(choice)

            valid_selections = [s for s in Input.companies if s != "Keine"]


        with col2_tab4:
            Input.is_heat_cooling_electric = st.toggle("Mit Wärme/Kälte Stromverbrauch?")
            expander = st.expander("Erklärung Wärme/Kälte")
            expander.write('''
                                Bei Auswahl "ohne Wärme/Kälte Stromverbrauch" werden fossiler Energiequellen für Wärme benutzt und es gibt keine Kälte
                                
                                Bei Auswahl "mit Wärme/Kälte Stromverbrauch" werden reversible Luftwärmepumpen und Geothermie-Sonden verwendet
                                ''')

        expander = st.expander("Erklärung Unternehmen")
        expander.write('''
                    1. Entsorgung: 
                    5 1/2 Tage Woche, Kein Schichtbetrieb, Anlehnung an Schönmackers Umweltdienste

                    2. Stahl: 
                    5 Tage Woche, 3-Schicht-Betrieb, Anlehnung an TecPro

                    3. Logistik und Lagerung: 
                    5 Tage Woche, Teilweise Samstag und Sonntag Betrieb, Kein Schichtbetrieb, Anlehnung an CTJ Janssen

                    4. Schrott- und Metallhandel: 
                    5 Tage Woche, Kein Schichtbetrieb, Anlehnung an Willi Jenner

                    5. Lagerung: 
                    5 Tage Woche, Kein Schichtbetrieb, Anlehnung an Kleine Logistik

                    6. Büro: 
                    5 Tage Woche, Kein Schichtbetrieb, Anlehnung an Marvin Wickenhäuser

                    7. Logistik Lebensmittel: 
                    6 1/2 Tage Woche, Kein Schichtbetrieb, Anlehnung an CTJ Janssen

                    8. Stahl: 
                    7 Tage Woche, 2-Schicht-Betrieb, Anlehnung an TecPro
                        ''')

    with tab5:
        col1_tab5, col2_tab5 = st.columns(2)

        with col1_tab5:
            electric_charger = st.slider("Anzahl Elektroladesäulen", 1, 30)
            elctric_cars_per_day = st.slider("Anzahl beladener Elektroautos pro Tag", 0, electric_charger*50)


        with col2_tab5:
            electric_charger = st.slider("Anzahl Wasserstopfzapfsäulen", 1, 5)
            elctric_cars_per_day = st.slider("Anzahl beladener Wasserstoffautos pro Tag", 0, electric_charger * 150)

        expander = st.expander("Erklärung")
        expander.write('''
            Pro Wasserstoffzapfsäule wird ein maximaler Durchsatz von 150 Autos/Tag angenommen.
            Für Elektroladesäulen ist die Annahme 50 Autos/Tag.
        ''')

if st.button("Simulation starten"):
    Output = run_simulation(Input)

    st.write("Der neue Traktor-Wenderadius ist:", Output.TEST_NUMBER)

st.markdown(
    """
    <style>
    /* Vollbild-SVG Container */
    .full-width-svg {
        width: 100vw;
        margin-left: calc(-50vw + 50%);
        padding: 0;
        overflow-x: hidden;
    }
    .full-width-svg svg {
        width: 100vw;
        height: auto;
        display: block;
    }
    </style>
    """,
    unsafe_allow_html=True
)
st.title("Energiesystem – Visualisierung")

BASE_DIR = Path(__file__).resolve().parent
svg_path1 = BASE_DIR / "assets" / "static_background.svg"
svg_code1 = svg_path1.read_text(encoding="utf-8")



svg_path2 = BASE_DIR / "assets" / "arrows.svg"
svg_code2 = svg_path2.read_text(encoding="utf-8")

# SVG-Tag anpassen: width 100%, height auto
svg_code1 = svg_code1.replace(
    "<svg", '<svg style="width:100%; height:auto;"'
)
# SVG-Tag anpassen: width 100%, height auto
svg_code2 = svg_code2.replace(
    "<svg", '<svg style="width:100%; height:auto;"'
)
# Vollbreite SVG Container
st.markdown(f'<div class="full-width-svg">{svg_code1}</div>', unsafe_allow_html=True)

