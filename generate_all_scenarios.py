import argparse
import json
import shutil
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pandas as pd

from Simulation import run_simulation
from core.export_utils import export_scenario_flows_to_json
from core.io_types import GuiInput


PROJECT_ROOT = Path(__file__).resolve().parent
PRECOMPUTED_DIR = PROJECT_ROOT / "web_frontend" / "precomputed"
LEGACY_PRECOMPUTED_DIR = PROJECT_ROOT / "data" / "outputs" / "precomputed"
CATALOG_PATH = PROJECT_ROOT / "web_frontend" / "catalog.json"


def sort_unique_strings(values: list[Any]) -> list[str]:
    return sorted({str(v) for v in (values or []) if v is not None})


def sort_unique_ints(values: list[Any]) -> list[int]:
    out: set[int] = set()
    for value in values or []:
        try:
            out.add(int(value))
        except (TypeError, ValueError):
            continue
    return sorted(out)


def round_float(value: Any, digits: int = 3, fallback: float = 0.0) -> float:
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return fallback


def canonicalize_input(raw_input: dict[str, Any]) -> dict[str, Any]:
    bs_energy_kwh = round_float(raw_input.get("bs_energy_kwh"), 3, fallback=0.0)
    battery_active = bs_energy_kwh > 0

    return {
        "h_highways": sort_unique_strings(raw_input.get("h_highways", [])),
        "h_pv_types": sort_unique_ints(raw_input.get("h_pv_types", [])),
        "el_build_state": int(raw_input.get("el_build_state") or 0),
        "el_pv_type": int(raw_input.get("el_pv_type") or 0),
        "el_tractor_width": round_float(raw_input.get("el_tractor_width"), 3),
        "el_tractor_length": round_float(raw_input.get("el_tractor_length"), 3),
        "el_tractor_turn_radius": round_float(raw_input.get("el_tractor_turn_radius"), 3),
        "i_heat_cooling_electric": bool(raw_input.get("i_heat_cooling_electric", False)),
        "i_companies": sort_unique_ints(raw_input.get("i_companies", [])),
        "geh_h2_load_scenario": str(raw_input.get("geh_h2_load_scenario") or "Keine"),
        "geh_e_load_scenario": str(raw_input.get("geh_e_load_scenario") or "Keine"),
        "bs_energy_kwh": bs_energy_kwh if battery_active else None,
        "bs_efficiency": round_float(raw_input.get("bs_efficiency"), 3) if battery_active else None,
        "bs_c_rate": round_float(raw_input.get("bs_c_rate"), 3) if battery_active else None,
        "js_scenario": str(raw_input.get("js_scenario") or "Aus"),
    }


def canonical_key(raw_input: dict[str, Any]) -> str:
    return json.dumps(canonicalize_input(raw_input), sort_keys=True, ensure_ascii=True)


