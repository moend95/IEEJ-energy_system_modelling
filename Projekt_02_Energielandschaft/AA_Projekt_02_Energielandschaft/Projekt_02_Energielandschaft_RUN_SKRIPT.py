# Horizontale PV-Anlage (bifazial) „Aufgeständerte Anlage“
# User-Auswahl: „Horizontale PV Ausrichtung“
# User-Input: Traktor Breite und Länge (Fahrbreite zwischen PV-Reihen (Traktor Breite plus Sicherheitsabstand), Wenderadius für Traktor am Acker-Rand (Traktor Länge bestimmt Wenderadius))
# Festgelegte Annahmen: PV-Reihen von Osten nach Westen, Bifaziale Module, Tilt mit 30° Richtung Süden, Optional mit Tracking Funktion

# Vertikale PV-Anlage (bifazial) „Senkrechter Zaun“
# User-Auswahl: „Vertikale PV Ausrichtung“ 
# User-Input: Traktor Breite und Länge (Fahrbreite zwischen PV-Reihen (Traktor Breite plus Sicherheitsabstand), Wenderadius für Traktor am Acker-Rand (Traktor Länge bestimmt Wenderadius))
# Festgelegte Annahmen: PV-Reihen von Norden nach Süden (bessere Verteilung über Tag), Bifaziale Module 

# ------------------------------------------------------------

import json
from pathlib import Path

class UserInputCollector:
	"""
	Objektorientierter Collector für die Benutzerabfrage.
	
	Nutzung:
	  c = UserInputCollector()
	  cfg = c.collect()
	  c.save(cfg)
	"""

	def __init__(self, default_width: float = 3.0, default_length: float = 5.0, default_turn: float = 6.0):
		self.default_width = default_width
		self.default_length = default_length
		self.default_turn = default_turn

	def _input_float(self, prompt: str, default: float) -> tuple:
		"""Sichere Float-Eingabe, returns (value, used_default)."""
		while True:
			try:
				s = input(f"{prompt}: ").strip()
				if s == "":
					return float(default), True
				return float(s), False
			except ValueError:
				print("Bitte eine gültige Zahl eingeben (z. B. 3.5).")

	def collect(self) -> dict:
		print('\n--- Benutzerkonfiguration Agri-PV ---')
		print('Wähle den Anlagentyp:')
		print('  1) Horizontale PV-Anlage (Aufgeständerte Anlage, bifazial)')
		print('  2) Vertikale PV-Anlage (Senkrechter Zaun, bifazial)')

		while True:
			choice = input('Auswahl 1 oder 2 (Standard 1): ').strip() or '1'
			if choice in ('1', '2'):
				break
			if choice.lower() in ('h', 'horizontal', 'hor', 'horizontale'):
				choice = '1'
				break
			if choice.lower() in ('v', 'vertical', 'vertikal'):
				choice = '2'
				break
			print('Ungültige Eingabe — bitte 1 oder 2 eingeben.')

		pv_type = 'horizontal' if choice == '1' else 'vertical'

		print('\nTraktor Parameter (Meter):')
		tractor_width, tw_used_default = self._input_float(f'Traktor Breite (Standard {self.default_width} Meter)', self.default_width)
		tractor_length, tl_used_default = self._input_float(f'Traktor Länge (Standard {self.default_length} Meter)', self.default_length)
		tractor_turn_radius, tr_used_default = self._input_float(f'Traktor Wenderadius (Standard {self.default_turn} Meter)', self.default_turn)

		cfg = {
			'pv_type': pv_type,
			'tractor_width': tractor_width,
			'tractor_length': tractor_length,
			'tractor_turn_radius': tractor_turn_radius,
		}

		print('\nEingabe zusammengefasst:')
		print(f"  Anlagentyp       : {'Horizontal (Aufgeständert)' if pv_type=='horizontal' else 'Vertikal (Senkrechter Zaun)'}")

		def _fmt(val, used):
			return f"{val} m" if not used else "(Standard verwendet)"

		print(f"  Traktor Breite   : {_fmt(tractor_width, tw_used_default)}")
		print(f"  Traktor Länge    : {_fmt(tractor_length, tl_used_default)}")
		print(f"  Traktor Wenderadius: {_fmt(tractor_turn_radius, tr_used_default)}\n")

		return cfg

	def save(self, cfg: dict, out_dir: Path = None) -> Path:
		"""
		Leitet zusätzliche Werte ab und speichert die Konfiguration als JSON.

		Ableitungen:
		  - horizontal: row_direction='Osten nach Westen', tilt=30
		  - vertical  : row_direction='Norden nach Süden', tilt=None
		"""
		if cfg.get('pv_type') == 'horizontal':
			# Standardisierte Richtung für weitere Verarbeitung
			cfg['row_direction'] = 'E-W'
			cfg['row_direction_label'] = 'Osten nach Westen'
			cfg['tilt'] = 30
			# Horizontale Anlage: pro Reihe 4 Module à 1.3 m Breite
			cfg['pv_row_width_m'] = round(4 * 1.3, 3)
		else:
			cfg['row_direction'] = 'N-S'
			cfg['row_direction_label'] = 'Norden nach Süden'
			cfg['tilt'] = None
			# Vertikale Anlage: schmale Reihen (Zaun-Elemente), Breite 0.5 m
			cfg['pv_row_width_m'] = 0.5

		if out_dir is None:
			out_dir = Path(__file__).resolve().parent / 'outputs'
		out_dir.mkdir(exist_ok=True)
		out_file = out_dir / 'user_selection.json'
		with out_file.open('w', encoding='utf-8') as f:
			json.dump(cfg, f, ensure_ascii=False, indent=2)
		return out_file


def get_user_inputs() -> dict:
	"""
	Kompatibler Wrapper für den bisherigen Funktionsaufruf.

	Erzeugt intern einen Collector und gibt das resultierende Dict zurück.
	"""
	c = UserInputCollector()
	return c.collect()


if __name__ == '__main__':
	# Beispiel: OO-basierte interaktive Abfrage
	collector = UserInputCollector()
	config = collector.collect()
	out_file = collector.save(config)
	print(f"→ Auswahl gespeichert in: {out_file}")
	print('Konfiguration bereit')

