# Projekt 02 - Energielandschaft 
# Input: Traktor Parameter (Länge, Breite, Wenderadius), Fläche (GeoJSON-Datei), Typ PV-Anlage
# Output: Max. mögliche PV-Fläche

import json
from pathlib import Path
from typing import Optional, Tuple
import os
import geopandas as gpd
import numpy as np
from shapely.ops import unary_union
from shapely.geometry import LineString

# Embedded GeoJSON (fallback default area) so this script is fully standalone
EMBEDDED_GEOJSON = '''{
	"type": "FeatureCollection",
	"features": [
		{
			"type": "Feature",
			"geometry": {
				"type": "Polygon",
				"coordinates": [
					[
						[6.500258,51.050945],[6.500752,51.051134],[6.501245,51.051296],[6.502404,51.051781],[6.503048,51.052078],[6.518154,51.058876],[6.522102,51.056394],[6.523132,51.057797],[6.525192,51.057473],[6.525707,51.06481],[6.528969,51.069125],[6.530771,51.070095],[6.534548,51.070095],[6.535063,51.077969],[6.525021,51.080449],[6.518841,51.086057],[6.525879,51.089184],[6.531587,51.089858],[6.536586,51.092122],[6.53811,51.093092],[6.531179,51.098766],[6.513691,51.095114],[6.514378,51.089399],[6.497211,51.086596],[6.492062,51.094143],[6.482964,51.092634],[6.481719,51.092391],[6.479852,51.089184],[6.47747,51.087674],[6.47644,51.086367],[6.478801,51.086084],[6.479273,51.085073],[6.480002,51.083873],[6.481762,51.082013],[6.484294,51.078805],[6.486611,51.075704],[6.484551,51.075354],[6.486483,51.073493],[6.487255,51.071929],[6.490345,51.072549],[6.494358,51.067655],[6.491997,51.066805],[6.495495,51.06303],[6.497104,51.061263],[6.498671,51.059065],[6.500816,51.054614],[6.50116,51.053346],[6.501331,51.051768],[6.499926,51.051343],[6.499293,51.054371],[6.497898,51.057365],[6.497126,51.058498],[6.494658,51.057878],[6.490002,51.06338],[6.492577,51.064095],[6.490345,51.066347],[6.488028,51.065942],[6.48217,51.072307],[6.484551,51.073035],[6.480775,51.077106],[6.477835,51.080058],[6.47526,51.082647],[6.474144,51.086529],[6.474466,51.090478],[6.471806,51.092418],[6.45421,51.092041],[6.442752,51.09355],[6.444211,51.089992],[6.450477,51.090316],[6.454639,51.081717],[6.459832,51.049326],[6.46524,51.041097],[6.481912,51.037265],[6.483307,51.042905],[6.4991,51.050513],[6.499658,51.050756],[6.500258,51.050945]
					]
				]
			},
			"properties": {"name": "Energielandschaft_Juechen_Agri_PV"}
		}
	]
}'''


class PVTypeSelector:
	"""
	Klasse zur Abfrage des PV-Anlagentyps (horizontal oder vertical).

	Methoden:
	- collect() -> str : Gibt 'horizontal' oder 'vertical' zurück.
	"""

	def __init__(self, default: str = 'horizontal'):
		self.default = default

	def collect(self) -> str:
		print('\n--- Auswahl PV-Anlagentyp ---')
		print('  1) Horizontale PV-Anlage (Aufgeständert, bifazial)')
		print('  2) Vertikale PV-Anlage (Senkrecht, bifazial)')
		while True:
			val = input(f'Auswahl 1 oder 2 (Standard {"1" if self.default=="horizontal" else "2"}): ').strip()
			if val == '':
				return self.default
			if val in ('1', '2'):
				return 'horizontal' if val == '1' else 'vertical'
			if val.lower() in ('h', 'horizontal', 'horizontale'):
				return 'horizontal'
			if val.lower() in ('v', 'vertical', 'vertikal'):
				return 'vertical'
			print('Ungültige Eingabe — bitte 1 oder 2 eingeben.')


