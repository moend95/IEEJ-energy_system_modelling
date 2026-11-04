import gzip
import json
from pathlib import Path
from typing import Any

import plotly.graph_objects as go
import streamlit as st

from core.functions_web_support import (
    add_legend,
    add_node_with_icon,
    add_optional_connection,
    add_routed_arrow,
    format_capacity,
    format_energy,
    format_power,
)


PROJECT_DIR = Path(__file__).resolve().parent
PRECOMPUTED_DIR = PROJECT_DIR / "data" / "outputs" / "precomputed"

PV_NAME_TO_ID = {
    "Windschutzwand": 0,
    "Laermschutzwand": 1,
    "Dach": 2,
    "Boeschung": 3,
    "Horizontal mit Single-Axis-Tracking (aufgestaendert, Nord-Sued)": 4,
    "Vertikal (Zaun, Nord-Sued)": 5,
    "Horizontal (aufgestaendert, Ost-West)": 6,
}

INDUSTRY_OPTIONS = {
    0: "Entsorgung",
    1: "Stahl (5-Tage-Woche, 3-Schicht)",
    2: "Logistik und Lagerung",
    3: "Schrott- und Metallhandel",
    5: "Buero",
}
ELSBACHTAL_BASIS_COMPANIES = [0, 1, 2, 3, 5]
INDUSTRY_MODES = ["Basis-Variante Elsbachtal", "Unternehmen selbst zusammenstellen"]

NODE_ICON_BY_ID = {
    "solar": "solar",
    "landscape": "landscape",
    "grid": "grid",
    "battery": "battery",
    "industry": "industry",
    "hub": "hub",
    "js": "js",
}

DEFAULT_FLOW_NODES = [
    {"id": "solar", "label": "Solarautobahn", "x": 0.10, "y": 0.48},
    {"id": "landscape", "label": "Energielandschaft", "x": 0.10, "y": 0.18},
    {"id": "system", "label": "System", "x": 0.54, "y": 0.33},
    {"id": "industry", "label": "Industriegebiet", "x": 0.98, "y": 0.59},
    {"id": "js", "label": "Juechen Sued", "x": 0.98, "y": 0.33},
    {"id": "hub", "label": "Green Energy Hub", "x": 0.98, "y": 0.07},
    {"id": "grid", "label": "Stromnetz", "x": 0.50, "y": 0.65},
    {"id": "battery", "label": "Batterie", "x": 0.50, "y": 0.03},
]

DEFAULT_FLOW_EDGES = [
    {"id": "solar_to_system", "color": "#10B35A"},
    {"id": "landscape_to_system", "color": "#10B35A"},
    {"id": "system_to_industry", "color": "#10B35A"},
    {"id": "system_to_js", "color": "#10B35A"},
    {"id": "system_to_hub", "color": "#10B35A"},
    {"id": "system_to_battery", "color": "#1DA1F2"},
    {"id": "battery_to_system", "color": "#1DA1F2"},
    {"id": "system_to_grid", "color": "#10B35A"},
    {"id": "grid_to_system", "color": "#B9B9B9"},
]

GEH_VARIANT_OPTIONS = ["Keine", "Basis", "Erweiterung"]
JS_CONCEPT_OPTIONS = ["Aus", "Warmes Netz", "Kaltes Netz", "Dezentral"]


def _sort_unique_ints(values: list[Any]) -> list[int]:
    out: list[int] = []
    for val in values or []:
        try:
            out.append(int(val))
        except (TypeError, ValueError):
            continue
    return sorted(set(out))


def _sort_unique_strings(values: list[Any]) -> list[str]:
    out = [str(v) for v in values or [] if v is not None]
    return sorted(set(out))


def _round_float(value: Any, digits: int, fallback: float = 0.0) -> float:
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return fallback


