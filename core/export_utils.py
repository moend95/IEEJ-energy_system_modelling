import json
import gzip
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


def _safe_float(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(value, max_value))


def _series_or_empty(df: pd.DataFrame, column: str) -> pd.Series:
    if df is None or df.empty or column not in df.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(df[column], errors="coerce").fillna(0.0)


def _build_timeseries_records(res_df: pd.DataFrame, round_digits: int = 6) -> list[dict[str, float | str]]:
    if not isinstance(res_df, pd.DataFrame) or res_df.empty:
        return []

    ts_df = pd.DataFrame(index=res_df.index)
    ts_df["generation_solar_kw"] = _series_or_empty(res_df, "Erzeugung_Solarautobahn [kW]")
    ts_df["generation_landscape_kw"] = _series_or_empty(res_df, "Erzeugung_Energielandschaft [kW]")
    ts_df["demand_industry_kw"] = _series_or_empty(res_df, "Last_Industrie [kW]")
    ts_df["demand_hub_kw"] = _series_or_empty(res_df, "Last_Green_Energy_Hub [kW]")
    ts_df["demand_js_kw"] = _series_or_empty(res_df, "Last_Juechen_Sued [kW]")
    ts_df["balance_kw"] = _series_or_empty(res_df, "Bilanz [kW]")
    ts_df = ts_df.fillna(0.0)

    return [
        {
            "timestamp": str(idx),
            "generation_solar_kw": round(_safe_float(row["generation_solar_kw"]), round_digits),
            "generation_landscape_kw": round(_safe_float(row["generation_landscape_kw"]), round_digits),
            "demand_industry_kw": round(_safe_float(row["demand_industry_kw"]), round_digits),
            "demand_hub_kw": round(_safe_float(row["demand_hub_kw"]), round_digits),
            "demand_js_kw": round(_safe_float(row["demand_js_kw"]), round_digits),
            "balance_kw": round(_safe_float(row["balance_kw"]), round_digits),
        }
        for idx, row in ts_df.iterrows()
    ]


def _write_json(path: Path, payload: Any, compress: bool = False) -> None:
    if compress:
        with gzip.open(path, "wt", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
    else:
        with path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)


def _grid_peaks_kw(sim_output: Any) -> tuple[float, float]:
    res_df = getattr(sim_output, "res_df", pd.DataFrame())
    import_series = _series_or_empty(res_df, "Netzbezug [kW]")
    export_series = _series_or_empty(res_df, "Netzeinspeisung [kW]")
    import_peak = _safe_float(import_series.max()) if not import_series.empty else 0.0
    export_peak = _safe_float(export_series.max()) if not export_series.empty else 0.0
    return import_peak, export_peak


