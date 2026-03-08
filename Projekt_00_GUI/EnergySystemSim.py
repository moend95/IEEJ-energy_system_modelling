import sys
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path

# UNBEDINGT RAUS DAMIT NUR EIN WORKAROUND FÜR DIE VERWENDUNG VON ÜBERGELAGERTEN MODULEN
sys.path.append(str(Path(__file__).resolve().parent.parent))

import streamlit as st
import os
import folium
from streamlit_folium import st_folium
import json

from core.io_types import GuiInput, SimOutput
from Simulation import run_simulation
from functions.plot_functions import (
    plot_industry_preview,
    plot_industry_annual_energy,
    plot_green_hub_weekly_profiles,
    plot_green_hub_annual_energy
)

script_dir = os.path.dirname(os.path.abspath(__file__))

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


def format_energy(value_kwh):
    """
    Formatiert Energie kompakt für die Visualisierung.
    """
    value_kwh = float(value_kwh or 0)

    if value_kwh >= 1_000_000:
        return f"{value_kwh / 1_000_000:.2f} GWh/a"
    elif value_kwh >= 1_000:
        return f"{value_kwh / 1_000:.1f} MWh/a"
    else:
        return f"{value_kwh:.0f} kWh/a"


def build_synergy_diagram(inp, sim_output):
    """
    Bilanzorientierte Systemgrafik ohne Mittelknoten.

    Logik:
    1) Beide Erzeuger priorisieren zuerst das Industriegebiet
    2) Verbleibende lokale Erzeugung versorgt danach den Green Energy Hub
    3) Überschuss wird separat dargestellt
    4) Restdefizite werden über das Netz gedeckt
    """

    # -----------------------------
    # 1) Werte direkt aus Simulation
    # -----------------------------
    solar_energy = 0.0
    landscape_energy = 0.0
    industry_energy = 0.0
    green_hub_energy = 0.0
    total_generation = 0.0
    total_demand = 0.0
    coverage_percent = 0.0
    surplus = 0.0
    deficit = 0.0

    if sim_output is not None:
        solar_energy = max(float(getattr(sim_output, "h_sum_energy_kwh", 0) or 0), 0.0)
        landscape_energy = max(float(getattr(sim_output, "el_sum_energy_kwh", 0) or 0), 0.0)
        industry_energy = max(float(getattr(sim_output, "i_sum_energy_kwh", 0) or 0), 0.0)
        green_hub_energy = max(float(getattr(sim_output, "geh_sum_energy_kwh", 0) or 0), 0.0)

        total_generation = solar_energy + landscape_energy
        total_demand = industry_energy + green_hub_energy

        coverage = float(getattr(sim_output, "coverage_rate", 0) or 0)
        coverage_percent = max(0.0, min(coverage * 100.0, 100.0))

        balance = float(getattr(sim_output, "balance_energy_kwh", 0) or 0)
        if balance >= 0:
            surplus = balance
            deficit = 0.0
        else:
            surplus = 0.0
            deficit = abs(balance)

    # -----------------------------
    # 2) Energetische Deckung
    #    Priorität: Industrie -> Hub
    # -----------------------------
    local_supply_industry = min(total_generation, industry_energy)
    remaining_generation = max(total_generation - local_supply_industry, 0.0)

    local_supply_hub = min(remaining_generation, green_hub_energy)
    remaining_after_hub = max(remaining_generation - local_supply_hub, 0.0)

    grid_import_industry = max(industry_energy - local_supply_industry, 0.0)
    grid_import_hub = max(green_hub_energy - local_supply_hub, 0.0)

    grid_import_total = grid_import_industry + grid_import_hub
    surplus_local_energy = remaining_after_hub
    grid_export = surplus_local_energy

    # -----------------------------
    # 3) Quellenbezogene Aufteilung
    #    Beide Erzeuger priorisieren Industrie zuerst
    # -----------------------------
    total_gen_for_split = solar_energy + landscape_energy

    if total_gen_for_split > 0:
        solar_share = solar_energy / total_gen_for_split
        landscape_share = landscape_energy / total_gen_for_split
    else:
        solar_share = 0.0
        landscape_share = 0.0

    # Lokale Versorgung Industrie proportional aus beiden Erzeugern
    solar_to_industry = local_supply_industry * solar_share
    landscape_to_industry = local_supply_industry * landscape_share

    # Verbleibende Quellbeiträge nach Industrie
    solar_remaining = max(solar_energy - solar_to_industry, 0.0)
    landscape_remaining = max(landscape_energy - landscape_to_industry, 0.0)

    remaining_for_hub_split = solar_remaining + landscape_remaining
    if remaining_for_hub_split > 0:
        solar_share_hub = solar_remaining / remaining_for_hub_split
        landscape_share_hub = landscape_remaining / remaining_for_hub_split
    else:
        solar_share_hub = 0.0
        landscape_share_hub = 0.0

    solar_to_hub = local_supply_hub * solar_share_hub
    landscape_to_hub = local_supply_hub * landscape_share_hub

    solar_remaining_after_hub = max(solar_remaining - solar_to_hub, 0.0)
    landscape_remaining_after_hub = max(landscape_remaining - landscape_to_hub, 0.0)

    solar_to_surplus = solar_remaining_after_hub
    landscape_to_surplus = landscape_remaining_after_hub

    # Numerische Glättung
    def clamp_small(x, eps=1e-6):
        return 0.0 if abs(x) < eps else x

    solar_to_industry = clamp_small(solar_to_industry)
    landscape_to_industry = clamp_small(landscape_to_industry)
    solar_to_hub = clamp_small(solar_to_hub)
    landscape_to_hub = clamp_small(landscape_to_hub)
    solar_to_surplus = clamp_small(solar_to_surplus)
    landscape_to_surplus = clamp_small(landscape_to_surplus)

    # -----------------------------
    # 4) Texte für Boxen
    # -----------------------------
    solar_text = "nicht aktiv"
    if inp.highways and inp.h_pv_types:
        if solar_energy > 0:
            solar_text = f"Jahreserzeugung:<br>{format_energy(solar_energy)}"
        else:
            solar_text = "aktiv, noch ohne Ergebnis"

    landscape_text = "nicht aktiv"
    if inp.el_build_state != 0:
        if landscape_energy > 0:
            landscape_text = f"Jahreserzeugung:<br>{format_energy(landscape_energy)}"
        else:
            landscape_text = f"Ausbaugrad: {inp.el_build_state} %<br>aktiv, noch ohne Ergebnis"

    n_companies = len([c for c in inp.companies if c is not None]) if inp.companies else 0

    if industry_energy == 0:
        industry_status = "kein Bedarf"
    elif grid_import_industry == 0:
        industry_status = "gedeckt"
    elif local_supply_industry > 0:
        industry_status = "teilweise gedeckt"
    else:
        industry_status = "nicht gedeckt"

    industry_text = (
        f"Auswahl: {n_companies} Unternehmen"
        f"<br>Bedarf: {format_energy(industry_energy)}"
        f"<br>Lokal gedeckt: {format_energy(local_supply_industry)}"
        f"<br>Netzbezug: {format_energy(grid_import_industry)}"
        f"<br>Status: {industry_status}"
    )

    if green_hub_energy == 0:
        hub_status = "kein Bedarf"
    elif grid_import_hub == 0:
        hub_status = "gedeckt"
    elif local_supply_hub > 0:
        hub_status = "teilweise gedeckt"
    else:
        hub_status = "nicht gedeckt"

    hub_text = (
        f"H₂-Szenario: {inp.h2_load_scenario}"
        f"<br>El.-Szenario: {inp.e_load_scenario}"
        f"<br>Bedarf: {format_energy(green_hub_energy)}"
        f"<br>Lokal gedeckt: {format_energy(local_supply_hub)}"
        f"<br>Netzbezug: {format_energy(grid_import_hub)}"
        f"<br>Status: {hub_status}"
    )

    grid_text = (
        f"Import: {format_energy(grid_import_total)}"
        f"<br>Export: {format_energy(grid_export)}"
    )

    surplus_text = (
        f"Überschuss: {format_energy(surplus_local_energy)}"
        f"<br>potenziell speicherbar"
    )

    # -----------------------------
    # 5) Knoten
    # -----------------------------
    nodes = {
        "surplus": {
            "x": 0, "y": 0.5,
            "label": "Überschuss",
            "info": surplus_text,
            "color": "#F3E8FF"
        },
        "solar": {
            "x": 0.28, "y": 0.68,
            "label": "Solarautobahn",
            "info": solar_text,
            "color": "#A7D8FF"
        },
        "landscape": {
            "x": 0.28, "y": 0.3,
            "label": "Energielandschaft",
            "info": landscape_text,
            "color": "#BFEFC4"
        },
        "industry": {
            "x": 0.78, "y": 0.68,
            "label": "Industriegebiet",
            "info": industry_text,
            "color": "#E8E8E8"
        },
        "hub": {
            "x": 0.78, "y": 0.3,
            "label": "Green Energy Hub",
            "info": hub_text,
            "color": "#D8F5D0"
        },
        "grid": {
            "x": 1.18, "y": 0.5,
            "label": "Netz",
            "info": grid_text,
            "color": "#FDE7C6"
        }
    }

    # -----------------------------
    # 6) Flüsse
    # -----------------------------
    flows = []

    # Beide Erzeuger -> Industrie zuerst
    if solar_to_industry > 0:
        flows.append({
            "source": "solar",
            "target": "industry",
            "color": "#4A90E2",
            "label": format_energy(solar_to_industry)
        })

    if landscape_to_industry > 0:
        flows.append({
            "source": "landscape",
            "target": "industry",
            "color": "#2E8B57",
            "label": format_energy(landscape_to_industry)
        })

    # Danach beide Erzeuger -> Hub
    if solar_to_hub > 0:
        flows.append({
            "source": "solar",
            "target": "hub",
            "color": "#7DB7F0",
            "label": format_energy(solar_to_hub)
        })

    if landscape_to_hub > 0:
        flows.append({
            "source": "landscape",
            "target": "hub",
            "color": "#16A34A",
            "label": format_energy(landscape_to_hub)
        })

    # Netz -> Verbraucher
    if grid_import_industry > 0:
        flows.append({
            "source": "grid",
            "target": "industry",
            "color": "#D95F02",
            "label": f"Import: {format_energy(grid_import_industry)}"
        })

    if grid_import_hub > 0:
        flows.append({
            "source": "grid",
            "target": "hub",
            "color": "#D95F02",
            "label": f"Import: {format_energy(grid_import_hub)}"
        })

    # Überschuss links
    if solar_to_surplus > 0:
        flows.append({
            "source": "solar",
            "target": "surplus",
            "color": "#8B5CF6",
            "label": format_energy(solar_to_surplus)
        })

    if landscape_to_surplus > 0:
        flows.append({
            "source": "landscape",
            "target": "surplus",
            "color": "#7A3EB1",
            "label": format_energy(landscape_to_surplus)
        })

    # -----------------------------
    # 7) Plotly Figure
    # -----------------------------
    fig = go.Figure()
    fig.update_xaxes(visible=False, range=[-0.3, 1.45])
    fig.update_yaxes(visible=False, range=[-0.08, 1.12])

    box_w = 0.24
    box_h = 0.15

    # KPI-Karten oben
    kpi_y = 1.01
    kpis = [
        ("Gesamterzeugung", format_energy(total_generation), "#EAF4FF"),
        ("Gesamtbedarf", format_energy(total_demand), "#F8F8F8"),
        ("Versorgungsgrad", f"{coverage_percent:.1f} %", "#EEF9EE"),
        ("Bilanz", f"+ {format_energy(surplus)}" if surplus > 0 else f"- {format_energy(deficit)}", "#FFF4E8"),
        ("Netzbezug", format_energy(grid_import_total), "#FFF0E6"),
        ("Netzeinspeisung", format_energy(grid_export), "#F3E8FF"),
    ]
    kpi_xs = [0.08, 0.31, 0.54, 0.77, 1.00, 1.23]

    for (title, value_text, fill), x in zip(kpis, kpi_xs):
        fig.add_shape(
            type="rect",
            x0=x - 0.10, x1=x + 0.10,
            y0=kpi_y - 0.055, y1=kpi_y + 0.055,
            line=dict(color="rgba(80,80,80,0.45)", width=1.2),
            fillcolor=fill,
            layer="below"
        )
        fig.add_annotation(
            x=x,
            y=kpi_y,
            text=f"<b>{title}</b><br>{value_text}",
            showarrow=False,
            font=dict(size=11, color="#2F3445"),
            align="center"
        )

    # Boxen
    for node in nodes.values():
        x = node["x"]
        y = node["y"]

        fig.add_shape(
            type="rect",
            x0=x - box_w / 2,
            x1=x + box_w / 2,
            y0=y - box_h / 2,
            y1=y + box_h / 2,
            line=dict(color="rgba(70,70,70,0.7)", width=1.5),
            fillcolor=node["color"],
            layer="below"
        )

        fig.add_annotation(
            x=x,
            y=y,
            text=f"<b>{node['label']}</b>",
            showarrow=False,
            align="center",
            font=dict(size=10, color="#2F3445")
        )

    # Unsichtbare Hover-Punkte für Detailinfos
    for node in nodes.values():
        fig.add_trace(
            go.Scatter(
                x=[node["x"]],
                y=[node["y"]],
                mode="markers",
                marker=dict(size=60, opacity=0),
                hovertemplate=f"<b>{node['label']}</b><br>{node['info']}<extra></extra>",
                showlegend=False
            )
        )

    # Pfeile
    for flow in flows:
        s = nodes[flow["source"]]
        t = nodes[flow["target"]]

        if s["x"] < t["x"]:
            x0 = s["x"] + box_w / 2 - 0.01
            x1 = t["x"] - box_w / 2 + 0.01
        elif s["x"] > t["x"]:
            x0 = s["x"] - box_w / 2 + 0.01
            x1 = t["x"] + box_w / 2 - 0.01
        else:
            x0 = s["x"]
            x1 = t["x"]

        if s["y"] < t["y"]:
            y0 = s["y"] + box_h / 2 - 0.01
            y1 = t["y"] - box_h / 2 + 0.01
        elif s["y"] > t["y"]:
            y0 = s["y"] - box_h / 2 + 0.01
            y1 = t["y"] + box_h / 2 - 0.01
        else:
            y0 = s["y"]
            y1 = t["y"]

        fig.add_annotation(
            x=x1, y=y1,
            ax=x0, ay=y0,
            xref="x", yref="y",
            axref="x", ayref="y",
            showarrow=True,
            arrowhead=3,
            arrowsize=1.1,
            arrowwidth=2.6,
            arrowcolor=flow["color"],
            text=""
        )

        if flow["label"]:
            xm = (x0 + x1) / 2
            ym = (y0 + y1) / 2 + 0.03

            fig.add_annotation(
                x=xm,
                y=ym,
                text=f"<span style='font-size:10px'>{flow['label']}</span>",
                showarrow=False,
                font=dict(size=10, color=flow["color"]),
                bgcolor="rgba(255,255,255,0.82)"
            )

    fig.update_layout(
        title="Synergien, Bilanz und potenzielle Versorgung der Teilprojekte",
        height=850,
        margin=dict(l=20, r=20, t=80, b=20),
        plot_bgcolor="white",
        paper_bgcolor="white"
    )

    return fig


