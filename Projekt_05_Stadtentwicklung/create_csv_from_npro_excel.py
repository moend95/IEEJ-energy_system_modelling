"""Erstellt eine 15-Minuten-CSV aus nPro-Strombezugsdaten."""

from pathlib import Path

import pandas as pd


EXCEL_FILE = "nPro_Lastprofil_Stadtentwicklung.xlsx"
SHEET_NAME = "Strombezug_Stadtentwicklung"
OUTPUT_FILE = "Strombezug_Stadtentwicklung_15min.csv"
TIMESTAMP_COL = "Timestamp"
VALUE_COL = "Strombezug (kW)"


def main() -> None:
	script_dir = Path(__file__).resolve().parent
	excel_path = script_dir / EXCEL_FILE
	output_path = script_dir / OUTPUT_FILE

	df = pd.read_excel(excel_path, sheet_name=SHEET_NAME)
	df = df[[TIMESTAMP_COL, VALUE_COL]].dropna(subset=[TIMESTAMP_COL, VALUE_COL]).copy()

	# nPro liefert Tages-/Uhrzeit ohne Jahr, daher wird ein Platzhalterjahr genutzt.
	parsed_ts = pd.to_datetime(df[TIMESTAMP_COL], format="%d.%m. %H:%M", errors="coerce")
	df = df.loc[parsed_ts.notna()].copy()
	df[TIMESTAMP_COL] = parsed_ts[parsed_ts.notna()]

	rows = []
	for _, row in df.iterrows():
		base_ts = row[TIMESTAMP_COL]
		value = row[VALUE_COL]
		for minute in (0, 15, 30, 45):
			rows.append({TIMESTAMP_COL: base_ts + pd.Timedelta(minutes=minute), VALUE_COL: value})

	result = pd.DataFrame(rows)
	result[TIMESTAMP_COL] = result[TIMESTAMP_COL].dt.strftime("%d.%m. %H:%M")
	result.to_csv(output_path, index=False, sep=",")

	print(f"CSV erstellt: {output_path}")
	print(f"Eingangszeilen: {len(df)} | 15-Minuten-Zeilen: {len(result)}")


if __name__ == "__main__":
	main()

