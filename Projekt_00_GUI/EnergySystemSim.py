import streamlit as st
import os
import folium
from streamlit_folium import st_folium
import json
import pandas as pd
import matplotlib.pyplot as plt
import math

#Überschrift
st.title("Energiesystem Modelierung - Innovationspark Jüchen")
st.write("### Erzeugung Eingabewerte")


# Fester Container für Darstellung der Erzeugungseingabe -> Fixierte Größe damit nachfolgender Inhalt nicht rutscht
with st.container(key="Erzeugung", width=1000, height=500):

    tab1, tab2, tab3 = st.tabs(["Solarautobahn", "Energielandschaft", "Industriegebiet"])

    with tab1:
        col1_tab1, col2_tab1 = st.columns(2)

        script_dir = os.path.dirname(os.path.abspath(__file__))

        with col1_tab1:
            highway_selection = st.multiselect("Autobahn auswählen", ["A44", "A46"])
            highway_pv_type = st.multiselect("PV-Typ", ["Lärmschutzwand", "Windschutzwand", "Dach", "Böschung"])

        with col2_tab1:
            # Mapping Autobahn → GeoJSON
            pv_geojson_mapping_col2_tab1 = {
                "A44": "a44_beide.geojson",
                "A46": "a46_beide.geojson",
            }

            # Karte erstellen
            m = folium.Map(location=[51.06280, 6.49554], zoom_start=12)

            # Loop über ausgewählte Autobahnen
            for highway in highway_selection:
                selected_file = pv_geojson_mapping_col2_tab1[highway]
                geojson_path = os.path.join(script_dir, "Geometry", selected_file)

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

    with tab2:
        col1_tab2, col2_tab2 = st.columns(2)
        with col1_tab2:
            energy_landscape_pv_type = st.selectbox("PV-Typ", ["Vertikal", "Horizontal"])
            tractor_width = st.segmented_control("Traktorbreite", ["10m", "100m", "200m"], default="100m")

        with col2_tab2:
            # --- Mapping PV-Typ → GeoJSON-Datei ---
            pv_geojson_mapping_col2_tab2 = {
                ("Vertikal", "10m"): "P_02_Agri_PV_Breite10.0_Laenge10.0_Wenderadius10.0_Vertikal.geojson",
                ("Vertikal", "100m"): "P_02_Agri_PV_Breite100.0_Laenge100.0_Wenderadius100.0_Vertikal.geojson",
                ("Vertikal", "200m"): "P_02_Agri_PV_Breite200.0_Laenge200.0_Wenderadius200.0_Vertikal.geojson",
                ("Horizontal", "10m"): "P_02_Agri_PV_Breite10.0_Laenge10.0_Wenderadius10.0_Horizontal.geojson",
                ("Horizontal", "100m"): "P_02_Agri_PV_Breite100.0_Laenge100.0_Wenderadius100.0_Horizontal.geojson",
                ("Horizontal", "200m"): "P_02_Agri_PV_Breite200.0_Laenge200.0_Wenderadius200.0_Horizontal.geojson",
            }

            selected_file = pv_geojson_mapping_col2_tab2[energy_landscape_pv_type, tractor_width]
            geojson_path = os.path.join(script_dir, "Geometry", selected_file)

            # GeoJSON laden
            with open(geojson_path, "r", encoding="utf-8") as f:
                geojson_data = json.load(f)

            # Karte erstellen
            m = folium.Map(location=[51.06280, 6.49554], zoom_start=12)

            # GeoJSON Layer hinzufügen
            folium.GeoJson(
                geojson_data,
                name=f"{energy_landscape_pv_type}{tractor_width}"
            ).add_to(m)

            # Layer Control (falls mehrere Layer kommen)
            folium.LayerControl().add_to(m)

            # Karte in Streamlit rendern
            st_data = st_folium(m, width=400, height=400)

    with tab3:
        pv_build_industry_roof = st.slider("Dachfläche mit PV bebaut [%]", 0, 100)
        st.write(f"{pv_build_industry_roof/100*50000} qm Dachfläche mit PV bebaut")
        parking_ground_pv_activated = st.toggle("Parkplatz PV instalieren?")




st.write("### Verbrauch Eingabewerte")

with st.container(key="Verbrauch", width=1500, height=600):

    tab4, tab5, tab6 = st.tabs(["Industriegebiet", "Green Energy Hub", "Neubaugebiet Jüchen Süd"])

    with tab4:
        options = ["Logistik", "Stahl", "Entsorgung", "Lebensmittel", "Büro"]

        st.write("Wähle bis zu 5 Unternehmen (Duplikate möglich):")

        selections = []
        for i in range(5):
            choice = st.selectbox(f"Unternehmen {i + 1}", ["Keine"] + options, key=f"selection_{i}")
            selections.append(choice)

        valid_selections = [s for s in selections if s != "Keine"]


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

