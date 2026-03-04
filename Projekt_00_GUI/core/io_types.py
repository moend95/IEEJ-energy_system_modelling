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
                 highways=None,
                 h_pv_types=None,
                 el_pv_type=None,
                 tractor_width=None,
                 tractor_length=None,
                 tractor_turn_radius=None,
                 is_heat_cooling_electric=None,
                 companies=None,
                 h2_load_scenario=None,
                 e_load_scenario=None):
        self.highways = highways
        self.h_pv_types = h_pv_types
        self.el_pv_type = el_pv_type
        self.tractor_width = tractor_width
        self.tractor_length = tractor_length
        self.tractor_turn_radius = tractor_turn_radius
        self.is_heat_cooling_electric = is_heat_cooling_electric
        self.companies = companies
        self.h2_load_scenario = h2_load_scenario
        self.e_load_scenario = e_load_scenario


    # ERZEUGUNG
    # Solarautobahn
    highways: list                      # Auswahl Autobahnen
    h_pv_types: list                    # Auswahl PV-Types für die Autobahnen

    # Energielandschaft
    el_pv_type: int                     # Auswahl PV-Types für die Energielandschaft
    tractor_width: float                # Traktorbreite [m]
    tractor_length: float               # Traktorlänge [m]
    tractor_turn_radius: float          # Traktor-Wenderadius [m]


    # VERBRAUCH
    # Industriegebiet
    companies: list[int]                #Auswahl der Unternehmenstypen im Industriegebiet
    is_heat_cooling_electric: bool      # Wärme/Kälte elektrisch? [true/false]

    # Green Energy Hub
    h2_load_scenario: str               # Auswahl H2 Bedarf Szenario 2022, 2030, 2050
    e_load_scenario: str                # Auswahl E Bedarf Szenario 2022, 2030, 2050


# =========================
# Output der Simulation
# =========================

@dataclass
class SimOutput:
    """
    Ergebnisse der Simulation. Die auf der Website dargestellt werden sollen.
    """

    def __init__(self,
                 h_number_of_points=None,
                 total_ac_kw = None,
                 sum_energy_kwh=None,
                 error_text=None,
                 el_error_text=None,
                 geh_error_text=None,
                 i_error_text=None,
                 res_df=None):
        self.h_number_of_points = h_number_of_points
        self.total_ac_kw = total_ac_kw
        self.sum_energy_kwh = sum_energy_kwh
        self.error_text = error_text
        self.el_error_text = el_error_text
        self.geh_error_text = geh_error_text
        self.i_error_text = i_error_text
        self.res_df = res_df if res_df is not None else pd.DataFrame()

    h_number_of_points: int
    sum_energy_kwh: float
    h_error_text: str
    el_error_text: str
    geh_error_text: str
    i_error_text: str
    res_df = pd.DataFrame()