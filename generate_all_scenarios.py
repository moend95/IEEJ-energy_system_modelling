import argparse
import json
import os
import shutil
import time
from itertools import combinations as subsets, product
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pandas as pd

from Simulation import run_simulation
from core.export_utils import export_scenario_flows_to_json
from core.io_types import GuiInput
from core.module_industrial_area import ELSBACHTAL_BASIS_COMPANIES
from core.module_energy_landscape import (
    LANDSCAPE_TRACTOR_LENGTH_M,
    LANDSCAPE_TRACTOR_TURN_RADIUS_M,
    LANDSCAPE_TRACTOR_WIDTH_M,
)


PROJECT_ROOT = Path(__file__).resolve().parent
WEB_FRONTEND_DIR = PROJECT_ROOT / "web_frontend"
PRECOMPUTED_DIR = WEB_FRONTEND_DIR / "precomputed_v2"
LEGACY_PRECOMPUTED_DIR = PROJECT_ROOT / "data" / "outputs" / "precomputed"
CATALOG_NAME = "catalog.json"   # liegt im Ausgabeordner, damit alte Daten bis zum Laufende nutzbar bleiben

MODEL_VERSION = "2026-11-geh2-el27"
SCHEMA_VERSION = "1.2.0"
INDUSTRY_MODES = ("leave-one-out", "all-subsets")


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
        # Feste Landmaschinen-Auslegung, wie canonicalizeInput in web_frontend/app.js
        "el_tractor_width": round_float(LANDSCAPE_TRACTOR_WIDTH_M, 3),
        "el_tractor_length": round_float(LANDSCAPE_TRACTOR_LENGTH_M, 3),
        "el_tractor_turn_radius": round_float(LANDSCAPE_TRACTOR_TURN_RADIUS_M, 3),
        "i_heat_cooling_electric": bool(raw_input.get("i_heat_cooling_electric", False)),
        "i_companies": sort_unique_ints(raw_input.get("i_companies", [])),
        "geh_variant": str(raw_input.get("geh_variant") or "Keine"),
        "bs_energy_kwh": bs_energy_kwh if battery_active else None,
        "bs_efficiency": round_float(raw_input.get("bs_efficiency"), 3) if battery_active else None,
        "bs_c_rate": round_float(raw_input.get("bs_c_rate"), 3) if battery_active else None,
        "js_concept": str(raw_input.get("js_concept") or "Aus"),
    }


def canonical_key(raw_input: dict[str, Any]) -> str:
    return json.dumps(canonicalize_input(raw_input), sort_keys=True, ensure_ascii=True)


def build_industry_profiles(mode: str = "leave-one-out") -> list[list[int]]:
    """
    Industrieprofile, Basis-Variante Elsbachtal immer zuerst (UI-Standard).
      leave-one-out: zusätzlich die Basis ohne jeweils einen Unternehmenstyp (6 Profile)
      all-subsets:   alle nicht leeren Teilmengen der Basis-Unternehmen (31 Profile)
    """
    basis = list(ELSBACHTAL_BASIS_COMPANIES)
    if mode == "leave-one-out":
        return [basis] + [[c for c in basis if c != removed] for removed in basis]
    if mode == "all-subsets":
        out = [basis]
        for size in range(len(basis) - 1, 0, -1):
            out += [list(s) for s in subsets(basis, size)]
        return out
    raise ValueError(f"Unbekannter Industriemodus '{mode}', erwartet {INDUSTRY_MODES}")


def landscape_stage(build_state: int, pv_type: int) -> dict[str, Any]:
    return {
        "el_build_state": build_state,
        "el_pv_type": pv_type,
        "el_tractor_width": LANDSCAPE_TRACTOR_WIDTH_M,
        "el_tractor_length": LANDSCAPE_TRACTOR_LENGTH_M,
        "el_tractor_turn_radius": LANDSCAPE_TRACTOR_TURN_RADIUS_M,
    }


