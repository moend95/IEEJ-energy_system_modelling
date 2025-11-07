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
from Projekt_02_Energielandschaft import PVMapPlotter
from Projekt_02_Energielandschaft_PVLIB import PVSimulator, get_default_simulator

# Embedded GeoJSON for Agri-PV area (inlined so no external path required)
EMBEDDED_GEOJSON = '''{
	"type": "FeatureCollection",
	"features": [
		{
			"type": "Feature",
			"geometry": {
				"coordinates": [
					[
						[
							6.500258,
							51.050945
						],
						[
							6.500752,
							51.051134
						],
						[
							6.501245,
							51.051296
						],
						[
							6.502404,
							51.051781
						],
						[
							6.503048,
							51.052078
						],
						[
							6.518154,
							51.058876
						],
						[
							6.522102,
							51.056394
						],
						[
							6.523132,
							51.057797
						],
						[
							6.525192,
							51.057473
						],
						[
							6.525707,
							51.06481
						],
						[
							6.528969,
							51.069125
						],
						[
							6.530771,
							51.070095
						],
						[
							6.534548,
							51.070095
						],
						[
							6.535063,
							51.077969
						],
						[
							6.525021,
							51.080449
						],
						[
							6.518841,
							51.086057
						],
						[
							6.525879,
							51.089184
						],
						[
							6.531587,
							51.089858
						],
						[
							6.536586,
							51.092122
						],
						[
							6.53811,
							51.093092
						],
						[
							6.531179,
							51.098766
						],
						[
							6.513691,
							51.095114
						],
						[
							6.514378,
							51.089399
						],
						[
							6.497211,
							51.086596
						],
						[
							6.492062,
							51.094143
						],
						[
							6.482964,
							51.092634
						],
						[
							6.481719,
							51.092391
						],
						[
							6.479852,
							51.089184
						],
						[
							6.47747,
							51.087674
						],
						[
							6.47644,
							51.086367
						],
						[
							6.478801,
							51.086084
						],
						[
							6.479273,
							51.085073
						],
						[
							6.480002,
							51.083873
						],
						[
							6.481762,
							51.082013
						],
						[
							6.484294,
							51.078805
						],
						[
							6.486611,
							51.075704
						],
						[
							6.484551,
							51.075354
						],
						[
							6.486483,
							51.073493
						],
						[
							6.487255,
							51.071929
						],
						[
							6.490345,
							51.072549
						],
						[
							6.494358,
							51.067655
						],
						[
							6.491997,
							51.066805
						],
						[
							6.495495,
							51.06303
						],
						[
							6.497104,
							51.061263
						],
						[
							6.498671,
							51.059065
						],
						[
							6.500816,
							51.054614
						],
						[
							6.50116,
							51.053346
						],
						[
							6.501331,
							51.051768
						],
						[
							6.499926,
							51.051343
						],
						[
							6.499293,
							51.054371
						],
						[
							6.497898,
							51.057365
						],
						[
							6.497126,
							51.058498
						],
						[
							6.494658,
							51.057878
						],
						[
							6.490002,
							51.06338
						],
						[
							6.492577,
							51.064095
						],
						[
							6.490345,
							51.066347
						],
						[
							6.488028,
							51.065942
						],
						[
							6.48217,
							51.072307
						],
						[
							6.484551,
							51.073035
						],
						[
							6.480775,
							51.077106
						],
						[
							6.477835,
							51.080058
						],
						[
							6.47526,
							51.082647
						],
						[
							6.474144,
							51.086529
						],
						[
							6.474466,
							51.090478
						],
						[
							6.471806,
							51.092418
						],
						[
							6.45421,
							51.092041
						],
						[
							6.442752,
							51.09355
						],
						[
							6.444211,
							51.089992
						],
						[
							6.450477,
							51.090316
						],
						[
							6.454639,
							51.081717
						],
						[
							6.459832,
							51.049326
						],
						[
							6.46524,
							51.041097
						],
						[
							6.481912,
							51.037265
						],
						[
							6.483307,
							51.042905
						],
						[
							6.4991,
							51.050513
						],
						[
							6.499658,
							51.050756
						],
						[
							6.500258,
							51.050945
						]
					]
				],
				"type": "Polygon"
			},
			"properties": {
				"_umap_options": {
					"color": "DarkOrange",
					"weight": 9
				},
				"name": "Energielandschaft_Juechen_Agri_PV",
				"description": "Agri-PV Fläche"
			},
			"id": "AzODE"
		}
	]
}'''
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

		# If no geojson_path provided, write embedded GeoJSON to outputs and use that file.
		if geojson_path is None:
			out_dir = Path(__file__).resolve().parent / 'outputs'
			out_dir.mkdir(exist_ok=True)
			emb_path = out_dir / 'embedded_area.geojson'
			# write embedded content if file not present
			if not emb_path.exists():
				with emb_path.open('w', encoding='utf-8') as f:
					f.write(EMBEDDED_GEOJSON)
			geojson_path = str(emb_path)

		# default output html if not provided
		if out_html is None:
			out_html = 'agri_pv_plot.html'

		# run area processing and plotting using PVMapPlotter (produces map + res dict)
		plotter = PVMapPlotter(cfg)
		try:
			out_path, res = plotter.plot(geojson_path, out_html=out_html, open_in_browser=open_in_browser)
			print(f'Karte erfolgreich erzeugt und gespeichert: {out_path}')
			# merge computed results into cfg
			cfg['total_area_m2'] = res.get('total_area_m2')
			cfg['usable_ground_area_m2'] = res.get('usable_ground_area_m2')
			cfg['pv_footprint_m2'] = res.get('pv_footprint_m2')
			if 'pv_vertical_front_m2' in res:
				cfg['pv_vertical_front_m2'] = res.get('pv_vertical_front_m2')
			# derive hectare values and coverage
			if cfg.get('total_area_m2'):
				cfg['total_area_ha'] = round(float(cfg['total_area_m2']) / 10000.0, 4)
			if cfg.get('usable_ground_area_m2'):
				cfg['usable_ground_area_ha'] = round(float(cfg['usable_ground_area_m2']) / 10000.0, 4)
			if cfg.get('pv_footprint_m2'):
				cfg['pv_footprint_ha'] = round(float(cfg['pv_footprint_m2']) / 10000.0, 4)
			if cfg.get('usable_ground_area_m2') and cfg.get('pv_footprint_m2') is not None:
				cfg['usable_after_pv_m2'] = round(float(cfg['usable_ground_area_m2']) - float(cfg['pv_footprint_m2']), 3)
				cfg['usable_after_pv_ha'] = round(float(cfg['usable_after_pv_m2']) / 10000.0, 4)
			if cfg.get('usable_ground_area_m2') and cfg.get('pv_footprint_m2') is not None:
				cfg['pv_coverage_of_usable_percent'] = round(100.0 * (float(cfg['pv_footprint_m2']) / float(cfg['usable_ground_area_m2'])), 2)
			else:
				cfg['pv_coverage_of_usable_percent'] = 0.0
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

