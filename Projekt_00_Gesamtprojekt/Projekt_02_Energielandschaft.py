"""
Projekt 02 - Energielandschaft

Dieses Skript enthält modular aufgebaute Klassen zur:
- Einlesung einer eingebetteten GeoJSON-Fläche (WGS84)
- Auswahl des PV-Typs (horizontal/vertical)
- Abfrage der Traktorparameter (Breite, Länge, Wenderadius)
- Berechnung von Wende- und Fahrspurbreiten mit Sicherheitszuschlag von 1 m
- Berechnung der verfügbaren Nutzfläche (in m², reprojiziert in UTM)
- Generierung von PV Modulmitten als GeoJSON FeatureCollection

Technische Hinweise:
- Shapely wird für Geometrieoperationen verwendet.
- Flächen-/Längenberechnungen erfolgen in metrischem UTM (automatische Zonenwahl
  basierend auf Polygon-Zentroid) und werden für GeoJSON wieder in WGS84 zurückprojiziert.
"""

EMBEDDED_GEOJSON = '''{
	"type": "FeatureCollection",
	"features": [
		{
			"type": "Feature",
			"geometry": {
				"type": "Polygon",
				"coordinates": [
					[
						[6.500084,51.050743],[6.500132,51.050763],[6.500138,51.051333],[6.500119,51.051485],[6.500084,51.052031],[6.499953,51.052911],[6.499781,51.053801],[6.499518,51.054607],[6.498939,51.055949],[6.498542,51.056664],[6.498389,51.05704],[6.498891,51.05717],[6.499202,51.057257],[6.499518,51.057347],[6.499558,51.057148],[6.499591,51.05694],[6.499727,51.056652],[6.499872,51.056367],[6.500387,51.055086],[6.500709,51.054162],[6.501052,51.052324],[6.501114,51.051163],[6.50124,51.051213],[6.501404,51.051274],[6.501964,51.051501],[6.502525,51.051721],[6.503212,51.052002],[6.505153,51.052815],[6.507082,51.053643],[6.51088,51.055275],[6.515107,51.056974],[6.517124,51.057783],[6.518648,51.058377],[6.520364,51.057379],[6.519967,51.056954],[6.522306,51.056091],[6.523079,51.056947],[6.523486,51.057473],[6.525729,51.057109],[6.526008,51.060939],[6.526415,51.063407],[6.527059,51.065268],[6.527832,51.067304],[6.528786,51.068902],[6.530836,51.070028],[6.533056,51.070028],[6.533271,51.071976],[6.534076,51.071916],[6.53487,51.071949],[6.534784,51.074457],[6.535428,51.076324],[6.536061,51.078185],[6.535234,51.078084],[6.53296,51.077821],[6.532488,51.07925],[6.53178,51.079506],[6.531136,51.079452],[6.527424,51.080598],[6.526093,51.080679],[6.526008,51.081663],[6.523089,51.082377],[6.52118,51.084318],[6.51912,51.086003],[6.523926,51.087405],[6.525578,51.088503],[6.526212,51.089069],[6.529001,51.089379],[6.530203,51.089474],[6.529961,51.089915],[6.530659,51.09007],[6.53097,51.089575],[6.531581,51.089682],[6.532418,51.089831],[6.536527,51.091926],[6.538239,51.093018],[6.537069,51.09413],[6.534805,51.095902],[6.531254,51.098752],[6.528432,51.098051],[6.52692,51.097714],[6.526254,51.097681],[6.525589,51.097553],[6.523325,51.097095],[6.518165,51.096111],[6.518015,51.095471],[6.51751,51.095316],[6.516931,51.095424],[6.514678,51.095134],[6.513326,51.095201],[6.513712,51.094655],[6.513906,51.091974],[6.51397,51.090639],[6.513133,51.090141],[6.505022,51.089602],[6.502576,51.089925],[6.502361,51.089615],[6.498456,51.089777],[6.49852,51.090087],[6.4941,51.09072],[6.492426,51.094359],[6.489894,51.093685],[6.487191,51.093321],[6.485034,51.092917],[6.482824,51.092674],[6.481687,51.092499],[6.481805,51.092412],[6.479959,51.091515],[6.480303,51.090916],[6.48026,51.090447],[6.48012,51.090003],[6.47967,51.089534],[6.478812,51.089002],[6.477782,51.088358],[6.476993,51.087526],[6.476446,51.086852],[6.476263,51.086663],[6.476129,51.086259],[6.476666,51.086178],[6.477798,51.086043],[6.478382,51.085949],[6.478736,51.085898],[6.478978,51.084995],[6.479176,51.084564],[6.479493,51.084055],[6.479941,51.083439],[6.480609,51.082576],[6.481429,51.081626],[6.484128,51.078623],[6.48667,51.075704],[6.485217,51.075522],[6.48402,51.075394],[6.485109,51.07412],[6.485978,51.07321],[6.487341,51.071659],[6.490152,51.072394],[6.492244,51.0699],[6.4941,51.067641],[6.491665,51.066859],[6.493553,51.06483],[6.495817,51.062173],[6.496804,51.06102],[6.497694,51.059833],[6.49851,51.058842],[6.499497,51.057375],[6.499443,51.05736],[6.499389,51.057343],[6.499355,51.057335],[6.499314,51.057327],[6.499274,51.057315],[6.499234,51.057301],[6.499188,51.057289],[6.49914,51.057278],[6.499097,51.057269],[6.499057,51.057256],[6.499022,51.057246],[6.498979,51.057237],[6.498917,51.057219],[6.498866,51.057205],[6.498797,51.05719],[6.498713,51.057163],[6.498668,51.057151],[6.498606,51.057138],[6.498553,51.057126],[6.498499,51.057111],[6.49844,51.057097],[6.498378,51.057077],[6.498252,51.057219],[6.498236,51.057247],[6.498217,51.057266],[6.498199,51.057288],[6.49734,51.058606],[6.496106,51.05832],[6.494733,51.058013],[6.492791,51.060582],[6.490463,51.063319],[6.493065,51.063957],[6.491852,51.065282],[6.490753,51.066492],[6.489347,51.066188],[6.488135,51.065922],[6.486697,51.067453],[6.485265,51.069087],[6.483817,51.070729],[6.482325,51.07229],[6.485265,51.072684],[6.481247,51.077072],[6.478634,51.080092],[6.477824,51.081005],[6.476945,51.082],[6.47621,51.083],[6.475824,51.08355],[6.4754,51.084483],[6.475099,51.0854],[6.474992,51.08633],[6.474971,51.087324],[6.475142,51.088213],[6.475679,51.089191],[6.475904,51.089635],[6.475936,51.090033],[6.475807,51.090518],[6.475486,51.090895],[6.474702,51.091515],[6.472031,51.091873],[6.46981,51.09192],[6.467611,51.091873],[6.463212,51.091718],[6.460669,51.091603],[6.458759,51.091657],[6.45435,51.091953],[6.451684,51.092294],[6.449039,51.092695],[6.44787,51.092752],[6.447269,51.092802],[6.447253,51.092883],[6.44552,51.092998],[6.442559,51.093207],[6.44434,51.089918],[6.450606,51.090242],[6.451936,51.085194],[6.451592,51.080935],[6.454704,51.081703],[6.454489,51.078562],[6.453009,51.07867],[6.452816,51.07654],[6.450734,51.077025],[6.450627,51.076607],[6.451356,51.076122],[6.450477,51.074976],[6.452365,51.074167],[6.44846,51.069394],[6.447837,51.068612],[6.447172,51.06783],[6.446679,51.068262],[6.444554,51.067722],[6.446314,51.065403],[6.44537,51.06516],[6.447172,51.062571],[6.450305,51.063218],[6.452107,51.059874],[6.459907,51.061391],[6.464092,51.060676],[6.464038,51.060359],[6.471462,51.057878],[6.473222,51.059092],[6.477385,51.056124],[6.47511,51.054587],[6.468244,51.049664],[6.463072,51.045873],[6.464757,51.045718],[6.464435,51.044612],[6.464188,51.043519],[6.463952,51.042365],[6.463813,51.041212],[6.465529,51.040463],[6.466902,51.039879],[6.468946,51.039046],[6.470046,51.038577],[6.47033,51.038729],[6.472203,51.038537],[6.474177,51.038254],[6.477486,51.037684],[6.479664,51.037333],[6.481129,51.037083],[6.481757,51.036786],[6.482481,51.038119],[6.482502,51.038655],[6.483618,51.040557],[6.484165,51.041441],[6.484509,51.042318],[6.485356,51.042871],[6.487201,51.04416],[6.488202,51.044854],[6.488508,51.044853],[6.492051,51.047397],[6.499148,51.050328],[6.499695,51.050567],[6.500084,51.050743]
					]
				]
			},
			"properties": {"name": "Energielandschaft_Juechen_Agri_PV"}
		}
	]
}'''

