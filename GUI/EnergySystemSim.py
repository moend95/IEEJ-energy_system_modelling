import streamlit as st
import os
import pandas as pd
import matplotlib.pyplot as plt
import math



st.title("Energiesystem Modelierung - Innovationspark Jüchen")
st.write("### Erzeugung Eingabewerte")

tab1, tab2, tab3, tab4 = st.tabs(["Solarautobahn", "Energielandschaft", "Industriegebiet", "Green Energy Hub"])

with tab1:
    col1, col2 = st.columns(2)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    image_files = {
        "A44": os.path.join(script_dir, "Pictures", "A44.png"),
        "A46": os.path.join(script_dir, "Pictures", "A46.png"),
    }

    with col1:
        highway_selection = st.selectbox("Autobahnabschnitt", image_files.keys())
        highway_pv_type = st.multiselect("PV-Typ", ["Lärmschutzwand", "Windschutzwand", "Dach", "Böschung"])

    with col2:
        st.image(image_files[highway_selection])


with tab2:
    st.markdown('<div class="tabs-erzeugung-eingabe">', unsafe_allow_html=True)
    energy_landscape_pv_type = st.selectbox("PV-Typ", ["Vertikal Ost-West", "Geneigt Süd", "Geneigt Süd Tracking"])
    tractor_width = st.segmented_control("Traktorbreite", ["1,40m", "2,20m", "3,00"])
    st.markdown('</div>', unsafe_allow_html=True)

with tab3:
    st.markdown('<div class="tabs-erzeugung-eingabe">', unsafe_allow_html=True)
    pv_build_industry_roof = st.slider("Dachfläche mit PV bebaut [%]", 0, 100)
    st.write(f"{pv_build_industry_roof/100*50000} qm Dachfläche mit PV bebaut")
    parking_ground_pv_activated = st.toggle("Parkplatz PV instalieren?")
    st.markdown('</div>', unsafe_allow_html=True)

with tab4:
    st.markdown('<div class="tabs-erzeugung-eingabe">', unsafe_allow_html=True)
    energy_hub_roof_pv_activated = st.toggle("Dach PV instalieren?")
    st.markdown('</div>', unsafe_allow_html=True)

st.write("### Verbrauch Eingabewerte")