class TractorParameters:
	"""
	Klasse zur Abfrage der Traktor-Parameter mit sicheren Float-Eingaben.

	collect() -> dict mit keys: tractor_width, tractor_length, tractor_turn_radius
	"""

	def __init__(self, default_width: float = 3.0, default_length: float = 5.0, default_turn: float = 6.0):
		self.default_width = default_width
		self.default_length = default_length
		self.default_turn = default_turn

	def _input_float(self, prompt: str, default: float) -> Tuple[float, bool]:
		while True:
			try:
				s = input(f"{prompt} (ENTER = Standard {default}): ").strip()
				if s == "":
					return float(default), True
				return float(s), False
			except ValueError:
				print('Bitte eine gültige Zahl eingeben (z. B. 3.5).')

	def collect(self) -> dict:
		print('\n--- Traktor-Parameter ---')
		w, w_default = self._input_float('Traktor Breite in Meter', self.default_width)
		l, l_default = self._input_float('Traktor Länge in Meter', self.default_length)
		r, r_default = self._input_float('Traktor Wenderadius in Meter', self.default_turn)
		return {
			'tractor_width': float(w),
			'tractor_length': float(l),
			'tractor_turn_radius': float(r),
		}


class UserInputCollector:
	"""
	Orchestriert die Benutzereingabe für PV-Typ und Traktorparameter und speichert die Konfiguration.

	Methoden:
	- collect() -> dict : sammelt Eingaben und fügt abgeleitete Defaults hinzu
	- save(cfg, out_dir) -> Path : speichert cfg als JSON in outputs/user_selection.json
	"""

	def __init__(self, defaults: Optional[dict] = None):
		self.defaults = defaults or {}
		self.pv_selector = PVTypeSelector(default=self.defaults.get('pv_type', 'horizontal'))
		self.tractor = TractorParameters(
			default_width=self.defaults.get('tractor_width', 3.0),
			default_length=self.defaults.get('tractor_length', 5.0),
			default_turn=self.defaults.get('tractor_turn_radius', 6.0),
		)

	def collect(self) -> dict:
		cfg = {}
		cfg['pv_type'] = self.pv_selector.collect()
		tractor_vals = self.tractor.collect()
		cfg.update(tractor_vals)

		# Ableitungen ähnlich wie in RUN_SKRIPT
		if cfg.get('pv_type') == 'horizontal':
			cfg['row_direction'] = 'E-W'
			cfg['row_direction_label'] = 'Osten nach Westen'
			cfg['tilt'] = 30
			cfg['pv_row_width_m'] = round(4 * 1.3, 3)
		else:
			cfg['row_direction'] = 'N-S'
			cfg['row_direction_label'] = 'Norden nach Süden'
			cfg['tilt'] = None
			cfg['pv_row_width_m'] = 0.5
			cfg['pv_row_height_m'] = 2.5

		# Default packing/bifacial params (überschreibbar)
		cfg.setdefault('albedo', 0.2)
		cfg.setdefault('bifaciality', 0.85)

		return cfg

	def save(self, cfg: dict, out_dir: Optional[Path] = None) -> Path:
		if out_dir is None:
			out_dir = Path(__file__).resolve().parent / 'outputs'
		out_dir.mkdir(exist_ok=True)
		out_file = out_dir / 'user_selection.json'
		with out_file.open('w', encoding='utf-8') as f:
			json.dump(cfg, f, ensure_ascii=False, indent=2)
		return out_file


def get_user_inputs() -> dict:
	"""Kompatibler Wrapper; erzeugt einen Collector, sammelt Eingaben und gibt das cfg zurück."""
	c = UserInputCollector()
	return c.collect()


class GeoJSONSelector:
	"""
	Interaktive Auswahl einer GeoJSON-Datei.

	Usage:
		selector = GeoJSONSelector(default_path='path/to/default.geojson')
		geojson_path = selector.collect()

	Die Methode `collect()` prüft, ob die Datei existiert und fordert den Nutzer erneut
	auf, falls nicht. Wenn ein Default gesetzt ist und ENTER gedrückt wird, wird der
	Default verwendet (nur, falls vorhanden).
	"""

	def __init__(self, default_path: Optional[str] = None):
		self.default_path = Path(default_path) if default_path else None

	def collect(self) -> str:
		print('\n--- GeoJSON-Auswahl ---')
		if self.default_path:
			prompt = f'Pfad zur GeoJSON-Datei (.geojson) eingeben (ENTER = Standard: {self.default_path}): '
		else:
			prompt = 'Pfad zur GeoJSON-Datei (.geojson) eingeben: '

		while True:
			s = input(prompt).strip()
			if s == '':
				if self.default_path and self.default_path.exists():
					return str(self.default_path)
				if self.default_path and not self.default_path.exists():
					print(f'Standard-Datei nicht gefunden: {self.default_path}')
					# continue loop to let user provide another path
					continue
				print('Kein Standardpfad gesetzt. Bitte Pfad eingeben.')
				continue

			p = Path(s)
			if p.exists():
				return str(p)
			print(f'GeoJSON-Datei nicht gefunden: {p}. Bitte erneut eingeben oder STRG-C zum Abbrechen.')