import json
from typing import Tuple, List, Dict, Any
from shapely.geometry import shape, Polygon, Point, mapping, LineString
from shapely.ops import transform
import pyproj
import math


class GeoJSONReader:
	"""Lädt eine GeoJSON-FeatureCollection (WGS84) und liefert Shapely-Objekte.

	Methoden:
	- load(): parsed Polygon in WGS84 und reprojiziert in UTM (metrische Einheit).
	"""

	def __init__(self, geojson_str: str):
		self.geojson_str = geojson_str

	def _choose_utm_crs(self, lon: float, lat: float) -> pyproj.CRS:
		zone = int((lon + 180) / 6) + 1
		if lat >= 0:
			epsg = 32600 + zone
		else:
			epsg = 32700 + zone
		return pyproj.CRS.from_epsg(epsg)

	def load(self) -> Tuple[Polygon, Polygon, pyproj.Transformer, pyproj.Transformer]:
		"""Parst das eingebettete GeoJSON und gibt zurück:
		(poly_wgs84, poly_utm, transformer_to_utm, transformer_to_wgs84)
		"""
		obj = json.loads(self.geojson_str)
		# Annahme: erste Feature enthält die Polygonfläche
		feat = obj.get("features", [])[0]
		geom = shape(feat["geometry"])  # in WGS84 (lon/lat)

		centroid = geom.representative_point()
		lon, lat = centroid.x, centroid.y
		utm_crs = self._choose_utm_crs(lon, lat)

		transformer_to_utm = pyproj.Transformer.from_crs("EPSG:4326", utm_crs, always_xy=True)
		transformer_to_wgs84 = pyproj.Transformer.from_crs(utm_crs, "EPSG:4326", always_xy=True)

		proj_to_utm = lambda x, y: transformer_to_utm.transform(x, y)
		poly_utm = transform(proj_to_utm, geom)

		return geom, poly_utm, transformer_to_utm, transformer_to_wgs84