def export_scenario_flows_to_json(
    inp: Any,
    sim_output: Any,
    scenario_id: str,
    output_dir: str | Path,
    schema_version: str = "1.2.0",
    min_px: float = 2.0,
    max_px: float = 8.0,
    timeseries_mode: str = "inline",
    compress_timeseries: bool = False,
) -> str:
    """
    Export simulation flow data to JSON for precomputed web visualization.

    The JSON includes:
    - metadata and annual summary
    - flow nodes and directed edges
    - normalized edge thickness for variable-width arrows
    """
    scenario_id = str(scenario_id)
    valid_timeseries_modes = {"inline", "separate", "none"}
    if timeseries_mode not in valid_timeseries_modes:
        raise ValueError(
            f"Unsupported timeseries_mode '{timeseries_mode}'. Use one of {sorted(valid_timeseries_modes)}"
        )

    out_dir = Path(output_dir) / scenario_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "flow_data.json"

    res_df = getattr(sim_output, "res_df", pd.DataFrame())
    bs_stats = getattr(sim_output, "bs_stats", {}) or {}

    solar_kwh = max(_safe_float(getattr(sim_output, "h_sum_energy_kwh", 0.0)), 0.0)
    landscape_kwh = max(_safe_float(getattr(sim_output, "el_sum_energy_kwh", 0.0)), 0.0)
    industry_kwh = max(_safe_float(getattr(sim_output, "i_sum_energy_kwh", 0.0)), 0.0)
    geh_kwh = max(_safe_float(getattr(sim_output, "geh_sum_energy_kwh", 0.0)), 0.0)
    geh_pv_kwh = max(_safe_float(getattr(sim_output, "geh_pv_sum_energy_kwh", 0.0)), 0.0)
    js_kwh = max(_safe_float(getattr(sim_output, "js_sum_energy_kwh", 0.0)), 0.0)

    total_generation_kwh = solar_kwh + landscape_kwh + geh_pv_kwh
    total_demand_kwh = industry_kwh + geh_kwh + js_kwh

    battery_charge_kwh = max(_safe_float(bs_stats.get("battery_charge_kwh", 0.0)), 0.0)
    battery_discharge_kwh = max(_safe_float(bs_stats.get("battery_discharge_kwh", 0.0)), 0.0)

    # Netzaustausch nach allen Speichern (GEH-Batterie und allgemeine Batterie)
    grid_import_kwh = max(_safe_float(getattr(sim_output, "grid_import_kwh", 0.0)), 0.0)
    grid_export_kwh = max(_safe_float(getattr(sim_output, "grid_export_kwh", 0.0)), 0.0)

    grid_import_peak_kw, grid_export_peak_kw = _grid_peaks_kw(sim_output)

    def nonneg(attr: str) -> float:
        return max(_safe_float(getattr(sim_output, attr, 0.0)), 0.0)

    nodes = [
        {"id": "solar", "label": "Solarautobahn", "x": 0.10, "y": 0.48, "type": "generation"},
        {"id": "landscape", "label": "Energielandschaft", "x": 0.10, "y": 0.18, "type": "generation"},
        {"id": "system", "label": "System", "x": 0.54, "y": 0.33, "type": "junction"},
        {"id": "industry", "label": "Industriegebiet", "x": 0.98, "y": 0.59, "type": "consumption"},
        {"id": "js", "label": "Juechen Sued", "x": 0.98, "y": 0.33, "type": "consumption"},
        {"id": "hub", "label": "Green Energy Hub", "x": 0.98, "y": 0.07, "type": "consumption"},
        {"id": "grid", "label": "Stromnetz", "x": 0.50, "y": 0.65, "type": "external"},
        {"id": "battery", "label": "Batterie", "x": 0.50, "y": 0.03, "type": "storage"},
    ]

    edges = [
        {
            "id": "solar_to_system",
            "source": "solar",
            "target": "system",
            "flow_type": "generation",
            "annual_kwh": solar_kwh,
            "peak_kw": max(_safe_float(getattr(sim_output, "h_max_power_kw", 0.0)), 0.0),
            "color": "#10B35A",
            "direction": "right",
        },
        {
            "id": "landscape_to_system",
            "source": "landscape",
            "target": "system",
            "flow_type": "generation",
            "annual_kwh": landscape_kwh,
            "peak_kw": max(_safe_float(getattr(sim_output, "el_max_power_kw", 0.0)), 0.0),
            "color": "#10B35A",
            "direction": "right",
        },
        {
            "id": "system_to_industry",
            "source": "system",
            "target": "industry",
            "flow_type": "consumption",
            "annual_kwh": industry_kwh,
            "peak_kw": max(_safe_float(getattr(sim_output, "i_max_power_kw", 0.0)), 0.0),
            "color": "#10B35A",
            "direction": "right",
        },
        {
            "id": "system_to_js",
            "source": "system",
            "target": "js",
            "flow_type": "consumption",
            "annual_kwh": js_kwh,
            "peak_kw": max(_safe_float(getattr(sim_output, "js_max_power_kw", 0.0)), 0.0),
            "color": "#10B35A",
            "direction": "right",
        },
        {
            "id": "hub_pv_to_system",
            "source": "hub",
            "target": "system",
            "flow_type": "generation",
            "annual_kwh": geh_pv_kwh,
            "peak_kw": max(_safe_float(getattr(sim_output, "geh_pv_max_power_kw", 0.0)), 0.0),
            "color": "#10B35A",
            "direction": "left",
        },
        {
            "id": "system_to_hub",
            "source": "system",
            "target": "hub",
            "flow_type": "consumption",
            "annual_kwh": geh_kwh,
            "peak_kw": max(_safe_float(getattr(sim_output, "geh_max_power_kw", 0.0)), 0.0),
            "color": "#10B35A",
            "direction": "right",
        },
        {
            "id": "system_to_battery",
            "source": "system",
            "target": "battery",
            "flow_type": "charge",
            "annual_kwh": battery_charge_kwh,
            "peak_kw": max(_safe_float(bs_stats.get("max_charge_kw", 0.0)), 0.0),
            "color": "#1DA1F2",
            "direction": "down",
        },
        {
            "id": "battery_to_system",
            "source": "battery",
            "target": "system",
            "flow_type": "discharge",
            "annual_kwh": battery_discharge_kwh,
            "peak_kw": max(_safe_float(bs_stats.get("max_discharge_kw", 0.0)), 0.0),
            "color": "#1DA1F2",
            "direction": "up",
        },
        {
            "id": "system_to_grid",
            "source": "system",
            "target": "grid",
            "flow_type": "export",
            "annual_kwh": grid_export_kwh,
            "peak_kw": grid_export_peak_kw,
            "color": "#10B35A",
            "direction": "up",
        },
        {
            "id": "grid_to_system",
            "source": "grid",
            "target": "system",
            "flow_type": "import",
            "annual_kwh": grid_import_kwh,
            "peak_kw": grid_import_peak_kw,
            "color": "#B9B9B9",
            "direction": "down",
        },
    ]

    max_flow_kwh = max((edge["annual_kwh"] for edge in edges), default=0.0)
    if max_flow_kwh <= 0:
        max_flow_kwh = 1.0

    for edge in edges:
        norm = _clamp(edge["annual_kwh"] / max_flow_kwh, 0.0, 1.0)
        edge["thickness_norm"] = round(norm, 6)
        edge["stroke_px"] = round(min_px + norm * (max_px - min_px), 3)

    annual_summary = {
        "generation": {
            "solar_highway_kwh": solar_kwh,
            "energy_landscape_kwh": landscape_kwh,
            "green_energy_hub_pv_kwh": geh_pv_kwh,
            "total_generation_kwh": total_generation_kwh,
        },
        "demand": {
            "industry_kwh": industry_kwh,
            "green_energy_hub_kwh": geh_kwh,
            "juechen_sued_kwh": js_kwh,
            "total_demand_kwh": total_demand_kwh,
        },
        "juechen_sued": {
            "concept": str(getattr(inp, "js_concept", None) or "Aus"),
            "household_kwh": nonneg("js_household_kwh"),
            "emob_kwh": nonneg("js_emob_kwh"),
            "space_heat_kwh": nonneg("js_space_heat_kwh"),
            "dhw_kwh": nonneg("js_dhw_kwh"),
            "cooling_kwh": nonneg("js_cooling_kwh"),
            "heat_pump_el_kwh": nonneg("js_hp_el_kwh"),
            "heater_el_kwh": nonneg("js_heater_el_kwh"),
            "cooling_el_kwh": nonneg("js_cooling_el_kwh"),
            "heat_unmet_kwh": nonneg("js_heat_unmet_kwh"),
            "heat_pump_scop": nonneg("js_hp_scop"),
        },
        "green_energy_hub": {
            "variant": str(getattr(inp, "geh_variant", None) or "Keine"),
            "charging_mcs_kwh": nonneg("geh_charging_mcs_kwh"),
            "charging_ccs_kwh": nonneg("geh_charging_ccs_kwh"),
            "charging_hpc_kwh": nonneg("geh_charging_hpc_kwh"),
            "charging_ac_kwh": nonneg("geh_charging_ac_kwh"),
            "building_kwh": nonneg("geh_building_kwh"),
            "pv_kwh": geh_pv_kwh,
            "pv_max_power_kw": nonneg("geh_pv_max_power_kw"),
            "electrolyzer_kwh": nonneg("geh_electrolyzer_kwh"),
            "electrolyzer_full_load_hours": nonneg("geh_electrolyzer_full_load_hours"),
            "compressor_demand_kwh": nonneg("geh_compressor_demand_kwh"),
            "h2_production_kwh": nonneg("geh_h2_production_kwh"),
            "h2_demand_kwh": nonneg("geh_h2_demand_kwh"),
            "h2_delivered_kwh": nonneg("geh_h2_delivered_kwh"),
            "h2_unmet_kwh": nonneg("geh_h2_unmet_kwh"),
            "battery_charge_kwh": nonneg("geh_battery_charge_kwh"),
            "battery_discharge_kwh": nonneg("geh_battery_discharge_kwh"),
            "battery_full_cycles": nonneg("geh_battery_full_cycles"),
            "electrolyzer_base_kw": nonneg("geh_electrolyzer_base_kw"),
            "grid_limit_kw": nonneg("geh_grid_limit_kw"),
            "grid_peak_kw": nonneg("geh_grid_peak_kw"),
            "grid_limit_exceed_hours": nonneg("geh_grid_limit_exceed_hours"),
        },
        "balance": {
            "bal_energy_kwh": _safe_float(getattr(sim_output, "bal_energy_kwh", 0.0)),
            "coverage_rate": _safe_float(getattr(sim_output, "bal_coverage_rate", 0.0)),
            "ee_self_consumption": _safe_float(getattr(sim_output, "ee_self_consumption", 0.0)),
            "autarky": _safe_float(getattr(sim_output, "autarky", 0.0)),
        },
        "battery": {
            "charge_kwh": battery_charge_kwh,
            "discharge_kwh": battery_discharge_kwh,
            "final_soc_kwh": _safe_float(bs_stats.get("final_soc_kwh", 0.0)),
            "final_soc_percent": _safe_float(bs_stats.get("final_soc_percent", 0.0)),
        },
        "grid": {
            "import_kwh": grid_import_kwh,
            "export_kwh": grid_export_kwh,
            "max_import_kw": grid_import_peak_kw,
            "max_export_kw": grid_export_peak_kw,
        },
    }

    timeseries_records: list[dict[str, float | str]] = []
    if timeseries_mode in {"inline", "separate"}:
        timeseries_records = _build_timeseries_records(res_df)

    timeseries_ref: dict[str, Any] | None = None
    if timeseries_mode == "separate":
        timeseries_name = "timeseries.json.gz" if compress_timeseries else "timeseries.json"
        timeseries_path = out_dir / timeseries_name
        _write_json(timeseries_path, timeseries_records, compress=compress_timeseries)
        timeseries_ref = {
            "path": timeseries_name,
            "compressed": bool(compress_timeseries),
            "records": len(timeseries_records),
        }

    payload = {
        "metadata": {
            "scenario_id": scenario_id,
            "schema_version": schema_version,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "time_step_minutes": 15,
            "timeseries_mode": timeseries_mode,
        },
        "input": asdict(inp),
        "annual_summary": annual_summary,
        "flow_nodes": nodes,
        "flow_edges": edges,
        "timeseries": timeseries_records if timeseries_mode == "inline" else [],
        "timeseries_ref": timeseries_ref,
    }

    _write_json(out_path, payload, compress=False)

    return str(out_path)
