"""
Green Energy Hub – Einzelne Ladevorgänge
========================================
Bildet Lkw-MCS und Pkw-HPC als einzelne Ladevorgänge ab, statt die Jahresenergie
glatt nach Tagesform zu verteilen. Gleichzeitige Vorgänge erzeugen so kurze, hohe
Spitzen bis zur Cluster-Grenze.

Ablauf (intern 1-Minuten-Auflösung, Ergebnis als 15-min-Mittel):
  1. Ankünfte als inhomogener Poisson-Prozess, Rate ∝ Tagesform × Tagesfaktor,
     skaliert auf die erwartete Zahl der Vorgänge (Jahresenergie / mittlere Energie)
  2. Jeder Vorgang zieht Energie und Wunschleistung (gleichverteilt)
  3. Alle Ladepunkte belegt → FIFO-Warteschlange (kein Vorgang geht verloren)
  4. Summe der Wunschleistungen über der Cluster-Grenze → alle laufenden Vorgänge
     werden in dieser Minute proportional gedrosselt
  5. Jahresenergie exakt treffen: die Energie je Vorgang wird nachskaliert und die
     Simulation wiederholt (die Leistungsgrenze bleibt dabei unberührt)

Das Ergebnis hängt nicht vom Szenario ab und wird im Prozess sowie als Datei unter
data/outputs/geh_sessions/ zwischengespeichert.

Einstiegsfunktion: simulate_charging_sessions()
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

MINUTES_PER_STEP: int = 15
SESSION_SEED: int = 42
ENERGY_TOLERANCE: float = 0.001        # 0,1 % Abweichung von der Jahresenergie
MAX_ENERGY_ITERATIONS: int = 6
CACHE_DIR: Path = Path(__file__).resolve().parents[1] / "data" / "outputs" / "geh_sessions"
CACHE_VERSION: int = 1                 # erhöhen, wenn sich das Modell ändert

# ---------------------------------------------------------------------------
# Cluster-Parameter (Basis und Erweiterung gleich)
# Ladepunkte, Leistung je Punkt und Cluster-Grenze aus der Studie,
# Energie- und Leistungsverteilungen je Vorgang: ANNAHME, nicht aus Studie
# ---------------------------------------------------------------------------
SESSION_CLUSTERS: dict[str, dict] = {
    "mcs": {
        "points": 4,                       # Studie
        "point_kw": 750.0,                 # Studie
        "limit_kw": 2_400.0,               # Studie
        "energy_kwh": (250.0, 550.0),      # ANNAHME, nicht aus Studie (Mittel 400 kWh)
        "power_kw": (600.0, 750.0),        # ANNAHME, nicht aus Studie
    },
    "hpc": {
        "points": 20,                      # Studie
        "point_kw": 150.0,                 # Studie
        "limit_kw": 2_400.0,               # Studie
        "energy_kwh": (20.0, 50.0),        # ANNAHME, nicht aus Studie (Mittel 35 kWh ≈ 208 Vorgänge/Tag lt. Studie)
        "power_kw": (80.0, 150.0),         # ANNAHME, nicht aus Studie
    },
}


@dataclass
class SessionSimulation:
    """Ergebnis von simulate_charging_sessions."""

    kw: np.ndarray                                     # 15-min-Mittel [kW], Länge = len(index)
    kw_1min: np.ndarray = field(repr=False, default_factory=lambda: np.zeros(0))
    sessions: int = 0                                  # Anzahl Ladevorgänge im Jahr
    mean_wait_min: float = 0.0                         # mittlere Wartezeit an der Warteschlange [min]
    max_concurrent: int = 0                            # max. gleichzeitig ladende Fahrzeuge
    peak_kw: float = 0.0                               # Spitzenleistung (15-min-Mittel) [kW]
    peak_1min_kw: float = 0.0                          # Spitzenleistung (1-min) [kW]
    energy_scale: float = 1.0                          # Faktor auf die Energie je Vorgang
    runtime_s: float = 0.0

    def stats(self) -> dict:
        return {
            "sessions": self.sessions,
            "mean_wait_min": self.mean_wait_min,
            "max_concurrent": self.max_concurrent,
            "peak_kw": self.peak_kw,
            "peak_1min_kw": self.peak_1min_kw,
            "energy_scale": self.energy_scale,
            "runtime_s": self.runtime_s,
        }


def _run_queue(
    arrival_minute: np.ndarray,
    energy_kwh: np.ndarray,
    power_kw: np.ndarray,
    points: int,
    limit_kw: float,
    n_minutes: int,
) -> tuple[np.ndarray, float, int]:
    """
    Minutenweise Belegung der Ladepunkte mit FIFO-Warteschlange und proportionaler Drosselung.
    Liefert die 1-min-Leistung [kW], die mittlere Wartezeit [min] und die max. Gleichzeitigkeit.
    """
    kw = np.zeros(n_minutes)
    queue: deque[int] = deque()
    remaining: list[float] = []        # Restenergie je laufendem Vorgang [kWh]
    desired: list[float] = []          # Wunschleistung je laufendem Vorgang [kW]
    wait_total = 0.0
    started = 0
    max_concurrent = 0
    next_arrival = 0
    n_sessions = len(arrival_minute)

    for minute in range(n_minutes):
        while next_arrival < n_sessions and arrival_minute[next_arrival] == minute:
            queue.append(next_arrival)
            next_arrival += 1
        while queue and len(remaining) < points:
            s = queue.popleft()
            remaining.append(float(energy_kwh[s]))
            desired.append(float(power_kw[s]))
            wait_total += minute - int(arrival_minute[s])
            started += 1
        if not remaining:
            continue
        if len(remaining) > max_concurrent:
            max_concurrent = len(remaining)

        total = sum(desired)
        factor = limit_kw / total if total > limit_kw else 1.0
        delivered_kwh = 0.0
        keep_remaining: list[float] = []
        keep_desired: list[float] = []
        for rest, p in zip(remaining, desired):
            step = min(rest, p * factor / 60.0)
            delivered_kwh += step
            rest -= step
            if rest > 1e-9:
                keep_remaining.append(rest)
                keep_desired.append(p)
        kw[minute] = delivered_kwh * 60.0
        remaining, desired = keep_remaining, keep_desired

    mean_wait = wait_total / started if started else 0.0
    return kw, mean_wait, max_concurrent


def _cache_key(cluster: dict, rate_per_step: np.ndarray, annual_kwh: float, seed: int) -> str:
    h = hashlib.sha256()
    h.update(json.dumps({"v": CACHE_VERSION, "cluster": cluster, "annual_kwh": round(annual_kwh, 3), "seed": seed},
                        sort_keys=True).encode())
    h.update(np.round(rate_per_step, 9).tobytes())
    return h.hexdigest()[:20]


_MEMORY_CACHE: dict[str, SessionSimulation] = {}


def simulate_charging_sessions(
    index: pd.DatetimeIndex,
    cluster: dict,
    shape_per_step: np.ndarray,
    annual_kwh: float,
    seed: int = SESSION_SEED,
    cache_dir: Path | None = CACHE_DIR,
) -> SessionSimulation:
    """
    Simuliert die Ladevorgänge eines Clusters für den Zeitindex.

    Args:
        index:          Zeitindex (15 min)
        cluster:        Eintrag aus SESSION_CLUSTERS (points, point_kw, limit_kw, energy_kwh, power_kw)
        shape_per_step: relative Ankunftsrate je 15-min-Schritt (Tagesform × Tagesfaktor, ≥ 0)
        annual_kwh:     Jahresenergie des Clusters [kWh]
        seed:           Startwert des Zufallsgenerators (fest, damit alle Szenarien gleich sind)
        cache_dir:      Ordner für den Datei-Zwischenspeicher, None = nur im Prozess

    Returns:
        SessionSimulation mit 15-min-Leistung [kW] und Statistik
    """
    n_steps = len(index)
    shape = np.clip(np.asarray(shape_per_step, dtype=float), 0.0, None)
    if annual_kwh <= 0.0 or n_steps == 0 or shape.sum() <= 0.0:
        return SessionSimulation(kw=np.zeros(n_steps), kw_1min=np.zeros(n_steps * MINUTES_PER_STEP))

    key = _cache_key(cluster, shape, annual_kwh, seed)
    if key in _MEMORY_CACHE:
        return _MEMORY_CACHE[key]
    cache_file = cache_dir / f"sessions_{key}.npz" if cache_dir is not None else None
    if cache_file is not None and cache_file.exists():
        data = np.load(cache_file)
        result = SessionSimulation(kw=data["kw"], kw_1min=data["kw_1min"], **json.loads(str(data["stats"])))
        _MEMORY_CACHE[key] = result
        return result

    t0 = time.perf_counter()
    rng = np.random.default_rng(seed)
    n_minutes = n_steps * MINUTES_PER_STEP
    e_lo, e_hi = cluster["energy_kwh"]
    p_lo, p_hi = cluster["power_kw"]

    # 1) Ankünfte: erwartete Anzahl = Jahresenergie / mittlere Energie je Vorgang
    expected_sessions = annual_kwh / ((e_lo + e_hi) / 2.0)
    rate_per_minute = np.repeat(shape / shape.sum() * expected_sessions / MINUTES_PER_STEP, MINUTES_PER_STEP)
    counts = rng.poisson(rate_per_minute)
    arrival_minute = np.repeat(np.arange(n_minutes), counts)

    # 2) Energie und Wunschleistung je Vorgang
    base_energy = rng.uniform(e_lo, e_hi, len(arrival_minute))
    power = np.minimum(rng.uniform(p_lo, p_hi, len(arrival_minute)), cluster["point_kw"])

    # 3)–5) Belegung simulieren, Energie je Vorgang nachskalieren, bis die Jahresenergie passt
    scale = 1.0
    for _ in range(MAX_ENERGY_ITERATIONS):
        kw_1min, mean_wait, max_concurrent = _run_queue(
            arrival_minute, base_energy * scale, power, int(cluster["points"]), float(cluster["limit_kw"]), n_minutes
        )
        delivered = kw_1min.sum() / 60.0
        if delivered <= 0.0 or abs(delivered - annual_kwh) <= ENERGY_TOLERANCE * annual_kwh:
            break
        scale *= annual_kwh / delivered

    kw = kw_1min.reshape(n_steps, MINUTES_PER_STEP).mean(axis=1)
    result = SessionSimulation(
        kw=kw,
        kw_1min=kw_1min,
        sessions=int(len(arrival_minute)),
        mean_wait_min=float(mean_wait),
        max_concurrent=int(max_concurrent),
        peak_kw=float(kw.max()),
        peak_1min_kw=float(kw_1min.max()),
        energy_scale=float(scale),
        runtime_s=time.perf_counter() - t0,
    )
    _MEMORY_CACHE[key] = result
    if cache_file is not None:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(cache_file, kw=result.kw, kw_1min=result.kw_1min, stats=json.dumps(result.stats()))
    return result