class PVTypeSelector:
	"""Fragt den PV-Typ ab ("horizontal" oder "vertical").

	Parameter:
	- default: Standardwert falls Enter gedrückt wird.
	- interactive: falls False, wird der Default zurückgegeben.
	"""

	VALID = ("horizontal", "vertical")

	@staticmethod
	def select(default: str = "horizontal", interactive: bool = True) -> str:
		if not interactive:
			return default
		prompt = f"Bitte PV-Typ auswählen [Default: {default}] Horizontale PV-Anlage (Aufgeständert, bifazial): 'horizontal' oder Vertikale PV-Anlage (Senkrecht, bifazial): 'vertical'): "
		val = input(prompt).strip().lower() or default
		if val not in PVTypeSelector.VALID:
			print("Ungültige Auswahl, verwende Default: %s" % default)
			return default
		return val


class TractorParameters:
	"""Container für Traktorparameter und Berechnung der Randzonen.

	Attribute:
	- width_m, length_m, turn_radius_m

	Methoden:
	- compute_wendestreifen_width(): Wende-/Rückzugsbreite inkl. 1 m Sicherheitszuschlag
	- compute_fahrspur_width(): Fahrspurbreite inkl. 1 m Sicherheitszuschlag
	"""

	def __init__(self, width_m: float, length_m: float, turn_radius_m: float):
		self.width_m = float(width_m)
		self.length_m = float(length_m)
		self.turn_radius_m = float(turn_radius_m)

	@staticmethod
	def from_input(interactive: bool = True, defaults: Tuple[float, float, float] = (2.5, 3.0, 4.0)) -> "TractorParameters":
		if not interactive:
			return TractorParameters(*defaults)
		try:
			w = input(f"Traktorbreite in Meter [{defaults[0]}]: ") or str(defaults[0])
			l = input(f"Traktorlaenge in Meter [{defaults[1]}]: ") or str(defaults[1])
			r = input(f"Wenderadius in Meter [{defaults[2]}]: ") or str(defaults[2])
			return TractorParameters(float(w), float(l), float(r))
		except ValueError:
			print("Ungültige Eingabe, benutze Defaultwerte.")
			return TractorParameters(*defaults)

	def compute_wendestreifen_width(self) -> float:
		# Formel: Länge + 2 * Wenderadius + 1 m Sicherheitszuschlag
		return self.length_m + 2.0 * self.turn_radius_m + 1.0

	def compute_fahrspur_width(self) -> float:
		# Fahrspurbreite: Traktorbreite + 2 m Sicherheitszuschlag (zwei Seiten je 1 m)
		return self.width_m + 2.0


class AreaCalculator:
	"""Berechnet die nutzbare Innenfläche einer Polygonfläche unter Abzug des
	Wende-/Fahrspurmargins. Alle Berechnungen erfolgen in UTM (metrisch).

	Methoden:
	- compute_usable_area(poly_utm, margin_m) -> (usable_poly_utm, usable_area_m2)
	"""

	@staticmethod
	def compute_usable_area(poly_utm: Polygon, margin_m: float) -> Tuple[Polygon, float]:
		if margin_m <= 0:
			area = poly_utm.area
			return poly_utm, area
		inner = poly_utm.buffer(-margin_m)
		if inner.is_empty:
			return inner, 0.0
		return inner, inner.area


def compute_restflaeche(poly_utm: Polygon, breite_gruenstreifen: Any) -> Polygon:
	"""Berechnet die nutzbare Restfläche durch Entfernen eines äußeren
	Randstreifens mit Breite `breite_gruenstreifen` (in Metern) vom gegebenen
	Polygon in UTM-Koordinaten.

	Implementation:
	- Validiert `breite_gruenstreifen` (nicht-negativ, finite Zahl).
	- Verwendet `shapely.buffer` mit negativem Wert: `poly_utm.buffer(-breite)`.
	- Gibt das resultierende Polygon (kann leer sein) zurück.

	Parameter:
	- poly_utm: Shapely-Polygon in metrischem Koordinatensystem (z. B. UTM)
	- breite_gruenstreifen: Breite des abzuziehenden Streifens in Metern

	Rückgabe:
	- Shapely-Polygon der verbleibenden Innenfläche (oder ein leeres Geometry-Objekt)
	"""
	# Validierung
	if poly_utm is None:
		raise ValueError("poly_utm darf nicht None sein")
	if not hasattr(poly_utm, "buffer"):
		raise TypeError("poly_utm muss ein Shapely-Polygon sein")

	try:
		b = float(breite_gruenstreifen)
	except Exception:
		raise ValueError(f"breite_gruenstreifen muss numerisch sein, gegeben: {breite_gruenstreifen}")

	if not math.isfinite(b) or b < 0:
		raise ValueError(f"breite_gruenstreifen muss eine nicht-negative endliche Zahl sein, gegeben: {breite_gruenstreifen}")

	if b == 0:
		return poly_utm

	inner = poly_utm.buffer(-b)
	return inner


