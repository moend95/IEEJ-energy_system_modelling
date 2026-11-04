"""
Jüchen Süd – Synthetische Bedarfsprofile
=========================================
Erzeugt 15-min-Profile für Raumwärme, Trinkwarmwasser, Raumkälte, Nutzerstrom
und E-Mobilität des Stadtteils Jüchen Süd, skaliert auf die Jahresbedarfe des
Energiekonzepts (Fraunhofer IEG, Abschlussveranstaltung 16.10.2026, Szenario
„moderat“).

Einstiegsfunktion: build_js_profiles()
"""

from __future__ import annotations

import os

import numpy as np
import pandas as pd

from core.geh_profiles import (
    _apply_power_limit,
    _base_shape,
    _local_time,
    _noise,
    _scale_to_energy,
)

DT_H: float = 0.25

_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_HOUSEHOLD_CSV = os.path.join(_PROJECT_DIR, "data", "inputs", "Strombezug_Stadtentwicklung_15min.csv")

# ---------------------------------------------------------------------------
# Jahresbedarfe aus der Studie (Szenario „moderat“, alle 4 Quartiere) [kWh/a]
# ---------------------------------------------------------------------------
JS_TOTAL_SPACE_HEAT_KWH: float = 5_664_000.0
JS_TOTAL_DHW_KWH: float = 3_649_000.0
JS_TOTAL_COOLING_KWH: float = 241_000.0
JS_TOTAL_HOUSEHOLD_KWH: float = 4_423_000.0
JS_TOTAL_HOUSEHOLD_PEAK_KW: float = 902.0
JS_TOTAL_EMOB_KWH: float = 3_989_900.0
JS_TOTAL_EMOB_PEAK_KW: float = 1_900.0

# Quartiersspezifische Bedarfe [GWh/a] (Folie 6) – Raumwärme, Trinkwarmwasser, Nutzerstrom
JS_QUARTERS: dict[str, dict[str, float]] = {
    "IGA-Quartier": {"space": 1.6, "dhw": 1.0, "household": 1.29},
    "Schulquartier": {"space": 2.0, "dhw": 1.2, "household": 1.43},
    "Gartenquartier": {"space": 1.1, "dhw": 0.8, "household": 0.90},
    "Forstquartier": {"space": 1.0, "dhw": 0.7, "household": 0.80},
}
# Basis-Variante der Studie: 3 Quartiere – welche, ist nicht angegeben
JS_BASIS_QUARTERS: list[str] = ["IGA-Quartier", "Schulquartier", "Gartenquartier"]  # ANNAHME, nicht aus Studie

# E-Mobilität (Folie 7): Fahrzeuge je Gruppe, Energieanteil proportional zur Fahrzeugzahl
JS_EMOB_VEHICLES: dict[str, int] = {"privat": 300, "oeffentlich": 300, "arbeitsplatz": 36}

# ---------------------------------------------------------------------------
# Profilannahmen – alle ANNAHME, nicht aus Studie
# ---------------------------------------------------------------------------
JS_HEATING_LIMIT_C: float = 15.0          # ANNAHME, nicht aus Studie: Heizgrenztemperatur
JS_HEATING_SMOOTH_STEPS: int = 48         # ANNAHME, nicht aus Studie: 12-h-Mittel der Außentemperatur (Gebäudeträgheit)
JS_NIGHT_SETBACK: float = 0.8             # ANNAHME, nicht aus Studie: Nachtabsenkung 22–5 Uhr
JS_COOLING_LIMIT_C: float = 22.0          # ANNAHME, nicht aus Studie: Kühlgrenztemperatur

# Tagesformen (Stunde 0 … 23) – ANNAHME, nicht aus Studie
SHAPE_DHW = [0.3, 0.2, 0.2, 0.2, 0.3, 0.6, 1.0, 1.0, 0.8, 0.6, 0.5, 0.5,
             0.6, 0.5, 0.4, 0.4, 0.5, 0.7, 0.9, 1.0, 0.9, 0.7, 0.5, 0.4]
SHAPE_EMOB_PRIVAT = [0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1,
                     0.1, 0.2, 0.3, 0.5, 0.7, 0.9, 1.0, 1.0, 1.0, 0.9, 0.8, 0.7]
SHAPE_EMOB_ARBEITSPLATZ = [0, 0, 0, 0, 0, 0, 0.3, 0.8, 1.0, 1.0, 0.8, 0.6,
                           0.4, 0.3, 0.2, 0.1, 0, 0, 0, 0, 0, 0, 0, 0]
SHAPE_EMOB_OEFFENTLICH = [0.1, 0.05, 0.05, 0.05, 0.05, 0.1, 0.2, 0.4, 0.7, 1.0, 1.0, 1.0,
                          1.0, 1.0, 1.0, 1.0, 1.0, 0.8, 0.6, 0.4, 0.3, 0.2, 0.15, 0.1]

# Tagesfaktoren (Werktag, Samstag, Sonntag) – ANNAHME, nicht aus Studie
DAY_FACTORS_DHW = (1.0, 1.1, 1.1)
DAY_FACTORS_EMOB_PRIVAT = (1.0, 1.1, 1.1)
DAY_FACTORS_EMOB_ARBEITSPLATZ = (1.0, 0.1, 0.05)
DAY_FACTORS_EMOB_OEFFENTLICH = (1.0, 1.0, 0.7)