def _canonicalize_input(raw_input: dict[str, Any]) -> dict[str, Any]:
    bs_energy_kwh_raw = raw_input.get("bs_energy_kwh")
    bs_energy_kwh = _round_float(bs_energy_kwh_raw, 3, fallback=0.0)
    battery_active = bs_energy_kwh > 0

    return {
        "h_highways": _sort_unique_strings(raw_input.get("h_highways", [])),
        "h_pv_types": _sort_unique_ints(raw_input.get("h_pv_types", [])),
        "el_build_state": int(raw_input.get("el_build_state") or 0),
        "el_pv_type": int(raw_input.get("el_pv_type") or 0),
        "el_tractor_width": _round_float(raw_input.get("el_tractor_width"), 3),
        "el_tractor_length": _round_float(raw_input.get("el_tractor_length"), 3),
        "el_tractor_turn_radius": _round_float(raw_input.get("el_tractor_turn_radius"), 3),
        "i_heat_cooling_electric": bool(raw_input.get("i_heat_cooling_electric", False)),
        "i_companies": _sort_unique_ints(raw_input.get("i_companies", [])),
        "geh_variant": str(raw_input.get("geh_variant") or "Keine"),
        "bs_energy_kwh": bs_energy_kwh if battery_active else None,
        "bs_efficiency": _round_float(raw_input.get("bs_efficiency"), 3) if battery_active else None,
        "bs_c_rate": _round_float(raw_input.get("bs_c_rate"), 3) if battery_active else None,
        "js_concept": str(raw_input.get("js_concept") or "Aus"),
    }


def _canonical_key(raw_input: dict[str, Any]) -> str:
    return json.dumps(_canonicalize_input(raw_input), sort_keys=True, ensure_ascii=True)


def _edge_hover_text(edge: dict[str, Any]) -> str:
    return (
        f"<b>{edge.get('id', 'edge')}</b><br>"
        f"Type: {edge.get('flow_type', '-') }<br>"
        f"Annual: {_fmt_energy(edge.get('annual_kwh', 0.0))}<br>"
        f"Peak: {_fmt_power(edge.get('peak_kw', 0.0))}<br>"
        f"Stroke: {float(edge.get('stroke_px', 2.0) or 2.0):.2f}px"
    )


def _add_hover_trace(fig: go.Figure, points: list[tuple[float, float]], edge: dict[str, Any]) -> None:
    if len(points) < 2:
        return
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    stroke = float(edge.get("stroke_px", 2.0) or 2.0)
    fig.add_trace(
        go.Scatter(
            x=xs,
            y=ys,
            mode="lines",
            line=dict(color="rgba(0,0,0,0)", width=max(10.0, stroke + 8.0)),
            hovertemplate=_edge_hover_text(edge) + "<extra></extra>",
            showlegend=False,
        )
    )


def _build_unavailable_payload(selected_input: dict[str, Any]) -> dict[str, Any]:
    edges = []
    for edge in DEFAULT_FLOW_EDGES:
        edges.append(
            {
                "id": edge["id"],
                "flow_type": "unavailable",
                "annual_kwh": 0.0,
                "peak_kw": 0.0,
                "color": edge["color"],
                "stroke_px": 2.0,
            }
        )

    return {
        "metadata": {
            "scenario_id": "noch_nicht_verfuegbar",
            "schema_version": "1.0.0",
            "created_at": "-",
            "time_step_minutes": 15,
            "timeseries_mode": "none",
        },
        "input": selected_input,
        "annual_summary": {
            "generation": {
                "solar_highway_kwh": 0.0,
                "energy_landscape_kwh": 0.0,
                "total_generation_kwh": 0.0,
            },
            "demand": {
                "industry_kwh": 0.0,
                "green_energy_hub_kwh": 0.0,
                "juechen_sued_kwh": 0.0,
                "total_demand_kwh": 0.0,
            },
            "balance": {
                "bal_energy_kwh": 0.0,
                "coverage_rate": 0.0,
                "ee_self_consumption": 0.0,
                "autarky": 0.0,
            },
            "battery": {
                "charge_kwh": 0.0,
                "discharge_kwh": 0.0,
                "final_soc_kwh": 0.0,
                "final_soc_percent": 0.0,
            },
            "grid": {
                "import_kwh": 0.0,
                "export_kwh": 0.0,
                "max_import_kw": 0.0,
                "max_export_kw": 0.0,
            },
        },
        "flow_nodes": DEFAULT_FLOW_NODES,
        "flow_edges": edges,
        "timeseries": [],
        "timeseries_ref": None,
    }


