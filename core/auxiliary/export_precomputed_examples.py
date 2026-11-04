import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.export_utils import export_scenario_flows_to_json
from core.io_types import GuiInput
from Simulation import run_simulation


def build_example_scenarios() -> list[tuple[str, GuiInput]]:
    """
    Returns a small fixed set of example scenarios for precomputed export tests.
    """
    scenarios: list[tuple[str, GuiInput]] = [
        (
            "s01_small_no_battery",
            GuiInput(
                h_highways=["A46"],
                h_pv_types=[0],
                el_build_state=50,
                el_pv_type=5,
                el_tractor_width=12.0,
                el_tractor_length=15.0,
                el_tractor_turn_radius=9.0,
                i_heat_cooling_electric=True,
                i_companies=[0, 1, 2, 3, 5],
                geh_variant="Basis",
                js_concept="Dezentral",
                bs_efficiency=None,
                bs_energy_kwh=None,
                bs_c_rate=None,
            ),
        ),
        (
            "s02_medium_with_battery",
            GuiInput(
                h_highways=["A44", "A46"],
                h_pv_types=[1, 2],
                el_build_state=50,
                el_pv_type=6,
                el_tractor_width=12.0,
                el_tractor_length=15.0,
                el_tractor_turn_radius=9.0,
                i_heat_cooling_electric=True,
                i_companies=[1, 3, 5, 6, 7],
                geh_variant="Erweiterung",
                js_concept="Warmes Netz",
                bs_efficiency=0.92,
                bs_energy_kwh=10000.0,
                bs_c_rate=1.0,
            ),
        ),
        (
            "s03_high_demand_no_battery",
            GuiInput(
                h_highways=["A46"],
                h_pv_types=[0],
                el_build_state=50,
                el_pv_type=5,
                el_tractor_width=12.0,
                el_tractor_length=15.0,
                el_tractor_turn_radius=9.0,
                i_heat_cooling_electric=True,
                i_companies=[0, 1, 2, 3, 4, 5, 6, 7],
                geh_variant="Erweiterung",
                js_concept="Kaltes Netz",
                bs_efficiency=None,
                bs_energy_kwh=None,
                bs_c_rate=None,
            ),
        ),
        (
            "s04_high_supply_with_battery",
            GuiInput(
                h_highways=["A44", "A46"],
                h_pv_types=[1, 2, 3],
                el_build_state=100,
                el_pv_type=4,
                el_tractor_width=12.0,
                el_tractor_length=15.0,
                el_tractor_turn_radius=9.0,
                i_heat_cooling_electric=True,
                i_companies=[0, 1, 2, 3, 5],
                geh_variant="Basis",
                js_concept="Dezentral",
                bs_efficiency=0.92,
                bs_energy_kwh=235000.0,
                bs_c_rate=1.0,
            ),
        ),
        (
            "s05_reference_mix",
            GuiInput(
                h_highways=["A44", "A46"],
                h_pv_types=[1, 2],
                el_build_state=50,
                el_pv_type=6,
                el_tractor_width=12.0,
                el_tractor_length=15.0,
                el_tractor_turn_radius=9.0,
                i_heat_cooling_electric=True,
                i_companies=[1, 5, 3, 6, 7],
                geh_variant="Erweiterung",
                js_concept="Warmes Netz",
                bs_efficiency=0.92,
                bs_energy_kwh=10000.0,
                bs_c_rate=1.0,
            ),
        ),
    ]
    return scenarios


def run_example_exports(
    limit: int = 3,
    timeseries_mode: str = "separate",
    compress_timeseries: bool = True,
) -> list[str]:
    """
    Runs 3-5 predefined scenarios and exports flow JSON per scenario.
    """
    limit = max(3, min(5, int(limit)))

    output_base = Path(__file__).resolve().parents[2] / "data" / "outputs" / "precomputed"
    output_base.mkdir(parents=True, exist_ok=True)

    exported_paths: list[str] = []
    scenarios = build_example_scenarios()[:limit]

    print(
        f"Running precomputed export for {len(scenarios)} scenarios "
        f"(timeseries_mode={timeseries_mode}, compress_timeseries={compress_timeseries})..."
    )
    for index, (scenario_id, inp) in enumerate(scenarios, start=1):
        print(f"[{index}/{len(scenarios)}] simulate: {scenario_id}")
        sim_output = run_simulation(inp)

        json_path = export_scenario_flows_to_json(
            inp=inp,
            sim_output=sim_output,
            scenario_id=scenario_id,
            output_dir=output_base,
            timeseries_mode=timeseries_mode,
            compress_timeseries=compress_timeseries,
        )
        exported_paths.append(json_path)
        print(f"[{index}/{len(scenarios)}] exported: {json_path}")

    print("Done.")
    return exported_paths


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run example scenarios and export precomputed flow JSON files."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=3,
        help="Number of example scenarios to export (3..5).",
    )
    parser.add_argument(
        "--timeseries-mode",
        choices=["inline", "separate", "none"],
        default="separate",
        help="How timeseries are stored in exports.",
    )
    parser.add_argument(
        "--compress-timeseries",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Compress separated timeseries output as gzip.",
    )
    args = parser.parse_args()

    run_example_exports(
        limit=args.limit,
        timeseries_mode=args.timeseries_mode,
        compress_timeseries=args.compress_timeseries,
    )


if __name__ == "__main__":
    main()
