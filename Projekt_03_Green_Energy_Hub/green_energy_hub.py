"""
Green Energy Hub Klasse
Author: Jannis Brinkmann
"""

from __future__ import annotations
from dataclasses import dataclass


# ===== Elektroladesäule =======================================================
class ElectricCharger:

    def __init__(self,
                 name: str,
                 rated_power_kw: float,
                 n_connectors: int = 1,
                 connection_type: str = "AC",
                 ):

        self.name = name
        self.rated_power_kw = rated_power_kw
        self.n_connectors = n_connectors
        self.connection_type = connection_type

        self.load_profile_kw = None
        self.time_resolution_s: float | None

        self.scale_factor: float | None
        self.target_peak_kw: float | None
        self.target_energy_kwh: float | None


# ===== Elektrolyseur =======================================================
class ElectrolyserH2Charger:
    def __init__(self,
                 name: str,
                 hydrogen_profile,
                 hydrogen_unit: str,

                 time_resolution_s: int,

                 specific_energy_kwh_per_kg: float | None = None,
                 electrical_efficiency: float | None = None,

                 lhv_h2_kwh_per_kg: float = 33.33,
                 auxiliary_power_share: float = 0.0
                 ):

        self.name = name
        self.hydrogen_profile = hydrogen_profile
        self.hydrogen_unit = hydrogen_unit
        self.time_resolution_s = time_resolution_s
        self.specific_energy_kwh_per_kg = specific_energy_kwh_per_kg
        self.electrical_efficiency = electrical_efficiency
        self.lhv_h2_kwh_per_kg = lhv_h2_kwh_per_kg
        self.auxiliary_power_share = auxiliary_power_share

        self.scale_factor: float | None
        self.target_peak_kw: float | None
        self.target_energy_kwh: float | None


class RoofPV:
    def __init__(self,
                 name: str,
                 generation_profile_kw,
                 time_resolution_s: int,
                 ):
        self.name = name
        self.generation_profile_kw = generation_profile_kw
        self.time_resolution_s = time_resolution_s

        self.scale_factor: float | None
        self.installed_power_kwp: float | None
        self.target_energy_kwh: float | None

class BatteryStorage:
    def __init__(self,
                 name: str,
                 capacity_kwh: float,
                 time_resolution_s: int,
                 initial_soc_kwh: float = 0.0,
                 charge_efficiency: float = 1.0,
                 discharge_efficiency: float = 1.0):

        self.name = name
        self.capacity_kwh = capacity_kwh
        self.time_resolution_s = time_resolution_s

        self.soc_kwh = initial_soc_kwh

        self.charge_efficiency = charge_efficiency
        self.discharge_efficiency = discharge_efficiency


# ------------------- Optionaler Direktstart:------------------------------------------
if __name__ == "__main__":

        charger = ElectricCharger
        H2system = ElectrolyserH2Charger
        pv = RoofPV
        storage = BatteryStorage