class PVGridGenerator:
	"""Generiert ein rasterförmiges Netz von Modulmitten (als Punkte) innerhalb
	der nutzbaren Fläche (UTM) und liefert ein GeoJSON FeatureCollection.

	Parameter:
	- usable_poly_utm: Shapely Polygon in UTM
	- transformer_to_wgs84: pyproj.Transformer (UTM -> EPSG:4326)

	Methode:
	- generate_points(pv_type, row_spacing_m, module_spacing_m) -> GeoJSON dict
	"""

	def __init__(self, usable_poly_utm: Polygon, transformer_to_wgs84: pyproj.Transformer):
		self.poly = usable_poly_utm
		self.transformer_to_wgs84 = transformer_to_wgs84

	@staticmethod
	def _frange(start: float, stop: float, step: float):
		vals = []
		v = start
		# guard against infinite loops
		if step <= 0:
			return vals
		while v <= stop:
			vals.append(v)
			v += step
		return vals

	def generate_points(self, pv_type: str = "horizontal", row_spacing_m: float = 12.0, module_spacing_m: float = 1.0) -> Dict[str, Any]:
		"""Erzeugt Punkte im Raster.

		Annahmen / Parameter:
		- `row_spacing_m`: Distanz zwischen zwei PV-Reihen (in Metern).
		  Empfohlen: Fahrspurbreite + Modulreihenbreite.
		- `module_spacing_m`: Abstand zwischen Modulmitten entlang einer Reihe.
		- `pv_type` beeinflusst momentan nur die Reihenorientierung.
		"""
		if self.poly.is_empty:
			return {"type": "FeatureCollection", "features": []}

		minx, miny, maxx, maxy = self.poly.bounds

		# Für horizontale Module: Reihen in x-Richtung, Abstand entlang y
		# Für vertikale Module: wir verwenden denselben Rastermechanismus, evtl. kleinerer Abstand
		if pv_type == "vertical":
			row_spacing = max(1.0, row_spacing_m / 3.0)
		else:
			row_spacing = row_spacing_m

		xs = self._frange(minx + module_spacing_m / 2.0, maxx - module_spacing_m / 2.0, module_spacing_m)
		ys = self._frange(miny + row_spacing / 2.0, maxy - row_spacing / 2.0, row_spacing)

		features = []
		for y in ys:
			for x in xs:
				pt = Point(x, y)
				if pt.within(self.poly):
					lon, lat = self.transformer_to_wgs84.transform(x, y)
					features.append({
						"type": "Feature",
						"geometry": {"type": "Point", "coordinates": [lon, lat]},
						"properties": {"pv_type": pv_type}
					})

		return {"type": "FeatureCollection", "features": features}

	def generate_pv_points(polygon: Polygon, ausrichtung: str, reihenbreite: float,
						   module_spacing_m: float = 1.0,
						   transformer_to_wgs84: pyproj.Transformer = None) -> Dict[str, Any]:
		"""Generiert PV-Modulpunkte als GeoJSON FeatureCollection.
		Implementiert die angeforderte Zeilen-Segmentierung, Schnittpunkt-Generierung,
		gleichmäßige Punkt-Generierung und GeoJSON-Ausgabe. Beinhaltet Parameter-Validierung
		und optionalen Transformer für WGS84-Ausgabe.
		"""
		# Parameter-Validierung
		if not isinstance(polygon, Polygon):
			raise ValueError("Das Polygon muss ein Shapely Polygon sein.")
		if ausrichtung not in ["horizontal", "vertical"]:
			raise ValueError(f"Ungültige Ausrichtung '{ausrichtung}': erwartet 'horizontal' oder 'vertical'.")

		# Diese Methode ist veraltet; verwende stattdessen generate_pv_points() oder generate_pv_reihen()
		return {"type": "FeatureCollection", "features": []}


def generate_pv_points(polygon: Polygon, ausrichtung: str, reihenbreite: float,
                       module_spacing_m: float = 1.0,
                       transformer_to_wgs84: pyproj.Transformer = None) -> Dict[str, Any]:
	"""Generiert PV-Modulpunkte als GeoJSON FeatureCollection.

	Vorgehen:
	1. Segmentiert die Bounding-Box des Polygons in Linien (Zeilen/Spalten) abhängig von `ausrichtung`.
	2. Prüft für jede Linie den Schnitt mit dem Polygon.
	3. Für jede Schnittlinie werden äquidistante Punkte in Abstand `module_spacing_m` erzeugt.
	4. Gibt alle Punkte als GeoJSON FeatureCollection zurück.

	Parameter:
	- polygon: Shapely-Polygon (vorzugsweise in metrischen Einheiten, z. B. UTM)
	- ausrichtung: 'horizontal' oder 'vertical'
	- reihenbreite: Abstand zwischen Reihen in Metern
	- module_spacing_m: Abstand zwischen Modulen entlang einer Reihe (default 1.0 m)
	- transformer_to_wgs84: optionaler pyproj.Transformer zum Zurückprojektion der Punktkoordinaten

	Rückgabe:
	- GeoJSON-Dict mit Point-Features (Koordinaten in CRS der Transformer, falls angegeben)
	"""
	# Validierung
	if polygon is None or polygon.is_empty:
		return {"type": "FeatureCollection", "features": []}
	try:
		r = float(reihenbreite)
	except Exception:
		raise ValueError("reihenbreite muss eine positive Zahl sein")
	if r <= 0:
		raise ValueError("reihenbreite muss > 0 sein")
	try:
		spacing = float(module_spacing_m)
	except Exception:
		raise ValueError("module_spacing_m muss eine positive Zahl sein")
	if spacing <= 0:
		raise ValueError("module_spacing_m muss > 0 sein")

	a = str(ausrichtung).strip().lower()
	if a not in ("horizontal", "vertical"):
		raise ValueError("ausrichtung muss 'horizontal' oder 'vertical' sein")

	minx, miny, maxx, maxy = polygon.bounds

	lines: List[LineString] = []
	if a == "horizontal":
		y = miny + r / 2.0
		while y <= maxy:
			# leicht überlappen, damit Schnitt robust ist
			lines.append(LineString([(minx - 1.0, y), (maxx + 1.0, y)]))
			y += r
	else:
		x = minx + r / 2.0
		while x <= maxx:
			lines.append(LineString([(x, miny - 1.0), (x, maxy + 1.0)]))
			x += r

	features: List[Dict[str, Any]] = []
	row_idx = 0
	for line in lines:
		inter = line.intersection(polygon)
		if inter.is_empty:
			row_idx += 1
			continue

		segments = []
		if inter.geom_type == 'LineString':
			segments = [inter]
		elif inter.geom_type == 'MultiLineString':
			segments = list(inter.geoms)
		else:
			row_idx += 1
			continue

		for seg in segments:
			seg_length = seg.length
			if seg_length <= 0:
				continue
			dist = spacing / 2.0
			while dist <= seg_length - 1e-9:
				pt = seg.interpolate(dist)
				x, y = pt.x, pt.y
				if transformer_to_wgs84 is not None:
					lon, lat = transformer_to_wgs84.transform(x, y)
					coords = [lon, lat]
				else:
					coords = [x, y]

				features.append({
					"type": "Feature",
					"geometry": {"type": "Point", "coordinates": coords},
					"properties": {"row": row_idx, "dist_m": round(dist, 3)}
				})
				dist += spacing

		row_idx += 1

	return {"type": "FeatureCollection", "features": features}