class GeoAreaCalculator:
	"""Berechnet Gesamtfläche einer GeoJSON und (für horizontale PV) maximale PV-Fläche.

	Arbeitsweise (horizontal):
	- Bestimme Gesamtfläche durch Projektion in UTM.
	- Leite notwendige Randfläche für Wenden ab: breite_gruenstreifen = 2*wenderadius + traktor_laenge + sicherheitszuschlag
	- Leite Fahrspurbreite ab: breite_fahrspur = traktor_breite + 2*sicherheitszuschlag
	- PV-Reihenbreite standardmäßig 9.2 m (vier Module à 2.3 m)
	- Erzeuge innerhalb der gefluteten inneren Fläche Linien in Schrittweite = pv_reihenbreite + breite_fahrspur; summiere Schnittlängen als total_row_length
	- PV-Fläche = total_row_length * pv_row_width
	"""

	def __init__(self, geojson_path: str):
		self.geojson_path = Path(geojson_path)
		self.poly_utm = None
		self.utm_epsg = None
		self.total_area_m2 = 0.0
		self.inner = None
		self.rows_gdf = None
		self.total_row_length_m = 0.0
		self.pv_footprint_m2 = 0.0

	def _choose_utm_crs_from_lonlat(self, lon: float, lat: float) -> int:
		zone = int((lon + 180) / 6) + 1
		hemisphere = 'north' if lat >= 0 else 'south'
		if hemisphere == 'north':
			epsg = 32600 + zone
		else:
			epsg = 32700 + zone
		return epsg

	def load_and_project(self):
		if not self.geojson_path.exists():
			raise FileNotFoundError(f'GeoJSON nicht gefunden: {self.geojson_path}')
		gdf = gpd.read_file(str(self.geojson_path))
		if gdf.empty:
			raise ValueError('GeoJSON enthält keine Geometrien')
		gdf = gdf.to_crs(epsg=4326)
		geom = unary_union(gdf.geometry)
		if geom.geom_type == 'GeometryCollection':
			polys = [g for g in geom.geoms if g.geom_type in ('Polygon', 'MultiPolygon')]
			geom = unary_union(polys)
		centroid = geom.centroid
		lon, lat = centroid.x, centroid.y
		utm_epsg = self._choose_utm_crs_from_lonlat(lon, lat)
		self.utm_epsg = utm_epsg
		gdf_utm = gpd.GeoDataFrame(geometry=[geom], crs='EPSG:4326').to_crs(epsg=utm_epsg)
		self.poly_utm = gdf_utm.geometry.iloc[0]
		self.total_area_m2 = float(self.poly_utm.area)
		return self.total_area_m2

	def compute_horizontal_pv(self, tractor_width: float, tractor_length: float, tractor_turn_radius: float,
							  pv_row_width_m: float = 9.2, safety_margin: float = 1.0):
		"""Berechnet maximale PV-Fläche für horizontale Aufstellung.

		Returns a dict with keys: green_strip_width_m, effective_row_spacing_m, usable_ground_area_m2,
		total_row_length_m, pv_footprint_m2
		"""
		if self.poly_utm is None:
			self.load_and_project()

		# Ableitungen
		breite_gruenstreifen = 2.0 * float(tractor_turn_radius) + float(tractor_length) + float(safety_margin)
		breite_fahrspur = float(tractor_width) + 2.0 * float(safety_margin)
		effective_spacing = float(pv_row_width_m) + breite_fahrspur

		# inner area after removing green strip at edges
		inner = self.poly_utm.buffer(-breite_gruenstreifen)
		if inner.is_empty:
			usable_area = 0.0
			self.inner = None
		else:
			self.inner = inner
			usable_area = float(inner.area)

		# generate rows as in FLAECHEN_BERECHNUNG
		total_length = 0.0
		rows = []
		if self.inner is not None:
			minx, miny, maxx, maxy = self.inner.bounds
			step = effective_spacing
			start = miny - step
			stop = maxy + step
			ys = np.arange(start, stop + step, step)
			for y in ys:
				line = LineString([(minx - 10 * step, y), (maxx + 10 * step, y)])
				seg = line.intersection(self.inner)
				if not seg.is_empty:
					if seg.geom_type == 'LineString' and seg.length > 0:
						rows.append(seg)
						total_length += seg.length
					elif seg.geom_type == 'MultiLineString':
						for part in seg.geoms:
							if part.length > 0:
								rows.append(part)
								total_length += part.length

		self.rows_gdf = rows
		self.total_row_length_m = float(total_length)
		self.pv_footprint_m2 = float(self.total_row_length_m) * float(pv_row_width_m)

		return {
			'total_area_m2': round(self.total_area_m2, 3),
			'green_strip_width_m': round(breite_gruenstreifen, 3),
			'fahrspur_breite_m': round(breite_fahrspur, 3),
			'effective_row_spacing_m': round(effective_spacing, 3),
			'usable_ground_area_m2': round(usable_area, 3),
			'total_row_length_m': round(self.total_row_length_m, 3),
			'pv_footprint_m2': round(self.pv_footprint_m2, 3),
		}