def build_permutation_space(industry_mode: str = "leave-one-out") -> list[GuiInput]:
    # Core axis 1: solar combinations (only UI-selectable pv_types: 0=Windschutzwand, 3=Böschung)
    solar_combinations = [
        {"h_highways": ["A46"], "h_pv_types": [0]},
        {"h_highways": ["A44"], "h_pv_types": [0]},
        {"h_highways": ["A44", "A46"], "h_pv_types": [0]},
        {"h_highways": ["A46"], "h_pv_types": [3]},
        {"h_highways": ["A44", "A46"], "h_pv_types": [3]},
        {"h_highways": ["A44", "A46"], "h_pv_types": [0, 3]},
    ]

    # Core axis 2: energy landscape stages (UI-Standard 50 % vertikal zuerst; 0 % mit Typ 5 als Platzhalter)
    landscape_stages = [
        landscape_stage(50, 5),
        landscape_stage(0, 5),
        landscape_stage(50, 4),
        landscape_stage(100, 5),
        landscape_stage(100, 4),
    ]

    # Core axis 3: industry profiles
    industry_profiles = build_industry_profiles(industry_mode)

    # Core axis 4: battery (kein Speicher — Batterie wird in der Web-App nicht unterstützt)
    battery_sizes = [
        {"bs_energy_kwh": None, "bs_efficiency": None, "bs_c_rate": None},
    ]

    # Achse 5 und 6: Green-Energy-Hub-Variante und Jüchen-Süd-Versorgungskonzept (UI-Standard zuerst)
    geh_variants = ["Basis", "Erweiterung", "Keine"]
    js_concepts = ["Dezentral", "Warmes Netz", "Kaltes Netz", "Aus"]

    combinations: list[GuiInput] = []
    for solar in solar_combinations:
        for landscape in landscape_stages:
            for industry in industry_profiles:
                for battery, geh_variant, js_concept in product(battery_sizes, geh_variants, js_concepts):
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
                            geh_variant=geh_variant,
                            js_concept=js_concept,
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


def annotate_flow_json(flow_json_path: Path, csv_name: str, records: int) -> None:
    """CSV-Verweis und Modellstand in flow_data.json eintragen."""
    with flow_json_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    metadata = payload.get("metadata") or {}
    metadata["timeseries_mode_detail"] = "separate_csv_gzip"
    metadata["model_version"] = MODEL_VERSION
    metadata["schema_version"] = SCHEMA_VERSION
    payload["metadata"] = metadata
    payload["timeseries_csv_ref"] = {
        "path": csv_name,
        "compressed": True,
        "format": "csv",
        "records": int(records),
    }

    with flow_json_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def frontend_relative(path: Path) -> str:
    """Pfad relativ zu web_frontend/, wie ihn das Frontend per fetch lädt."""
    return "./" + Path(os.path.relpath(path, WEB_FRONTEND_DIR)).as_posix()


def build_catalog_from_precomputed(output_dir: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if not output_dir.exists():
        return entries

    for scenario_dir in sorted(output_dir.iterdir()):
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
                "flow_path": frontend_relative(flow_path),
                "input": raw_input,
            }
        )

    entries.sort(key=lambda item: str(item.get("scenario_id", "")))
    return entries


def write_catalog(entries: list[dict[str, Any]], output_dir: Path) -> Path:
    catalog_path = output_dir / CATALOG_NAME
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    with catalog_path.open("w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
    return catalog_path


def migrate_legacy_scenarios(output_dir: Path) -> dict[str, int]:
    """Kopiert Null-Batterie-Szenarien aus data/outputs/precomputed/ in den Ausgabeordner."""
    if not LEGACY_PRECOMPUTED_DIR.exists():
        print("Legacy-Verzeichnis nicht gefunden, Migration übersprungen.")
        return {"copied": 0, "skipped_battery": 0, "failed": 0}

    output_dir.mkdir(parents=True, exist_ok=True)
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
            dest = output_dir / scenario_dir.name
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


def format_duration(seconds: float) -> str:
    seconds = int(round(seconds))
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours:d}:{minutes:02d}:{secs:02d}"


def unique_candidates(industry_mode: str) -> tuple[list[GuiInput], int]:
    """Kandidaten ohne Duplikate (gleicher kanonischer Schlüssel) und Gesamtzahl vor dem Entfernen."""
    all_candidates = build_permutation_space(industry_mode)
    seen_keys: set[str] = set()
    unique: list[GuiInput] = []
    for candidate in all_candidates:
        key = canonical_key(asdict(candidate))
        if key not in seen_keys:
            seen_keys.add(key)
            unique.append(candidate)
    return unique, len(all_candidates)


