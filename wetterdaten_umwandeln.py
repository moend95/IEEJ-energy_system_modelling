from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def interpolate_csv_10min_to_15min(input_path: Path, output_path: Path) -> None:
	df = pd.read_csv(input_path)

	if "date" not in df.columns:
		raise ValueError("Die CSV muss eine Spalte 'date' enthalten.")

	df["date"] = pd.to_datetime(df["date"], errors="raise", utc=True).dt.tz_convert("Europe/Berlin")
	df = df.sort_values("date").set_index("date")

	numeric_columns = df.select_dtypes(include="number").columns
	if len(numeric_columns) == 0:
		raise ValueError("Keine numerischen Spalten für Interpolation gefunden.")

	interpolated = df[numeric_columns].resample("15min").interpolate(method="linear")

	output = interpolated.reset_index()
	output.to_csv(output_path, index=False)


def build_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(
		description="Interpoliert Wetterdaten von 10-Minuten- auf 15-Minuten-Werte."
	)
	parser.add_argument(
		"-i",
		"--input",
		type=Path,
		default=Path("merge_teilprojekte_test/functions/inputs/wetter_daten.csv"),
		help="Pfad zur Eingabe-CSV.",
	)
	parser.add_argument(
		"-o",
		"--output",
		type=Path,
		default=Path("merge_teilprojekte_test/functions/inputs/wetter_daten_15min.csv"),
		help="Pfad zur Ausgabe-CSV.",
	)
	return parser


def main() -> None:
	parser = build_parser()
	args = parser.parse_args()

	args.output.parent.mkdir(parents=True, exist_ok=True)
	interpolate_csv_10min_to_15min(args.input, args.output)

	print(f"Fertig: {args.output}")


if __name__ == "__main__":
	main()
