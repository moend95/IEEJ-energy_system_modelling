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
from typing import Optional

# Import orchestrator components
from Projekt_02_Energielandschaft_FLAECHEN_BERECHNUNG import PVFieldProcessor
from Projekt_02_Energielandschaft_PVLIB import PVSimulator, get_default_simulator

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
			# Vertikale Montagehöhe (z.B. als Zaun) in Metern
			cfg['pv_row_height_m'] = 2.5

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


class Application:
	"""Main orchestration class for the Agri-PV workflow.

	Usage:
		app = Application()
		app.run()  # interactive
		# or programmatic:
		app.run(geojson_path='path.geojson', out_html='out.html', open_in_browser=False)
	"""

	def __init__(self, simulator: Optional[PVSimulator] = None):
		self.collector = UserInputCollector()
		self.simulator = simulator or get_default_simulator()

	def run(self, cfg: Optional[dict] = None, geojson_path: Optional[str] = None, out_html: Optional[str] = None, open_in_browser: bool = True):
		# collect inputs if cfg not provided programmatically
		if cfg is None:
			cfg = self.collector.collect()
			# persist initial config (adds derived defaults)
			self.collector.save(cfg)

		# interactive prompts for geojson and out_html if not provided
		# allow a sensible default geojson path when user presses ENTER
		default_geojson = cfg.get('default_geojson') or r'C:\Users\johan\TH_Koeln_Masterprojekt\IEEJ-energy_system_modelling\Projekt_02_Energielandschaft\AA_Projekt_02_Energielandschaft\Projekt_02_Energielandschaft_Flaeche_Agri_PV.geojson'
		if geojson_path is None:
			ans = input(f'Pfad zur GeoJSON-Datei (.geojson) eingeben (ENTER = Standard: {default_geojson}): ').strip()
			if not ans:
				geojson_path = default_geojson
			else:
				geojson_path = ans

		# verify existence
		if not Path(geojson_path).exists():
			print(f'GeoJSON-Datei nicht gefunden: {geojson_path} — Abbruch.')
			return

		if out_html is None:
			out_html = input('Name der Ausgabedatei (HTML) [Standard: agri_pv_plot.html]: ').strip() or 'agri_pv_plot.html'

		# if open_in_browser was not explicitly provided by caller (default True), allow interactive override
		if open_in_browser is True:
			open_answer = input('HTML-Datei direkt im Browser öffnen? (j/n) [j]: ').strip().lower()
			open_in_browser = not (open_answer in ('n', 'nein', 'no'))

		# run area processing
		processor = PVFieldProcessor(cfg)
		try:
			result = processor.run(geojson_path, output_html=out_html, open_in_browser=open_in_browser)
			out_path, total_area_m2, usable_ground_area_m2, pv_footprint_m2, pv_vertical_front_m2 = result
			print(f'Karte erfolgreich erzeugt und gespeichert: {out_path}')
			# persist the cfg after geometry processing
			self.collector.save(cfg)

			# run PV simulation using the configured simulator object
			try:
				sim_res = self.simulator.run(cfg)
				if sim_res is not None:
					cfg['pv_simulation'] = sim_res
					self.collector.save(cfg)
					print('PV-Simulationsergebnis in cfg gespeichert.')
				else:
					print('Keine Simulationsergebnisse (Simulation übersprungen).')
			except Exception as e:
				print('Fehler bei der PV-Simulation:', e)

			# Print summary
			print(f"Gesamtfläche Feld: {cfg.get('total_area_m2')} m² ({cfg.get('total_area_ha')} ha)")
			print(f"Fläche des Feldes abzüglich Grünstreifen: {cfg.get('usable_ground_area_m2')} m² ({cfg.get('usable_ground_area_ha')} ha)")
			print(f"Fläche abzüglich Grünstreifen und PV-Reihen: {cfg.get('usable_after_pv_m2')} m² ({cfg.get('usable_after_pv_ha')} ha)")
			if cfg.get('pv_type') == 'horizontal':
				print(f"Fläche für horizontale PV-Anlage (Reihenbreite {cfg.get('pv_row_width_m')} m): {cfg.get('pv_footprint_m2')} m² ({cfg.get('pv_footprint_ha')} ha)")
			else:
				print(f"Boden-Fußabdruck der PV-Reihen (Reihenbreite {cfg.get('pv_row_width_m')} m): {cfg.get('pv_footprint_m2')} m² ({cfg.get('pv_footprint_ha')} ha)")
				print(f"PV-Fläche (Länge der Reihen × Höhe {cfg.get('pv_row_height_m')} m): {cfg.get('pv_vertical_front_m2')} m² ({cfg.get('pv_vertical_front_ha')} ha)")
			print(f"Das entspricht {cfg.get('pv_coverage_of_usable_percent')} % der nutzbaren Bodenfläche")

		except Exception as exc:
			print('Fehler beim Erzeugen der Karte:', exc)


if __name__ == '__main__':
	app = Application()
	app.run()

