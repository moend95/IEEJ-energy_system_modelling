"""
Tests Green Energy Hub (Machbarkeitsstudie „Autohof der Zukunft“)
===================================================================
Schnelle Tests: Datenmodell, Ladeprofile, Dispatch mit synthetischen Arrays.
Integrationstests (@pytest.mark.slow): einmal run_simulation je Variante.
"""

import sys
from dataclasses import fields
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.io_types import GuiInput, SimOutput


# ---------------------------------------------------------------------------
# Datenmodell
# ---------------------------------------------------------------------------

def test_guiinput_geh_felder():
    names = {f.name for f in fields(GuiInput)}
    for neu in ("geh_variant", "geh_pv_kwp", "geh_battery_kwh", "geh_battery_kw",
                "geh_h2_demand_t_per_a", "geh_h2_min_soc"):
        assert neu in names
    for alt in ("geh_h2_load_scenario", "geh_e_load_scenario",
                "geh_dispenser_demand_kg_per_h", "geh_storage_max_charge_kw"):
        assert alt not in names


def test_simoutput_geh_felder():
    names = {f.name for f in fields(SimOutput)}
    assert "geh_h2_curtailed_kwh" not in names
    for neu in ("geh_pv_sum_energy_kwh", "geh_electrolyzer_full_load_hours",
                "geh_h2_unmet_kwh", "geh_battery_full_cycles", "geh_battery_soc_df",
                "grid_import_kwh", "grid_export_kwh", "grid_max_import_kw"):
        assert neu in names