@st.cache_data(show_spinner=False)
def list_precomputed_scenarios() -> list[str]:
    if not PRECOMPUTED_DIR.exists():
        return []

    scenarios: list[str] = []
    for path in sorted(PRECOMPUTED_DIR.iterdir()):
        if path.is_dir() and (path / "flow_data.json").exists():
            scenarios.append(path.name)
    return scenarios


@st.cache_data(show_spinner=False)
def load_precomputed_catalog() -> list[dict[str, Any]]:
    catalog: list[dict[str, Any]] = []
    for scenario_id in list_precomputed_scenarios():
        flow_path = PRECOMPUTED_DIR / scenario_id / "flow_data.json"
        payload = _read_json(str(flow_path))
        raw_input = payload.get("input", {})
        catalog.append(
            {
                "scenario_id": scenario_id,
                "canonical_key": _canonical_key(raw_input),
                "input": raw_input,
            }
        )
    return catalog


@st.cache_data(show_spinner=False)
def _read_json(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@st.cache_data(show_spinner=False)
def _read_timeseries(path: str, compressed: bool) -> list[dict[str, Any]]:
    if compressed:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return json.load(f)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_scenario_payload(scenario_id: str) -> dict[str, Any]:
    scenario_dir = PRECOMPUTED_DIR / scenario_id
    flow_path = scenario_dir / "flow_data.json"
    payload = _read_json(str(flow_path))

    if payload.get("timeseries"):
        return payload

    ref = payload.get("timeseries_ref") or {}
    ref_path = ref.get("path")
    if not ref_path:
        return payload

    ts_path = scenario_dir / ref_path
    if not ts_path.exists():
        return payload

    compressed = bool(ref.get("compressed", str(ts_path).endswith(".gz")))
    payload["timeseries"] = _read_timeseries(str(ts_path), compressed=compressed)
    return payload


def _fmt_energy(kwh: float) -> str:
    return format_energy(kwh)


def _fmt_power(kw: float) -> str:
    return format_power(kw)


def _make_nodes(payload: dict[str, Any], unavailable: bool) -> dict[str, dict[str, Any]]:
    node_map = {n.get("id"): n for n in payload.get("flow_nodes", DEFAULT_FLOW_NODES)}
    summary = payload.get("annual_summary", {})
    generation = summary.get("generation", {})
    demand = summary.get("demand", {})
    battery = summary.get("battery", {})
    grid = summary.get("grid", {})
    balance = summary.get("balance", {})

    note = "<br>Status: noch nicht verfuegbar" if unavailable else ""

    return {
        "solar": {
            "x": float(node_map.get("solar", {}).get("x", 0.10)),
            "y": float(node_map.get("solar", {}).get("y", 0.48)),
            "label": "Solarautobahn",
            "icon": "solar",
            "hover": f"Jahreserzeugung: {_fmt_energy(generation.get('solar_highway_kwh', 0.0))}{note}",
        },
        "landscape": {
            "x": float(node_map.get("landscape", {}).get("x", 0.10)),
            "y": float(node_map.get("landscape", {}).get("y", 0.18)),
            "label": "Energielandschaft",
            "icon": "landscape",
            "hover": f"Jahreserzeugung: {_fmt_energy(generation.get('energy_landscape_kwh', 0.0))}{note}",
        },
        "grid": {
            "x": float(node_map.get("grid", {}).get("x", 0.50)),
            "y": float(node_map.get("grid", {}).get("y", 0.65)),
            "label": "Stromnetz",
            "icon": "grid",
            "hover": (
                f"Import: {_fmt_energy(grid.get('import_kwh', 0.0))}<br>"
                f"Export: {_fmt_energy(grid.get('export_kwh', 0.0))}{note}"
            ),
        },
        "battery": {
            "x": float(node_map.get("battery", {}).get("x", 0.50)),
            "y": float(node_map.get("battery", {}).get("y", 0.03)),
            "label": "Batterie Speicher",
            "icon": "battery",
            "hover": (
                f"Kapazitaet: {format_capacity(payload.get('input', {}).get('bs_energy_kwh', 0) or 0)}<br>"
                f"Ladung: {_fmt_energy(battery.get('charge_kwh', 0.0))}<br>"
                f"Entladung: {_fmt_energy(battery.get('discharge_kwh', 0.0))}{note}"
            ),
        },
        "industry": {
            "x": float(node_map.get("industry", {}).get("x", 0.98)),
            "y": float(node_map.get("industry", {}).get("y", 0.59)),
            "label": "Industriegebiet",
            "icon": "industry",
            "hover": f"Jahresbedarf: {_fmt_energy(demand.get('industry_kwh', 0.0))}{note}",
        },
        "js": {
            "x": float(node_map.get("js", {}).get("x", 0.98)),
            "y": float(node_map.get("js", {}).get("y", 0.33)),
            "label": "Stadtteil Juechen Sued",
            "icon": "js",
            "hover": f"Jahresbedarf: {_fmt_energy(demand.get('juechen_sued_kwh', 0.0))}{note}",
        },
        "hub": {
            "x": float(node_map.get("hub", {}).get("x", 0.98)),
            "y": float(node_map.get("hub", {}).get("y", 0.07)),
            "label": "Green Energy Hub",
            "icon": "hub",
            "hover": f"Jahresbedarf: {_fmt_energy(demand.get('green_energy_hub_kwh', 0.0))}{note}",
        },
        "system": {
            "x": float(node_map.get("system", {}).get("x", 0.54)),
            "y": float(node_map.get("system", {}).get("y", 0.33)),
            "label": "Systemknoten",
            "icon": None,
            "hover": (
                f"Gesamterzeugung: {_fmt_energy(generation.get('total_generation_kwh', 0.0))}<br>"
                f"Gesamtbedarf: {_fmt_energy(demand.get('total_demand_kwh', 0.0))}<br>"
                f"Bilanz: {_fmt_energy(balance.get('bal_energy_kwh', 0.0))}<br>"
                f"Autarkie: {100.0 * float(balance.get('coverage_rate', 0.0) or 0.0):.1f} %{note}"
            ),
        },
    }


def build_icon_flow_figure(payload: dict[str, Any], unavailable: bool) -> go.Figure:
    edges = {e.get("id"): e for e in payload.get("flow_edges", [])}
    nodes = _make_nodes(payload, unavailable)

    fig = go.Figure()
    fig.update_xaxes(visible=False, range=[-0.02, 1.10])
    fig.update_yaxes(visible=False, range=[-0.15, 1.10])

    box_w = 0.2
    box_h = 0.15

    add_legend(fig)

    for key in ["solar", "landscape", "grid", "battery", "industry", "hub", "js"]:
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
            layer="below",
        )
        add_node_with_icon(
            fig=fig,
            x=x,
            y=y,
            label=node["label"],
            icon_key=NODE_ICON_BY_ID[key],
            box_w=box_w,
            box_h=box_h,
            label_pos="below" if key == "battery" else "above",
        )

    fig.add_shape(
        type="circle",
        x0=nodes["system"]["x"] - 0.025,
        x1=nodes["system"]["x"] + 0.025,
        y0=nodes["system"]["y"] - 0.025,
        y1=nodes["system"]["y"] + 0.025,
        line=dict(color="gray", width=1.2),
        fillcolor="white",
    )

    for key, node in nodes.items():
        fig.add_trace(
            go.Scatter(
                x=[node["x"]],
                y=[node["y"]],
                mode="markers",
                marker=dict(size=26 if key == "system" else 60, opacity=0),
                hovertemplate=f"<b>{node['label']}</b><br>{node['hover']}<extra></extra>",
                showlegend=False,
            )
        )

    solar_right = (nodes["solar"]["x"] + box_w / 2, nodes["solar"]["y"])
    landscape_right = (nodes["landscape"]["x"] + box_w / 2, nodes["landscape"]["y"])
    grid_bottom = (nodes["grid"]["x"], nodes["grid"]["y"] - box_h / 2)
    battery_top = (nodes["battery"]["x"], nodes["battery"]["y"] + box_h / 2)
    industry_left = (nodes["industry"]["x"] - box_w / 2, nodes["industry"]["y"])
    js_left = (nodes["js"]["x"] - box_w / 2, nodes["js"]["y"])
    hub_left = (nodes["hub"]["x"] - box_w / 2, nodes["hub"]["y"])
    system_center = (nodes["system"]["x"], nodes["system"]["y"])

    x_left_join = (system_center[0] + solar_right[0]) / 2 - 0.07
    x_right_split = (system_center[0] + industry_left[0]) / 2 + 0.03
    half_y_grid = (grid_bottom[1] + system_center[1]) / 2
    half_y_bat = (battery_top[1] + system_center[1]) / 2

    def draw_edge(edge_id: str, points: list[tuple[float, float]], label: str | None = None) -> None:
        edge = edges.get(edge_id, {})
        annual = float(edge.get("annual_kwh", 0.0) or 0.0)
        if annual <= 0:
            return
        width = max(1.8, float(edge.get("stroke_px", 2.0) or 2.0))
        color = str(edge.get("color", "#10B35A"))
        add_routed_arrow(fig=fig, points=points, color=color, width=width, label=label)
        _add_hover_trace(fig, points, edge)

    draw_edge(
        "solar_to_system",
        [solar_right, (x_left_join, solar_right[1]), (x_left_join, system_center[1]), system_center],
    )
    draw_edge(
        "landscape_to_system",
        [landscape_right, (x_left_join, landscape_right[1]), (x_left_join, system_center[1]), system_center],
    )
    draw_edge(
        "system_to_industry",
        [system_center, (x_right_split, system_center[1]), (x_right_split, industry_left[1]), industry_left],
    )
    draw_edge(
        "system_to_js",
        [system_center, (x_right_split, system_center[1]), (x_right_split, js_left[1]), js_left],
    )
    draw_edge(
        "system_to_hub",
        [system_center, (x_right_split, system_center[1]), (x_right_split, hub_left[1]), hub_left],
    )
    draw_edge(
        "system_to_battery",
        [system_center, (system_center[0], half_y_bat), (battery_top[0], half_y_bat), battery_top],
    )
    draw_edge(
        "battery_to_system",
        [battery_top, (battery_top[0], half_y_bat), (system_center[0], half_y_bat), system_center],
    )

    export_edge = edges.get("system_to_grid", {})
    import_edge = edges.get("grid_to_system", {})
    export_kwh = float(export_edge.get("annual_kwh", 0.0) or 0.0)
    import_kwh = float(import_edge.get("annual_kwh", 0.0) or 0.0)

    if export_kwh > 0:
        points = [system_center, (system_center[0], half_y_grid), (grid_bottom[0], half_y_grid), grid_bottom]
        draw_edge("system_to_grid", points, label="Ueberschuss")
    elif import_kwh > 0:
        points = [grid_bottom, (grid_bottom[0], half_y_grid), (system_center[0], half_y_grid), system_center]
        draw_edge("grid_to_system", points, label="Netzbezug")

        # Visual hint that demand side is also grid-supplied when import dominates.
        demand_edge_ids = ["system_to_industry", "system_to_js", "system_to_hub"]
        demand_targets = [industry_left, js_left, hub_left]
        for demand_edge_id, target in zip(demand_edge_ids, demand_targets):
            demand_edge = edges.get(demand_edge_id, {})
            demand_width = max(1.2, float(demand_edge.get("stroke_px", 2.0) or 2.0) - 0.6)
            if float(demand_edge.get("annual_kwh", 0.0) or 0.0) > 0:
                add_optional_connection(
                    fig,
                    points=[system_center, (x_right_split, system_center[1]), (x_right_split, target[1]), target],
                    color="#B9B9B9",
                    width=demand_width,
                    dash="dot",
                )

    if unavailable:
        fig.add_annotation(
            x=0.54,
            y=0.88,
            text="<b>Auswahl noch nicht verfuegbar</b>",
            showarrow=False,
            font=dict(size=16, color="#B45309"),
            bgcolor="rgba(255,245,230,0.9)",
        )

    fig.add_shape(
        type="line",
        x0=0.1,
        x1=1.0,
        y0=0.815,
        y1=0.815,
        line=dict(color="gray", width=1),
    )
    fig.update_layout(
        margin=dict(l=20, r=20, t=30, b=20),
        height=760,
    )
    return fig


