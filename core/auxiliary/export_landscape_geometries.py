"""
Lageplan-Geometrien der Energielandschaft für das Web-Frontend erzeugen.

Erzeugt einmalig die PV-Reihen für vertikal/Tracking × 50/100 % mit der festen
Landmaschinen-Auslegung (LANDSCAPE_TRACTOR_*) über core/module_energy_landscape.py
und schreibt sie nach web_frontend/geometries/landscape_<vertical|tracking>_<50|100>.geojson.
Koordinaten werden auf 6 Nachkommastellen gerundet (≈ 0,1 m), damit jede Datei < 1 MB bleibt.

Für Teilausbau (50 %) werden – nur für die Karte, die Simulation bleibt unverändert –
zusammenhängend von Westen so viele Reihen genommen, bis mindestens der Anteil an
der gesamten Reihenlänge erreicht ist (statt der ersten Hälfte nach Anzahl).

Aufruf (aus dem Projektordner):
    python -m core.auxiliary.export_landscape_geometries
"""

import json
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.module_energy_landscape import (  # noqa: E402
    LANDSCAPE_TRACTOR_LENGTH_M,
    LANDSCAPE_TRACTOR_TURN_RADIUS_M,
    LANDSCAPE_TRACTOR_WIDTH_M,
    main as build_landscape,
)

OUTPUT_DIR = PROJECT_ROOT / "web_frontend" / "geometries"
MAX_BYTES = 1_000_000
COORD_DIGITS = 6

# Dateiname → Ausrichtung im Energielandschafts-Modul
ORIENTATIONS = {"vertical": "vertical", "tracking": "horizontal_tracking"}
BUILD_STATES = [50, 100]


def round_coords(value):
    if isinstance(value, float):
        return round(value, COORD_DIGITS)
    if isinstance(value, list):
        return [round_coords(v) for v in value]
    return value


def _west_x(feature: dict) -> float:
    """Westlichste Länge einer Reihe (LineString oder MultiLineString)."""
    coords = feature["geometry"]["coordinates"]
    if feature["geometry"]["type"] == "MultiLineString":
        coords = [pt for line in coords for pt in line]
    return min(pt[0] for pt in coords)


def select_from_west(features: list[dict], share: float) -> tuple[list[dict], float]:
    """Reihen von Westen her, bis ≥ share der gesamten Reihenlänge erreicht ist; liefert Auswahl und Anteil."""
    total = sum(f["properties"].get("length_m", 0.0) for f in features)
    selected, length = [], 0.0
    for feature in sorted(features, key=_west_x):
        if total > 0 and length >= share * total:
            break
        selected.append(feature)
        length += feature["properties"].get("length_m", 0.0)
    return selected, (length / total if total > 0 else 0.0)


def export_one(name: str, orientation: str, build_state: int, tmp_dir: Path) -> Path:
    # Immer den Vollausbau erzeugen, Teilausbau wird anschließend für die Karte ausgewählt
    result = build_landscape(
        interactive=False,
        output_dir=str(tmp_dir),
        pv_ausrichtung=orientation,
        ausbau_status=100,
        tractor_width_m=LANDSCAPE_TRACTOR_WIDTH_M,
        tractor_length_m=LANDSCAPE_TRACTOR_LENGTH_M,
        tractor_turn_radius_m=LANDSCAPE_TRACTOR_TURN_RADIUS_M,
    )
    if not result.get("success"):
        raise RuntimeError(f"{name}_{build_state}: {result.get('error')}")

    data = json.loads(Path(result["metadata"]["output_file"]).read_text(encoding="utf-8"))
    data["features"], achieved = select_from_west(data.get("features", []), build_state / 100.0)
    for feature in data.get("features", []):
        geometry = feature.get("geometry") or {}
        geometry["coordinates"] = round_coords(geometry.get("coordinates"))

    target = OUTPUT_DIR / f"landscape_{name}_{build_state}.geojson"
    target.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    size = target.stat().st_size
    if size >= MAX_BYTES:
        raise RuntimeError(f"{target.name} ist {size} Bytes groß (Grenze {MAX_BYTES})")
    length = sum(f["properties"].get("length_m", 0.0) for f in data["features"])
    print(f"{target.name}: {len(data['features'])} Reihen, {length:.0f} m "
          f"({100 * achieved:.1f} % der Reihenlänge), {size / 1000:.0f} kB")
    return target


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for name, orientation in ORIENTATIONS.items():
            for build_state in BUILD_STATES:
                export_one(name, orientation, build_state, Path(tmp))


if __name__ == "__main__":
    main()