def js_annual_demands(quarters: list[str] | None = None) -> dict[str, float]:
    """
    Jahresbedarfe [kWh/a] für die gewählten Quartiere.
    Raumwärme, Trinkwarmwasser und Nutzerstrom anteilig nach Folie 6;
    Kälte und E-Mobilität anteilig nach Nutzerstrom (ANNAHME, nicht aus Studie).
    """
    quarters = JS_BASIS_QUARTERS if quarters is None else quarters

    def share(key: str) -> float:
        total = sum(q[key] for q in JS_QUARTERS.values())
        return sum(JS_QUARTERS[name][key] for name in quarters) / total

    household_share = share("household")
    return {
        "space_heat_kwh": JS_TOTAL_SPACE_HEAT_KWH * share("space"),
        "dhw_kwh": JS_TOTAL_DHW_KWH * share("dhw"),
        "cooling_kwh": JS_TOTAL_COOLING_KWH * household_share,
        "household_kwh": JS_TOTAL_HOUSEHOLD_KWH * household_share,
        "household_peak_kw": JS_TOTAL_HOUSEHOLD_PEAK_KW * household_share,
        "emob_kwh": JS_TOTAL_EMOB_KWH * household_share,
        "emob_peak_kw": JS_TOTAL_EMOB_PEAK_KW * household_share,
    }


def _household_shape(n: int) -> np.ndarray:
    """
    Form des bisherigen Lastgangs Stadtentwicklung (positionsgleich, 15 min),
    zum Mittelwert hin gestaucht, sodass Spitze/Mittelwert dem Verhältnis der Studie entspricht.
    """
    df = pd.read_csv(JS_HOUSEHOLD_CSV)
    df.columns = df.columns.str.strip()
    values = pd.to_numeric(
        df["Strombezug (kW)"].astype(str).str.replace(",", ".", regex=False), errors="coerce"
    ).fillna(0.0).clip(lower=0.0).to_numpy()
    if len(values) < n:
        values = np.resize(values, n)
    values = values[:n]

    target_ratio = JS_TOTAL_HOUSEHOLD_PEAK_KW / (JS_TOTAL_HOUSEHOLD_KWH / 8760.0)
    mean = values.mean()
    current_ratio = values.max() / mean
    if current_ratio > target_ratio:
        values = mean + (values - mean) * (target_ratio - 1.0) / (current_ratio - 1.0)
    return np.clip(values, 0.0, None)


def build_js_profiles(
    index: pd.DatetimeIndex,
    temp_air: np.ndarray,
    demands: dict[str, float] | None = None,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Erzeugt die synthetischen Bedarfsprofile Jüchen Süd.

    Args:
        index:    Zeitindex (15 min); tz-naive Zeitstempel gelten als UTC
        temp_air: Außentemperatur [°C] je Zeitschritt (positionsgleich zu index)
        demands:  Jahresbedarfe aus js_annual_demands(); None = Basis (3 Quartiere)
        seed:     Startwert des Zufallsgenerators (reproduzierbar)

    Returns:
        DataFrame mit space_heat_kw, dhw_kw, cooling_kw (thermisch) sowie
        household_kw und emob_kw (elektrisch)
    """
    demands = js_annual_demands() if demands is None else demands
    local = _local_time(pd.DatetimeIndex(index))
    hours = local.hour.to_numpy()
    weekday = local.weekday.to_numpy()
    day_type = np.where(weekday == 6, 2, np.where(weekday == 5, 1, 0))
    n = len(index)
    rng = np.random.default_rng(seed)
    temp = np.asarray(temp_air, dtype=float)

    result = pd.DataFrame(index=index)

    # Raumwärme: Heizgradstunden auf geglätteter Außentemperatur, mit Nachtabsenkung
    temp_smooth = pd.Series(temp).rolling(JS_HEATING_SMOOTH_STEPS, min_periods=1).mean().to_numpy()
    night = (hours >= 22) | (hours < 5)
    space_shape = np.clip(JS_HEATING_LIMIT_C - temp_smooth, 0.0, None) * np.where(night, JS_NIGHT_SETBACK, 1.0)
    result["space_heat_kw"] = _scale_to_energy(space_shape, demands["space_heat_kwh"], DT_H)

    # Trinkwarmwasser: Tagesform mit Rauschen
    dhw_shape = _base_shape(hours, day_type, SHAPE_DHW, DAY_FACTORS_DHW) * _noise(rng, n)
    result["dhw_kw"] = _scale_to_energy(dhw_shape, demands["dhw_kwh"], DT_H)

    # Raumkälte: Kühlgradstunden
    cooling_shape = np.clip(temp - JS_COOLING_LIMIT_C, 0.0, None)
    result["cooling_kw"] = _scale_to_energy(cooling_shape, demands["cooling_kwh"], DT_H)

    # Nutzerstrom: Form des bisherigen Lastgangs, skaliert auf den Studienwert
    result["household_kw"] = _scale_to_energy(_household_shape(n), demands["household_kwh"], DT_H)

    # E-Mobilität: drei Nutzergruppen, Summe auf die Spitzenleistung der Studie begrenzt
    vehicles_total = sum(JS_EMOB_VEHICLES.values())
    groups = [
        ("privat", SHAPE_EMOB_PRIVAT, DAY_FACTORS_EMOB_PRIVAT),
        ("oeffentlich", SHAPE_EMOB_OEFFENTLICH, DAY_FACTORS_EMOB_OEFFENTLICH),
        ("arbeitsplatz", SHAPE_EMOB_ARBEITSPLATZ, DAY_FACTORS_EMOB_ARBEITSPLATZ),
    ]
    emob_kw = np.zeros(n)
    for name, shape, day_factors in groups:
        energy = demands["emob_kwh"] * JS_EMOB_VEHICLES[name] / vehicles_total
        group_shape = _base_shape(hours, day_type, shape, day_factors) * _noise(rng, n)
        emob_kw += _scale_to_energy(group_shape, energy, DT_H)
    result["emob_kw"] = _apply_power_limit(emob_kw, demands["emob_peak_kw"], demands["emob_kwh"], DT_H)

    return result