def _render_selector_form() -> dict[str, Any]:
    st.write("### Eingabeauswahl (wie Haupt-GUI)")

    with st.container(border=True):
        tab_gen1, tab_gen2 = st.tabs(["Solarautobahn", "Energielandschaft"])

        with tab_gen1:
            col1, col2 = st.columns(2)
            with col1:
                h_highways = st.multiselect("Autobahn auswaehlen", ["A44", "A46"], default=["A46"])
                h_pv_labels = st.multiselect(
                    "PV-Typ",
                    ["Laermschutzwand", "Windschutzwand", "Dach", "Boeschung"],
                    default=["Windschutzwand"],
                )
            with col2:
                if not h_highways or not h_pv_labels:
                    st.info("Solarautobahn deaktiviert.")
                else:
                    st.info("Solarautobahn aktiv.")

        with tab_gen2:
            col1, col2 = st.columns(2)
            with col1:
                el_build_state = st.segmented_control(
                    "Ausbaugrad Energielandschaft",
                    options=[0, 50, 100],
                    default=50,
                    format_func=lambda x: f"{x}%",
                )
                el_build_state = 0 if el_build_state is None else int(el_build_state)

                el_pv_name = st.selectbox(
                    "PV-Typ",
                    [
                        "Vertikal (Zaun, Nord-Sued)",
                        "Horizontal (aufgestaendert, Ost-West)",
                        "Horizontal mit Single-Axis-Tracking (aufgestaendert, Nord-Sued)",
                    ],
                    index=0,
                )
                el_tractor_width = st.segmented_control(
                    "Traktorbreite",
                    options=[9.0, 12.0, 15.0],
                    default=12.0,
                    format_func=lambda x: f"{x:.0f}m",
                )
                el_tractor_length = st.segmented_control(
                    "Traktorlaenge",
                    options=[12.0, 15.0, 18.0],
                    default=15.0,
                    format_func=lambda x: f"{x:.0f}m",
                )
                el_tractor_turn_radius = st.segmented_control(
                    "Traktor-Wenderadius",
                    options=[6.0, 9.0, 12.0],
                    default=9.0,
                    format_func=lambda x: f"{x:.0f}m",
                )
            with col2:
                if el_build_state == 0:
                    st.info("Energielandschaft deaktiviert.")
                else:
                    st.info("Energielandschaft aktiv.")

    st.write("### Verbrauchsauswahl")
    with st.container(border=True):
        tab_con1, tab_con2, tab_con3 = st.tabs(["Industriegebiet", "Green Energy Hub", "Juechen Sued"])

        with tab_con1:
            col1, col2 = st.columns(2)
            selected_companies: list[int] = []
            with col1:
                industry_mode = st.segmented_control(
                    "Unternehmensauswahl",
                    options=INDUSTRY_MODES,
                    default=INDUSTRY_MODES[0],
                    key="demo_industry_mode",
                )
                if industry_mode == INDUSTRY_MODES[1]:
                    st.write("Bis zu 5 Unternehmen auswaehlen (Duplikate moeglich):")
                    slot_options = [None] + list(INDUSTRY_OPTIONS.keys())
                    for idx in range(5):
                        selected = st.selectbox(
                            f"Unternehmen {idx + 1}",
                            options=slot_options,
                            index=slot_options.index(ELSBACHTAL_BASIS_COMPANIES[idx]),
                            format_func=lambda x: "Keine" if x is None else INDUSTRY_OPTIONS[x],
                            key=f"demo_company_{idx}",
                        )
                        if selected is not None:
                            selected_companies.append(int(selected))
                else:
                    selected_companies = list(ELSBACHTAL_BASIS_COMPANIES)
                    st.write("Je ein Unternehmen jedes Typs:")
                    st.markdown("\n".join(f"- {INDUSTRY_OPTIONS[i]}" for i in ELSBACHTAL_BASIS_COMPANIES))
            with col2:
                i_heat_cooling_electric = st.toggle("Mit Waerme/Kaelte Stromverbrauch?", value=True)
                if not selected_companies:
                    st.info("Industriegebiet deaktiviert.")
                else:
                    st.info(f"Industriegebiet aktiv ({len(selected_companies)} Auswahlwerte).")

        with tab_con2:
            geh_variant = st.segmented_control(
                "Variante",
                options=GEH_VARIANT_OPTIONS,
                default="Basis",
            )
            geh_variant = "Keine" if geh_variant is None else str(geh_variant)

            if geh_variant == "Keine":
                st.info("Green Energy Hub deaktiviert.")
            else:
                st.info(f"Green Energy Hub aktiv: {geh_variant}")

        with tab_con3:
            js_concept = st.segmented_control("Versorgungskonzept", options=JS_CONCEPT_OPTIONS, default="Dezentral")
            js_concept = "Aus" if js_concept is None else str(js_concept)
            if js_concept == "Aus":
                st.info("Juechen Sued deaktiviert.")
            else:
                st.info(f"Juechen Sued aktiv: {js_concept}")

    st.write("### Batterieauswahl")
    with st.container(border=True):
        capacity_mode = st.radio(
            "Kapazitaet waehlen ueber",
            options=["Standardwert", "Eigene Eingabe"],
            horizontal=True,
            index=0,
        )
        if capacity_mode == "Standardwert":
            bs_energy_kwh = st.segmented_control(
                "Kapazitaet",
                options=[0, 10000, 50000, 100000, 235000],
                default=0,
                format_func=lambda x: f"{x / 1000:.0f} MWh",
            )
            bs_energy_kwh = 0 if bs_energy_kwh is None else float(bs_energy_kwh)
        else:
            custom_mwh = st.number_input("Eigene Kapazitaet [MWh]", min_value=0.0, value=42.0, step=1.0)
            bs_energy_kwh = float(custom_mwh * 1000.0)

        bs_efficiency = st.select_slider(
            "Roundtrip Effizienz",
            options=[round(x, 3) for x in [0.80 + i * 0.01 for i in range(21)]],
            value=1.0,
            format_func=lambda x: f"{x:.0%}",
        )
        bs_c_rate = st.select_slider(
            "C-Rate",
            options=[0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0],
            value=1.0,
            format_func=lambda x: f"{x:.2g} C",
        )
        if bs_energy_kwh > 0:
            st.info(
                f"Batterie aktiv: {bs_energy_kwh / 1000:.0f} MWh, Effizienz {bs_efficiency:.0%}, C-Rate {bs_c_rate:.2g} C"
            )
        else:
            st.info("Batterie deaktiviert.")

    return {
        "h_highways": h_highways,
        "h_pv_types": [PV_NAME_TO_ID[label] for label in h_pv_labels],
        "el_build_state": el_build_state,
        "el_pv_type": PV_NAME_TO_ID[el_pv_name],
        "el_tractor_width": float(el_tractor_width if el_tractor_width is not None else 12.0),
        "el_tractor_length": float(el_tractor_length if el_tractor_length is not None else 15.0),
        "el_tractor_turn_radius": float(el_tractor_turn_radius if el_tractor_turn_radius is not None else 9.0),
        "i_heat_cooling_electric": bool(i_heat_cooling_electric),
        "i_companies": selected_companies,
        "geh_variant": geh_variant,
        "bs_efficiency": float(bs_efficiency) if bs_energy_kwh > 0 else None,
        "bs_energy_kwh": float(bs_energy_kwh) if bs_energy_kwh > 0 else None,
        "bs_c_rate": float(bs_c_rate) if bs_energy_kwh > 0 else None,
        "js_concept": js_concept,
    }