def generate_pv_reihen(polygon: Polygon, ausrichtung: str, row_spacing: float,
                       transformer_to_wgs84: pyproj.Transformer = None) -> Dict[str, Any]:
	"""Generiert PV-Reihen als LineString-Features (ohne Breite) in einer GeoJSON FeatureCollection.

	Die PV-Reihen werden als **geometrielose Linien** (LineStrings ohne Pufferung) dargestellt.
	Der wichtige Parameter ist der **Abstand zwischen den Linien** (row_spacing).

	Vorgehen:
	1. Bestimmt basierend auf der Ausrichtung die Segmentierungsrichtung:
	   - horizontal: Linien Ost–West, Verschiebung Nord–Süd
	   - vertikal: Linien Nord–Süd, Verschiebung Ost–West
	2. Erzeugt aus der Bounding Box des Polygons parallele Linien im Abstand `row_spacing`.
	3. Schneidet jede Linie mit dem nutzbaren Polygon (Shapely intersection).
	4. Fügt jede resultierende nichtleere Schnittgeometrie als LineString-Feature ein (ohne Breite).
	5. Exportiert eine GeoJSON-Datei, deren Features ausschließlich LineStrings enthalten.

	Parameter:
	- polygon: Shapely-Polygon (vorzugsweise in metrischen Einheiten, z. B. UTM)
	- ausrichtung: 'horizontal' oder 'vertical'
	- row_spacing: Abstand zwischen parallelen Reihen in Metern (wichtiger Parameter!)
	- transformer_to_wgs84: optionaler pyproj.Transformer zur Zurückprojektion in WGS84

	Rückgabe:
	- GeoJSON-Dict mit LineString-Features (ein Feature pro Reihe oder Reihen-Segment)

	Fehlerbehandlung:
	- ValueError bei ungültiger Ausrichtung oder negativem row_spacing
	- Leere Polygone liefern leere FeatureCollection
	"""
	# Validierung
	if polygon is None or polygon.is_empty:
		return {"type": "FeatureCollection", "features": []}

	try:
		r = float(row_spacing)
	except Exception:
		raise ValueError("row_spacing muss eine positive Zahl sein")
	if r <= 0:
		raise ValueError("row_spacing muss > 0 sein")

	a = str(ausrichtung).strip().lower()
	if a not in ("horizontal", "vertical"):
		raise ValueError("ausrichtung muss 'horizontal' oder 'vertical' sein")

	minx, miny, maxx, maxy = polygon.bounds

	# Schritt 1 & 2: Generiere parallele Linien basierend auf Ausrichtung
	lines: List[LineString] = []
	if a == "horizontal":
		# Linien verlaufen Ost–West (Konstante Y)
		# Verschiebung Nord–Süd nach row_spacing
		y = miny + r / 2.0
		while y <= maxy:
			# Linien erstrecken sich leicht über die Bounding Box
			lines.append(LineString([(minx - 1.0, y), (maxx + 1.0, y)]))
			y += r
	else:  # vertical
		# Linien verlaufen Nord–Süd (Konstante X)
		# Verschiebung Ost–West nach row_spacing
		x = minx + r / 2.0
		while x <= maxx:
			lines.append(LineString([(x, miny - 1.0), (x, maxy + 1.0)]))
			x += r

	# Schritt 3, 4 & 5: Schneide Linien mit Polygon und generiere Features
	features: List[Dict[str, Any]] = []
	row_idx = 0

	for line in lines:
		inter = line.intersection(polygon)

		# Überspringe leere Schnitte
		if inter.is_empty:
			row_idx += 1
			continue

		# Behandle verschiedene Geometry-Typen
		segments: List[LineString] = []
		if inter.geom_type == 'LineString':
			segments = [inter]
		elif inter.geom_type == 'MultiLineString':
			segments = list(inter.geoms)
		else:
			# Ignoriere Points oder andere Geometrie-Typen
			row_idx += 1
			continue

		# Konvertiere jedes Segment in ein Feature
		for seg_idx, seg in enumerate(segments):
			if seg.length <= 0:
				continue

			# Reprojiziere Koordinaten falls Transformer vorhanden
			if transformer_to_wgs84 is not None:
				coords_wgs84 = []
				for x, y in seg.coords:
					lon, lat = transformer_to_wgs84.transform(x, y)
					coords_wgs84.append([lon, lat])
				coords = coords_wgs84
			else:
				coords = [[x, y] for x, y in seg.coords]

			features.append({
				"type": "Feature",
				"geometry": {
					"type": "LineString",
					"coordinates": coords
				},
				"properties": {
					"row": row_idx,
					"segment": seg_idx,
					"length_m": round(seg.length, 3),
					"orientation": "EW" if a == "horizontal" else "NS"
				}
			})

		row_idx += 1

	return {"type": "FeatureCollection", "features": features}

