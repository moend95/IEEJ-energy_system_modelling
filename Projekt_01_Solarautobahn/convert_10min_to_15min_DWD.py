from __future__ import annotations

from pathlib import Path
import pandas as pd


def interpolate_csv_10min_to_15min(input_path: Path, output_path: Path) -> None:
    """
    Liest eine CSV mit 10-minütigen Wetterdaten ein und interpoliert sie
    auf ein 15-minütiges Raster.

    Erwartet:
    - eine Spalte 'date'
    - numerische Wetterspalten wie z. B. ghi, dhi, dni, temp_air, wind_speed ...

    Wichtig:
    - Die Zeitstempel werden als lokale naive Zeit interpretiert
      (also OHNE UTC-/Zeitzonen-Umrechnung).
    """

    df = pd.read_csv(input_path)

    if "date" not in df.columns:
        raise ValueError(f"Die CSV '{input_path.name}' muss eine Spalte 'date' enthalten.")

    # Datum einlesen OHNE UTC-/TZ-Umrechnung
    df["date"] = pd.to_datetime(df["date"], errors="raise")

    # Sortieren und Index setzen
    df = df.sort_values("date").set_index("date")

    # Nur numerische Spalten interpolieren
    numeric_columns = df.select_dtypes(include="number").columns
    if len(numeric_columns) == 0:
        raise ValueError(f"Keine numerischen Spalten für Interpolation in '{input_path.name}' gefunden.")

    # Auf 15 Minuten resamplen und linear interpolieren
    interpolated = df[numeric_columns].resample("15min").interpolate(method="linear")
    interpolated = interpolated.sort_index()

    # Zurück in DataFrame mit date-Spalte
    output = interpolated.reset_index()

    # Zielordner anlegen, falls nötig
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Speichern
    output.to_csv(output_path, index=False)

    print(f"Fertig: {output_path.name}")
    print(f"  Zeitschritte: {len(output)}")
    print(f"  Start: {output['date'].iloc[0]}")
    print(f"  Ende:  {output['date'].iloc[-1]}")
    print("-" * 60)


def main() -> None:
    # Dieses Skript liegt in:
    # Projekt_01_Solarautobahn/convert_10min_to_15min_DWD.py
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent

    input_dir = repo_root / "Projekt_00_GUI" / "functions" / "inputs" / "Wetterdaten_10min_DWD"
    output_dir = repo_root / "Projekt_00_GUI" / "functions" / "inputs"

    years = range(2018, 2025)  # 2018 bis einschließlich 2024

    print("Eingabeordner :", input_dir)
    print("Ausgabeordner :", output_dir)
    print("=" * 60)

    for year in years:
        input_file = input_dir / f"wetter_daten_{year}_10min.csv"
        output_file = output_dir / f"wetter_daten_{year}_15min.csv"

        if not input_file.exists():
            print(f"Übersprungen: Datei nicht gefunden -> {input_file.name}")
            print("-" * 60)
            continue

        try:
            interpolate_csv_10min_to_15min(input_file, output_file)
        except Exception as e:
            print(f"Fehler bei {input_file.name}: {e}")
            print("-" * 60)


if __name__ == "__main__":
    main()