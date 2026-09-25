"""
Green Energy Hub – H2-Prozessketten-Modul
==========================================
Prozesskette: Überschuss-Strom → Elektrolyseur → Kompressor → H2-Speicher → Dispenser

Einstiegsfunktion: run_geh_h2_chain()

Wird von Simulation.py aufgerufen, nachdem eine vorläufige Bilanz berechnet wurde,
damit der verfügbare Überschuss-Strom bekannt ist.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import numpy as np
import pandas as pd
import pvlib
from pvlib.location import Location

from core.io_types import GuiInput

# ---------------------------------------------------------------------------
# Physikalische Konstanten
# ---------------------------------------------------------------------------
LHV_H2_KWH_PER_KG: float = 33.33  # Unterer Heizwert Wasserstoff [kWh/kg]

# Vereinfachtes Kompressor-Modell: ~6 % der H2-Energie für Verdichtung 30 → 1000 bar
# Abgeleitet aus MA_Saur_GEH.py (energy_loss_compressor ≈ 5–8 %)
COMPRESSOR_FACTOR: float = 0.06

# ---------------------------------------------------------------------------
# Varianten aus der Machbarkeitsstudie „Green Energy Hub – Autohof der Zukunft“
# (inno2grid / PRSch, 10/2025, Zieljahr 2035)
# ---------------------------------------------------------------------------
GEH_PV_KWP_PARKHAUSDACH: float = 500.0      # ANNAHME, nicht aus Studie (Basis = Erweiterung − Parkhausdach)
GEH_BATTERY_EFF_RT: float = 0.90            # ANNAHME, nicht aus Studie
GEH_H2_MIN_SOC: float = 0.30                # ANNAHME, nicht aus Studie
GEH_SOC_START: float = 0.50                 # ANNAHME, nicht aus Studie (H2-Speicher und Batterie)

# H2-Nachfrage abgeleitet: 1.500 kW × 5.000 h × 0,70 / 33,33 kWh/kg ≈ 157,5 t/a
GEH_H2_DEMAND_T_PER_A: float = 157.5

_GEH_COMMON: dict = {
    # Ladecluster: Jahresenergie [kWh/a], Leistungsgrenze [kW], Ladepunkte × Leistung [kW]
    "mcs_kwh": 11_108_000.0, "mcs_limit_kw": 2_400.0, "mcs_points": 4, "mcs_point_kw": 750.0,
    "ccs_kwh": 3_699_000.0, "ccs_limit_kw": 1_600.0, "ccs_points": 17, "ccs_point_kw": None,
    "hpc_kwh": 2_632_000.0, "hpc_limit_kw": 2_400.0, "hpc_points": 20, "hpc_point_kw": 150.0,
    "ac_limit_kw": 220.0, "ac_points": 102, "ac_point_kw": 11.0,
    "building_kwh": 135_000.0,
    # Batteriespeicher
    "battery_kwh": 6_200.0, "battery_kw": 5_000.0, "battery_eff_rt": GEH_BATTERY_EFF_RT,
    # H2-Kette
    "electrolyzer_kw": 1_500.0, "electrolyzer_eff": 0.70,
    "h2_storage_kwh": 40_000.0, "h2_demand_t_per_a": GEH_H2_DEMAND_T_PER_A,
    "h2_min_soc": GEH_H2_MIN_SOC, "soc_start": GEH_SOC_START,
}

GEH_VARIANTS: dict[str, dict] = {
    "Basis": {
        **_GEH_COMMON,
        "ac_kwh": 0.0,                                   # Parkhaus entfällt
        "pv_kwp": 1_245.0 - GEH_PV_KWP_PARKHAUSDACH,     # 745 kWp
    },
    "Erweiterung": {
        **_GEH_COMMON,
        "ac_kwh": 560_000.0,
        "pv_kwp": 1_245.0,
    },
}

# ---------------------------------------------------------------------------
# PV am Hub (Standort AK Jackerath)
# ---------------------------------------------------------------------------
GEH_PV_LAT: float = 51.06                   # ANNAHME, nicht aus Studie
GEH_PV_LON: float = 6.49                    # ANNAHME, nicht aus Studie
GEH_PV_GAMMA_PDC: float = -0.0037           # Temperaturkoeffizient [1/K]
GEH_PV_INVERTER_ETA: float = 0.96           # Nennwirkungsgrad Wechselrichter
GEH_PV_LOSSES: float = 0.14                 # Gesamtverluste (Verschmutzung, Kabel, Mismatch, …)

# Teilflächen: (Anteil an kWp, Azimut [°], Neigung [°])
GEH_PV_SURFACES: list[tuple[float, float, float]] = [
    (0.50, 180.0, 15.0),                    # ANNAHME, nicht aus Studie: Dächer Süd
    (0.25, 90.0, 10.0),                     # ANNAHME, nicht aus Studie: Carports Ost
    (0.25, 270.0, 10.0),                    # ANNAHME, nicht aus Studie: Carports West
]


def simulate_geh_pv(weather_df: pd.DataFrame, kwp: float, index: pd.DatetimeIndex) -> pd.Series:
    """
    PV-Erzeugung am Hub mit dem vereinfachten PVWatts-Modell.

    Zwei Teilflächen (Dächer Süd, Carports Ost-West), Zelltemperatur nach Faiman,
    pauschale Systemverluste GEH_PV_LOSSES, PVWatts-Wechselrichter.

    Args:
        weather_df: Wetterdaten (tz-naiv UTC, 15 min) mit ghi, dhi, dni, temp_air, wind_speed
        kwp:        installierte PV-Leistung [kWp]
        index:      Zielindex der Ergebniszeitreihe

    Returns:
        AC-Leistung [kW] auf index, NaN → 0
    """
    if kwp <= 0.0:
        return pd.Series(0.0, index=index)

    times = weather_df.index
    times_utc = times.tz_localize("UTC") if times.tz is None else times.tz_convert("UTC")

    loc = Location(GEH_PV_LAT, GEH_PV_LON, tz="Europe/Berlin")
    solpos = loc.get_solarposition(times_utc)
    dni_extra = pvlib.irradiance.get_extra_radiation(times_utc)

    ghi = weather_df["ghi"].to_numpy()
    dhi = weather_df["dhi"].to_numpy()
    dni = weather_df["dni"].to_numpy()
    temp_air = weather_df["temp_air"].to_numpy()
    wind_speed = weather_df["wind_speed"].to_numpy()

    pdc0_w = kwp * 1000.0
    pdc_w = np.zeros(len(times))
    for share, azimuth, tilt in GEH_PV_SURFACES:
        poa = pvlib.irradiance.get_total_irradiance(
            surface_tilt=tilt,
            surface_azimuth=azimuth,
            solar_zenith=solpos["apparent_zenith"].to_numpy(),
            solar_azimuth=solpos["azimuth"].to_numpy(),
            dni=dni,
            ghi=ghi,
            dhi=dhi,
            dni_extra=dni_extra.to_numpy(),
            model="haydavies",
        )
        poa_global = np.nan_to_num(np.asarray(poa["poa_global"], dtype=float), nan=0.0)
        temp_cell = pvlib.temperature.faiman(poa_global, temp_air, wind_speed)
        pdc_w += pvlib.pvsystem.pvwatts_dc(poa_global, temp_cell, share * pdc0_w, GEH_PV_GAMMA_PDC)

    pdc_w = np.clip(pdc_w, 0.0, None) * (1.0 - GEH_PV_LOSSES)
    pac_w = pvlib.inverter.pvwatts(pdc_w, pdc0_w, eta_inv_nom=GEH_PV_INVERTER_ETA)

    pv_kw = pd.Series(np.clip(np.asarray(pac_w, dtype=float), 0.0, None) / 1000.0, index=times)
    return pv_kw.reindex(index).fillna(0.0)


# ---------------------------------------------------------------------------
# Ergebnis-Datenklasse
# ---------------------------------------------------------------------------
@dataclass
class GEHResult:
    """Ergebnisse des H2-Prozessketten-Moduls (Zeitreihen + Jahreswerte)."""

    # Zeitreihen [kW] bzw. [kg] je Zeitschritt
    electrolyzer_power_kw: pd.Series = field(default_factory=pd.Series)
    compressor_power_kw: pd.Series = field(default_factory=pd.Series)
    h2_production_kg: pd.Series = field(default_factory=pd.Series)
    h2_delivered_kg: pd.Series = field(default_factory=pd.Series)
    storage_soc_kwh: pd.Series = field(default_factory=pd.Series)
    total_el_demand_kw: pd.Series = field(default_factory=pd.Series)

    # Jahreswerte
    h2_production_kwh: float = 0.0
    compressor_demand_kwh: float = 0.0
    h2_delivered_kwh: float = 0.0
    h2_curtailed_kwh: float = 0.0


# ---------------------------------------------------------------------------
# Teilschritte
# ---------------------------------------------------------------------------

def _electrolyzer_step(
    surplus_kw: pd.Series,
    p_nominal_kw: float,
    efficiency: float,
    dt_h: float,
) -> tuple[pd.Series, pd.Series]:
    """
    Vereinfachtes Elektrolyseur-Modell (Stationär, ohne Anlaufzeiten).

    Der Elektrolyseur nimmt Strom bis zur Nennleistung ab, wenn Überschuss
    vorhanden ist. H2-Produktion = Strombezug × Systemwirkungsgrad / LHV.

    Returns:
        el_power_kw  – tatsächlicher Strombezug [kW] je Zeitschritt
        h2_kg_per_dt – H2-Massenstrom [kg] je Zeitschritt
    """
    el_power_kw = surplus_kw.clip(lower=0.0).clip(upper=p_nominal_kw)
    h2_kwh_per_dt = el_power_kw * dt_h * efficiency
    h2_kg_per_dt = h2_kwh_per_dt / LHV_H2_KWH_PER_KG
    return el_power_kw, h2_kg_per_dt


def _compressor_step(h2_kg_per_dt: pd.Series, dt_h: float) -> pd.Series:
    """
    Vereinfachtes Kompressor-Modell (30 → 1000 bar).

    Strombedarf ≈ COMPRESSOR_FACTOR × H2-Energie je Zeitschritt.
    Gibt Leistung in kW zurück.
    """
    h2_kwh_per_dt = h2_kg_per_dt * LHV_H2_KWH_PER_KG
    comp_kwh_per_dt = h2_kwh_per_dt * COMPRESSOR_FACTOR
    return comp_kwh_per_dt / dt_h  # kW


def _storage_step(
    h2_produced_kwh: pd.Series,
    h2_demanded_kwh: pd.Series,
    capacity_kwh: float,
    max_charge_kw: float,
    dt_h: float,
) -> tuple[pd.Series, pd.Series, float]:
    """
    Einfaches SOC-Tracking für den H2-Speicher.

    Logik je Zeitschritt:
      1. Produktion deckt Nachfrage direkt
      2. Restbedarf kommt aus dem Speicher
      3. Überschuss-H2 geht in den Speicher (bis Kapazität)
      4. Kann der Speicher nicht mehr aufnehmen → Abregelung

    Returns:
        h2_delivered_kwh – tatsächlich an Dispenser gelieferte H2-Energie [kWh]
        soc_kwh          – Speicher-SOC je Zeitschritt [kWh_H2]
        curtailed_kwh    – Abgeregelter H2 (kein Platz) [kWh_H2]
    """
    max_charge_kwh = max_charge_kw * dt_h if max_charge_kw > 0 else float("inf")

    soc = 0.0
    soc_list: list[float] = []
    delivered_list: list[float] = []
    curtailed_total = 0.0

    for produced, demanded in zip(h2_produced_kwh, h2_demanded_kwh):
        # Nachfrage zuerst aus aktueller Produktion decken
        direct = min(produced, demanded)
        surplus = produced - direct
        remaining_demand = demanded - direct

        # Restbedarf aus Speicher
        from_storage = min(remaining_demand, soc)
        soc -= from_storage
        delivered = direct + from_storage

        # Überschuss in Speicher laden (max. Ladeleistung + freie Kapazität)
        to_storage = min(surplus, capacity_kwh - soc, max_charge_kwh)
        soc += to_storage
        soc = max(0.0, min(soc, capacity_kwh))  # Numerische Absicherung

        curtailed_this = surplus - to_storage
        curtailed_total += max(0.0, curtailed_this)

        soc_list.append(soc)
        delivered_list.append(delivered)

    idx = h2_produced_kwh.index
    return (
        pd.Series(delivered_list, index=idx, dtype=float),
        pd.Series(soc_list, index=idx, dtype=float),
        curtailed_total,
    )


# ---------------------------------------------------------------------------
# Haupt-Einstiegsfunktion
# ---------------------------------------------------------------------------

def run_geh_h2_chain(
    inp: GuiInput,
    surplus_kw: pd.Series,
    dt_h: float = 0.25,
) -> GEHResult:
    """
    Berechnet die H2-Prozesskette des Green Energy Hubs.

    Args:
        inp:        GuiInput mit GEH-Parametern (geh_electrolyzer_power_kw etc.)
        surplus_kw: Vorläufige Bilanz [kW] – positiv = Strom-Überschuss
        dt_h:       Zeitschrittgröße [h] (Standard 0.25 = 15 min)

    Returns:
        GEHResult mit Zeitreihen und aggregierten Jahreswerten
    """
    result = GEHResult()
    idx = surplus_kw.index

    p_nom = float(inp.geh_electrolyzer_power_kw or 0.0)
    if p_nom <= 0.0:
        empty = pd.Series(0.0, index=idx)
        result.electrolyzer_power_kw = empty
        result.compressor_power_kw = empty
        result.h2_production_kg = empty
        result.h2_delivered_kg = empty
        result.storage_soc_kwh = empty
        result.total_el_demand_kw = empty
        return result

    efficiency = float(inp.geh_electrolyzer_efficiency or 0.70)
    capacity_kwh = float(inp.geh_storage_capacity_kwh or 0.0)
    max_charge_kw = float(inp.geh_storage_max_charge_kw or p_nom)
    dispenser_kg_per_h = float(inp.geh_dispenser_demand_kg_per_h or 0.0)

    # 1 – Elektrolyseur
    el_kw, h2_kg_dt = _electrolyzer_step(surplus_kw, p_nom, efficiency, dt_h)
    h2_kwh_dt = h2_kg_dt * LHV_H2_KWH_PER_KG

    # 2 – Kompressor
    comp_kw = _compressor_step(h2_kg_dt, dt_h)

    # 3 – Dispenser-Nachfrage (konstantes Profil aus Eingabeparameter)
    dispenser_kwh_dt = pd.Series(
        dispenser_kg_per_h * dt_h * LHV_H2_KWH_PER_KG,
        index=idx,
        dtype=float,
    )

    # 4 – Speicher-Tracking
    if capacity_kwh > 0.0:
        delivered_kwh, soc_kwh, curtailed = _storage_step(
            h2_kwh_dt, dispenser_kwh_dt, capacity_kwh, max_charge_kw, dt_h
        )
    else:
        # Kein Speicher: direkter Durchlauf
        delivered_kwh = pd.Series(
            np.minimum(h2_kwh_dt.values, dispenser_kwh_dt.values),
            index=idx,
            dtype=float,
        )
        soc_kwh = pd.Series(0.0, index=idx)
        curtailed = float((h2_kwh_dt - delivered_kwh).clip(lower=0.0).sum())

    # 5 – Ergebnisse
    result.electrolyzer_power_kw = el_kw
    result.compressor_power_kw = comp_kw
    result.h2_production_kg = h2_kg_dt
    result.h2_delivered_kg = delivered_kwh / LHV_H2_KWH_PER_KG
    result.storage_soc_kwh = soc_kwh
    result.total_el_demand_kw = el_kw + comp_kw

    result.h2_production_kwh = float(h2_kwh_dt.sum())
    result.compressor_demand_kwh = float((comp_kw * dt_h).sum())
    result.h2_delivered_kwh = float(delivered_kwh.sum())
    result.h2_curtailed_kwh = curtailed

    return result