def export_geojson(points: Dict[str, Any], dateiname: str) -> None:
	"""Exportiert eine GeoJSON FeatureCollection in eine Datei (RFC 7946 konform).

	Parameter:
	- points: GeoJSON FeatureCollection Dict (z. B. Rückgabe von generate_pv_points)
	- dateiname: Pfad der Ausgabedatei (z. B. 'outputs/pv_points.geojson')

	Funktionalität:
	- Validiert, dass `points` die erforderlichen GeoJSON-Felder enthält.
	- Schreibt die Datei mit UTF-8 Encoding, 2-Leerzeichen-Indentation und sortiertem JSON.
	- RFC 7946 Konformität: Koordinaten sind [lon, lat], CRS ist implicit EPSG:4326 (WGS84).
	- Erstellt ggf. das Parent-Verzeichnis falls nicht vorhanden.

	Fehlerbehandlung:
	- ValueError bei ungültigem Input (fehlende 'type' oder 'features' Schlüssel).
	- IOError/OSError bei Dateischreib-Problemen.
	"""
	if not isinstance(points, dict):
		raise ValueError("points muss ein Dictionary sein (GeoJSON FeatureCollection)")
	if points.get("type") != "FeatureCollection":
		raise ValueError("points.type muss 'FeatureCollection' sein")
	if "features" not in points:
		raise ValueError("points muss ein 'features' Feld (Liste) enthalten")
	if not isinstance(points["features"], list):
		raise ValueError("points['features'] muss eine Liste sein")

	if not isinstance(dateiname, str) or not dateiname.strip():
		raise ValueError("dateiname muss ein nicht-leerer String sein")

	try:
		import os
		outdir = os.path.dirname(dateiname)
		if outdir and not os.path.exists(outdir):
			os.makedirs(outdir, exist_ok=True)

		with open(dateiname, 'w', encoding='utf-8') as f:
			json.dump(points, f, ensure_ascii=False, indent=2, sort_keys=True)

		print(f"GeoJSON erfolgreich exportiert: {dateiname}")
	except IOError as e:
		raise IOError(f"Fehler beim Schreiben der Datei '{dateiname}': {e}")
	except Exception as e:
		raise RuntimeError(f"Unerwarteter Fehler beim Export: {e}")

def run_standalone(interactive: bool = True) -> Dict[str, Any]:
	"""Kurzer Ablauf (bindet alle Komponenten zusammen) und liefert ein Ergebnis-Dict:
	- Liest EMBEDDED_GEOJSON
	- Fragt PV-Typ und Traktorparameter ab (interaktiv oder Default)
	- Berechnet Wende-/Fahrspurmargen
	- Ermittelt nutzbare Innenfläche (UTM)
	- Generiert PV-Punkte und gibt GeoJSON zurück
	"""
	reader = GeoJSONReader(EMBEDDED_GEOJSON)
	geom_wgs84, geom_utm, to_utm, to_wgs84 = reader.load()

	pv_type = PVTypeSelector.select(interactive=interactive)
	tractor = TractorParameters.from_input(interactive=interactive)

	wendestreifen = tractor.compute_wendestreifen_width()
	fahrspur = tractor.compute_fahrspur_width()

	# Margin: wir nehmen als konservativen Rand die größere der beiden Breiten
	margin = max(wendestreifen, fahrspur)

	usable_poly_utm, usable_area_m2 = AreaCalculator.compute_usable_area(geom_utm, margin)

	grid_gen = PVGridGenerator(usable_poly_utm, to_wgs84)
	row_spacing = fahrspur + 2.0  # grobe Heuristik: Fahrspur + 2m frei
	geojson_points = grid_gen.generate_points(pv_type=pv_type, row_spacing_m=row_spacing, module_spacing_m=1.0)

	result = {
		"pv_type": pv_type,
		"tractor": {"width_m": tractor.width_m, "length_m": tractor.length_m, "turn_radius_m": tractor.turn_radius_m},
		"wendestreifen_m": wendestreifen,
		"fahrspur_m": fahrspur,
		"margin_used_m": margin,
		"usable_area_m2": usable_area_m2,
		"n_pv_points": len(geojson_points.get("features", [])),
		"pv_points_geojson": geojson_points,
	}

	return result


def compute_tractor_margins(traktor_breite: Any = None, traktor_laenge: Any = None, wenderadius: Any = None,
							interactive: bool = True, defaults: Tuple[float, float, float] = (2.5, 3.0, 4.0)) -> Dict[str, Any]:
	"""Fragt Traktorparameter ab oder verwendet übergebene Werte und berechnet:
	- breite_gruenstreifen = 2*wenderadius + traktor_laenge + 1
	- breite_fahrspur = traktor_breite + 2*1

	Robustheit:
	- Bei interaktiver Nutzung werden Eingaben validiert und ggf. erneut abgefragt.
	- Bei nicht-interaktivem Aufruf werden ungültige oder fehlende Werte durch Defaults ersetzt.
	- Negative oder Null-Werte werden als ungültig betrachtet und ersetzt.

	Rückgabe: Dict mit den numerischen Werten und optionalen Warnungen.
	"""

	warnings: List[str] = []

	def _to_valid_float(name: str, val: Any, default: float) -> float:
		# Versuche Umwandlung; bei Fehler Default verwenden
		if val is None:
			if interactive:
				raw = input(f"{name} in m [{default}]: ") or str(default)
			else:
				warnings.append(f"{name} nicht angegeben, verwende Default {default}")
				return float(default)
		else:
			raw = str(val)
		try:
			f = float(raw)
			if not math.isfinite(f) or f <= 0:
				raise ValueError("Nicht-positive Zahl")
			return f
		except Exception:
			warnings.append(f"Ungültiger Wert für {name}: '{raw}', benutze Default {default}")
			return float(default)

	b = _to_valid_float("traktor_breite", traktor_breite, defaults[0])
	l = _to_valid_float("traktor_laenge", traktor_laenge, defaults[1])
	r = _to_valid_float("wenderadius", wenderadius, defaults[2])

	breite_gruenstreifen = 2.0 * r + l + 1.0
	breite_fahrspur = b + 2.0 * 1.0

	res = {
		"traktor_breite_m": b,
		"traktor_laenge_m": l,
		"wenderadius_m": r,
		"breite_gruenstreifen_m": breite_gruenstreifen,
		"breite_fahrspur_m": breite_fahrspur,
	}
	if warnings:
		res["warnings"] = warnings

	return res


