from dataclasses import dataclass
from typing import Optional, Dict, Any

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
                 pv_equip_pct=None,
                 is_parking_pv_equip=None,
                 companies=None):
        self.highways = highways
        self.h_pv_types = h_pv_types
        self.el_pv_type = el_pv_type
        self.tractor_width = tractor_width
        self.pv_equip_pct = pv_equip_pct
        self.is_parking_pv_equip = is_parking_pv_equip
        self.companies = companies

    # ERZEUGUNG
    # Solarautobahn
    highways: list                      # Auswahl Autobahnen
    h_pv_types: list                    # Auswahl PV-Types für die Autobahnen

    # Energielandschaft
    el_pv_type: str                     # Auswahl PV-Types für die Energielandschaft
    tractor_width: str                  # Traktorbreite [m]

    # Industriegebiet
    pv_equip_pct: float                 # PV Ausbau Dachfläche Indurstriegebiet [%]
    is_parking_pv_equip: bool           # Parkplatz pv installiert [true/false]

    # VERBRAUCH
    # Industriegebiet
    companies: list[str]                #Auswahl der Unternehmenstypen im Industriegebiet

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
                 power_data=None,):
        self.power_data = power_data
