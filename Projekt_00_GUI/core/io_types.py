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
    # ERZEUGUNG
    # Solarautobahn
    highways: list                  # Auswahl Autobahnen
    pv_types: list                  # Auswahl PV-Types für die Autobahnen

    # Energielandschaft
    pv_type: str                    # Auswahl PV-Types für die Energielandschaft
    tractor_width: str              # Traktorbreite [m]

    # Industriegebiet
    pv_equip_pct: float             # PV Ausbau Dachfläche Indurstriegebiet [%]
    is_parking_pv_equip: bool       # Parkplatz pv installiert [true/false]

    # VERBRAUCH
    # Industriegebiet
    companies: list[str]            #Auswahl der Unternehmenstypen im Industriegebiet

    # Green Energy Hub

# =========================
# Output der Simulation
# =========================

@dataclass
class SimOutput:
    """
    Ergebnisse der Simulation. Die auf der Website dargestellt werden sollen.
    """


