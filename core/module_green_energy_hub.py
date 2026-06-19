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

from core.io_types import GuiInput

# ---------------------------------------------------------------------------
# Physikalische Konstanten
# ---------------------------------------------------------------------------
LHV_H2_KWH_PER_KG: float = 33.33  # Unterer Heizwert Wasserstoff [kWh/kg]

# Vereinfachtes Kompressor-Modell: ~6 % der H2-Energie für Verdichtung 30 → 1000 bar
# Abgeleitet aus MA_Saur_GEH.py (energy_loss_compressor ≈ 5–8 %)
COMPRESSOR_FACTOR: float = 0.06


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
