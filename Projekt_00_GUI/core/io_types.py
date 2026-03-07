from dataclasses import dataclass
from typing import Optional, Dict, Any
import pandas as pd

# =================================
# Input aus der Streamlit-Anwendung
# =================================

@dataclass
class GuiInput:
    """
    Alle Parameter, die die GUI eingegeben werden können und an die Simulation übergeben werden sollen.
    """
    def __init__(self,
                 highways:list | None = None,
                 h_pv_types:list | None = None,
                 el_build_state:int | None = None,
                 el_pv_type:int | None = None,
                 tractor_width:float | None = None,
                 tractor_length:float | None = None,
                 tractor_turn_radius:float | None = None,
                 is_heat_cooling_electric:bool | None = None,
                 companies:list[int] | None = None,
                 h2_load_scenario:str | None = None,
                 e_load_scenario:str | None = None,
                 bs_efficiency:float | None = None,
                 bs_energy_kwh:float | None = None,
                 bs_power_kw:float | None = None,):
        # ERZEUGUNG
        # Solarautobahn
        self.highways = highways                                    # Auswahl Autobahnen
        self.h_pv_types = h_pv_types                                # Auswahl PV-Types für die Autobahnen
        # Energielandschaft
        self.el_build_state = el_build_state                        # Ausbaugrad in %
        self.el_pv_type = el_pv_type                                # Auswahl PV-Types für die Energielandschaft
        self.tractor_width = tractor_width                          # Traktorbreite [m]
        self.tractor_length = tractor_length                        # Traktorlänge [m]
        self.tractor_turn_radius = tractor_turn_radius              # Traktor-Wenderadius [m]
        # Industriegebiet
        self.is_heat_cooling_electric = is_heat_cooling_electric    # Wärme/Kälte elektrisch? [true/false]
        self.companies = companies                                  #Auswahl der Unternehmenstypen im Industriegebiet
        # Green Energy Hub
        self.h2_load_scenario = h2_load_scenario                    # Auswahl H2 Bedarf Szenario 2022, 2030, 2050
        self.e_load_scenario = e_load_scenario                      # Auswahl E Bedarf Szenario 2022, 2030, 2050
        # Batteriespeicher
        self.bs_efficiency = bs_efficiency
        self.bs_energy_kwh = bs_energy_kwh
        self.bs_power_kw = bs_power_kw

    def __repr__(self):
        return (
            f"GuiInput("
            f"highways={self.highways}, "
            f"h_pv_types={self.h_pv_types}, "
            f"el_pv_type={self.el_pv_type}, "
            f"tractor_width={self.tractor_width}, "
            f"tractor_length={self.tractor_length}, "
            f"tractor_turn_radius={self.tractor_turn_radius}, "
            f"is_heat_cooling_electric={self.is_heat_cooling_electric}, "
            f"companies={self.companies}, "
            f"h2_load_scenario={self.h2_load_scenario}, "
            f"e_load_scenario={self.e_load_scenario}, "
            f"bs_efficiency={self.bs_efficiency}, "
            f"bs_energy_kwh={self.bs_energy_kwh}, "
            f"bs_power_kw={self.bs_power_kw}"
            f")"
        )
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
            f"h_number_of_points={self.h_number_of_points}, "
            f"el_pv_length={self.el_pv_length}"
            f")"
        )