st.set_page_config(layout="centered")

Input = GuiInput()
Output = SimOutput()

if "simulation_ran" not in st.session_state:
    st.session_state.simulation_ran = False

if "sim_output" not in st.session_state:
    st.session_state.sim_output = None

# Überschrift
st.title("Energiesystem Modellierung - Innovationspark Jüchen")
st.write("### Erzeugung Eingabewerte")

# Fester Container für Darstellung der Erzeugungseingabe
with st.container(key="Erzeugung", width=1000, height=500):

    tab1, tab2 = st.tabs(["Solarautobahn", "Energielandschaft"])

    # SOLARAUTOBAHN
    with tab1:
        col1_tab1, col2_tab1 = st.columns(2)

        script_dir = os.path.dirname(os.path.abspath(__file__))

        with col1_tab1:
            Input.highways = st.multiselect("Autobahn auswählen", ["A44", "A46"])
            h_selected_names = st.multiselect("PV-Typ", ["Lärmschutzwand", "Windschutzwand", "Dach", "Böschung"])
            Input.h_pv_types = [pv_name_to_id[name] for name in h_selected_names]

        with col2_tab1:
            pv_geojson_mapping_col2_tab1 = {
                "A44": "a44_beide.geojson",
                "A46": "a46_beide.geojson",
            }

            m = folium.Map(location=[51.06280, 6.49554], zoom_start=12)

            for highway in Input.highways:
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
                default=100,
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

            Input.tractor_width = st.segmented_control(
                "Traktorbreite",
                options=[9.0, 12.0, 15.0],
                default=12.0,
                format_func=lambda x: f"{x:.0f}m"
            )

            Input.tractor_length = st.segmented_control(
                "Traktorlänge",
                options=[12.0, 15.0, 18.0],
                default=15.0,
                format_func=lambda x: f"{x:.0f}m"
            )

            Input.tractor_turn_radius = st.segmented_control(
                "Traktor-Wenderadius",
                options=[6.0, 9.0, 12.0],
                default=9.0,
                format_func=lambda x: f"{x:.0f}m"
            )

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

            if Input.el_build_state != 0:
                selected_file = pv_geojson_mapping_col2_tab2[el_selected_names][Input.el_build_state]
                geojson_path = os.path.join(script_dir, "geometry", selected_file)

                with open(geojson_path, "r", encoding="utf-8") as f:
                    geojson_data = json.load(f)

            m = folium.Map(location=[51.07596, 6.48599], zoom_start=14)

            if Input.el_build_state != 0:
                folium.GeoJson(
                    geojson_data,
                    name=f"{Input.el_pv_type}{Input.tractor_width}"
                ).add_to(m)

            folium.LayerControl().add_to(m)
            st_data = st_folium(m, width=400, height=400)

