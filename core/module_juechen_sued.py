"""
Jüchen Süd – Versorgungskonzepte
================================
Vereinfachte Abbildung des Energiekonzepts für die Stadtteilentwicklung
Jüchen Süd (Fraunhofer IEG, Abschlussveranstaltung 16.10.2026) in den drei
Versorgungskonzepten der Basis-Variante (Bedarf „moderat“, 3 Quartiere):

  - Warmes Netz:  zentrale Luft-Wärmepumpe → Wärmenetz 40–50 °C, Tankspeicher,
                  dezentraler Heizstab für die Warmwasser-Nachheizung
  - Kaltes Netz:  Anergienetz 10–25 °C, dezentrale Booster-Wärmepumpen, Heizstab
  - Dezentral:    Grundwasser-Wärmepumpen je Gebäude, Heizstab

Die Agri-PV der Studie (5,56 MW) wird über die Energielandschaft abgebildet
und hier nicht doppelt gezählt.

  - Parameter der Konzepte:  JS_CONCEPTS, resolve_js_concept()
  - Wärmepumpen-COP:         heat_pump_cop()
  - Betriebsführung:         run_js_heat_dispatch()

Die Bedarfsprofile liegen in core/js_profiles.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from core.io_types import GuiInput

# ---------------------------------------------------------------------------
# Temperaturen und Wärmepumpenmodell – alle ANNAHME, nicht aus Studie
# ---------------------------------------------------------------------------
JS_COP_CARNOT_FACTOR: float = 0.45        # ANNAHME, nicht aus Studie: Gütegrad bezogen auf Carnot-COP
JS_COP_MAX: float = 8.0                   # ANNAHME, nicht aus Studie
JS_COP_MIN_LIFT_K: float = 5.0            # ANNAHME, nicht aus Studie: Mindesthub für die Carnot-Formel
JS_T_SPACE_HEAT_C: float = 35.0           # ANNAHME, nicht aus Studie: Vorlauf Flächenheizung (Neubau)
JS_T_DHW_C: float = 60.0                  # ANNAHME, nicht aus Studie: Warmwassertemperatur
JS_T_COLD_WATER_C: float = 10.0           # ANNAHME, nicht aus Studie: Kaltwassertemperatur
JS_T_GROUNDWATER_C: float = 10.0          # ANNAHME, nicht aus Studie
JS_T_COLD_NET_C: float = 12.0             # ANNAHME, nicht aus Studie: Temperatur Anergienetz
JS_T_WARM_NET_C: float = 45.0             # ANNAHME, nicht aus Studie: Vorlauf warmes Netz (Studie: 40–50 °C)
JS_WARM_NET_LOSS: float = 0.10            # ANNAHME, nicht aus Studie: Wärmenetzverluste
JS_EER_SPLIT: float = 3.5                 # ANNAHME, nicht aus Studie: dezentrale Klimageräte
JS_EER_COLD_NET: float = 15.0             # ANNAHME, nicht aus Studie: Kühlung über das Anergienetz (nur Pumpen)

# ---------------------------------------------------------------------------
# Versorgungskonzepte, Basis-Variante (Folien 27, 29, 31)
# Leistungen der Wärmeerzeuger als thermische Nennleistung interpretiert (ANNAHME, nicht aus Studie)
# ---------------------------------------------------------------------------
JS_CONCEPTS: dict[str, dict] = {
    "Warmes Netz": {
        "hp_label": "Luft-Wärmepumpe zentral",
        "hp_source": "air",
        "hp_kw": 3_480.0,
        "heater_kw": 760.0,
        "tank_kwh": 3_060.0,
        "warm_net": True,
        "cooling_eer": JS_EER_SPLIT,
        "study": {"Strompreis": "11,8 ct/kWh", "Wärmepreis": "12,4 ct/kWh",
                  "Autarkiegrad Strom": "67 %", "PV-Eigenverbrauch": "66 %"},
    },
    "Kaltes Netz": {
        "hp_label": "Booster-Wärmepumpen dezentral",
        "hp_source": "cold_net",
        "hp_kw": 1_680.0,
        "heater_kw": 1_640.0,
        "tank_kwh": 0.0,
        "warm_net": False,
        "cooling_eer": JS_EER_COLD_NET,
        "sources": "Luft-Wärmepumpe 1,35 MW, Agrothermie-Kollektor 0,45 MW",
        "study": {"Strompreis": "12,4 ct/kWh", "Wärmepreis": "13,7 ct/kWh",
                  "Autarkiegrad Strom": "74 %", "PV-Eigenverbrauch": "59 %"},
    },
    "Dezentral": {
        "hp_label": "Grundwasser-Wärmepumpen dezentral",
        "hp_source": "groundwater",
        "hp_kw": 2_300.0,
        "heater_kw": 590.0,
        "tank_kwh": 0.0,
        "warm_net": False,
        "cooling_eer": JS_EER_SPLIT,
        "study": {"Strompreis": "12,7 ct/kWh", "Wärmepreis": "8,9 ct/kWh",
                  "Autarkiegrad Strom": "80 %", "PV-Eigenverbrauch": "57 %"},
    },
}

# GuiInput-Feld → Schlüssel in JS_CONCEPTS
_JS_OVERRIDES: dict[str, str] = {
    "js_hp_kw": "hp_kw",
    "js_heater_kw": "heater_kw",
    "js_tank_kwh": "tank_kwh",
}


def resolve_js_concept(inp: GuiInput) -> dict | None:
    """
    Liefert die Parameter des gewählten Versorgungskonzepts inkl. Overrides.
    None, wenn kein Konzept aktiv ist (js_concept None oder "Aus").
    """
    if inp.js_concept not in JS_CONCEPTS:
        return None
    concept = dict(JS_CONCEPTS[inp.js_concept])
    for inp_field, key in _JS_OVERRIDES.items():
        value = getattr(inp, inp_field, None)
        if value is not None:
            concept[key] = float(value)
    return concept


# ---------------------------------------------------------------------------
# Wärmepumpen-COP
# ---------------------------------------------------------------------------

def heat_pump_cop(t_source_c: np.ndarray | float, t_sink_c: float) -> np.ndarray:
    """COP = Gütegrad × Carnot-COP, begrenzt auf [1, JS_COP_MAX]."""
    t_source = np.asarray(t_source_c, dtype=float)
    lift = np.maximum(t_sink_c - t_source, JS_COP_MIN_LIFT_K)
    cop = JS_COP_CARNOT_FACTOR * (t_sink_c + 273.15) / lift
    return np.clip(cop, 1.0, JS_COP_MAX)


def concept_cops(concept: dict, temp_air: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    COP-Zeitreihen der Wärmepumpe für Raumwärme und Warmwasser.
    Beim warmen Netz liefert die zentrale Wärmepumpe für beides auf Netztemperatur.
    """
    n = len(temp_air)
    source = concept["hp_source"]
    if source == "air":
        t_source = np.asarray(temp_air, dtype=float)
    elif source == "groundwater":
        t_source = np.full(n, JS_T_GROUNDWATER_C)
    else:
        t_source = np.full(n, JS_T_COLD_NET_C)

    if concept["warm_net"]:
        cop_net = heat_pump_cop(t_source, JS_T_WARM_NET_C)
        return cop_net, cop_net
    return heat_pump_cop(t_source, JS_T_SPACE_HEAT_C), heat_pump_cop(t_source, JS_T_DHW_C)