def _find_match(selected_input: dict[str, Any], catalog: list[dict[str, Any]]) -> str | None:
    selected_key = _canonical_key(selected_input)
    for entry in catalog:
        if entry.get("canonical_key") == selected_key:
            return str(entry["scenario_id"])
    return None


def _summary_cards(annual_summary: dict[str, Any]) -> None:
    generation = annual_summary.get("generation", {})
    demand = annual_summary.get("demand", {})
    balance = annual_summary.get("balance", {})
    grid = annual_summary.get("grid", {})

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Erzeugung", _fmt_energy(generation.get("total_generation_kwh", 0.0)))
    with col2:
        st.metric("Verbrauch", _fmt_energy(demand.get("total_demand_kwh", 0.0)))
    with col3:
        st.metric("Bilanz", _fmt_energy(balance.get("bal_energy_kwh", 0.0)))
    with col4:
        st.metric("Netzimport", _fmt_energy(grid.get("import_kwh", 0.0)))


def _render_catalog_overview(catalog: list[dict[str, Any]]) -> None:
    rows = []
    for entry in catalog:
        inp = entry.get("input", {})
        rows.append(
            {
                "scenario_id": entry.get("scenario_id"),
                "highways": ", ".join(inp.get("h_highways", [])) or "-",
                "h_pv_types": ", ".join(str(v) for v in inp.get("h_pv_types", [])) or "-",
                "el_build_state": inp.get("el_build_state", "-"),
                "companies": ", ".join(str(v) for v in inp.get("i_companies", [])) or "-",
                "geh": inp.get("geh_variant", "-"),
                "battery_kwh": inp.get("bs_energy_kwh", "-"),
                "js": inp.get("js_concept", "-"),
            }
        )
    st.dataframe(rows, use_container_width=True)


