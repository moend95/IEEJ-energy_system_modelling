"""
Marker-Icons für den Lageplan verkleinern.

Die Cliparts in web_frontend/icons/ sind bis zu 1024 px groß (je ca. 1,4 MB); im
Lageplan werden sie nur mit ca. 28 px angezeigt. Dieses Skript schreibt kleine
Kopien (MARKER_PX, ausreichend für hochauflösende Displays) nach
web_frontend/assets/markers/. Die Originale bleiben unverändert.

Aufruf (aus dem Projektordner):
    python -m core.auxiliary.optimize_marker_icons
"""

from pathlib import Path

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIR = PROJECT_ROOT / "web_frontend" / "icons"
TARGET_DIR = PROJECT_ROOT / "web_frontend" / "assets" / "markers"
MARKER_PX = 64
ICONS = ["solar_highway", "energy_landscape", "green_energy_hub", "juechen_sued", "industrial_area"]


def main() -> None:
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    for name in ICONS:
        source = SOURCE_DIR / f"{name}.png"
        target = TARGET_DIR / f"{name}.png"
        with Image.open(source) as image:
            icon = image.convert("RGBA")
            icon.thumbnail((MARKER_PX, MARKER_PX), Image.LANCZOS)   # verkleinert nur, nie größer
            icon.save(target, optimize=True)
        print(f"{target.name}: {source.stat().st_size / 1000:.0f} kB → {target.stat().st_size / 1000:.1f} kB")


if __name__ == "__main__":
    main()