def build_permutation_space() -> list[GuiInput]:
    # Core axis 1: solar combinations (only UI-selectable pv_types: 0=Windschutzwand, 3=Böschung)
    solar_combinations = [
        {"h_highways": ["A46"], "h_pv_types": [0]},
        {"h_highways": ["A44"], "h_pv_types": [0]},
        {"h_highways": ["A44", "A46"], "h_pv_types": [0]},
        {"h_highways": ["A46"], "h_pv_types": [3]},
        {"h_highways": ["A44", "A46"], "h_pv_types": [3]},
        {"h_highways": ["A44", "A46"], "h_pv_types": [0, 3]},
    ]

    # Core axis 2: energy landscape stages
    landscape_stages = [
        {
            "el_build_state": 0,
            "el_pv_type": 5,
            "el_tractor_width": 12.0,
            "el_tractor_length": 15.0,
            "el_tractor_turn_radius": 9.0,
        },
        {
            "el_build_state": 50,
            "el_pv_type": 5,
            "el_tractor_width": 12.0,
            "el_tractor_length": 15.0,
            "el_tractor_turn_radius": 9.0,
        },
        {
            "el_build_state": 100,
            "el_pv_type": 6,
            "el_tractor_width": 12.0,
            "el_tractor_length": 15.0,
            "el_tractor_turn_radius": 9.0,
        },
    ]

    # Core axis 3: industry profiles (5-company style as in UI)
    industry_profiles = [
        [2, 3, 4, 5, 6],
        [1, 3, 5, 6, 7],
        [0, 1, 2, 3, 4],
        [0, 2, 4, 6, 7],
        [0, 1, 5, 6, 7],
        [1, 2, 3, 4, 7],
        [0, 3, 4, 5, 6],
        [0, 2, 3, 5, 7],
        [1, 2, 4, 5, 6],
        [0, 1, 3, 6, 7],
        [0, 2, 3, 4, 6],
        [1, 3, 4, 5, 7],
    ]

    # Core axis 4: battery (kein Speicher — Batterie wird in der Web-App nicht unterstützt)
    battery_sizes = [
        {"bs_energy_kwh": None, "bs_efficiency": None, "bs_c_rate": None},
    ]

    combinations: list[GuiInput] = []
    for solar in solar_combinations:
        for landscape in landscape_stages:
            for industry in industry_profiles:
                for battery in battery_sizes:
                    combinations.append(
                        GuiInput(
                            h_highways=list(solar["h_highways"]),
                            h_pv_types=list(solar["h_pv_types"]),
                            el_build_state=int(landscape["el_build_state"]),
                            el_pv_type=int(landscape["el_pv_type"]),
                            el_tractor_width=float(landscape["el_tractor_width"]),
                            el_tractor_length=float(landscape["el_tractor_length"]),
                            el_tractor_turn_radius=float(landscape["el_tractor_turn_radius"]),
                            i_heat_cooling_electric=True,
                            i_companies=list(industry),
                            geh_h2_load_scenario="2022",
                            geh_e_load_scenario="2022",
                            # H2-Prozesskette: Standardparameter für Webszenarien
                            geh_electrolyzer_power_kw=1000.0,       # 1 MW Elektrolyseur
                            geh_electrolyzer_efficiency=0.70,        # 70 % Systemwirkungsgrad
                            geh_storage_capacity_kwh=10_000.0,       # 10 MWh H2-Speicher
                            geh_storage_max_charge_kw=1000.0,        # Max. Ladeleistung = Elektrolyseur
                            geh_dispenser_demand_kg_per_h=10.0,      # ~330 kW Dauerverbrauch
                            js_scenario="1000 Bewohner",
                            bs_energy_kwh=battery["bs_energy_kwh"],
                            bs_efficiency=battery["bs_efficiency"],
                            bs_c_rate=battery["bs_c_rate"],
                        )
                    )

    return combinations


def build_timeseries_csv_frame(sim_output: Any) -> pd.DataFrame:
    res_df = getattr(sim_output, "res_df", pd.DataFrame())
    if not isinstance(res_df, pd.DataFrame) or res_df.empty:
        return pd.DataFrame(
            columns=[
                "timestamp",
                "generation_solar_kw",
                "generation_landscape_kw",
                "demand_industry_kw",
                "demand_hub_kw",
                "demand_js_kw",
                "balance_kw",
            ]
        )

    ts_df = pd.DataFrame(index=res_df.index)
    ts_df["generation_solar_kw"] = pd.to_numeric(
        res_df.get("Erzeugung_Solarautobahn [kW]", 0.0), errors="coerce"
    ).fillna(0.0)
    ts_df["generation_landscape_kw"] = pd.to_numeric(
        res_df.get("Erzeugung_Energielandschaft [kW]", 0.0), errors="coerce"
    ).fillna(0.0)
    ts_df["demand_industry_kw"] = pd.to_numeric(
        res_df.get("Last_Industrie [kW]", 0.0), errors="coerce"
    ).fillna(0.0)
    ts_df["demand_hub_kw"] = pd.to_numeric(
        res_df.get("Last_Green_Energy_Hub [kW]", 0.0), errors="coerce"
    ).fillna(0.0)
    ts_df["demand_js_kw"] = pd.to_numeric(
        res_df.get("Last_Juechen_Sued [kW]", 0.0), errors="coerce"
    ).fillna(0.0)
    ts_df["balance_kw"] = pd.to_numeric(res_df.get("Bilanz [kW]", 0.0), errors="coerce").fillna(0.0)

    ts_df = ts_df.reset_index().rename(columns={"index": "timestamp"})
    if "timestamp" not in ts_df.columns:
        ts_df["timestamp"] = ""
    ts_df["timestamp"] = ts_df["timestamp"].astype(str)

    for col in [
        "generation_solar_kw",
        "generation_landscape_kw",
        "demand_industry_kw",
        "demand_hub_kw",
        "demand_js_kw",
        "balance_kw",
    ]:
        ts_df[col] = ts_df[col].round(6)

    return ts_df[
        [
            "timestamp",
            "generation_solar_kw",
            "generation_landscape_kw",
            "demand_industry_kw",
            "demand_hub_kw",
            "demand_js_kw",
            "balance_kw",
        ]
    ]


