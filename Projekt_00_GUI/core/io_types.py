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
                 pv_equip_pct=None,
                 is_heat_cooling_electric=None,
                 companies=None):
        self.highways = highways
        self.h_pv_types = h_pv_types
        self.el_pv_type = el_pv_type
        self.tractor_width = tractor_width
        self.tractor_length = tractor_length
        self.tractor_turn_radius = tractor_turn_radius
        self.pv_equip_pct = pv_equip_pct
        self.is_heat_cooling_electric = is_heat_cooling_electric
        self.companies = companies

    # ERZEUGUNG
    # Solarautobahn
    highways: list                      # Auswahl Autobahnen
    h_pv_types: list                    # Auswahl PV-Types für die Autobahnen

    # Energielandschaft
    el_pv_type: str                     # Auswahl PV-Types für die Energielandschaft
    tractor_width: str                  # Traktorbreite [m]
    tractor_length: str                 # Traktorlänge [m]
    tractor_turn_radius: str            # Traktor-Wenderadius [m]

    # Industriegebiet
    pv_equip_pct: float                 # PV Ausbau Dachfläche Indurstriegebiet [%]


    # VERBRAUCH
    # Industriegebiet
    companies: list[str]                #Auswahl der Unternehmenstypen im Industriegebiet
    is_heat_cooling_electric: bool      # Wärme/Kälte elektrisch? [true/false]

    # Green Energy Hub


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
                 error_text=None):
        self.h_number_of_points = h_number_of_points
        self.total_ac_kw = total_ac_kw
        self.sum_energy_kwh = sum_energy_kwh
        self.error_text = error_text

    h_number_of_points: int
    sum_energy_kwh: float
    error_text: str