class GeoAreaVerticalCalculator(GeoAreaCalculator):
	"""Spezialisierung für vertikale PV-Anlagen.

	Verwendet die Logik von GeoAreaCalculator und berechnet zusätzlich die
	vertikale Frontfläche (Länge der Reihen × Höhe der Module/Reihen).
	"""

	def compute_vertical_pv(self, tractor_width: float, tractor_length: float, tractor_turn_radius: float,
							pv_row_width_m: float = 0.1, pv_row_height_m: float = 2.5, safety_margin: float = 1.0):
		"""Berechnet Werte analog zur horizontalen Version, aber erzeugt Reihen
		parallel zur Y-Achse (vertikale Elemente entlang der Reihen).

		Returns dict with total_area_m2, green_strip_width_m, fahrspur_breite_m,
		effective_row_spacing_m, usable_ground_area_m2, total_row_length_m,
		pv_footprint_m2, pv_vertical_front_m2
		"""
		if self.poly_utm is None:
			self.load_and_project()

		breite_gruenstreifen = 2.0 * float(tractor_turn_radius) + float(tractor_length) + float(safety_margin)
		breite_fahrspur = float(tractor_width) + 2.0 * float(safety_margin)
		effective_spacing = float(pv_row_width_m) + breite_fahrspur

		inner = self.poly_utm.buffer(-breite_gruenstreifen)
		if inner.is_empty:
			usable_area = 0.0
			self.inner = None
		else:
			self.inner = inner
			usable_area = float(inner.area)

		total_length = 0.0
		rows = []
		if self.inner is not None:
			minx, miny, maxx, maxy = self.inner.bounds
			step = effective_spacing
			start = minx - step
			stop = maxx + step
			xs = np.arange(start, stop + step, step)
			for x in xs:
				line = LineString([(x, miny - 10 * step), (x, maxy + 10 * step)])
				seg = line.intersection(self.inner)
				if not seg.is_empty:
					if seg.geom_type == 'LineString' and seg.length > 0:
						rows.append(seg)
						total_length += seg.length
					elif seg.geom_type == 'MultiLineString':
						for part in seg.geoms:
							if part.length > 0:
								rows.append(part)
								total_length += part.length

		self.rows_gdf = rows
		self.total_row_length_m = float(total_length)
		# Boden-Fußabdruck (sehr schmal bei vertikalen Montageelementen)
		self.pv_footprint_m2 = float(self.total_row_length_m) * float(pv_row_width_m)
		# Vertikale Frontfläche (Länge der Reihen × Höhe)
		self.pv_vertical_front_m2 = float(self.total_row_length_m) * float(pv_row_height_m)

		return {
			'total_area_m2': round(self.total_area_m2, 3),
			'green_strip_width_m': round(breite_gruenstreifen, 3),
			'fahrspur_breite_m': round(breite_fahrspur, 3),
			'effective_row_spacing_m': round(effective_spacing, 3),
			'usable_ground_area_m2': round(usable_area, 3),
			'total_row_length_m': round(self.total_row_length_m, 3),
			'pv_footprint_m2': round(self.pv_footprint_m2, 3),
			'pv_vertical_front_m2': round(self.pv_vertical_front_m2, 3),
		}