st.write("### Verbrauch Eingabewerte")

with st.container(key="Verbrauch", width=1500, height=1000):

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

            Input.companies = []
            for i in range(5):
                choice = st.selectbox(
                    f"Unternehmen {i + 1}",
                    options=[None] + list(options.keys()),
                    format_func=lambda x: "Keine" if x is None else options[x],
                    key=f"selection_{i}"
                )
                if choice is not None:
                    Input.companies.append(choice)

        with col2_tab4:
            Input.is_heat_cooling_electric = st.toggle("Mit Wärme/Kälte Stromverbrauch?")
            expander = st.expander("Erklärung Wärme/Kälte")
            expander.write('''
    Bei Auswahl "ohne Wärme/Kälte Stromverbrauch" werden fossiler Energiequellen für Wärme benutzt und es gibt keine Kälte

    Bei Auswahl "mit Wärme/Kälte Stromverbrauch" werden reversible Luftwärmepumpen und Geothermie-Sonden verwendet
            ''')

        preview_csv_path = os.path.join(
            script_dir,
            "functions",
            "inputs",
            "Projekt_04_Lastgaenge_Industriegebiet_und_nPro_Waerme_Kaelte.csv"
        )

        expander = st.expander("Erklärung Unternehmen")
        with expander:
            st.write('''
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

            fig_annual_all = plot_industry_annual_energy(
                preview_csv_path,
                ordered_columns=industry_order_all,
                title="Jahresenergie aller Unternehmensprofile"
            )
            st.pyplot(fig_annual_all)

        selected_columns = [industry_csv_mapping[i] for i in Input.companies if i in industry_csv_mapping]
        selected_columns = list(dict.fromkeys(selected_columns))

        if selected_columns:
            st.write("### Beispielhafte Wochenlastgänge der ausgewählten Unternehmen")

            fig_preview = plot_industry_preview(
                preview_csv_path,
                selected_columns=selected_columns,
                start="2017-03-05"
            )
            st.pyplot(fig_preview)

    # GREEN ENERGY HUB
    with tab5:
        Input.h2_load_scenario = st.segmented_control(
            "Wasserstoff-Bedarf Szenario",
            ["2022", "2030", "2050"],
            default="2030"
        )
        Input.e_load_scenario = st.segmented_control(
            "Elektro-Bedarf Szenario",
            ["2022", "2030", "2050"],
            default="2030"
        )

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
    - Anzahl an FCEVs:
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

        if Input.h2_load_scenario and Input.e_load_scenario:
            st.write("### Beispielhafte Wochenlastprofile der ausgewählten Green-Energy-Hub-Szenarien")

            fig_green_hub_week = plot_green_hub_weekly_profiles(
                green_hub_base_dir,
                h2_year=str(Input.h2_load_scenario),
                e_year=str(Input.e_load_scenario),
                start="2022-03-05"
            )
            st.pyplot(fig_green_hub_week)

if st.button("Simulation starten"):
    Output = run_simulation(Input)

    st.session_state.simulation_ran = True
    st.session_state.sim_output = Output

    st.write(Output.h_error_text)
    st.write("Berechnete Anzahl Punkte", Output.h_number_of_points)

    st.write("<u>Solarautobahn Gesamtjahr</u>", unsafe_allow_html=True)
    st.write(f"Berechnete Gesamtenergie: {Output.h_sum_energy_kwh:.0f} kWh")

# =========================================================
# Neue Visualisierung: Synergie-Diagramm
# =========================================================

st.title("Energiesystem – Visualisierung")

sim_output = st.session_state.sim_output if st.session_state.simulation_ran else None

fig_synergy = build_synergy_diagram(Input, sim_output)
st.plotly_chart(fig_synergy, width="stretch")