def get_reihenparameter(ausrichtung: Any, fahrspur_breite: float = None) -> Dict[str, Any]:
	"""Gibt Reihenparameter zurück abhängig von der Ausrichtung.

	**Reihenabstand (Zeile-zu-Zeile-Abstand in Meters):**
	- Bei "horizontal": Reihenabstand = Fahrspurbreite + 9.2 m (EW-Ausrichtung)
	- Bei "vertical": Reihenabstand = Fahrspurbreite + 0.5 m (NS-Ausrichtung)

	**Orientierung der PV-Reihen:**
	- Bei "horizontal": Reihen verlaufen Ost–West (EW), Reihenbreite = 9.2 m
	- Bei "vertical": Reihen verlaufen Nord–Süd (NS), Reihenbreite = 0.5 m

	Parameter:
	- ausrichtung: Erwartet 'horizontal' oder 'vertical' (Groß-/Kleinschreibung ignoriert).
	- fahrspur_breite: Fahrspurbreite des Traktors in Metern (optional).
	                   Falls None, wird nur die Reihenbreite berechnet.

	Rückgabe: Dict mit Schlüsseln:
	- `orientation` ("EW" oder "NS")
	- `reihenbreite_m` (Breite der Modulreihe)
	- `row_spacing_m` (Abstand zwischen Reihen, falls fahrspur_breite übergeben)

	Fehlerbehandlung:
	- Bei ungültigem Wert wird eine `ValueError` mit erklärendem Hinweis ausgelöst.
	"""
	if ausrichtung is None:
		raise ValueError("Ausrichtung darf nicht None sein; benutze 'horizontal' oder 'vertical'.")

	a = str(ausrichtung).strip().lower()
	
	if a == "horizontal":
		result = {"orientation": "EW", "reihenbreite_m": 9.2}
		if fahrspur_breite is not None:
			result["row_spacing_m"] = fahrspur_breite + 9.2
	elif a == "vertical":
		result = {"orientation": "NS", "reihenbreite_m": 0.5}
		if fahrspur_breite is not None:
			result["row_spacing_m"] = fahrspur_breite + 0.5
	else:
		raise ValueError(f"Ungültige Ausrichtung '{ausrichtung}': erwartet 'horizontal' oder 'vertical'.")
	
	return result