def write_timeseries_csv_gz(sim_output: Any, scenario_dir: Path) -> tuple[str, int]:
    ts_df = build_timeseries_csv_frame(sim_output)
    csv_gz_name = "timeseries.csv.gz"
    csv_gz_path = scenario_dir / csv_gz_name
    ts_df.to_csv(csv_gz_path, index=False, compression="gzip")
    return csv_gz_name, len(ts_df)


def annotate_flow_json_with_csv_ref(flow_json_path: Path, csv_name: str, records: int) -> None:
    with flow_json_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    metadata = payload.get("metadata") or {}
    metadata["timeseries_mode_detail"] = "separate_csv_gzip"
    payload["metadata"] = metadata
    payload["timeseries_csv_ref"] = {
        "path": csv_name,
        "compressed": True,
        "format": "csv",
        "records": int(records),
    }

    with flow_json_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def build_catalog_from_precomputed() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if not PRECOMPUTED_DIR.exists():
        return entries

    for scenario_dir in sorted(PRECOMPUTED_DIR.iterdir()):
        if not scenario_dir.is_dir():
            continue

        flow_path = scenario_dir / "flow_data.json"
        if not flow_path.exists():
            continue

        with flow_path.open("r", encoding="utf-8") as f:
            payload = json.load(f)

        raw_input = payload.get("input") or {}
        entries.append(
            {
                "scenario_id": scenario_dir.name,
                "canonical_key": canonical_key(raw_input),
                "flow_path": f"./precomputed/{scenario_dir.name}/flow_data.json",
                "input": raw_input,
            }
        )

    entries.sort(key=lambda item: str(item.get("scenario_id", "")))
    return entries


