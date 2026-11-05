"""
Green Energy Hub – Synthetische Lastprofile
============================================
Erzeugt 15-min-Profile für die Ladecluster (MCS, CCS, HPC, AC), die Gebäudelast
und die H2-Tankstellennachfrage aus Tagesform × Tagesfaktor × Rauschen,
skaliert auf die Jahresenergie der Machbarkeitsstudie und begrenzt auf die
Leistungsgrenze des Clusters.

Im Lademodell "sessions" (Standard) kommen MCS und HPC stattdessen aus einzelnen
Ladevorgängen (core/geh_sessions.py); "profile" erzeugt die glatten Profile.

Einstiegsfunktion: build_geh_load_profiles()
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from core.geh_sessions import SESSION_CLUSTERS, simulate_charging_sessions
from core.module_green_energy_hub import LHV_H2_KWH_PER_KG

CHARGING_MODELS: tuple[str, ...] = ("sessions", "profile")

DT_H: float = 0.25
NOISE_STD: float = 0.10          # Standardabweichung Rauschfaktor
MAX_CAP_ITERATIONS: int = 50
ENERGY_TOLERANCE: float = 0.001  # 0,1 %

# ---------------------------------------------------------------------------
# Tagesformen (Stunde 0 … 23)
# ---------------------------------------------------------------------------
SHAPE_MCS = [0.2, 0.1, 0.1, 0.1, 0.2, 0.4, 0.7, 0.9, 1.0, 1.0, 1.0, 0.9,
             0.8, 0.9, 1.0, 1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2]
SHAPE_CCS = [1.0, 1.0, 1.0, 0.9, 0.7, 0.4, 0.2, 0.05, 0, 0, 0, 0,
             0, 0, 0, 0, 0, 0.05, 0.2, 0.5, 0.8, 1.0, 1.0, 1.0]
SHAPE_HPC = [0.1, 0.05, 0.05, 0.05, 0.1, 0.2, 0.4, 0.6, 0.7, 0.8, 0.9, 1.0,
             1.0, 0.9, 0.9, 1.0, 1.0, 1.0, 0.9, 0.7, 0.5, 0.4, 0.3, 0.2]
SHAPE_AC = [0, 0, 0, 0, 0, 0, 0.2, 0.8, 1.0, 0.9, 0.7, 0.5,
            0.4, 0.4, 0.3, 0.2, 0.1, 0.05, 0, 0, 0, 0, 0, 0]
SHAPE_BUILDING = [0.7, 0.7, 0.7, 0.7, 0.7, 0.8, 0.9, 1.0, 1.0, 1.0, 1.0, 1.0,
                  1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.9, 0.8, 0.8, 0.7]
SHAPE_H2 = SHAPE_MCS

# ---------------------------------------------------------------------------
# Tagesfaktoren (Werktag, Samstag, Sonntag) – alle ANNAHME, nicht aus Studie
# ---------------------------------------------------------------------------
DAY_FACTORS_MCS = (1.0, 0.6, 0.15)        # ANNAHME, nicht aus Studie
SUNDAY_BAN_END_HOUR: int = 22             # ANNAHME, nicht aus Studie (Lkw-Sonntagsfahrverbot bis 22 Uhr)
DAY_FACTORS_CCS = (1.0, 0.6, 0.8)         # ANNAHME, nicht aus Studie
DAY_FACTORS_HPC = (1.0, 1.1, 1.2)         # ANNAHME, nicht aus Studie
DAY_FACTORS_AC = (1.0, 0.05, 0.05)        # ANNAHME, nicht aus Studie
DAY_FACTORS_BUILDING = (1.0, 1.0, 1.0)    # ANNAHME, nicht aus Studie


def _local_time(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """
    Wandelt den Zeitindex in Ortszeit Europe/Berlin um.
    tz-naive Zeitstempel werden – wie die Wetterdaten – als UTC interpretiert.
    """
    if index.tz is None:
        index = index.tz_localize("UTC")
    return index.tz_convert("Europe/Berlin")


def _base_shape(
    hours: np.ndarray,
    day_type: np.ndarray,
    shape: list[float],
    day_factors: tuple[float, float, float],
    sunday_ban: bool = False,
) -> np.ndarray:
    """
    Tagesform × Tagesfaktor je Zeitschritt.
    day_type: 0 = Werktag, 1 = Samstag, 2 = Sonntag.
    Bei sunday_ban gilt sonntags ab SUNDAY_BAN_END_HOUR der Werktagsfaktor.
    """
    factors = np.asarray(day_factors, dtype=float)[day_type]
    if sunday_ban:
        after_ban = (day_type == 2) & (hours >= SUNDAY_BAN_END_HOUR)
        factors = np.where(after_ban, day_factors[0], factors)
    return np.asarray(shape, dtype=float)[hours] * factors


def _scale_to_energy(shape: np.ndarray, annual_kwh: float, dt_h: float) -> np.ndarray:
    """Skaliert eine Form auf die Jahresenergie [kWh] und gibt Leistung [kW] zurück."""
    total = shape.sum() * dt_h
    if annual_kwh <= 0.0 or total <= 0.0:
        return np.zeros_like(shape)
    return shape / total * annual_kwh


def _apply_power_limit(
    profile_kw: np.ndarray,
    limit_kw: float | None,
    annual_kwh: float,
    dt_h: float,
) -> np.ndarray:
    """
    Kappt das Profil auf die Leistungsgrenze und verteilt die gekappte Energie
    proportional auf die nicht gekappten Zeitschritte. Iteriert, bis Jahresenergie
    (± ENERGY_TOLERANCE) und Grenze eingehalten sind.
    """
    if limit_kw is None or annual_kwh <= 0.0:
        return profile_kw

    p = profile_kw.copy()
    if (p > 0).sum() * limit_kw * dt_h < annual_kwh:
        raise ValueError(
            f"Jahresenergie {annual_kwh:.0f} kWh ist mit Leistungsgrenze {limit_kw:.0f} kW nicht erreichbar."
        )

    for _ in range(MAX_CAP_ITERATIONS):
        p = np.minimum(p, limit_kw)
        missing_kwh = annual_kwh - p.sum() * dt_h
        within_energy = abs(missing_kwh) <= ENERGY_TOLERANCE * annual_kwh
        if within_energy and p.max() <= limit_kw:
            break
        free = (p > 0) & (p < limit_kw)
        free_kwh = p[free].sum() * dt_h
        if free_kwh <= 0.0:
            break
        p[free] *= 1.0 + missing_kwh / free_kwh

    return np.minimum(p, limit_kw)


def _noise(rng: np.random.Generator, n: int) -> np.ndarray:
    """Deterministischer Rauschfaktor 1 + N(0; NOISE_STD), auf ≥ 0 begrenzt."""
    return np.clip(1.0 + rng.normal(0.0, NOISE_STD, n), 0.0, None)


def build_geh_load_profiles(
    index: pd.DatetimeIndex,
    variant: dict,
    seed: int = 42,
    charging_model: str = "sessions",
) -> pd.DataFrame:
    """
    Erzeugt die synthetischen GEH-Lastprofile.

    Args:
        index:          Zeitindex (15 min); tz-naive Zeitstempel gelten als UTC
        variant:        Parameter-Dictionary einer Variante aus GEH_VARIANTS
        seed:           Startwert des Zufallsgenerators (reproduzierbar)
        charging_model: "sessions" = MCS und HPC als einzelne Ladevorgänge,
                        "profile" = glatte Profile für alle Cluster

    Returns:
        DataFrame mit mcs_kw, ccs_kw, hpc_kw, ac_kw, building_kw [kW]
        und h2_demand_kwh [kWh_H2 je Zeitschritt]; bei "sessions" stehen die
        Statistiken der Ladevorgänge in result.attrs["sessions"]
    """
    if charging_model not in CHARGING_MODELS:
        raise ValueError(f"Unbekanntes Lademodell '{charging_model}', erwartet {CHARGING_MODELS}")
    local = _local_time(pd.DatetimeIndex(index))
    hours = local.hour.to_numpy()
    weekday = local.weekday.to_numpy()
    day_type = np.where(weekday == 6, 2, np.where(weekday == 5, 1, 0))
    n = len(index)
    rng = np.random.default_rng(seed)

    h2_annual_kwh = float(variant.get("h2_demand_t_per_a", 0.0)) * 1000.0 * LHV_H2_KWH_PER_KG

    # (Spalte, Form, Tagesfaktoren, Sonntagsfahrverbot, Jahresenergie, Leistungsgrenze)
    specs = [
        ("mcs_kw", SHAPE_MCS, DAY_FACTORS_MCS, True, variant.get("mcs_kwh", 0.0), variant.get("mcs_limit_kw")),
        ("ccs_kw", SHAPE_CCS, DAY_FACTORS_CCS, False, variant.get("ccs_kwh", 0.0), variant.get("ccs_limit_kw")),
        ("hpc_kw", SHAPE_HPC, DAY_FACTORS_HPC, False, variant.get("hpc_kwh", 0.0), variant.get("hpc_limit_kw")),
        ("ac_kw", SHAPE_AC, DAY_FACTORS_AC, False, variant.get("ac_kwh", 0.0), variant.get("ac_limit_kw")),
        ("building_kw", SHAPE_BUILDING, DAY_FACTORS_BUILDING, False, variant.get("building_kwh", 0.0), None),
        ("h2_demand_kw", SHAPE_H2, DAY_FACTORS_MCS, True, h2_annual_kwh, None),
    ]

    # Spalte → Cluster im Ladevorgangsmodell
    session_columns = {"mcs_kw": "mcs", "hpc_kw": "hpc"} if charging_model == "sessions" else {}

    result = pd.DataFrame(index=index)
    session_stats: dict[str, dict] = {}
    for column, shape, day_factors, sunday_ban, annual_kwh, limit_kw in specs:
        base = _base_shape(hours, day_type, shape, day_factors, sunday_ban)
        # Rauschen immer ziehen, damit die übrigen Profile in beiden Lademodellen gleich bleiben
        noisy = base * _noise(rng, n)
        annual_kwh = float(annual_kwh or 0.0)
        if column in session_columns:
            name = session_columns[column]
            cluster = dict(SESSION_CLUSTERS[name])
            if limit_kw is not None:
                cluster["limit_kw"] = float(limit_kw)
            sim = simulate_charging_sessions(index, cluster, base, annual_kwh, seed=seed)
            result[column] = sim.kw
            session_stats[name] = sim.stats()
            continue
        profile_kw = _scale_to_energy(noisy, annual_kwh, DT_H)
        profile_kw = _apply_power_limit(profile_kw, limit_kw, annual_kwh, DT_H)
        result[column] = profile_kw

    result["h2_demand_kwh"] = result.pop("h2_demand_kw") * DT_H
    if session_stats:
        result.attrs["sessions"] = session_stats
    return result