# ---------------------------------------------------------------------------
# Betriebsführung (regelbasiert, 1:1 nach JavaScript übertragbar)
# ---------------------------------------------------------------------------

@dataclass
class JSParams:
    """Anlagenparameter für run_js_heat_dispatch."""

    hp_kw: float               # Wärmepumpe, thermische Leistung [kW]
    heater_kw: float           # Heizstab [kW]
    tank_kwh: float            # Tankspeicher [kWh_th]
    warm_net: bool             # Wärmenetz mit Netzverlusten und Warmwasser-Nachheizung
    cooling_eer: float
    net_loss: float = JS_WARM_NET_LOSS
    dhw_lift_share: float = (JS_T_DHW_C - JS_T_WARM_NET_C) / (JS_T_DHW_C - JS_T_COLD_WATER_C)
    tank_soc_start: float = 0.5   # ANNAHME, nicht aus Studie

    @classmethod
    def from_concept(cls, concept: dict) -> "JSParams":
        return cls(
            hp_kw=float(concept["hp_kw"]),
            heater_kw=float(concept["heater_kw"]),
            tank_kwh=float(concept["tank_kwh"]),
            warm_net=bool(concept["warm_net"]),
            cooling_eer=float(concept["cooling_eer"]),
        )


def _zeros() -> np.ndarray:
    return np.zeros(0)


@dataclass
class JSDispatchResult:
    """Ergebnisse von run_js_heat_dispatch (Zeitreihen [kW] bzw. [kWh] + Jahreswerte)."""

    hp_th_kw: np.ndarray = field(default_factory=_zeros)
    hp_el_kw: np.ndarray = field(default_factory=_zeros)
    heater_kw: np.ndarray = field(default_factory=_zeros)
    cooling_el_kw: np.ndarray = field(default_factory=_zeros)
    tank_soc_kwh: np.ndarray = field(default_factory=_zeros)
    unmet_kw: np.ndarray = field(default_factory=_zeros)
    net_loss_kw: np.ndarray = field(default_factory=_zeros)

    tank_soc_start_kwh: float = 0.0
    hp_th_kwh: float = 0.0
    hp_el_kwh: float = 0.0
    heater_kwh: float = 0.0
    cooling_el_kwh: float = 0.0
    unmet_kwh: float = 0.0
    net_loss_kwh: float = 0.0
    scop: float = 0.0


