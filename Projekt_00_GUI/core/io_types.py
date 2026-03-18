from dataclasses import dataclass
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
        h = highway, el = energy landscape, is = industry
    """

    # ERZEUGUNG
    # Solarautobahn
    h_highways: Optional[List[str]] = None              # IDs der ausgewählten Autobahnen
    h_pv_types: Optional[List[str]] = None              # PV-Typen entlang der Autobahnen

    # Energielandschaft
    el_build_state: Optional[int] = None                # Ausbaugrad [%]
    el_pv_type: Optional[int] = None                    # PV-Typ Energielandschaft
    el_tractor_width: Optional[float] = None            # [m]
    el_tractor_length: Optional[float] = None           # [m]
    el_tractor_turn_radius: Optional[float] = None      # [m]

    # Industriegebiet
    is_heat_cooling_electric: Optional[bool] = None     # Elektrische Wärme/Kälte
    is_companies: Optional[List[int]] = None            # Unternehmens-Typen

    # Green Energy Hub
    geh_h2_load_scenario: Optional[str] = None          # Szenario: 2022, 2030, 2050
    geh_e_load_scenario: Optional[str] = None           # Szenario: 2022, 2030, 2050

    # Batteriespeicher
    bs_efficiency: Optional[float] = None               # Roundtrip-Effizienz [0–1]
    bs_energy_kwh: Optional[float] = None               # Kapazität [kWh]
    bs_c_rate: Optional[float] = None                   # C-Rate

# =========================
# Output der Simulation
# =========================

@dataclass
class SimOutput:
    """
    Ergebnisse der Simulation. Die auf der Website dargestellt werden sollen.
    """
    def __init__(self,
                 h_sum_energy_kwh:float | None = None,
                 el_sum_energy_kwh: float | None = None,
                 geh_sum_energy_kwh: float | None = None,
                 i_sum_energy_kwh: float | None = None,
                 h_max_power_kw:float | None = None,
                 el_max_power_kw:float | None = None,
                 geh_max_power_kw:float | None = None,
                 i_max_power_kw:float | None = None,
                 res_df:pd.DataFrame | None = None,
                 bat_df: pd.DataFrame | None = None,
                 battery_stats: dict | None = None,
                 balance_energy_kwh:float | None = None,
                 coverage_rate: float | None = None,
                 balance_power_max_kw:float | None = None,
                 balance_power_min_kw:float | None = None,
                 h_error_text:str | None = None,
                 el_error_text:str | None = None,
                 geh_error_text:str | None = None,
                 i_error_text:str | None = None,
                 h_number_of_points:int | None = None,
                 el_pv_length:float | None = None,):

        # Energiemengen für das Jahr pro Modul
        self.h_sum_energy_kwh = h_sum_energy_kwh
        self.el_sum_energy_kwh = el_sum_energy_kwh
        self.geh_sum_energy_kwh = geh_sum_energy_kwh
        self.i_sum_energy_kwh = i_sum_energy_kwh
        # Maximal Leistung des Jahreslastgang pro Modul
        self.h_max_power_kw = h_max_power_kw
        self.el_max_power_kw = el_max_power_kw
        self.geh_max_power_kw = geh_max_power_kw
        self.i_max_power_kw = i_max_power_kw
        # Result Data Frame mit Lastgängen
        self.res_df = res_df if res_df is not None else pd.DataFrame()
        #Batterie Data Frame und Stats dict
        self.bat_df = bat_df if bat_df is not None else pd.DataFrame()
        self.battery_stats = battery_stats if battery_stats is not None else {}
        # Bilanzenergie
        self.balance_energy_kwh = balance_energy_kwh
        self.coverage_rate = coverage_rate
        self.balance_power_max_kw = balance_power_max_kw
        self.balance_power_min_kw = balance_power_min_kw
        # Error Texte für die einzelnen Module
        self.h_error_text = h_error_text
        self.el_error_text = el_error_text
        self.geh_error_text = geh_error_text
        self.i_error_text = i_error_text
        # Debug Zeug
        self.h_number_of_points = h_number_of_points
        self.el_pv_length = el_pv_length

    def __repr__(self):
        return (
            f"SimOutput("
            f"h_sum_energy_kwh={self.h_sum_energy_kwh}, "
            f"el_sum_energy_kwh={self.el_sum_energy_kwh}, "
            f"geh_sum_energy_kwh={self.geh_sum_energy_kwh}, "
            f"i_sum_energy_kwh={self.i_sum_energy_kwh}, "
            f"h_max_power_kw={self.h_max_power_kw}, "
            f"el_max_power_kw={self.el_max_power_kw}, "
            f"geh_max_power_kw={self.geh_max_power_kw}, "
            f"i_max_power_kw={self.i_max_power_kw}, "
            f"res_df_shape={None if self.res_df is None else self.res_df.shape}, "
            f"bat_df_shape={None if self.bat_df is None else self.bat_df.shape}, "
            f"balance_energy_kw={self.balance_energy_kwh},"
            f"coverage_rate={self.coverage_rate}," 
            f"balance_power_max_kw={self.balance_power_max_kw},"
            f"balance_power_min_kw={self.balance_power_min_kw},"
            f"h_number_of_points={self.h_number_of_points}, "
            f"el_pv_length={self.el_pv_length}"
            f")"
        )
