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
import numpy as np

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

ICON_SCALE = {
    "solar": 0.96,
    "landscape": 0.96,
    "industry": 1,
    "hub": 1,
    "battery": 0.6,
    "grid": 0.5,
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
    scale = ICON_SCALE.get(icon_key, 0.80)

    if icon_path and os.path.exists(icon_path):
        fig.add_layout_image(
            dict(
                source=Image.open(icon_path).convert("RGBA"),
                xref="x",
                yref="y",
                x=x,
                y=y,
                sizex=box_w * scale,
                sizey=box_h * scale,
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

def scale_arrow_width(flow_value, max_flow, min_width=1.5, max_width=5.0):
    """
    Skaliert die Pfeildicke linear auf Basis des größten dargestellten Flusses.
    """
    flow_value = float(flow_value or 0)
    max_flow = float(max_flow or 1)

    if flow_value <= 0:
        return min_width

    return min_width + (flow_value / max_flow) * (max_width - min_width)


def add_physical_connection(
    fig,
    points,
    color="#A8A8A8",
    width=1.3,
    dash="dot",
    add_arrow=False
):
    """
    Zeichnet eine physische, dauerhaft vorhandene Verbindung.
    Optional mit kleiner Pfeilspitze am Ende.
    """
    if len(points) < 2:
        return

    for i in range(len(points) - 1):
        x0, y0 = points[i]
        x1, y1 = points[i + 1]
        fig.add_shape(
            type="line",
            x0=x0, y0=y0,
            x1=x1, y1=y1,
            line=dict(color=color, width=width, dash=dash)
        )

    if add_arrow:
        x0, y0 = points[-2]
        x1, y1 = points[-1]

        dx = x1 - x0
        dy = y1 - y0

        fig.add_annotation(
            x=x1,
            y=y1,
            ax=x1 - dx * 0.12,
            ay=y1 - dy * 0.12,
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            showarrow=True,
            arrowhead=3,
            arrowsize=0.9,
            arrowwidth=max(width, 1.4),
            arrowcolor=color,
            text=""
        )

def add_legend(fig):
    legend_y1 = 0.06
    legend_y2 = 0.035

    # Zeile 1: durchgezogene Linien
    items_row1 = [
        ("Erneuerbare Versorgung", "#10B35A", 0.1, "solid"),
        ("Überschuss / Speicheroption", "#1DA1F2", 0.4, "solid"),
        ("Netzstrombezug", "#B9B9B9", 0.75, "solid"),
    ]

    # Zeile 2: gestrichelte Linien
    items_row2 = [
        ("Optionale Nutzung", "#1DA1F2", 0.1, "dot"),
        ("Netzanbindung", "#A8A8A8", 0.4, "dot"),
    ]

    for text, color, x, dash in items_row1:
        fig.add_shape(
            type="line",
            x0=x,
            y0=legend_y1,
            x1=x + 0.05,
            y1=legend_y1,
            line=dict(color=color, width=3, dash=dash)
        )
        fig.add_annotation(
            x=x + 0.06,
            y=legend_y1,
            text=text,
            showarrow=False,
            xanchor="left",
            yanchor="middle",
            font=dict(size=11, color="#333333")
        )

    for text, color, x, dash in items_row2:
        fig.add_shape(
            type="line",
            x0=x,
            y0=legend_y2,
            x1=x + 0.05,
            y1=legend_y2,
            line=dict(color=color, width=3, dash=dash)
        )
        fig.add_annotation(
            x=x + 0.06,
            y=legend_y2,
            text=text,
            showarrow=False,
            xanchor="left",
            yanchor="middle",
            font=dict(size=11, color="#333333")
        )

def add_optional_connection(fig, points, color="#1DA1F2", width=1.6, dash="dot", label=None, label_x=None, label_y=None):
    """
    Zeichnet eine optionale / konzeptionelle Verbindung.
    Nicht als simulierten Energiefluss interpretieren.
    """
    if len(points) < 2:
        return

    for i in range(len(points) - 2):
        x0, y0 = points[i]
        x1, y1 = points[i + 1]
        fig.add_shape(
            type="line",
            x0=x0, y0=y0,
            x1=x1, y1=y1,
            line=dict(color=color, width=width, dash=dash)
        )

    x0, y0 = points[-2]
    x1, y1 = points[-1]

    fig.add_shape(
        type="line",
        x0=x0, y0=y0,
        x1=x1, y1=y1,
        line=dict(color=color, width=width, dash=dash)
    )

    dx = x1 - x0
    dy = y1 - y0

    # Mindestlänge für sichtbare Pfeilspitze
    arrow_len = 0.025

    if abs(dx) >= abs(dy):  # eher horizontal
        ax = x1 - arrow_len if dx >= 0 else x1 + arrow_len
        ay = y1
    else:  # eher vertikal
        ax = x1
        ay = y1 - arrow_len if dy >= 0 else y1 + arrow_len

    fig.add_annotation(
        x=x1,
        y=y1,
        ax=ax,
        ay=ay,
        xref="x",
        yref="y",
        axref="x",
        ayref="y",
        showarrow=True,
        arrowhead=3,
        arrowsize=1.2,
        arrowwidth=max(width, 1.8),
        arrowcolor=color,
        text=""
    )

    if label:
        fig.add_annotation(
            x=label_x if label_x is not None else (x0 + x1) / 2,
            y=label_y if label_y is not None else (y0 + y1) / 2 + 0.02,
            text=f"<span style='font-size:10px'>{label}</span>",
            showarrow=False,
            font=dict(size=10, color=color),
            bgcolor="rgba(255,255,255,0.75)"
        )



def build_synergy_diagram(inp, sim_output):
    """
    Einfache bilanzielle Systemvisualisierung.

    Logik:
    - Solarautobahn + Energielandschaft speisen in einen zentralen Systemknoten
    - Vom Systemknoten gehen Flüsse zu Industriegebiet und Green Energy Hub
    - Bei Jahresüberschuss: Pfeil vom System zum Netz
    - Bei Jahresdefizit: Pfeil vom Netz zum System
    - Batterie aktuell nur als Layout-Knoten, ohne simulierten Lade-/Entladefluss
    """

    # =========================================================
    # 1) Werte aus Simulation lesen
    # =========================================================
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

    # =========================================================
    # 2) Bilanzlogik für Darstellung
    # =========================================================
    # Lokale Deckung insgesamt
    local_supply_total = min(total_generation, total_demand)

    # Verteilung der lokalen Versorgung proportional auf die beiden Verbraucher
    if total_demand > 0:
        industry_share = industry_energy / total_demand
        hub_share = green_hub_energy / total_demand
    else:
        industry_share = 0.0
        hub_share = 0.0

    local_supply_industry = local_supply_total * industry_share
    local_supply_hub = local_supply_total * hub_share

    grid_import_industry = max(industry_energy - local_supply_industry, 0.0)
    grid_import_hub = max(green_hub_energy - local_supply_hub, 0.0)
    grid_import_total = grid_import_industry + grid_import_hub
    grid_export = surplus

    # Quellaufteilung Solar / Landschaft für die Abgänge vom linken Bereich
    total_gen_for_split = solar_energy + landscape_energy
    if total_gen_for_split > 0:
        solar_share = solar_energy / total_gen_for_split
        landscape_share = landscape_energy / total_gen_for_split
    else:
        solar_share = 0.0
        landscape_share = 0.0

    solar_to_system = total_generation * solar_share
    landscape_to_system = total_generation * landscape_share

    # Batterie nur visuell aktiv/inaktiv
    battery_active = bool(getattr(inp, "bs_energy_kwh", 0) and getattr(inp, "bs_energy_kwh", 0) > 0)

    # =========================================================
    # 3) Texte für Hover
    # =========================================================
    solar_text = "nicht aktiv"
    if inp.h_highways and inp.h_pv_types:
        solar_text = (
            f"Jahreserzeugung:<br>{format_energy(solar_energy)}"
            if solar_energy > 0 else
            "aktiv, noch ohne Ergebnis"
        )

    landscape_text = "nicht aktiv"
    if inp.el_build_state != 0:
        landscape_text = (
            f"Jahreserzeugung:<br>{format_energy(landscape_energy)}"
            if landscape_energy > 0 else
            f"Ausbaugrad: {inp.el_build_state} %<br>aktiv, noch ohne Ergebnis"
        )

    n_companies = len([c for c in inp.i_companies if c is not None]) if inp.i_companies else 0

    industry_status = (
        "kein Bedarf" if industry_energy == 0 else
        "gedeckt" if grid_import_industry == 0 else
        "teilweise gedeckt"
    )

    industry_text = (
        f"Auswahl: {n_companies} Unternehmen"
        f"<br>Bedarf: {format_energy(industry_energy)}"
        f"<br>Lokal gedeckt: {format_energy(local_supply_industry)}"
        f"<br>Netzbezug: {format_energy(grid_import_industry)}"
        f"<br>Status: {industry_status}"
    )

    if inp.geh_h2_load_scenario is None or inp.geh_e_load_scenario is None:
        hub_text = "deaktiviert"
    else:
        hub_status = (
            "kein Bedarf" if green_hub_energy == 0 else
            "gedeckt" if grid_import_hub == 0 else
            "teilweise gedeckt"
        )
        hub_text = (
            f"H₂-Szenario: {inp.geh_h2_load_scenario}"
            f"<br>El.-Szenario: {inp.geh_e_load_scenario}"
            f"<br>Bedarf: {format_energy(green_hub_energy)}"
            f"<br>Lokal gedeckt: {format_energy(local_supply_hub)}"
            f"<br>Netzbezug: {format_energy(grid_import_hub)}"
            f"<br>Status: {hub_status}"
        )

    battery_text = (
        f"Kapazität: {format_energy(float(getattr(inp, 'bs_energy_kwh', 0) or 0))}"
        f"<br>Status: {'aktiv' if battery_active else 'deaktiviert'}"
        f"<br>Aktuell nur grafisch dargestellt"
        f"<br>keine Lade-/Entladeflüsse in dieser Grafik"
    )

    grid_text = (
        f"Import: {format_energy(grid_import_total)}"
        f"<br>Export: {format_energy(grid_export)}"
    )

    system_text = (
        f"Gesamterzeugung: {format_energy(total_generation)}"
        f"<br>Gesamtbedarf: {format_energy(total_demand)}"
        f"<br>Versorgungsgrad: {coverage_percent:.1f} %"
        f"<br>Bilanz: + {format_energy(surplus)}" if surplus > 0
        else f"Gesamterzeugung: {format_energy(total_generation)}"
             f"<br>Gesamtbedarf: {format_energy(total_demand)}"
             f"<br>Versorgungsgrad: {coverage_percent:.1f} %"
             f"<br>Bilanz: - {format_energy(deficit)}"
    )

    # =========================================================
    # 4) Knotenpositionen
    #    -> hier kannst du später leicht rumspielen
    # =========================================================
    nodes = {
        "solar": {
            "x": 0.1, "y": 0.65,
            "label": "Solar Highway",
            "info": solar_text,
            "icon": "solar"
        },
        "landscape": {
            "x": 0.1, "y": 0.35,
            "label": "Energy Landscape",
            "info": landscape_text,
            "icon": "landscape"
        },
        "grid": {
            "x": 0.57, "y": 0.78,
            "label": "Power Grid",
            "info": grid_text,
            "icon": "grid"
        },
        "system": {
            "x": 0.54, "y": 0.50,
            "label": "",
            "info": system_text,
            "icon": None
        },
        "battery": {
            "x": 0.51, "y": 0.22,
            "label": "Battery Storage",
            "info": battery_text,
            "icon": "battery"
        },
        "industry": {
            "x": 0.98, "y": 0.65,
            "label": "Industrial Area",
            "info": industry_text,
            "icon": "industry"
        },
        "hub": {
            "x": 0.98, "y": 0.35,
            "label": "Green Energy Hub",
            "info": hub_text,
            "icon": "hub"
        }
    }

    # =========================================================
    # 5) Figure Setup
    # =========================================================
    fig = go.Figure()
    fig.update_xaxes(visible=False, range=[-0.02, 1.10])
    fig.update_yaxes(visible=False, range=[0.00, 1.10])

    box_w = 0.22
    box_h = 0.16

    COLOR_RENEWABLE = "#10B35A"
    COLOR_GRID = "#B9B9B9"
    COLOR_OPTIONAL = "#10B35A"

    flow_values = [
        solar_energy, landscape_energy,
        local_supply_industry, local_supply_hub,
        grid_import_total, grid_export
    ]
    max_flow = max(flow_values) if max(flow_values) > 0 else 1.0

    # KPI-Karten oben
    kpi_y = 1.04
    kpis = [
        ("Jahreserzeugung", format_energy(total_generation), "#EAF4FF"),
        ("Jahresbedarf", format_energy(total_demand), "#F8F8F8"),
        ("Versorgungsgrad", f"{coverage_percent:.1f} %", "#EEF9EE"),
        ("Jahresbilanz", f"+ {format_energy(surplus)}" if surplus > 0 else f"- {format_energy(deficit)}", "#FFF4E8"),
        ("Netzbezug", format_energy(grid_import_total), "#FFF0E6"),
        ("Netzeinspeisung", format_energy(grid_export), "#F3E8FF"),
    ]
    kpi_xs = [0.06, 0.25, 0.44, 0.63, 0.82, 1.01]

    for (title, value_text, fill), x in zip(kpis, kpi_xs):
        fig.add_shape(
            type="rect",
            x0=x - 0.08, x1=x + 0.08,
            y0=kpi_y - 0.045, y1=kpi_y + 0.045,
            line=dict(color="rgba(80,80,80,0.45)", width=1.1),
            fillcolor=fill,
            layer="below"
        )
        fig.add_annotation(
            x=x,
            y=kpi_y,
            text=f"<b>{title}</b><br>{value_text}",
            showarrow=False,
            font=dict(size=10, color="#2F3445"),
            align="center"
        )

    # =========================================================
    # 6) Boxen und Knoten
    # =========================================================
    add_legend(fig)

    # Rechteckige Knoten mit Icons
    for key in ["solar", "landscape", "grid", "battery", "industry", "hub"]:
        node = nodes[key]
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

        label_pos = "above" if key in ["solar", "grid", "industry"] else "below"

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

    # Zentraler Systemknoten
    system = nodes["system"]
    fig.add_shape(
        type="circle",
        x0=system["x"] - 0.025, x1=system["x"] + 0.025,
        y0=system["y"] - 0.025, y1=system["y"] + 0.025,
        line=dict(color="gray", width=1.2),
        fillcolor="white"
    )

    # Hoverpunkte
    for key, node in nodes.items():
        marker_size = 26 if key == "system" else 60
        fig.add_trace(
            go.Scatter(
                x=[node["x"]],
                y=[node["y"]],
                mode="markers",
                marker=dict(size=marker_size, opacity=0),
                hovertemplate=f"<b>{node['label'] if node['label'] else 'Systemknoten'}</b><br>{node['info']}<extra></extra>",
                showlegend=False
            )
        )

    # =========================================================
    # 7) Hilfspunkte für Pfeile
    # =========================================================
    solar_right = (nodes["solar"]["x"] + box_w / 2, nodes["solar"]["y"])
    landscape_right = (nodes["landscape"]["x"] + box_w / 2, nodes["landscape"]["y"])
    grid_bottom = (nodes["grid"]["x"], nodes["grid"]["y"] - box_h / 2)
    battery_top = (nodes["battery"]["x"], nodes["battery"]["y"] + box_h / 2)
    industry_left = (nodes["industry"]["x"] - box_w / 2, nodes["industry"]["y"])
    hub_left = (nodes["hub"]["x"] - box_w / 2, nodes["hub"]["y"])
    system_center = (nodes["system"]["x"], nodes["system"]["y"])

    x_left_join = (system_center[0]+solar_right[0])/2
    x_right_split = (system_center[0]+industry_left[0])/2

    half_y_grid =  (grid_bottom[1]+system_center[1])/2
    half_y_bat =  (battery_top[1]+system_center[1])/2
    # =========================================================
    # 8) Erzeuger -> System
    # =========================================================
    if solar_to_system > 0:
        add_routed_arrow(
            fig,
            points=[solar_right, (x_left_join, solar_right[1]), (x_left_join, system_center[1]), system_center],
            color=COLOR_RENEWABLE,
            width=scale_arrow_width(solar_to_system, max_flow)
        )

    if landscape_to_system > 0:
        add_routed_arrow(
            fig,
            points=[landscape_right, (x_left_join, landscape_right[1]), (x_left_join, system_center[1]), system_center],
            color=COLOR_RENEWABLE,
            width=scale_arrow_width(landscape_to_system, max_flow)
        )

    # =========================================================
    # 9) System -> Verbraucher
    # =========================================================
    if local_supply_industry > 0:
        add_routed_arrow(
            fig,
            points=[system_center, (x_right_split, system_center[1]), (x_right_split, industry_left[1]), industry_left],
            color=COLOR_RENEWABLE,
            width=scale_arrow_width(local_supply_industry, max_flow)
        )

    if local_supply_hub > 0:
        add_routed_arrow(
            fig,
            points=[system_center, (x_right_split, system_center[1]), (x_right_split, hub_left[1]), hub_left],
            color=COLOR_RENEWABLE,
            width=scale_arrow_width(local_supply_hub, max_flow)
        )

    # =========================================================
    # 10) Batterie nur schematisch anbinden
    # =========================================================
    if sim_output.bs_df is not None:
        add_routed_arrow(
            fig,
            points=[system_center, (system_center[0], half_y_bat),(battery_top[0], half_y_bat), battery_top],
            color=COLOR_OPTIONAL,
            width=1.6
        )
        add_routed_arrow(
            fig,
            points=[battery_top,(battery_top[0], half_y_bat), (system_center[0], half_y_bat),system_center],
            color=COLOR_OPTIONAL,
            width=1.6
        )

    # =========================================================
    # 11) Netzlogik:
    #     Überschuss => System -> Grid
    #     Defizit    => Grid -> System
    # =========================================================
    if grid_export > 0:
        add_routed_arrow(
            fig,
            points=[system_center, (system_center[0], half_y_grid), (grid_bottom[0],  half_y_grid), grid_bottom],
            color=COLOR_RENEWABLE,
            width=scale_arrow_width(grid_export, max_flow),
            label="Überschuss",
            label_x=0.60,
            label_y=0.74
        )

    elif grid_import_total > 0:
        add_routed_arrow(
            fig,
            points=[grid_bottom, (grid_bottom[0], half_y_grid), (system_center[0], half_y_grid), system_center],
            color=COLOR_GRID,
            width=scale_arrow_width(grid_import_total, max_flow),
            label="Netzbezug",
            label_x=0.60,
            label_y=0.74
        )

    # Optionale gestrichelte Hinweise vom System zu den Verbrauchern bei Defizit,
    # damit man im Stil deiner Skizze andeuten kann, dass dort Netzstrom ankommt
    if grid_import_total > 0:
        if grid_import_industry > 0:
            add_optional_connection(
                fig,
                points=[(x_right_split, system_center[1]), (x_right_split, industry_left[1]), industry_left],
                color=COLOR_GRID,
                width=1.4,
                dash="dot",
                label="Netzbezug",
                label_x=0.76,
                label_y=0.66
            )

        if grid_import_hub > 0:
            add_optional_connection(
                fig,
                points=[(x_right_split, system_center[1]), (x_right_split, hub_left[1]), hub_left],
                color=COLOR_GRID,
                width=1.4,
                dash="dot",
                label="Netzbezug",
                label_x=0.76,
                label_y=0.39
            )

    # =========================================================
    # 12) Layout
    # =========================================================
    fig.update_layout(
        title="Annual Energy Balance",
        height=820,
        margin=dict(l=20, r=20, t=100, b=20),
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
    st.session_state.sim_output = Output

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
            Input.h_highways = st.multiselect("Autobahn auswählen", ["A44", "A46"])
            h_selected_names = st.multiselect("PV-Typ", ["Lärmschutzwand", "Windschutzwand", "Dach", "Böschung"])
            Input.h_pv_types = [pv_name_to_id[name] for name in h_selected_names]

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
                    name=f"{Input.el_pv_type}{Input.el_tractor_width}"
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

        selected_columns = [industry_csv_mapping[i] for i in Input.i_companies if i in industry_csv_mapping]
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

        scenario_options = [None, "2022", "2030", "2050"]

        Input.geh_h2_load_scenario = st.segmented_control(
            "Wasserstoff-Bedarf Szenario",
            options=scenario_options,
            default=None,
            format_func=lambda x: "Keine" if x is None else x
        )

        Input.geh_e_load_scenario = st.segmented_control(
            "Elektro-Bedarf Szenario",
            options=scenario_options,
            default=None,
            format_func=lambda x: "Keine" if x is None else x
        )

        green_hub_active = (
                Input.geh_h2_load_scenario is not None and
                Input.geh_e_load_scenario is not None
        )

        if green_hub_active:
            st.write("### Beispielhafte Wochenlastprofile der ausgewählten Green-Energy-Hub-Szenarien")

            fig_green_hub_week = plot_green_hub_weekly_profiles(
                green_hub_base_dir,
                h2_year=str(Input.geh_h2_load_scenario),
                e_year=str(Input.geh_e_load_scenario),
                start="2022-03-05"
            )
            st.pyplot(fig_green_hub_week)
        else:
            st.info("Green Energy Hub ist deaktiviert.")

st.write("### Batterie Eingabewerte")

with st.container(key="Batterie", width=1500, height=500):

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
            step=1.0
        )
        Input.bs_energy_kwh = int(custom_mwh * 1000)

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

    if bat_active:
        st.info(
            f"""
            **Batterie aktiv:**

            Kapazität: **{Input.bs_energy_kwh / 1000:.0f} MWh**  
            Roundtrip Effizienz: **{Input.bs_efficiency:.0%}**
            """
        )
    else:
        st.info("Batterie deaktiviert.")



col1, col2, col3 = st.columns([0.15, 0.7, 0.15])

with col2:
    run = st.button(
        "⚡ Simulation starten",
        type="primary",
        use_container_width=True
    )


if run:
    with st.spinner("Simulation läuft..."):
        Output = run_simulation(Input)

    st.success("Simulation abgeschlossen.")


    st.session_state.simulation_ran = True

st.session_state.sim_output = Output


# =========================================================
# Neue Visualisierung: Synergie-Diagramm
# =========================================================

st.title("Energiesystem – Visualisierung")

#sim_output = st.session_state.sim_output if st.session_state.simulation_ran else Output

fig_synergy = build_synergy_diagram(Input, st.session_state.sim_output)
st.plotly_chart(fig_synergy, width="stretch")