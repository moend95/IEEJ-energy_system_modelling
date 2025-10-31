# pvLib
# Input: Welche PV-Module, Horizontal oder Vertikale PV-Module (Aus Run_Skript), Wetter Daten CSV-Datei (Typical meteorological year (TMY)), Fixer Albedo Wert festlegen 
# Ausgabe: PV Ertrag für ein Modul (Berechnung erfolgt für ein einzelnes Modul, wird in PV_Ertrags_Berechnung auf die gesamte Fläche skaliert)

# ------------------------------------------------------------

"""
pvLib helper for AgriPV project

Provides a function `run_simulation_from_cfg(cfg)` which reads a configuration
dictionary (as produced by the UserInputCollector and area calculation) and
runs a simplified pvlib simulation for vertical Agri-PV installations.

The function expects the following keys in cfg when pv_type == 'vertical':
 - pv_vertical_front_m2 : float  (vertical front area in m2)
 - pv_row_height_m      : float  (height of vertical rows, m)
 - pv_row_width_m       : float  (ground footprint width, m)

It uses a small pvlib setup adapted from the project's example script. The
weather CSV path is taken from a sensible default in the repository; you can
edit `WEATHER_CSV_DEFAULT` if needed.
"""

from pathlib import Path
import math
import warnings

WEATHER_CSV_DEFAULT = (
	Path(__file__).resolve().parent.parent
	/ 'Energielandschaft_Vorlage_von_Moritz'
	/ '04_Energielandschaft'
	/ 'AgriPV-Tool'
	/ 'pvlib_TMY_Demoflaeche.csv'
)


