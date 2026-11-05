#Übergabefertig kommentiert JB
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
import pandas as pd

# =================================
# Input from the streamlit website
# =================================

@dataclass
class GuiInput:
    """
    All website input parameters.
    The following abbreviations are used in the variable names:
        h = highway, el = energy landscape, i = industry, geh = green energy hub, bs = battery storage
    """

    # Energy production
    # PV Highway
    h_highways: Optional[List[str]] = None              # IDs of the selected highways
    h_pv_types: Optional[List[str]] = None              # PV types that the highway will be equipped with

    # Energy landscape
    el_build_state: Optional[int] = None                # Build state [%]
    el_pv_type: Optional[int] = None                    # PV types that the energy landscape will be equipped with
    el_tractor_width: Optional[float] = None            # [m]
    el_tractor_length: Optional[float] = None           # [m]
    el_tractor_turn_radius: Optional[float] = None      # [m]

    # Energy consumption
    # Industry area
    i_heat_cooling_electric: Optional[bool] = None     # Electric Heating/Cooling active
    i_companies: Optional[List[int]] = None            # Company typ list

    # Green Energy Hub – Variante aus der Machbarkeitsstudie
    geh_variant: Optional[str] = None                      # "Keine", "Basis", "Erweiterung"

    # Green Energy Hub – optionale Overrides (None = Wert aus GEH_VARIANTS)
    geh_pv_kwp: Optional[float] = None                     # PV-Leistung am Hub [kWp]
    geh_battery_kwh: Optional[float] = None                # Batteriekapazität [kWh]
    geh_battery_kw: Optional[float] = None                 # Batterieleistung [kW]
    geh_h2_demand_t_per_a: Optional[float] = None          # H2-Nachfrage Tankstelle [t/a]
    geh_h2_min_soc: Optional[float] = None                 # Mindestfüllstand H2-Speicher [0–1]
    geh_electrolyzer_power_kw: Optional[float] = None      # Nennleistung Elektrolyseur [kW]
    geh_electrolyzer_efficiency: Optional[float] = None    # System-Wirkungsgrad (LHV-bezogen, 0–1)
    geh_storage_capacity_kwh: Optional[float] = None       # H2-Speicherkapazität [kWh_H2]
    geh_grid_limit_kw: Optional[float] = None              # Netzgrenze des Hubs für die Spitzenkappung [kW]
    geh_electrolyzer_base_kw: Optional[float] = None       # Grundlast Elektrolyseur [kW] (None = aus H2-Nachfrage)
    geh_h2_high_soc: Optional[float] = None                # Oberer Füllstand H2-Speicher [0–1]
    geh_battery_recharge_margin: Optional[float] = None    # Nachladen aus dem Netz unter diesem Anteil der Grenze [0–1]
    geh_charging_model: Optional[str] = None               # "sessions" (Standard) oder "profile"

    # Battery storage
    bs_efficiency: Optional[float] = None               # Roundtrip efficience [0–1]
    bs_energy_kwh: Optional[float] = None               # Capacity [kWh]
    bs_c_rate: Optional[float] = None                   # C-rate

    # Jüchen Süd – Versorgungskonzept aus dem Energiekonzept (Fraunhofer IEG, Basis-Variante)
    js_concept: Optional[str] = None                    # "Aus", "Warmes Netz", "Kaltes Netz", "Dezentral"

    # Jüchen Süd – optionale Overrides (None = Wert aus JS_CONCEPTS)
    js_hp_kw: Optional[float] = None                    # Wärmepumpenleistung (thermisch) [kW]
    js_heater_kw: Optional[float] = None                # Heizstableistung [kW]
    js_tank_kwh: Optional[float] = None                 # Tankspeicher (thermisch) [kWh]


# =========================
# Output der Simulation
# =========================

