"""
Green Energy Hub - Struktur
------------------------------------
15-min Raster vorgesehen
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, Any
import pandas as pd


# ===== 0) Gemeinsame Zeitbasis ===============================================
def make_time_index(start: str, days: int) -> pd.DatetimeIndex:
    """
    Erzeugt einen 15-min Index mit 'days' Tagen Dauer.
    Noch keine Daten – nur das Raster.
    """
    periods = days * 24 * 4  # 4 * 15min = 1h
    return pd.date_range(start, periods=periods, freq="15min")


# ===== 1) Erzeuger-Klassen ===================================================
@dataclass
class PVSystem:
    """PV: nur Parameter + Zeitschnittstelle. Noch keine Physik/Daten."""
    capacity_kwp: float

    def attach_timeseries(self, index: pd.DatetimeIndex) -> None:
        """Hier später: PV-Leistungs-Zeitreihe erzeugen/zuweisen (synthetisch oder CSV)."""
        self.index = index
        self.series_kw = None  # TODO: füllen in Step 1/2
        # raise NotImplementedError("PV series not set yet")  # bewusst leer


@dataclass
class WindTurbine:
    """Wind: nur Parameter + Zeitschnittstelle."""
    capacity_kw: float

    def attach_timeseries(self, index: pd.DatetimeIndex) -> None:
        self.index = index
        self.series_kw = None  #


# ===== 2) Nachfrage / Last ===================================================
@dataclass
class H2Demand:
    """
    H2-Nachfrage: nur Container.
    Später: synthetisch ODER aus CSV; Einheit: kg pro 15min.
    """
    daily_total_kg: Optional[float] = None  # optionaler Parameter für später

    def attach_timeseries(self, index: pd.DatetimeIndex) -> None:
        self.index = index
        self.series_kg = None  #


# ===== 3) Speicher ===========================================================
@dataclass
class H2Storage:
    """
    H2-Speicher: nur Parameter (Kapazität etc.), noch keine Logik.
    Später: SOC, Lade/Entlade-Limits, Wirkungsgrade.
    """
    capacity_kg: float
    soc_init_kg: float = 0.0

    def reset(self) -> None:
        self.soc_kg = self.soc_init_kg

    # Platzhalter-API für Step 2:
    def charge(self, kg: float, dt_h: float) -> float:
        """Nimmt kg an, liefert später 'akzeptierte' Menge zurück."""
        # TODO: in Step 2 implementieren
        return 0.0

    def discharge(self, kg: float, dt_h: float) -> float:
        """Liefert bis zu kg aus, begrenzt durch SOC/Limits (später)."""
        # TODO: in Step 2 implementieren
        return 0.0


# ===== 4) Elektrolyseur (Adapter) ============================================
@dataclass
class Electrolyzer:
    """
    Elektrolyseur-Adapter:
    - Heute: nur Nameplate & Schnittstelle.
    - Später: a) einfaches η+LHV-Modell, b) Moritz-Modell einbinden.
    """
    nameplate_kw: float

    def h2_from_power(self, p_ac_kw: float, dt_min: float = 15.0) -> float:
        """
        Eingabe: elektrische Leistung (AC), Zeit [min]
        Ausgabe: H2-Masse [kg] – aktuell noch 0, wird in Step 1 implementiert.
        """
        return 0.0


# ===== 5) Orchestrator =======================================================
class GreenEnergyHub:
    """
    Koppelt PV, Wind, EL, Speicher, Nachfrage.
    Heute: nur „Drähte legen“ & Loop – ohne echte Rechnungen.
    """
    def __init__(
        self,
        pv: PVSystem,
        wind: WindTurbine,
        electrolyzer: Electrolyzer,
        storage: H2Storage,
        demand: H2Demand,
        grid_import_kw_limit: float = 0.0,  # später nutzbar
    ):
        self.pv = pv
        self.wind = wind
        self.electrolyzer = electrolyzer
        self.storage = storage
        self.demand = demand
        self.grid_import_kw_limit = grid_import_kw_limit

    def attach_timebase(self, index: pd.DatetimeIndex) -> None:
        """Gibt allen Komponenten die gemeinsame Zeitachse."""
        self.index = index
        self.pv.attach_timeseries(index)
        self.wind.attach_timeseries(index)
        self.demand.attach_timeseries(index)
        self.storage.reset()

    def simulate(self) -> pd.DataFrame:
        """
        Hauptschleife über alle Zeitschritte.
        Heute: baut nur ein leeres Ergebnis-DataFrame mit Spalten,
        damit du die Struktur siehst. Zahlen = 0/None.
        """
        if not hasattr(self, "index"):
            raise RuntimeError("Call attach_timebase(index) before simulate()")

        records = []
        dt_min = 15.0
        dt_h = dt_min / 60.0

        for t in self.index:
            # === Eingänge (heute None) ===
            pv_kw = None  # später: self.pv.series_kw.loc[t]
            wind_kw = None  # später: self.wind.series_kw.loc[t]
            demand_kg = None  # später: self.demand.series_kg.loc[t]

            # === Dispatch-Logik (später) ===
            p_res_kw = None
            p_el_in_kw = None
            h2_prod_kg = 0.0  # derzeit 0
            h2_direct_to_load_kg = 0.0
            h2_from_storage_kg = 0.0
            h2_to_storage_kg = 0.0
            h2_unmet_kg = 0.0
            h2_soc_kg = getattr(self.storage, "soc_kg", self.storage.soc_init_kg)

            # === Ergebniszeile ===
            records.append({
                "time": t,
                "pv_kw": pv_kw,
                "wind_kw": wind_kw,
                "p_el_in_kw": p_el_in_kw,
                "h2_prod_kg": h2_prod_kg,
                "h2_direct_to_load_kg": h2_direct_to_load_kg,
                "h2_from_storage_kg": h2_from_storage_kg,
                "h2_to_storage_kg": h2_to_storage_kg,
                "h2_unmet_kg": h2_unmet_kg,
                "h2_storage_soc_kg": h2_soc_kg,
                "h2_demand_kg": demand_kg,
            })

        df = pd.DataFrame.from_records(records).set_index("time")
        return df


# ===== 6) Minimaler „Main“-Block ============================================
if __name__ == "__main__":
    # 6.1 Zeitbasis & Komponenten „leer“ verdrahten
    index = make_time_index(start="2019-01-01 00:00", days=1)
    pv = PVSystem(capacity_kwp=20_000)
    wind = WindTurbine(capacity_kw=20_000)
    ely = Electrolyzer(nameplate_kw=17_200)
    store = H2Storage(capacity_kg=100_000, soc_init_kg=50_000)
    load = H2Demand()

    hub = GreenEnergyHub(pv, wind, ely, store, load, grid_import_kw_limit=0.0)
    hub.attach_timebase(index)

    # 6.2 Simulation (liefert nur Struktur, noch keine echten Zahlen)
    df = hub.simulate()
    print(df.head(8))
    print("\nHinweis: Das ist nur das Gerüst. Zahlen sind noch leer/0. "
          "In Step 1 füllen wir PV/Wind/Last & eine einfache EL-Umrechnung.")
