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
from PIL import Image

from core.io_types import GuiInput, SimOutput
from Simulation import run_simulation
from functions.plot_functions import (
    plot_industry_preview,
    plot_industry_annual_energy,
    plot_green_hub_weekly_profiles,
    plot_green_hub_annual_energy
)

script_dir = os.path.dirname(os.path.abspath(__file__))

icon_dir = os.path.join(script_dir, "icon")

ICON_PATHS = {
    "solar": os.path.join(icon_dir, "solar_highway.png"),
    "landscape": os.path.join(icon_dir, "energy_landscape.png"),
    "battery": os.path.join(icon_dir, "battery_storage.png"),
    "industry": os.path.join(icon_dir, "industrial_area.png"),
    "hub": os.path.join(icon_dir, "green_energy_hub.png"),
    "grid": os.path.join(icon_dir, "grid_supply.png"),
    "surplus": None,
}


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


def add_node_with_icon(fig, x, y, label, icon_key, box_w, box_h, label_pos="below"):
    """
    Fügt ein Icon und den Knotentitel hinzu.
    Der eigentliche weiße Hintergrundkasten wird separat gezeichnet.
    """
    icon_path = ICON_PATHS.get(icon_key)

    if icon_path and os.path.exists(icon_path):
        fig.add_layout_image(
            dict(
                source=Image.open(icon_path).convert("RGBA"),
                xref="x",
                yref="y",
                x=x,
                y=y,
                sizex=box_w * 0.80,
                sizey=box_h * 0.80,
                xanchor="center",
                yanchor="middle",
                layer="above"
            )
        )

    if label_pos == "above":
        label_y = y + box_h / 2 + 0.04
    else:
        label_y = y - box_h / 2 - 0.04

    fig.add_annotation(
        x=x,
        y=label_y,
        text=f"<b>{label}</b>",
        showarrow=False,
        align="center",
        font=dict(size=12, color="#222222")
    )



def add_routed_arrow(fig, points, color, width=2.5, label=None, label_x=None, label_y=None):
    """
    Zeichnet eine geroutete Verbindung aus mehreren Segmenten.
    `points` ist eine Liste von (x, y)-Punkten.
    Die Segmente werden als Linien gezeichnet, die Pfeilspitze sitzt nur am Ende.
    """
    if len(points) < 2:
        return

    # Alle Segmente bis auf das letzte als Linien
    for i in range(len(points) - 2):
        x0, y0 = points[i]
        x1, y1 = points[i + 1]
        fig.add_shape(
            type="line",
            x0=x0, y0=y0,
            x1=x1, y1=y1,
            line=dict(color=color, width=width)
        )

    # Letztes Segment mit Pfeilspitze
    x0, y0 = points[-2]
    x1, y1 = points[-1]
    fig.add_annotation(
        x=x1,
        y=y1,
        ax=x0,
        ay=y0,
        xref="x",
        yref="y",
        axref="x",
        ayref="y",
        showarrow=True,
        arrowhead=3,
        arrowsize=1.0,
        arrowwidth=width,
        arrowcolor=color,
        text=""
    )

    # Optionales Label
    if label:
        if label_x is None or label_y is None:
            label_x = (x0 + x1) / 2
            label_y = (y0 + y1) / 2 + 0.03

        fig.add_annotation(
            x=label_x,
            y=label_y,
            text=f"<span style='font-size:11px'>{label}</span>",
            showarrow=False,
            font=dict(size=11, color=color),
            bgcolor="rgba(255,255,255,0.85)"
        )