@dataclass
class SimOutput:
    """
    All results that are shown on the website.
    The following abbreviations are used in the variable names:
        h = highway, el = energy landscape, i = industry, geh = green energy hub, bs = battery storage
    """

    # Energy amounts [kWh]
    h_sum_energy_kwh: float | None = None
    el_sum_energy_kwh: float | None = None
    geh_sum_energy_kwh: float | None = None
    i_sum_energy_kwh: float | None = None
    js_sum_energy_kwh: float | None = None

    # Max power [kW] - all values production and consumption are positive,
    h_max_power_kw: float | None = None
    el_max_power_kw: float | None = None
    geh_max_power_kw: float | None = None
    i_max_power_kw: float | None = None
    js_max_power_kw: float | None = None

    # Green Energy Hub – H2-Prozessketten-Ergebnisse
    geh_h2_production_kwh: float | None = None       # H2-Jahresproduktion [kWh_H2]
    geh_compressor_demand_kwh: float | None = None   # Kompressor-Strombedarf [kWh/a]
    geh_h2_delivered_kwh: float | None = None        # An Dispenser gelieferte H2-Energie [kWh_H2]
    geh_storage_soc_df: pd.DataFrame = field(default_factory=pd.DataFrame)  # SOC-Zeitreihe H2-Speicher

    # Green Energy Hub – Erzeugung, Lasten, Batterie
    geh_pv_sum_energy_kwh: float | None = None       # PV-Ertrag am Hub [kWh/a]
    geh_pv_max_power_kw: float | None = None         # PV-Spitzenleistung am Hub [kW]
    geh_charging_mcs_kwh: float | None = None        # Ladeenergie Lkw MCS [kWh/a]
    geh_charging_ccs_kwh: float | None = None        # Ladeenergie Lkw Overnight CCS [kWh/a]
    geh_charging_hpc_kwh: float | None = None        # Ladeenergie Pkw HPC [kWh/a]
    geh_charging_ac_kwh: float | None = None         # Ladeenergie Pkw Parkhaus AC [kWh/a]
    geh_building_kwh: float | None = None            # Strombedarf Gebäude [kWh/a]
    geh_electrolyzer_kwh: float | None = None        # Strombezug Elektrolyseur [kWh/a]
    geh_electrolyzer_full_load_hours: float | None = None  # Volllaststunden Elektrolyseur [h/a]
    geh_h2_demand_kwh: float | None = None           # H2-Nachfrage Tankstelle [kWh_H2/a]
    geh_h2_unmet_kwh: float | None = None            # Ungedeckte H2-Nachfrage [kWh_H2/a]
    geh_battery_charge_kwh: float | None = None      # Batterie-Ladung [kWh/a]
    geh_battery_discharge_kwh: float | None = None   # Batterie-Entladung [kWh/a]
    geh_battery_full_cycles: float | None = None     # Batterie-Vollzyklen [1/a]
    geh_battery_soc_df: pd.DataFrame = field(default_factory=pd.DataFrame)  # SOC-Zeitreihe Batterie
    geh_electrolyzer_base_kw: float | None = None    # Grundlast Elektrolyseur [kW]
    geh_grid_limit_kw: float | None = None           # Netzgrenze des Hubs [kW]
    geh_grid_peak_kw: float | None = None            # Netzspitze des Hubs [kW] (Zeitreihe: res_df "Netzlast_GEH [kW]")
    geh_grid_limit_exceed_hours: float | None = None # Stunden über der Netzgrenze des Hubs [h/a]
    geh_charging_model: str | None = None            # verwendetes Lademodell
    geh_mcs_sessions: int | None = None              # Ladevorgänge Lkw MCS [1/a] (nur "sessions")
    geh_hpc_sessions: int | None = None              # Ladevorgänge Pkw HPC [1/a] (nur "sessions")
    geh_mcs_peak_kw: float | None = None             # Spitze Lkw MCS (15 min) [kW]
    geh_hpc_peak_kw: float | None = None             # Spitze Pkw HPC (15 min) [kW]
    geh_fixed_load_peak_kw: float | None = None      # Spitze Hub-Last ohne Flexibilität (Ladecluster + Gebäude) [kW]

    # Jüchen Süd – Bedarfe und Wärmeversorgung
    js_household_kwh: float | None = None            # Nutzerstrom [kWh/a]
    js_emob_kwh: float | None = None                 # Ladestrom E-Mobilität [kWh/a]
    js_space_heat_kwh: float | None = None           # Raumwärmebedarf [kWh_th/a]
    js_dhw_kwh: float | None = None                  # Trinkwarmwasserbedarf [kWh_th/a]
    js_cooling_kwh: float | None = None              # Kältebedarf [kWh_th/a]
    js_hp_el_kwh: float | None = None                # Strombedarf Wärmepumpen [kWh/a]
    js_heater_el_kwh: float | None = None            # Strombedarf Heizstab [kWh/a]
    js_cooling_el_kwh: float | None = None           # Strombedarf Kälte [kWh/a]
    js_heat_unmet_kwh: float | None = None           # Ungedeckter Wärmebedarf [kWh_th/a]
    js_hp_scop: float | None = None                  # Jahresarbeitszahl Wärmepumpen [-]
    js_tank_soc_df: pd.DataFrame = field(default_factory=pd.DataFrame)  # SOC-Zeitreihe Tankspeicher

    # Netzaustausch des Parks (nach allen Speichern)
    grid_import_kwh: float | None = None             # Netzbezug [kWh/a]
    grid_export_kwh: float | None = None             # Netzeinspeisung [kWh/a]
    grid_max_import_kw: float | None = None          # Maximale Netzbezugsleistung [kW]

    # pandas dataframes with load profiles
    res_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    bs_df: pd.DataFrame = field(default_factory=pd.DataFrame)

    # Battery statistics
    bs_stats: dict = field(default_factory=dict)


    # System balance
    bal_energy_kwh: float | None = None
    bal_coverage_rate: float | None = None                          # Balanced Autarky (incl. back and forth with grid)
    bal_power_max_kw: float | None = None
    bal_power_min_kw: float | None = None

    # Internal Generation KPIs
    ee_self_consumption: float | None = None                        # Direct self consumption of generated energy in relation to total generation
    autarky: float | None = None                                    # Direct self consumption of generated energy in relation to demand

    # Error texts
    h_error_text: str | None = None
    el_error_text: str | None = None
    geh_error_text: str | None = None
    i_error_text: str | None = None
    js_error_text: str | None = None

    # Debug
    h_number_of_points: int | None = None
    el_pv_length: float | None = None