def run_js_heat_dispatch(
    space_kw: np.ndarray,
    dhw_kw: np.ndarray,
    cooling_kw: np.ndarray,
    cop_space: np.ndarray,
    cop_dhw: np.ndarray,
    p: JSParams,
    dt_h: float = 0.25,
) -> JSDispatchResult:
    """
    Wärmeversorgung je Zeitschritt, nachfragegeführt.

    Reihenfolge je Zeitschritt:
      1. Warmes Netz: Netzwärme = (Raumwärme + Warmwasseranteil bis Netztemperatur)
         / (1 − Netzverluste); der Rest des Warmwassers wird per Heizstab nachgeheizt.
         Sonst: Wärmepumpe deckt Raumwärme und Warmwasser direkt.
      2. Wärmepumpe bis zur Nennleistung, Fehlmenge zuerst aus dem Tankspeicher
      3. Freie Wärmepumpenleistung lädt den Tankspeicher
      4. Heizstab deckt Nachheizung und Restfehlmenge; was übrig bleibt, ist ungedeckt
      5. Kälte: elektrisch über festen EER
    """
    n = len(space_kw)
    hp_th_arr = np.zeros(n)
    hp_el_arr = np.zeros(n)
    heater_arr = np.zeros(n)
    cool_el_arr = np.zeros(n)
    soc_arr = np.zeros(n)
    unmet_arr = np.zeros(n)
    loss_arr = np.zeros(n)

    soc = p.tank_soc_start * p.tank_kwh

    for t in range(n):
        space = float(space_kw[t])
        dhw = float(dhw_kw[t])

        # 1) Wärmebedarf an der Wärmepumpe
        if p.warm_net:
            heater_need = dhw * p.dhw_lift_share
            delivered = space + dhw - heater_need
            demand_hp = delivered / (1.0 - p.net_loss)
            loss_arr[t] = demand_hp - delivered
        else:
            heater_need = 0.0
            demand_hp = space + dhw

        # 2) Wärmepumpe, Fehlmenge aus dem Tankspeicher
        hp_out = min(p.hp_kw, demand_hp)
        short = demand_hp - hp_out
        from_tank = min(short, soc / dt_h) if p.tank_kwh > 0.0 else 0.0
        soc -= from_tank * dt_h
        short -= from_tank

        # 3) Freie Leistung lädt den Tankspeicher
        to_tank = 0.0
        if p.tank_kwh > 0.0:
            to_tank = min(p.hp_kw - hp_out, (p.tank_kwh - soc) / dt_h)
            soc += to_tank * dt_h
        soc = min(max(soc, 0.0), p.tank_kwh)                 # Numerische Absicherung

        # Strombedarf: Wärmepumpenwärme zuerst für Raumwärme, Rest auf Warmwasser-COP
        hp_th = hp_out + to_tank
        if p.warm_net:
            hp_el = hp_th / float(cop_space[t])
        else:
            served_space = min(hp_th, space)
            hp_el = served_space / float(cop_space[t]) + (hp_th - served_space) / float(cop_dhw[t])

        # 4) Heizstab
        heater_need += short
        heater = min(p.heater_kw, heater_need)

        # 5) Kälte
        cool_el = float(cooling_kw[t]) / p.cooling_eer if p.cooling_eer > 0.0 else 0.0

        hp_th_arr[t] = hp_th
        hp_el_arr[t] = hp_el
        heater_arr[t] = heater
        cool_el_arr[t] = cool_el
        soc_arr[t] = soc
        unmet_arr[t] = heater_need - heater

    r = JSDispatchResult(
        hp_th_kw=hp_th_arr,
        hp_el_kw=hp_el_arr,
        heater_kw=heater_arr,
        cooling_el_kw=cool_el_arr,
        tank_soc_kwh=soc_arr,
        unmet_kw=unmet_arr,
        net_loss_kw=loss_arr,
        tank_soc_start_kwh=p.tank_soc_start * p.tank_kwh,
    )
    r.hp_th_kwh = float(hp_th_arr.sum() * dt_h)
    r.hp_el_kwh = float(hp_el_arr.sum() * dt_h)
    r.heater_kwh = float(heater_arr.sum() * dt_h)
    r.cooling_el_kwh = float(cool_el_arr.sum() * dt_h)
    r.unmet_kwh = float(unmet_arr.sum() * dt_h)
    r.net_loss_kwh = float(loss_arr.sum() * dt_h)
    r.scop = r.hp_th_kwh / r.hp_el_kwh if r.hp_el_kwh > 0 else 0.0
    return r