def main(interactive: bool = True, output_dir: str = "outputs") -> Dict[str, Any]:
	"""Hauptfunktion: Orchestriert alle Schritte für die PV-Flächenberechnung.

	Schritte:
	1. Einlesen der eingebetteten GeoJSON-Fläche.
	2. Abfrage der Benutzerinputs: Ausrichtung und Traktorparameter.
	3. Berechnung von Rand- und Fahrspurbreiten.
	4. Berechnung der nutzbaren Restfläche.
	5. Generierung der PV-Modulpunkte.
	6. Export der Punkte als GeoJSON.

	Parameter:
	- interactive: Falls True, fragt die Funktion Benutzereingaben ab. Falls False, werden Defaults verwendet.
	- output_dir: Verzeichnis für die Ausgabedateien (default: 'outputs')

	Rückgabe:
	- Dictionary mit allen Ergebnissen und Metadaten.
	"""
	print("\n" + "="*70)
	print("PV-Flächenberechnung - Energielandschaft")
	print("="*70 + "\n")

	# Schritt 1: Einlesen der eingebetteten GeoJSON-Fläche
	print("[1/6] Einlesen der eingebetteten GeoJSON-Fläche...")
	try:
		reader = GeoJSONReader(EMBEDDED_GEOJSON)
		geom_wgs84, geom_utm, to_utm, to_wgs84 = reader.load()
		print(f"  ✓ Polygon geladen (WGS84)")
		print(f"    - Fläche (WGS84): {geom_wgs84.area:.2f} deg²")
		print(f"    - Fläche (UTM): {geom_utm.area:.2f} m²\n")
	except Exception as e:
		print(f"  ✗ Fehler beim Laden des GeoJSON: {e}\n")
		raise

	# Schritt 2: Abfrage der Benutzerinputs
	print("[2/6] Abfrage der Benutzerinputs...")
	try:
		ausrichtung = PVTypeSelector.select(interactive=interactive)
		print(f"  ✓ PV-Ausrichtung: {ausrichtung}")

		tractor = TractorParameters.from_input(interactive=interactive)
		print(f"  ✓ Traktorparameter:")
		print(f"    - Breite: {tractor.width_m} m")
		print(f"    - Länge: {tractor.length_m} m")
		print(f"    - Wenderadius: {tractor.turn_radius_m} m\n")
	except Exception as e:
		print(f"  ✗ Fehler bei Eingabeverarbeitung: {e}\n")
		raise

	# Schritt 3: Berechnung von Rand- und Fahrspurbreiten
	print("[3/6] Berechnung von Rand- und Fahrspurbreiten...")
	try:
		wendestreifen = tractor.compute_wendestreifen_width()
		fahrspur = tractor.compute_fahrspur_width()
		print(f"  ✓ Wendestreifen-Breite: {wendestreifen:.2f} m (Formel: 2*r + l + 1)")
		print(f"  ✓ Fahrspur-Breite: {fahrspur:.2f} m (Formel: b + 2)\n")
	except Exception as e:
		print(f"  ✗ Fehler bei Breitenberechnung: {e}\n")
		raise

	# Schritt 4: Berechnung der nutzbaren Restfläche
	print("[4/6] Berechnung der nutzbaren Restfläche...")
	try:
		margin = max(wendestreifen, fahrspur)
		rest_poly = compute_restflaeche(geom_utm, margin)
		usable_area = rest_poly.area if not rest_poly.is_empty else 0.0
		print(f"  ✓ Randstreifen-Marge: {margin:.2f} m")
		print(f"  ✓ Nutzbare Fläche: {usable_area:.2f} m²")
		if rest_poly.is_empty:
			print(f"  ⚠ Warnung: Nutzbare Fläche ist leer (Randstreifen zu groß)\n")
			return {
				"success": False,
				"error": "Nutzbare Fläche ist leer",
				"metadata": {
					"ausrichtung": ausrichtung,
					"traktor": {"width_m": tractor.width_m, "length_m": tractor.length_m, "turn_radius_m": tractor.turn_radius_m},
					"wendestreifen_m": wendestreifen,
					"fahrspur_m": fahrspur,
					"usable_area_m2": 0.0,
				}
			}
		print()
	except Exception as e:
		print(f"  ✗ Fehler bei Flächenberechnung: {e}\n")
		raise

	# Schritt 5: Abfrage der Reihenparameter und Generierung der PV-Reihen
	print("[5/6] Generierung der PV-Reihen (LineString-basiert)...")
	try:
		reihen_info = get_reihenparameter(ausrichtung, fahrspur_breite=fahrspur)
		row_spacing = reihen_info.get("row_spacing_m")
		orientation = reihen_info["orientation"]
		
		print(f"  ✓ Reihenparameter für '{ausrichtung}':")
		print(f"    - Ausrichtung: {orientation} ({'Ost-West' if orientation == 'EW' else 'Nord-Süd'})")
		print(f"    - Reihenabstand (Zeile-zu-Zeile): {row_spacing:.2f} m")

		# Generiere PV-Reihen (LineStrings statt Punkte)
		geojson_points = generate_pv_reihen(rest_poly, ausrichtung, row_spacing, 
											transformer_to_wgs84=to_wgs84)
		n_points = len(geojson_points.get("features", []))
		print(f"  ✓ Generierte PV-Reihen: {n_points}")
		print(f"    - Geometrie: LineString (durchgehende Reihen)\n")
	except Exception as e:
		print(f"  ✗ Fehler bei Reihengenerierung: {e}\n")
		raise

	# Schritt 6: Export der Reihen als GeoJSON
	print("[6/6] Export der Reihen als GeoJSON...")
	try:
		import os
		if not os.path.exists(output_dir):
			os.makedirs(output_dir, exist_ok=True)
		
		output_file = os.path.join(output_dir, "pv_reihen.geojson")
		export_geojson(geojson_points, output_file)
		print(f"  ✓ GeoJSON exportiert: {output_file}\n")
	except Exception as e:
		print(f"  ✗ Fehler beim Export: {e}\n")
		raise

	# Zusammenfassung
	print("="*70)
	print("ZUSAMMENFASSUNG")
	print("="*70)
	result = {
		"success": True,
		"ausrichtung": ausrichtung,
		"metadata": {
			"ausrichtung": ausrichtung,
			"orientation": orientation,
			"traktor": {
				"width_m": tractor.width_m,
				"length_m": tractor.length_m,
				"turn_radius_m": tractor.turn_radius_m
			},
		"wendestreifen_m": wendestreifen,
		"fahrspur_m": fahrspur,
		"margin_m": margin,
		"usable_area_m2": usable_area,
		"row_spacing_m": row_spacing,
		"n_pv_reihen": n_points,
			"output_file": output_file,
		}
	}

	print(f"PV-Ausrichtung: {ausrichtung}")
	print(f"Traktor - Breite: {tractor.width_m} m, Länge: {tractor.length_m} m, Radius: {tractor.turn_radius_m} m")
	print(f"Wendestreifen: {wendestreifen:.2f} m | Fahrspur: {fahrspur:.2f} m")
	print(f"Nutzbare Fläche: {usable_area:.2f} m²")
	print(f"Reihenabstand (Zeile-zu-Zeile: Traktor Fahrspur plus Breite PV-Anlage (Horizontale Ausrichtung 9.2 Meter, Vertikale Ausrichtung 0.5 Meter)): {row_spacing:.2f} m")
	print(f"Orientierung: {orientation} ({'Ost-West' if orientation == 'EW' else 'Nord-Süd'})") 
	print(f"Generierte PV-Reihen: {n_points}")
	print(f"Output: {output_file}")
	print("="*70 + "\n")

	return result


if __name__ == "__main__":
	try:
		result = main(interactive=True, output_dir="outputs")
		if result.get("success"):
			print("✓ Verarbeitung erfolgreich abgeschlossen!")
		else:
			print(f"✗ Verarbeitung abgebrochen: {result.get('error')}")
	except Exception as e:
		print(f"✗ Kritischer Fehler: {e}")
		import traceback
		traceback.print_exc()

