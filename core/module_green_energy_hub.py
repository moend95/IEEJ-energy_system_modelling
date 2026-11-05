"""
Green Energy Hub – Autohof der Zukunft
======================================
Vereinfachte Abbildung der Machbarkeitsstudie „Green Energy Hub – Autohof der
Zukunft“ (inno2grid / PRSch, 10/2025, Zieljahr 2035) in zwei Varianten
(Basis, Erweiterung):

  - Parameter der Varianten:  GEH_VARIANTS, resolve_geh_variant()
  - PV am Hub:                simulate_geh_pv()
  - Betriebsführung:          run_geh_dispatch()
    Elektrolyseur → H2-Speicher → Tankstelle, Batterie, Netzbezug/-einspeisung

Die Ladeprofile der Ladecluster liegen in core/geh_profiles.py.
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
GEH_H2_HIGH_SOC: float = 0.90               # ANNAHME, nicht aus Studie: darüber Elektrolyseur nur mit Überschuss
GEH_BATTERY_RECHARGE_MARGIN: float = 0.80   # ANNAHME, nicht aus Studie: Nachladen aus dem Netz unter 80 % der Grenze

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
    "h2_high_soc": GEH_H2_HIGH_SOC,
    # Betriebsführung: Grundlast Elektrolyseur (None = aus der H2-Nachfrage), Nachladen der Batterie
    "electrolyzer_base_kw": None,
    "battery_recharge_margin": GEH_BATTERY_RECHARGE_MARGIN,
}

GEH_VARIANTS: dict[str, dict] = {
    "Basis": {
        **_GEH_COMMON,
        "ac_kwh": 0.0,                                   # Parkhaus entfällt
        "pv_kwp": 1_245.0 - GEH_PV_KWP_PARKHAUSDACH,     # 745 kWp
        "grid_limit_kw": 3_900.0,                        # Netzanschluss-Spitze (Studie)
    },
    "Erweiterung": {
        **_GEH_COMMON,
        "ac_kwh": 560_000.0,
        "pv_kwp": 1_245.0,
        "grid_limit_kw": 4_000.0,                        # Netzanschluss-Spitze (Studie)
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
# Variante auflösen (GEH_VARIANTS + Overrides aus GuiInput)
# ---------------------------------------------------------------------------

# GuiInput-Feld → Schlüssel in GEH_VARIANTS
_GEH_OVERRIDES: dict[str, str] = {
    "geh_pv_kwp": "pv_kwp",
    "geh_battery_kwh": "battery_kwh",
    "geh_battery_kw": "battery_kw",
    "geh_h2_demand_t_per_a": "h2_demand_t_per_a",
    "geh_h2_min_soc": "h2_min_soc",
    "geh_electrolyzer_power_kw": "electrolyzer_kw",
    "geh_electrolyzer_efficiency": "electrolyzer_eff",
    "geh_storage_capacity_kwh": "h2_storage_kwh",
    "geh_grid_limit_kw": "grid_limit_kw",
    "geh_electrolyzer_base_kw": "electrolyzer_base_kw",
    "geh_h2_high_soc": "h2_high_soc",
    "geh_battery_recharge_margin": "battery_recharge_margin",
}


def resolve_geh_variant(inp: GuiInput) -> dict | None:
    """
    Liefert die Parameter der gewählten Variante inkl. Overrides aus GuiInput.
    None, wenn keine Variante aktiv ist (geh_variant None oder "Keine").
    """
    if inp.geh_variant not in GEH_VARIANTS:
        return None
    variant = dict(GEH_VARIANTS[inp.geh_variant])
    for inp_field, key in _GEH_OVERRIDES.items():
        value = getattr(inp, inp_field, None)
        if value is not None:
            variant[key] = float(value)
    return variant


# ---------------------------------------------------------------------------
# Dispatch (regelbasiert, 1:1 nach JavaScript übertragbar)
# ---------------------------------------------------------------------------

@dataclass
class GEHParams:
    """Anlagenparameter für run_geh_dispatch."""

    electrolyzer_kw: float
    electrolyzer_eff: float
    h2_storage_kwh: float
    h2_min_soc: float          # 0..1
    h2_soc_start: float        # 0..1
    battery_kwh: float
    battery_kw: float
    battery_eff_rt: float
    battery_soc_start: float   # 0..1
    compressor_factor: float = COMPRESSOR_FACTOR
    h2_high_soc: float = 1.0               # 0..1, darüber Elektrolyseur nur mit Überschuss
    electrolyzer_base_kw: float = 0.0      # Grundlast Elektrolyseur [kW]
    grid_limit_kw: float = 0.0             # Netzgrenze des Hubs [kW], 0 = keine Grenze
    battery_recharge_margin: float = 0.0   # Anteil der Grenze, bis zu dem aus dem Netz nachgeladen wird

    @classmethod
    def from_variant(cls, variant: dict | None) -> "GEHParams":
        """Parameter aus einer aufgelösten Variante; None ergibt Nullkomponenten."""
        if variant is None:
            return cls(
                electrolyzer_kw=0.0, electrolyzer_eff=1.0, h2_storage_kwh=0.0,
                h2_min_soc=0.0, h2_soc_start=0.0, battery_kwh=0.0, battery_kw=0.0,
                battery_eff_rt=1.0, battery_soc_start=0.0,
            )
        eff = float(variant["electrolyzer_eff"])
        base_kw = variant.get("electrolyzer_base_kw")
        if base_kw is None:
            # Grundlast so, dass der Elektrolyseur im Jahresmittel genau die H2-Nachfrage erzeugt
            h2_demand_kwh = float(variant["h2_demand_t_per_a"]) * 1000.0 * LHV_H2_KWH_PER_KG
            base_kw = h2_demand_kwh / (eff * 8760.0) if eff > 0 else 0.0
        return cls(
            electrolyzer_kw=float(variant["electrolyzer_kw"]),
            electrolyzer_eff=float(variant["electrolyzer_eff"]),
            h2_storage_kwh=float(variant["h2_storage_kwh"]),
            h2_min_soc=float(variant["h2_min_soc"]),
            h2_soc_start=float(variant["soc_start"]),
            battery_kwh=float(variant["battery_kwh"]),
            battery_kw=float(variant["battery_kw"]),
            battery_eff_rt=float(variant["battery_eff_rt"]),
            battery_soc_start=float(variant["soc_start"]),
            h2_high_soc=float(variant.get("h2_high_soc", 1.0)),
            electrolyzer_base_kw=min(float(base_kw), float(variant["electrolyzer_kw"])),
            grid_limit_kw=float(variant.get("grid_limit_kw") or 0.0),
            battery_recharge_margin=float(variant.get("battery_recharge_margin") or 0.0),
        )


def _zeros() -> np.ndarray:
    return np.zeros(0)


@dataclass
class GEHDispatchResult:
    """Ergebnisse von run_geh_dispatch (Zeitreihen [kW] bzw. [kWh] + Jahreswerte)."""

    # Zeitreihen
    electrolyzer_kw: np.ndarray = field(default_factory=_zeros)
    compressor_kw: np.ndarray = field(default_factory=_zeros)
    h2_soc_kwh: np.ndarray = field(default_factory=_zeros)
    h2_delivered_kwh: np.ndarray = field(default_factory=_zeros)     # je Zeitschritt [kWh_H2]
    battery_charge_kw: np.ndarray = field(default_factory=_zeros)
    battery_discharge_kw: np.ndarray = field(default_factory=_zeros)
    battery_soc_kwh: np.ndarray = field(default_factory=_zeros)
    grid_import_kw: np.ndarray = field(default_factory=_zeros)
    grid_export_kw: np.ndarray = field(default_factory=_zeros)
    balance_after_kw: np.ndarray = field(default_factory=_zeros)
    geh_grid_kw: np.ndarray = field(default_factory=_zeros)         # Netzlast des Hubs (bilanziell)

    # Startwerte (für Bilanzprüfungen)
    h2_soc_start_kwh: float = 0.0
    battery_soc_start_kwh: float = 0.0

    # Jahreswerte
    electrolyzer_kwh: float = 0.0
    compressor_kwh: float = 0.0
    h2_production_kwh: float = 0.0
    h2_demand_kwh: float = 0.0
    h2_delivered_total_kwh: float = 0.0
    unmet_kwh: float = 0.0
    electrolyzer_full_load_hours: float = 0.0
    battery_charge_kwh: float = 0.0
    battery_discharge_kwh: float = 0.0
    battery_full_cycles: float = 0.0
    grid_import_kwh: float = 0.0
    grid_export_kwh: float = 0.0
    grid_max_import_kw: float = 0.0          # Park gesamt
    geh_grid_peak_kw: float = 0.0            # Netzspitze des Hubs
    geh_grid_limit_exceed_hours: float = 0.0
    geh_electrolyzer_base_kw: float = 0.0


def run_geh_dispatch(
    net_kw: np.ndarray,
    h2_demand_kwh: np.ndarray,
    p: GEHParams,
    dt_h: float = 0.25,
    geh_fixed_load_kw: np.ndarray | None = None,
    geh_pv_kw: np.ndarray | None = None,
) -> GEHDispatchResult:
    """
    Regelbasierte Betriebsführung des Green Energy Hubs je Zeitschritt.

    Reihenfolge je Zeitschritt:
      1. Elektrolyseur: unter Mindestfüllstand volle Leistung (Versorgungssicherung),
         bis zum oberen Füllstand Grundlast oder Überschuss, darüber nur Überschuss;
         begrenzt durch den freien Platz im H2-Speicher
      2. Elektrolyseur drosseln, wenn der Hub über seiner Netzgrenze liegt
         (nicht unter Mindestfüllstand; der Überschuss-Anteil bleibt)
      3. H2-Speicher: Produktion rein, Tankstellennachfrage raus
      4. Batterie: kappt Hub-Spitzen über der Grenze, lädt sonst Park-Überschuss
         (ohne den Hub über die Grenze zu heben) und in ruhigen Zeiten aus dem Netz
         nach; ohne Netzgrenze deckt sie stattdessen Park-Defizite
      5. Netz: verbleibender Überschuss → Einspeisung, Defizit → Bezug

    Args:
        net_kw:            Park-Bilanz vor Flexibilität [kW], positiv = Überschuss
                           (enthält Hub-Lasten und Hub-PV bereits)
        h2_demand_kwh:     H2-Nachfrage Tankstelle je Zeitschritt [kWh_H2]
        p:                 Anlagenparameter
        dt_h:              Zeitschrittgröße [h]
        geh_fixed_load_kw: feste Hub-Lasten (Ladecluster + Gebäude) [kW], None = 0
        geh_pv_kw:         PV am Hub [kW], None = 0
    """
    n = len(net_kw)
    fixed = np.zeros(n) if geh_fixed_load_kw is None else np.asarray(geh_fixed_load_kw, dtype=float)
    pv = np.zeros(n) if geh_pv_kw is None else np.asarray(geh_pv_kw, dtype=float)
    el_arr = np.zeros(n)
    comp_arr = np.zeros(n)
    soc_h2_arr = np.zeros(n)
    delivered_arr = np.zeros(n)
    ch_arr = np.zeros(n)
    dis_arr = np.zeros(n)
    soc_b_arr = np.zeros(n)
    import_arr = np.zeros(n)
    export_arr = np.zeros(n)
    balance_arr = np.zeros(n)
    hub_grid_arr = np.zeros(n)

    eta_c = np.sqrt(p.battery_eff_rt)
    eta_d = eta_c
    soc_h2 = p.h2_soc_start * p.h2_storage_kwh
    soc_b = p.battery_soc_start * p.battery_kwh
    h2_min_kwh = p.h2_min_soc * p.h2_storage_kwh
    h2_high_kwh = p.h2_high_soc * p.h2_storage_kwh
    el_active = p.electrolyzer_kw > 0.0 and p.electrolyzer_eff > 0.0
    battery_active = p.battery_kwh > 0.0 and p.battery_kw > 0.0
    limit = p.grid_limit_kw
    limit_active = limit > 0.0
    recharge_level = p.battery_recharge_margin * limit
    el_factor = 1.0 + p.compressor_factor * p.electrolyzer_eff   # Elektrolyseur + Kompressor je kW Elektrolyseur
    unmet = 0.0

    for t in range(n):
        demand_t = float(h2_demand_kwh[t])
        net_t = float(net_kw[t])
        hub_base = float(fixed[t]) - float(pv[t])          # Hub-Netzlast ohne Flexibilität
        surplus = max(net_t, 0.0)

        # 1) Elektrolyseur – Sollwert
        p_el_max = 0.0
        if el_active:
            free_h2 = p.h2_storage_kwh - soc_h2 + demand_t   # so viel H2 passt noch rein (inkl. Abgabe)
            p_el_max = min(p.electrolyzer_kw, max(free_h2, 0.0) / (p.electrolyzer_eff * dt_h))
        if soc_h2 < h2_min_kwh:
            p_el = p_el_max                                  # Versorgungssicherung
        elif soc_h2 < h2_high_kwh:
            p_el = min(p_el_max, max(p.electrolyzer_base_kw, surplus))
        else:
            p_el = min(p_el_max, surplus)                    # nur Überschuss

        # 2) Drosseln, wenn der Hub über der Grenze liegt (Überschuss-Anteil bleibt)
        hub_net = hub_base + p_el * el_factor
        if limit_active and hub_net > limit and soc_h2 >= h2_min_kwh:
            p_el = max(p_el - (hub_net - limit) / el_factor, min(surplus, p_el))
            hub_net = hub_base + p_el * el_factor
        p_comp = p.compressor_factor * p_el * p.electrolyzer_eff
        net2 = net_t - p_el - p_comp

        # 3) H2-Speicher
        prod = p_el * p.electrolyzer_eff * dt_h
        avail = soc_h2 + prod
        delivered = min(demand_t, avail)
        unmet += demand_t - delivered
        soc_h2 = min(avail - delivered, p.h2_storage_kwh)

        # 4) Batterie
        ch = 0.0
        dis = 0.0
        if battery_active:
            room_kw = (p.battery_kwh - soc_b) / (eta_c * dt_h)
            content_kw = soc_b * eta_d / dt_h
            if limit_active and hub_net > limit:
                dis = min(hub_net - limit, p.battery_kw, content_kw)          # Spitzenkappung (auch bei Park-Überschuss)
            elif net2 > 0.0:
                # Park-Überschuss laden; mit Netzgrenze nur so weit, dass der Hub unter der Grenze bleibt
                headroom = max(limit - hub_net, 0.0) if limit_active else net2
                ch = min(net2, p.battery_kw, room_kw, headroom)
            elif not limit_active:
                dis = min(-net2, p.battery_kw, content_kw)  # ohne Netzgrenze: Park-Defizit decken
            elif hub_net < recharge_level:
                ch = min(recharge_level - hub_net, p.battery_kw, room_kw)     # aus dem Netz nachladen
        ch = max(ch, 0.0)
        soc_b += (ch * eta_c - dis / eta_d) * dt_h
        soc_b = min(max(soc_b, 0.0), p.battery_kwh)          # Numerische Absicherung
        net3 = net2 - ch + dis

        # 5) Netz
        el_arr[t] = p_el
        comp_arr[t] = p_comp
        soc_h2_arr[t] = soc_h2
        delivered_arr[t] = delivered
        ch_arr[t] = ch
        dis_arr[t] = dis
        soc_b_arr[t] = soc_b
        export_arr[t] = max(net3, 0.0)
        import_arr[t] = max(-net3, 0.0)
        balance_arr[t] = net3
        hub_grid_arr[t] = hub_net + ch - dis

    r = GEHDispatchResult(
        electrolyzer_kw=el_arr,
        compressor_kw=comp_arr,
        h2_soc_kwh=soc_h2_arr,
        h2_delivered_kwh=delivered_arr,
        battery_charge_kw=ch_arr,
        battery_discharge_kw=dis_arr,
        battery_soc_kwh=soc_b_arr,
        grid_import_kw=import_arr,
        grid_export_kw=export_arr,
        balance_after_kw=balance_arr,
        geh_grid_kw=hub_grid_arr,
        h2_soc_start_kwh=p.h2_soc_start * p.h2_storage_kwh,
        battery_soc_start_kwh=p.battery_soc_start * p.battery_kwh,
    )
    r.electrolyzer_kwh = float(el_arr.sum() * dt_h)
    r.compressor_kwh = float(comp_arr.sum() * dt_h)
    r.h2_production_kwh = r.electrolyzer_kwh * p.electrolyzer_eff
    r.h2_demand_kwh = float(np.sum(h2_demand_kwh))
    r.h2_delivered_total_kwh = float(delivered_arr.sum())
    r.unmet_kwh = unmet
    r.electrolyzer_full_load_hours = r.electrolyzer_kwh / p.electrolyzer_kw if p.electrolyzer_kw > 0 else 0.0
    r.battery_charge_kwh = float(ch_arr.sum() * dt_h)
    r.battery_discharge_kwh = float(dis_arr.sum() * dt_h)
    r.battery_full_cycles = r.battery_discharge_kwh / p.battery_kwh if p.battery_kwh > 0 else 0.0
    r.grid_import_kwh = float(import_arr.sum() * dt_h)
    r.grid_export_kwh = float(export_arr.sum() * dt_h)
    r.grid_max_import_kw = float(import_arr.max()) if n else 0.0
    r.geh_grid_peak_kw = float(hub_grid_arr.max()) if n else 0.0
    r.geh_grid_limit_exceed_hours = float((hub_grid_arr > limit + 1e-6).sum() * dt_h) if limit_active else 0.0
    r.geh_electrolyzer_base_kw = p.electrolyzer_base_kw
    return r
