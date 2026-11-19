"""
Schlanke Kopie der Website für GitHub Pages (oder jeden anderen statischen Webspace) bauen.

Kopiert aus web_frontend/ nur, was die Seite lädt: HTML/JS/CSS, Leaflet, Assets, die
verwendeten Geometrien sowie catalog.json und die flow_data.json-Dateien aus precomputed_v2/.
Zeitreihen (timeseries.csv.gz), Testdaten und die Vorschauseite bleiben draußen.

Aufruf (aus dem Projektordner):
    python -m core.auxiliary.build_pages              # nach deploy/
    python -m core.auxiliary.build_pages --output pfad

Der Zielordner wird geleert; ein darin liegendes .git (Worktree des Branches gh-pages) bleibt erhalten.
"""

import argparse
import json
import re
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = PROJECT_ROOT / "web_frontend"
DEFAULT_OUTPUT = PROJECT_ROOT / "deploy"
DATA_DIR_NAME = "precomputed_v2"

FILES = ["index.html", "app.js", "park_map.js", "lightbox.js", "style.css"]
DIRS = ["assets", "vendor"]
KEEP_IN_OUTPUT = {".git", ".gitignore"}


def clear_output(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for entry in output.iterdir():
        if entry.name in KEEP_IN_OUTPUT:
            continue
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()


def referenced_geometries() -> list[str]:
    """Geometrien, die app.js tatsächlich lädt (GEOJSON_PATHS)."""
    app_js = (WEB_DIR / "app.js").read_text(encoding="utf-8")
    return sorted(set(re.findall(r'"\./geometries/([^"]+\.geojson)"', app_js)))


def copy_scenarios(output: Path) -> int:
    src = WEB_DIR / DATA_DIR_NAME
    catalog = json.loads((src / "catalog.json").read_text(encoding="utf-8"))
    dest = output / DATA_DIR_NAME
    dest.mkdir(parents=True, exist_ok=True)
    missing = []
    for entry in catalog:
        rel = entry["flow_path"].removeprefix("./")
        source_file = WEB_DIR / rel
        if not source_file.exists():
            missing.append(rel)
            continue
        target = output / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_file, target)
    if missing:
        raise SystemExit(f"Katalog verweist auf {len(missing)} fehlende Dateien, z. B. {missing[:3]}")
    shutil.copy2(src / "catalog.json", dest / "catalog.json")
    return len(catalog)


def folder_size_mb(path: Path) -> float:
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file() and ".git" not in p.parts) / 1e6


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    output = parser.parse_args().output.resolve()

    clear_output(output)
    for name in FILES:
        shutil.copy2(WEB_DIR / name, output / name)
    for name in DIRS:
        shutil.copytree(WEB_DIR / name, output / name)
    geometries = referenced_geometries()
    (output / "geometries").mkdir()
    for name in geometries:
        shutil.copy2(WEB_DIR / "geometries" / name, output / "geometries" / name)
    scenarios = copy_scenarios(output)
    # GitHub Pages: Jekyll überspringen (sonst werden u. a. Ordner mit „_“ ignoriert)
    (output / ".nojekyll").write_text("", encoding="utf-8")

    print(f"{output}: {scenarios} Szenarien, {len(geometries)} Geometrien, {folder_size_mb(output):.1f} MB")


if __name__ == "__main__":
    main()