def run_simulation_from_cfg(cfg: dict, weather_csv: str | Path = None):
	"""Run a simplified pvlib simulation using values from cfg.

	Returns a dict with summary results (total_energy_kwh, specific_yield_kwh_per_kwp,
	installed_capacity_kwp, number_of_modules).
	"""
	try:
		import pandas as pd
		from pvlib import pvsystem, location, modelchain
		from pvlib.temperature import TEMPERATURE_MODEL_PARAMETERS as PARAMS
		from pvlib.bifacial.pvfactors import pvfactors_timeseries
	except Exception as e:
		print('pvlib or dependencies not available:', e)
		return None

	# Determine weather CSV
	weather_csv = Path(weather_csv) if weather_csv is not None else WEATHER_CSV_DEFAULT
	if not weather_csv.exists():
		print(f'Warnung: Wetterdatei nicht gefunden: {weather_csv}. Simulation übersprungen.')
		return None

	# Load weather
	weather = pd.read_csv(str(weather_csv))
	if 'Unnamed: 0' in weather.columns:
		weather['Unnamed: 0'] = pd.to_datetime(weather['Unnamed: 0'])
		weather.set_index('Unnamed: 0', inplace=True)
	times = weather.index

	# location (use a default or allow override from cfg)
	lat = cfg.get('lat', 51.079928)
	lon = cfg.get('lon', 6.490433)
	tz = cfg.get('tz', 'Europe/Berlin')
	altitude = cfg.get('altitude', 80)
	site = location.Location(lat, lon, tz=tz, altitude=altitude, name='ProjectSite')
	solar_position = site.get_solarposition(times)

	# simple system parameters (adapted from example)
	axis_tilt = 90
	axis_azimuth = 90
	gcr = cfg.get('gcr', 0.07)
	albedo = cfg.get('albedo', 0.2)
	bifaciality = cfg.get('bifaciality', 0.85)

	# module/inverter parameters (small default module)
	module = {
		'Vmpo': 35.1,
		'Impo': 10.97,
		'Area': 1.85,
	}
	inverter = {
		'Paco': 60000,
	}

	# derive number of modules from vertical front area and module area
	# Support both vertical and horizontal configurations
	pv_type = cfg.get('pv_type', 'vertical')
	module_area = float(cfg.get('module_area_m2', module['Area']))
	if pv_type == 'vertical':
		pv_vertical_front_m2 = float(cfg.get('pv_vertical_front_m2', 0.0))
		if pv_vertical_front_m2 <= 0:
			print('Keine vertikale PV-Fläche vorhanden (0 m2) — Simulation übersprungen.')
			return None
		number_of_modules = math.floor(pv_vertical_front_m2 / module_area)
		if number_of_modules == 0:
			print('Zu wenig Fläche für ein Modul — Simulation übersprungen.')
			return None
	else:
		# horizontal: use ground footprint area to derive module count
		pv_footprint_m2 = float(cfg.get('pv_footprint_m2', 0.0))
		if pv_footprint_m2 <= 0:
			print('Keine horizontale PV-Bodenfläche vorhanden (0 m2) — Simulation übersprungen.')
			return None
		number_of_modules = math.floor(pv_footprint_m2 / module_area)
		if number_of_modules == 0:
			print('Zu wenig Fläche für ein Modul — Simulation übersprungen.')
			return None

	# prepare irradiance / effective irradiance depending on configuration
	if pv_type == 'vertical':
		# prepare pvfactors input for vertical rows
		pvrow_height = cfg.get('pv_row_height_m', 2.5)
		pvrow_width = cfg.get('pv_row_width_m', 0.5)
		# Try to use pvfactors; if it fails (e.g. shapely GEOS incompatibility), fall back to a POA-based estimate
		try:
			warnings.filterwarnings(action='ignore', module='pvfactors')
			irrad = pvfactors_timeseries(
				solar_position['azimuth'],
				solar_position['apparent_zenith'],
				axis_azimuth,
				axis_tilt,
				axis_azimuth,
				times,
				weather['dni'],
				weather['dhi'],
				gcr,
				pvrow_height,
				pvrow_width,
				albedo,
				n_pvrows=3,
				index_observed_pvrow=1,
			)
			irrad = pd.concat(irrad, axis=1)
			irrad['effective_irradiance'] = irrad['total_abs_front'] + (irrad['total_abs_back'] * bifaciality)
		except Exception as e:
			# Common issue: shapely 2.x removed lgeos attribute used by older pvfactors
			print('Warnung: pvfactors konnte nicht verwendet werden, verwende POA‑Fallback. Ursache:', e)
			# Fallback: estimate plane-of-array irradiance with pvlib.irradiance
			try:
				from pvlib import irradiance
				surface_tilt = 90.0
				surface_azimuth = 90.0
				dni = weather['dni'] if 'dni' in weather.columns else 0
				ghi = weather['ghi'] if 'ghi' in weather.columns else 0
				dhi = weather['dhi'] if 'dhi' in weather.columns else 0
				poa = irradiance.get_total_irradiance(
					surface_tilt,
					surface_azimuth,
					solar_position['apparent_zenith'],
					solar_position['azimuth'],
					dni,
					ghi,
					dhi,
				)
				irrad = pd.DataFrame(index=times)
				irrad['effective_irradiance'] = poa['poa_global'].fillna(0)
			except Exception as e2:
				# Last-resort fallback: use GHI or DNI as proxy
				print('Warnung: POA-Fallback ebenfalls fehlgeschlagen, verwende GHI/DNI-Proxies. Ursache:', e2)
				irrad = pd.DataFrame(index=times)
				if 'ghi' in weather.columns:
					irrad['effective_irradiance'] = weather['ghi'].fillna(0)
				else:
					irrad['effective_irradiance'] = weather.get('dni', pd.Series(0, index=times)).fillna(0)
	else:
		# horizontal: compute POA using pvlib.irradiance
		from pvlib import irradiance
		surface_tilt = float(cfg.get('tilt', 30.0))
		surface_azimuth = float(cfg.get('azimuth', 180.0))
		# weather must contain dni, ghi, dhi; fallback if only ghi available
		dni = weather.get('dni') if 'dni' in weather.columns else None
		ghi = weather.get('ghi') if 'ghi' in weather.columns else None
		dhi = weather.get('dhi') if 'dhi' in weather.columns else None
		if dni is None and ghi is None:
			print('Wetterdaten enthalten weder DNI noch GHI — Simulation übersprungen.')
			return None
		poa = irradiance.get_total_irradiance(surface_tilt,
								surface_azimuth,
								solar_position['apparent_zenith'],
								solar_position['azimuth'],
								dni if dni is not None else 0,
								ghi if ghi is not None else 0,
								dhi if dhi is not None else 0)
		irrad = pd.DataFrame(index=times)
		irrad['effective_irradiance'] = poa['poa_global']

	# temperature model
	temp_params = PARAMS['sapm']['open_rack_glass_glass'] if 'sapm' in PARAMS else PARAMS['open_rack_glass_glass']

	# define array and system
	# estimate installed capacity per module (approx)
	module_capacity_kwp = module['Vmpo'] * module['Impo'] / 1000.0
	total_installed_capacity_kwp = module_capacity_kwp * number_of_modules

	array = pvsystem.Array(mount=pvsystem.FixedMount(surface_tilt=axis_tilt, surface_azimuth=axis_azimuth),
		                   module_parameters=module,
		                   temperature_model_parameters=temp_params,
		                   strings=1,
		                   modules_per_string=number_of_modules)
	system = pvsystem.PVSystem(arrays=[array], inverter_parameters=inverter)
	# Try to run ModelChain; if module parameters are insufficient for dc-model, fall back to a simple pvwatts-like estimate
	try:
		mc = modelchain.ModelChain(system, site, aoi_model='no_loss')
		mc.run_model_from_effective_irradiance(irrad)
		ac = mc.results.ac
		ac *= 0.9
		total_energy_kwh = ac.sum() / 1000.0
		specific_yield = total_energy_kwh / total_installed_capacity_kwp if total_installed_capacity_kwp > 0 else 0.0
	except Exception as e:
		# fallback simple estimation: energy = sum(effective_irradiance * module_area * eff * losses)
		module_eff = float(cfg.get('module_efficiency', 0.18))
		loss_factor = float(cfg.get('system_loss_factor', 0.9))
		# irrad['effective_irradiance'] is in W/m2; integrate over timestamps (assume hourly data) -> Wh/m2 per timestep = W/m2 * 1 h
		energy_wh = (irrad['effective_irradiance'] * module_area * module_eff * loss_factor).sum()
		total_energy_kwh = float(energy_wh) / 1000.0
		specific_yield = total_energy_kwh / total_installed_capacity_kwp if total_installed_capacity_kwp > 0 else 0.0

	summary = {
		'number_of_modules': int(number_of_modules),
		'installed_capacity_kwp': float(total_installed_capacity_kwp),
		'total_energy_kwh': float(total_energy_kwh),
		'specific_yield_kwh_per_kwp': float(specific_yield),
	}
	# Format and print a user-friendly German summary
	def _fmt_int_de(n: int) -> str:
		return f"{n:,}".replace(',', '.')

	def _fmt_float_de(x: float, decimals: int = 2) -> str:
		s = f"{x:,.{decimals}f}"
		# transform en-US grouping (comma) and decimal (dot) to German style: grouping '.' and decimal ','
		s = s.replace(',', 'X').replace('.', ',').replace('X', '.')
		return s

	msg_lines = [
		'PV-Simulation abgeschlossen — Zusammenfassung:',
		f"  Anzahl Module: {_fmt_int_de(int(summary.get('number_of_modules', 0)))}",
		f"  Installierte Leistung: {_fmt_float_de(float(summary.get('installed_capacity_kwp', 0.0)), 2)} kWp",
		f"  Jahresenergie (geschätzt): {_fmt_float_de(float(summary.get('total_energy_kwh', 0.0)), 2)} kWh",
		f"  Spezifischer Ertrag: {_fmt_float_de(float(summary.get('specific_yield_kwh_per_kwp', 0.0)), 4)} kWh/kWp",
	]
	print('\n'.join(msg_lines))
	return summary


if __name__ == '__main__':
	print('Dieses Modul stellt die Funktion run_simulation_from_cfg(cfg) bereit. Es läuft keine Simulation beim Import.')


class PVSimulator:
	"""Objektorientierter Wrapper für pvlib-basierte Simulationen.

	Nutzung:
		sim = PVSimulator(weather_csv=...)
		res = sim.run(cfg)
	"""

	def __init__(self, weather_csv: str | Path = None):
		self.weather_csv = Path(weather_csv) if weather_csv is not None else None

	def run(self, cfg: dict):
		"""Run simulation using existing helper. Returns summary dict or None."""
		return run_simulation_from_cfg(cfg, weather_csv=self.weather_csv)


def get_default_simulator():
	"""Convenience factory using repo default weather path."""
	return PVSimulator(weather_csv=WEATHER_CSV_DEFAULT)