def write_catalog(entries: list[dict[str, Any]]) -> None:
    CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CATALOG_PATH.open("w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)


def migrate_legacy_scenarios() -> dict[str, int]:
    """Kopiert Null-Batterie-Szenarien aus data/outputs/precomputed/ nach web_frontend/precomputed/."""
    if not LEGACY_PRECOMPUTED_DIR.exists():
        print("Legacy-Verzeichnis nicht gefunden, Migration übersprungen.")
        return {"copied": 0, "skipped_battery": 0, "failed": 0}

    PRECOMPUTED_DIR.mkdir(parents=True, exist_ok=True)
    copied = 0
    skipped_battery = 0
    failed = 0

    for scenario_dir in sorted(LEGACY_PRECOMPUTED_DIR.iterdir()):
        if not scenario_dir.is_dir():
            continue
        flow_path = scenario_dir / "flow_data.json"
        if not flow_path.exists():
            continue
        try:
            with flow_path.open("r", encoding="utf-8") as f:
                payload = json.load(f)
            raw_input = payload.get("input") or {}
            if raw_input.get("bs_energy_kwh") is not None:
                skipped_battery += 1
                continue
            dest = PRECOMPUTED_DIR / scenario_dir.name
            if dest.exists():
                print(f"  [skip] {scenario_dir.name} bereits vorhanden")
            else:
                shutil.copytree(str(scenario_dir), str(dest))
                print(f"  [copy] {scenario_dir.name}")
                copied += 1
        except Exception as exc:
            failed += 1
            print(f"  [warn] Migration fehlgeschlagen für {scenario_dir.name}: {exc}")

    return {"copied": copied, "skipped_battery": skipped_battery, "failed": failed}


def generate_scenarios(max_scenarios: int, overwrite: bool) -> dict[str, int]:
    PRECOMPUTED_DIR.mkdir(parents=True, exist_ok=True)

    all_candidates = build_permutation_space()
    seen_keys: set[str] = set()

    generated = 0
    skipped_duplicates = 0
    failed = 0

    for candidate in all_candidates:
        raw_input = asdict(candidate)
        key = canonical_key(raw_input)
        if key in seen_keys:
            skipped_duplicates += 1
            continue
        seen_keys.add(key)

        scenario_id = f"s_auto_{generated + 1:04d}"
        scenario_dir = PRECOMPUTED_DIR / scenario_id

        if overwrite and scenario_dir.exists():
            shutil.rmtree(scenario_dir)

        print(f"[{generated + 1}] simulate {scenario_id}")
        try:
            sim_output = run_simulation(candidate)

            flow_json_str = export_scenario_flows_to_json(
                inp=candidate,
                sim_output=sim_output,
                scenario_id=scenario_id,
                output_dir=PRECOMPUTED_DIR,
                timeseries_mode="none",
                compress_timeseries=False,
            )

            flow_json_path = Path(flow_json_str)
            csv_name, records = write_timeseries_csv_gz(sim_output, scenario_dir)
            annotate_flow_json_with_csv_ref(flow_json_path, csv_name, records)

            generated += 1
            if max_scenarios > 0 and generated >= max_scenarios:
                break
        except Exception as exc:
            failed += 1
            print(f"[warn] scenario failed {scenario_id}: {exc}")

    catalog_entries = build_catalog_from_precomputed()
    write_catalog(catalog_entries)

    return {
        "generated": generated,
        "failed": failed,
        "skipped_duplicates": skipped_duplicates,
        "catalog_entries": len(catalog_entries),
        "total_candidates": len(all_candidates),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate precomputed scenarios, export flow_data.json and timeseries.csv.gz, then refresh web_frontend/catalog.json."
    )
    parser.add_argument(
        "--max-scenarios",
        type=int,
        default=8,
        help="Maximum number of scenarios to generate (0 means all). Default is 8 for a safe test run.",
    )
    parser.add_argument(
        "--overwrite",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Overwrite existing scenario folders with same scenario_id.",
    )
    parser.add_argument(
        "--migrate-legacy",
        action="store_true",
        default=False,
        help="Null-Batterie-Szenarien aus data/outputs/precomputed/ nach web_frontend/precomputed/ kopieren.",
    )
    parser.add_argument(
        "--catalog-only",
        action="store_true",
        default=False,
        help="Nur catalog.json neu aufbauen, keine neue Simulation.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.migrate_legacy:
        print("=== Migriere Legacy-Szenarien ===")
        m = migrate_legacy_scenarios()
        print(f"kopiert: {m['copied']}, Batterie übersprungen: {m['skipped_battery']}, Fehler: {m['failed']}")

    if args.catalog_only:
        print("=== Baue Katalog neu (nur Katalog) ===")
        entries = build_catalog_from_precomputed()
        write_catalog(entries)
        print(f"catalog.json aktualisiert: {len(entries)} Einträge")
        return

    if not args.migrate_legacy:
        stats = generate_scenarios(max_scenarios=max(0, int(args.max_scenarios)), overwrite=bool(args.overwrite))
        print("\nDone.")
        print(f"generated: {stats['generated']}")
        print(f"failed: {stats['failed']}")
        print(f"skipped_duplicates: {stats['skipped_duplicates']}")
        print(f"catalog_entries: {stats['catalog_entries']}")
        print(f"total_candidates: {stats['total_candidates']}")
    else:
        print("=== Baue Katalog nach Migration neu ===")
        entries = build_catalog_from_precomputed()
        write_catalog(entries)
        print(f"catalog.json aktualisiert: {len(entries)} Einträge")


if __name__ == "__main__":
    main()