class PVMapPlotter:
	"""Erzeugt eine HTML-Karte mit Feldgrenze, nutzbarer Fläche und eingezeichneten PV-Reihen.

	Die Darstellung richtet sich nach den Traktorparametern und dem PV-Typ
	(horizontal / vertical). Die Klasse verwendet die GeoAreaCalculator-Klassen
	um Reihen und Flächen zu berechnen und zeichnet diese mit folium.
	"""

	def __init__(self, cfg: dict):
		self.cfg = cfg

	def plot(self, geojson_path: str, out_html: str = 'agri_pv_plot.html', open_in_browser: bool = True):
		import folium
		# choose calculator by pv_type
		pv_type = self.cfg.get('pv_type', 'horizontal')
		if pv_type == 'vertical':
			calc = GeoAreaVerticalCalculator(geojson_path)
			pv_row_width = float(self.cfg.get('pv_row_width_m', 0.1))
			pv_row_height = float(self.cfg.get('pv_row_height_m', 2.5))
			res = calc.compute_vertical_pv(
				tractor_width=float(self.cfg.get('tractor_width', 3.0)),
				tractor_length=float(self.cfg.get('tractor_length', 5.0)),
				tractor_turn_radius=float(self.cfg.get('tractor_turn_radius', 6.0)),
				pv_row_width_m=pv_row_width,
				pv_row_height_m=pv_row_height,
			)
		else:
			calc = GeoAreaCalculator(geojson_path)
			pv_row_width = float(self.cfg.get('pv_row_width_m', 9.2))
			res = calc.compute_horizontal_pv(
				tractor_width=float(self.cfg.get('tractor_width', 3.0)),
				tractor_length=float(self.cfg.get('tractor_length', 5.0)),
				tractor_turn_radius=float(self.cfg.get('tractor_turn_radius', 6.0)),
				pv_row_width_m=pv_row_width,
			)

		# prepare geometries in WGS84 for plotting
		# original polygon
		poly_wgs = gpd.GeoDataFrame(geometry=[calc.poly_utm], crs=f"EPSG:{calc.utm_epsg}").to_crs(epsg=4326).geometry.iloc[0]
		# inner usable area (may be None)
		inner_wgs = None
		if getattr(calc, 'inner', None) is not None:
			inner_wgs = gpd.GeoDataFrame(geometry=[calc.inner], crs=f"EPSG:{calc.utm_epsg}").to_crs(epsg=4326).geometry.iloc[0]

		# rows
		rows_geo = []
		if getattr(calc, 'rows_gdf', None):
			try:
				rows_gdf = gpd.GeoDataFrame(geometry=calc.rows_gdf, crs=f"EPSG:{calc.utm_epsg}")
				rows_wgs = rows_gdf.to_crs(epsg=4326)
				rows_geo = list(rows_wgs.geometry)
			except Exception:
				rows_geo = list(calc.rows_gdf)

		# map center
		centroid = poly_wgs.centroid
		lon, lat = centroid.x, centroid.y
		m = folium.Map(location=[lat, lon], zoom_start=15)

		# add original polygon
		folium.GeoJson(data=gpd.GeoSeries([poly_wgs], crs='EPSG:4326').__geo_interface__, name='Feldrand',
					   style_function=lambda x: {'color': 'DarkOrange', 'weight': 3, 'fill': False}).add_to(m)

		# add inner usable area
		if inner_wgs is not None:
			folium.GeoJson(data=gpd.GeoSeries([inner_wgs], crs='EPSG:4326').__geo_interface__,
						   style_function=lambda x: {'fillColor': '#1ca728', 'color': '#1ca728', 'weight': 1, 'fillOpacity': 0.35},
						   name='PV-nutzfläche').add_to(m)

		# add PV rows
		rows_fg = folium.FeatureGroup(name='PV-Reihen')
		for geom in rows_geo:
			if geom is None:
				continue
			if geom.geom_type == 'LineString':
				coords_latlon = [(y, x) for x, y in geom.coords]
				folium.PolyLine(locations=coords_latlon, color='#ffee00', weight=2).add_to(rows_fg)
			elif geom.geom_type == 'MultiLineString':
				for part in geom.geoms:
					coords = [(y, x) for x, y in part.coords]
					folium.PolyLine(locations=coords, color='#ffee00', weight=2).add_to(rows_fg)
		rows_fg.add_to(m)

		# add a small info panel as Marker
		info_html = f"PV-Typ: {pv_type}<br>Gesamtfläche: {res.get('total_area_m2')} m²<br>PV-Fußabdruck: {res.get('pv_footprint_m2')} m²"
		folium.Marker(location=[lat, lon], icon=folium.DivIcon(html=f"<div style='font-size:12px'>{info_html}</div>"))

		# fit bounds
		try:
			b_minx, b_miny, b_maxx, b_maxy = poly_wgs.bounds
			m.fit_bounds([[b_miny, b_minx], [b_maxy, b_maxx]])
		except Exception:
			pass

		out_path = Path(out_html)
		m.save(str(out_path))

		# browser open with fallbacks (similar to PVFieldProcessor)
		opened = False
		if open_in_browser:
			try:
				opened = __import__('webbrowser').open(out_path.as_uri(), new=2)
			except Exception:
				opened = False
			if not opened:
				try:
					p = str(out_path.resolve())
					if os.name == 'nt':
						os.startfile(p)
						opened = True
					else:
						import subprocess
						subprocess.run(['xdg-open', p], check=False)
						opened = True
				except Exception:
					opened = False
			if not opened:
				print(f'Karte gespeichert unter: {out_path} (Öffnen im Browser fehlgeschlagen)')
		else:
			print(f'Karte gespeichert unter: {out_path}')

		return out_path, res



