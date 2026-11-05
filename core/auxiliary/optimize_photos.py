"""
Fotos der Teilprojekte für das Web-Frontend aufbereiten.

Verkleinert die Originale (längste Kante max. MAX_EDGE_PX, kleinere Bilder werden
nicht hochskaliert), speichert sie als WebP (Qualität WEBP_QUALITY) nach
web_frontend/assets/photos/ und gibt die Dateigrößen aus. Die Originale bleiben
unverändert. Bildtexte und Bildnachweise stehen in web_frontend/assets/photos/photos.json.

Aufruf (aus dem Projektordner):
    python -m core.auxiliary.optimize_photos [Quellordner]
"""

import sys
from pathlib import Path

from PIL import Image, ImageOps

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_DIR = Path(r"C:\Users\moend\Downloads\Bilder")
TARGET_DIR = PROJECT_ROOT / "web_frontend" / "assets" / "photos"
MAX_EDGE_PX = 1600
WEBP_QUALITY = 80

# Originaldatei → Zieldatei (id in photos.json in Klammern)
PHOTOS = {
    "Solarautobahn_PV-Lärm-und-windschutzwand.jpeg": "solarautobahn_laermschutzwand.webp",  # solar, Foto 1
    "Solarautobahn_Böschung_PV.jpeg": "solarautobahn_boeschung.webp",                       # solar, Foto 2
    "Agri-PV-Anlage_Energielandschaft.png": "energielandschaft_agri_pv.webp",               # landscape
    "Green Energy Hub_Übersicht.jpeg": "green_energy_hub.webp",                             # hub
    "Jüchen-Süd_Überblick.png": "juechen_sued_rahmenplan.webp",                             # js
    "Elsbachtal_Übersicht.png": "elsbachtal.webp",                                          # industry
}


def optimize(source: Path, target: Path) -> tuple[tuple[int, int], tuple[int, int]]:
    with Image.open(source) as image:
        image = ImageOps.exif_transpose(image)            # Hochformat-Fotos richtig drehen
        original_size = image.size
        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
        image.thumbnail((MAX_EDGE_PX, MAX_EDGE_PX), Image.LANCZOS)   # verkleinert nur, nie größer
        image.save(target, "WEBP", quality=WEBP_QUALITY, method=6)
        return original_size, image.size


def main() -> None:
    source_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SOURCE_DIR
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    total = 0
    for source_name, target_name in PHOTOS.items():
        source = source_dir / source_name
        target = TARGET_DIR / target_name
        if not source.exists():
            print(f"[fehlt] {source}")
            continue
        (w0, h0), (w1, h1) = optimize(source, target)
        size = target.stat().st_size
        total += size
        print(f"{target_name}: {w0}×{h0} → {w1}×{h1} px, {source.stat().st_size / 1000:.0f} kB → {size / 1000:.0f} kB")
    print(f"Summe WebP: {total / 1000:.0f} kB")


if __name__ == "__main__":
    main()