def generate_scenarios(
    output_dir: Path,
    limit: int = 0,
    overwrite: bool = True,
    resume: bool = False,
    industry_mode: str = "leave-one-out",
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)

    candidates, total_candidates = unique_candidates(industry_mode)
    planned = candidates[:limit] if limit > 0 else candidates
    print(f"Szenarien: {len(candidates)} eindeutig ({total_candidates} Kandidaten), dieser Lauf: {len(planned)}")
    print(f"Ausgabe: {output_dir}")

    generated = 0
    skipped_existing = 0
    failed = 0
    durations: list[float] = []

    for index, candidate in enumerate(planned):
        scenario_id = f"s_auto_{index + 1:04d}"
        scenario_dir = output_dir / scenario_id

        # Fortsetzen: vollständig geschriebene Szenarien (flow_data.json + timeseries.csv.gz) überspringen
        if resume and (scenario_dir / "flow_data.json").exists() and (scenario_dir / "timeseries.csv.gz").exists():
            skipped_existing += 1
            continue

        if overwrite and scenario_dir.exists():
            shutil.rmtree(scenario_dir)

        started = time.perf_counter()
        try:
            sim_output = run_simulation(candidate)

            flow_json_str = export_scenario_flows_to_json(
                inp=candidate,
                sim_output=sim_output,
                scenario_id=scenario_id,
                output_dir=output_dir,
                schema_version=SCHEMA_VERSION,
                timeseries_mode="none",
                compress_timeseries=False,
            )

            flow_json_path = Path(flow_json_str)
            csv_name, records = write_timeseries_csv_gz(sim_output, scenario_dir)
            annotate_flow_json(flow_json_path, csv_name, records)
            generated += 1
        except Exception as exc:
            failed += 1
            print(f"[warn] scenario failed {scenario_id}: {exc}")

        durations.append(time.perf_counter() - started)
        mean_s = sum(durations) / len(durations)
        remaining = len(planned) - (index + 1)
        print(
            f"[{index + 1}/{len(planned)}] {scenario_id} in {durations[-1]:.1f} s | "
            f"Mittel {mean_s:.1f} s | Restzeit ca. {format_duration(mean_s * remaining)}",
            flush=True,
        )

    # Katalog erst am Ende schreiben: bis dahin bleiben die alten Daten nutzbar
    catalog_entries = build_catalog_from_precomputed(output_dir)
    catalog_path = write_catalog(catalog_entries, output_dir)

    return {
        "generated": generated,
        "skipped_existing": skipped_existing,
        "failed": failed,
        "catalog_entries": len(catalog_entries),
        "catalog_path": str(catalog_path),
        "unique_scenarios": len(candidates),
        "total_candidates": total_candidates,
        "mean_seconds": (sum(durations) / len(durations)) if durations else 0.0,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Vorberechnete Szenarien erzeugen (flow_data.json + timeseries.csv.gz) und am Ende catalog.json im Ausgabeordner schreiben."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Nur die ersten N Szenarien berechnen (Probelauf). 0 = alle.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PRECOMPUTED_DIR,
        help=f"Ausgabeordner (Standard: {PRECOMPUTED_DIR.relative_to(PROJECT_ROOT).as_posix()}); muss unter web_frontend/ liegen, damit das Frontend die Pfade findet.",
    )
    parser.add_argument(
        "--industry",
        choices=INDUSTRY_MODES,
        default="leave-one-out",
        help="Industrieprofile: Basis + je eines weggelassen (Standard) oder alle nicht leeren Teilmengen.",
    )
    parser.add_argument(
        "--overwrite",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Vorhandene Szenarioordner mit gleicher ID überschreiben.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        default=False,
        help="Bereits vollständig berechnete Szenarien überspringen (abgebrochenen Lauf fortsetzen).",
    )
    parser.add_argument(
        "--count",
        action="store_true",
        default=False,
        help="Nur die Anzahl der Szenarien ausgeben, nichts berechnen.",
    )
    parser.add_argument(
        "--migrate-legacy",
        action="store_true",
        default=False,
        help="Null-Batterie-Szenarien aus data/outputs/precomputed/ in den Ausgabeordner kopieren.",
    )
    parser.add_argument(
        "--catalog-only",
        action="store_true",
        default=False,
        help="Nur catalog.json im Ausgabeordner neu aufbauen, keine neue Simulation.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.resolve()

    if args.count:
        candidates, total = unique_candidates(args.industry)
        industry = len(build_industry_profiles(args.industry))
        print(f"6 Solar × 5 Landschaft × {industry} Industrie × 3 GEH × 4 Jüchen Süd = {total} Kandidaten, {len(candidates)} eindeutig")
        return

    if args.migrate_legacy:
        print("=== Migriere Legacy-Szenarien ===")
        m = migrate_legacy_scenarios(output_dir)
        print(f"kopiert: {m['copied']}, Batterie übersprungen: {m['skipped_battery']}, Fehler: {m['failed']}")

    if args.catalog_only or args.migrate_legacy:
        print("=== Baue Katalog neu (nur Katalog) ===")
        entries = build_catalog_from_precomputed(output_dir)
        path = write_catalog(entries, output_dir)
        print(f"{path} aktualisiert: {len(entries)} Einträge")
        return

    stats = generate_scenarios(
        output_dir=output_dir,
        limit=max(0, int(args.limit)),
        overwrite=bool(args.overwrite),
        resume=bool(args.resume),
        industry_mode=args.industry,
    )
    print("\nFertig.")
    for key, value in stats.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