if __name__ == '__main__':
	# Make script fully standalone: write embedded geojson if needed, collect inputs, compute and plot
	out_dir = Path(__file__).resolve().parent / 'outputs'
	out_dir.mkdir(exist_ok=True)
	emb_path = out_dir / 'embedded_area.geojson'
	if not emb_path.exists():
		with emb_path.open('w', encoding='utf-8') as f:
			f.write(EMBEDDED_GEOJSON)

	collector = UserInputCollector()
	cfg = collector.collect()
	# persist initial config
	collector.save(cfg)

	# compute areas depending on pv_type
	if cfg.get('pv_type') == 'horizontal':
		calc = GeoAreaCalculator(str(emb_path))
		calc.load_and_project()
		res = calc.compute_horizontal_pv(
			tractor_width=cfg.get('tractor_width', 3.0),
			tractor_length=cfg.get('tractor_length', 5.0),
			tractor_turn_radius=cfg.get('tractor_turn_radius', 6.0),
			pv_row_width_m=cfg.get('pv_row_width_m', 9.2),
		)
	else:
		calc = GeoAreaVerticalCalculator(str(emb_path))
		calc.load_and_project()
		res = calc.compute_vertical_pv(
			tractor_width=cfg.get('tractor_width', 3.0),
			tractor_length=cfg.get('tractor_length', 5.0),
			tractor_turn_radius=cfg.get('tractor_turn_radius', 6.0),
			pv_row_width_m=cfg.get('pv_row_width_m', 0.1),
			pv_row_height_m=cfg.get('pv_row_height_m', 2.5),
		)

	# merge results into cfg and save
	cfg.update(res)
	collector.save(cfg)

	# plot map
	plotter = PVMapPlotter(cfg)
	out_path, plot_res = plotter.plot(str(emb_path), out_html=str(out_dir / 'agri_pv_plot.html'), open_in_browser=False)

	# save final cfg with plot info
	cfg['map_html'] = str(out_path)
	collector.save(cfg)

	print('Fertig. Ergebnisse:')
	print(f"  Karte: {out_path}")
	print(f"  Gesamtfläche: {cfg.get('total_area_m2')} m²")
	print(f"  PV-Fußabdruck: {cfg.get('pv_footprint_m2')} m²")