def main() -> None:
    st.set_page_config(page_title="Precomputed Demo", layout="wide")

    st.markdown(
        """
        <style>
        :root {
            --bg-1: #f8fafc;
            --bg-2: #f1f5f9;
            --ink: #0f172a;
            --sub: #334155;
            --accent: #0a7f46;
        }
        .demo-hero {
            border: 1px solid #dbe3ec;
            border-radius: 18px;
            padding: 18px 20px;
            background: linear-gradient(120deg, var(--bg-1), var(--bg-2));
            margin-bottom: 14px;
        }
        .demo-title {
            color: var(--ink);
            font-size: 1.55rem;
            font-weight: 700;
            line-height: 1.2;
            margin: 0;
        }
        .demo-sub {
            color: var(--sub);
            margin-top: 8px;
            margin-bottom: 0;
        }
        .accent {
            color: var(--accent);
            font-weight: 700;
        }
        </style>
        <div class="demo-hero">
            <p class="demo-title">Precomputed Demo - Inputbasierte Szenario-Auswahl</p>
            <p class="demo-sub">
                Eingaben wie in der Haupt-GUI setzen, dann passendes Precomputed-Szenario laden und Flussstaerken ueber <span class="accent">stroke_px</span> visualisieren.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    catalog = load_precomputed_catalog()
    if not catalog:
        st.error(
            "Keine Precomputed-Szenarien gefunden. Erwartet werden Unterordner mit flow_data.json unter data/outputs/precomputed/."
        )
        st.stop()

    top_left, top_right = st.columns([3, 1])
    with top_left:
        st.caption(f"Verfuegbare Precomputed-Szenarien: {len(catalog)}")
    with top_right:
        if st.button("Cache leeren", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    selected_input = _render_selector_form()
    matched_scenario = _find_match(selected_input, catalog)

    unavailable = matched_scenario is None
    if unavailable:
        st.warning("Die aktuelle Kombination ist noch nicht verfuegbar. Es wird eine Dummy-Visualisierung gezeigt.")
        payload = _build_unavailable_payload(selected_input)
    else:
        st.success(f"Passendes Szenario gefunden: {matched_scenario}")
        try:
            with st.spinner("Lade Szenario aus Precomputed JSON..."):
                payload = load_scenario_payload(matched_scenario)
        except Exception as exc:
            st.error(f"Fehler beim Laden des Szenarios: {exc}")
            st.stop()

    metadata = payload.get("metadata", {})
    annual_summary = payload.get("annual_summary", {})

    info_col1, info_col2, info_col3 = st.columns(3)
    with info_col1:
        st.caption(f"scenario_id: {metadata.get('scenario_id', 'noch_nicht_verfuegbar')}")
    with info_col2:
        st.caption(f"schema_version: {metadata.get('schema_version', '-')}")
    with info_col3:
        st.caption(f"created_at: {metadata.get('created_at', '-')}")

    _summary_cards(annual_summary)

    fig = build_icon_flow_figure(payload, unavailable=unavailable)
    st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False})

    with st.expander("Flow-Details", expanded=False):
        edges = payload.get("flow_edges", [])
        if edges:
            st.dataframe(edges, use_container_width=True)
        else:
            st.info("Keine Flow-Edges im Szenario gefunden.")

    with st.expander("Timeseries-Vorschau", expanded=False):
        timeseries = payload.get("timeseries", [])
        if not timeseries:
            st.info("Keine Timeseries im Payload geladen.")
        else:
            preview = timeseries[:96]
            st.dataframe(preview, use_container_width=True)

    with st.expander("Verfuegbare Precomputed-Kombinationen", expanded=False):
        _render_catalog_overview(catalog)


if __name__ == "__main__":
    main()