def add_legend(fig):
    legend_y = 0.935
    items = [
        ("Renewable Supply", "#10B35A", 0.10),
        ("Storage Flow", "#1DA1F2", 0.38),
        ("Grid Electricity", "#B9B9B9", 0.63),
    ]

    for text, color, x in items:
        fig.add_shape(
            type="line",
            x0=x,
            y0=legend_y,
            x1=x + 0.05,
            y1=legend_y,
            line=dict(color=color, width=3)
        )

        fig.add_annotation(
            x=x + 0.06,
            y=legend_y,
            text=text,
            showarrow=False,
            xanchor="left",
            yanchor="middle",
            font=dict(size=11, color="#333333")
        )

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

    storage_input = solar_to_surplus + landscape_to_surplus
    COLOR_RENEWABLE = "#10B35A"
    COLOR_STORAGE = "#1DA1F2"
    COLOR_GRID = "#B9B9B9"

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


    # -----------------------------
    # 5) Knoten
    # -----------------------------
    nodes = {
        "solar": {
            "x": 0.12, "y": 0.72,
            "label": "Solar Highway",
            "info": solar_text,
            "icon": "solar"
        },
        "landscape": {
            "x": 0.12, "y": 0.28,
            "label": "Energy Landscape",
            "info": landscape_text,
            "icon": "landscape"
        },
        "battery": {
            "x": 0.39, "y": 0.50,
            "label": "Battery Storage",
            "info": (
                f"Schematische Speicheranbindung.<br>"
                f"Potenziell speicherbarer bilanzieller Überschuss: {format_energy(storage_input)}<br>"
                f"Derzeit keine explizite Batteriesimulation "
                f"(keine Kapazität, kein SOC, keine Verluste)."
            ),
            "icon": "battery"
        },
        "industry": {
            "x": 0.88, "y": 0.72,
            "label": "Industrial Area",
            "info": industry_text,
            "icon": "industry"
        },
        "hub": {
            "x": 0.88, "y": 0.28,
            "label": "Green Energy Hub",
            "info": hub_text,
            "icon": "hub"
        },
        "grid": {
            "x": 1.18, "y": 0.50,
            "label": "Grid Supply",
            "info": grid_text,
            "icon": "grid"
        }
    }

    # -----------------------------
    # 7) Plotly Figure
    # -----------------------------
    fig = go.Figure()
    fig.update_xaxes(visible=False, range=[-0.02, 1.30])
    fig.update_yaxes(visible=False, range=[0.02, 1.12])

    box_w = 0.22
    box_h = 0.16

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

    add_legend(fig)

    # Boxen + Icons
    for key, node in nodes.items():
        x = node["x"]
        y = node["y"]

        fig.add_shape(
            type="rect",
            x0=x - box_w / 2,
            x1=x + box_w / 2,
            y0=y - box_h / 2,
            y1=y + box_h / 2,
            line=dict(color="black", width=2),
            fillcolor="white",
            layer="below"
        )

        label_pos = "above" if key in ["solar", "industry"] else "below"

        add_node_with_icon(
            fig=fig,
            x=x,
            y=y,
            label=node["label"],
            icon_key=node["icon"],
            box_w=box_w,
            box_h=box_h,
            label_pos=label_pos
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
    # -------------------------------------------------
    # Geroutete Hauptpfade im Layout der Zielskizze
    # -------------------------------------------------
    COLOR_RENEWABLE = "#10B35A"
    COLOR_STORAGE = "#1DA1F2"
    COLOR_GRID = "#B9B9B9"

    x_left_join = 0.62
    x_merge = 0.62
    x_right_join = 0.89
    y_mid = 0.50

    has_industry_supply = local_supply_industry > 0
    has_hub_supply = local_supply_hub > 0
    has_storage = storage_input > 0

    # Anschlusspunkte: mittig an den Boxseiten
    solar_right_mid = (nodes["solar"]["x"] + box_w / 2, nodes["solar"]["y"])
    landscape_right_mid = (nodes["landscape"]["x"] + box_w / 2, nodes["landscape"]["y"])

    solar_bottom_mid = (nodes["solar"]["x"], nodes["solar"]["y"] - box_h / 2)
    landscape_top_mid = (nodes["landscape"]["x"], nodes["landscape"]["y"] + box_h / 2)

    battery_left_mid = (nodes["battery"]["x"] - box_w / 2, nodes["battery"]["y"])
    battery_right_mid = (nodes["battery"]["x"] + box_w / 2, nodes["battery"]["y"])

    industry_bottom_mid = (nodes["industry"]["x"], nodes["industry"]["y"] - box_h / 2)
    hub_top_mid = (nodes["hub"]["x"], nodes["hub"]["y"] + box_h / 2)

    industry_right_mid = (nodes["industry"]["x"] + box_w / 2, nodes["industry"]["y"])
    hub_right_mid = (nodes["hub"]["x"] + box_w / 2, nodes["hub"]["y"])

    grid_top_mid = (nodes["grid"]["x"], nodes["grid"]["y"] + box_h / 2)
    grid_bottom_mid = (nodes["grid"]["x"], nodes["grid"]["y"] - box_h / 2)

    # --- Grüne Hauptstruktur links ---
    if (solar_to_industry + solar_to_hub) > 0:
        add_routed_arrow(
            fig,
            points=[solar_right_mid, (x_left_join, solar_right_mid[1])],
            color=COLOR_RENEWABLE
        )

    if (landscape_to_industry + landscape_to_hub) > 0:
        add_routed_arrow(
            fig,
            points=[landscape_right_mid, (x_left_join, landscape_right_mid[1])],
            color=COLOR_RENEWABLE
        )

    # linker vertikaler Sammelstrang - verbunden
    if has_industry_supply or has_hub_supply:
        fig.add_shape(
            type="line",
            x0=x_left_join, y0=landscape_right_mid[1],
            x1=x_left_join, y1=solar_right_mid[1],
            line=dict(color=COLOR_RENEWABLE, width=2.5)
        )
        fig.add_shape(
            type="line",
            x0=x_left_join, y0=y_mid,
            x1=x_merge, y1=y_mid,
            line=dict(color=COLOR_RENEWABLE, width=2.5)
        )

    # mittlere Direct Supply Leitung
    if has_industry_supply or has_hub_supply:
        add_routed_arrow(
            fig,
            points=[(x_merge, y_mid), (x_right_join, y_mid)],
            color=COLOR_RENEWABLE,
            label="Direct Supply",
            label_x=0.84,
            label_y=0.53
        )

    # rechter vertikaler Verteiler - startet erst rechts von den Boxen
    if has_industry_supply or has_hub_supply:
        y_top = industry_bottom_mid[1] if has_industry_supply else y_mid
        y_bottom = hub_top_mid[1] if has_hub_supply else y_mid

        if y_top != y_bottom:
            fig.add_shape(
                type="line",
                x0=x_right_join, y0=y_bottom,
                x1=x_right_join, y1=y_top,
                line=dict(color=COLOR_RENEWABLE, width=2.5)
            )

    # grüner Pfeil -> Industry mittig unten
    if has_industry_supply:
        add_routed_arrow(
            fig,
            points=[
                (x_right_join, y_mid),
                (x_right_join, industry_bottom_mid[1]),
                industry_bottom_mid
            ],
            color=COLOR_RENEWABLE
        )
        fig.add_annotation(
            x=0.80, y=0.61,
            text=f"<span style='font-size:11px'>{format_energy(local_supply_industry)}</span>",
            showarrow=False,
            font=dict(size=11, color=COLOR_RENEWABLE),
            bgcolor="rgba(255,255,255,0.85)"
        )

    # grüner Pfeil -> Hub mittig oben
    if has_hub_supply:
        add_routed_arrow(
            fig,
            points=[
                (x_right_join, y_mid),
                (x_right_join, hub_top_mid[1]),
                hub_top_mid
            ],
            color=COLOR_RENEWABLE
        )
        fig.add_annotation(
            x=0.80, y=0.18,
            text=f"<span style='font-size:11px'>{format_energy(local_supply_hub)}</span>",
            showarrow=False,
            font=dict(size=11, color=COLOR_RENEWABLE),
            bgcolor="rgba(255,255,255,0.85)"
        )

    # --- Blauer Speicherpfad ---
    if solar_to_surplus > 0:
        add_routed_arrow(
            fig,
            points=[solar_bottom_mid, (solar_bottom_mid[0], battery_left_mid[1]), battery_left_mid],
            color=COLOR_STORAGE,
            label="Surplus Energy",
            label_x=0.24,
            label_y=0.54
        )

    if landscape_to_surplus > 0:
        add_routed_arrow(
            fig,
            points=[landscape_top_mid, (landscape_top_mid[0], battery_left_mid[1]), battery_left_mid],
            color=COLOR_STORAGE
        )

    if has_storage:
        add_routed_arrow(
            fig,
            points=[battery_right_mid, (x_merge, y_mid)],
            color=COLOR_STORAGE
        )

    # --- Grauer Netzpfad ---
    if grid_import_industry > 0:
        add_routed_arrow(
            fig,
            points=[
                grid_top_mid,
                (grid_top_mid[0], industry_right_mid[1]),
                industry_right_mid
            ],
            color=COLOR_GRID
        )

        fig.add_annotation(
            x=1.05, y=0.76,
            text=f"<span style='font-size:11px'>{format_energy(grid_import_industry)}</span>",
            showarrow=False,
            font=dict(size=11, color=COLOR_GRID),
            bgcolor="rgba(255,255,255,0.85)"
        )

    if grid_import_hub > 0:
        add_routed_arrow(
            fig,
            points=[
                grid_bottom_mid,
                (grid_bottom_mid[0], hub_right_mid[1]),
                hub_right_mid
            ],
            color=COLOR_GRID
        )
        fig.add_annotation(
            x=1.05, y=0.22,
            text=f"<span style='font-size:11px'>{format_energy(grid_import_hub)}</span>",
            showarrow=False,
            font=dict(size=11, color=COLOR_GRID),
            bgcolor="rgba(255,255,255,0.85)"
        )

    fig.update_layout(
        title="Synergien, Bilanz und potenzielle Versorgung der Teilprojekte",
        height=860,
        margin=dict(l=20, r=20, t=110, b=20),
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