import os
import pandas as pd
import matplotlib.pyplot as plt

# OPTION 1 - Import

# #HILFSFUNKTIONEN
# from merge_teilprojekte_test.functions.hilfsfunktionen import *

# #PV IMPORTS
# from merge_teilprojekte_test.functions.functions_weather_data import DWDWeatherConfig, DWDWeatherFetcher
# from merge_teilprojekte_test.functions.pv_baukasten import PV_System, PV_TYPEN

# #INDUSTRIE IMPORT
# from merge_teilprojekte_test.functions.Industriegebiet import IndustryLoadAggregator

# #ENERGIELANDSCHAFT IMPORT
# from merge_teilprojekte_test.functions.Energielandschaft import main

# OPTION 2 - Import

#HILFSFUNKTIONEN
from functions.hilfsfunktionen import *

#PV IMPORTS
from functions.functions_weather_data import DWDWeatherConfig, DWDWeatherFetcher
from functions.pv_baukasten import PV_System, PV_TYPEN

#INDUSTRIE IMPORT
from functions.Industriegebiet import IndustryLoadAggregator

#ENERGIELANDSCHAFT IMPORT
from functions.Energielandschaft import main

# ------------------------------------------------------------
# 1) Wetterdaten laden (CSV ODER DWD)
# ------------------------------------------------------------
#WETTERDATEN CSV
USE_EXISTING_WEATHER = True
weather_csv = "./functions/inputs/wetter_daten_15min.csv"

if USE_EXISTING_WEATHER:
	print("→ Verwende vorhandene Wetterdaten-CSV")
	weather_df = pd.read_csv(weather_csv, index_col=0, parse_dates=True)
	weather_df.index = pd.to_datetime(weather_df.index, utc=True).tz_convert(None)
else:
	print("→ Hole Wetterdaten neu vom DWD")
	cfg = DWDWeatherConfig(
		coords=(51.08579, 6.47554),
		start="2022-01-01",
		end="2022-12-31",
		station_id=None,
		auto_select=False,
		min_quality=0.95,
		save_path=weather_csv,
	)
	weather_df = DWDWeatherFetcher(cfg).run()
# --------------------------------------------------
# Data Frame für Ergebnisse
# --------------------------------------------------
res_df = pd.DataFrame()



# --------------------------------------------------
# Directories
# --------------------------------------------------
base_input = "./functions/inputs"
output_dir = os.path.join(base_input, "punkte")
os.makedirs(output_dir, exist_ok=True)



# ------------------------------------------------------------
# 2) SOLARAUTOBAHN
# ------------------------------------------------------------
#INPUT für PV SOLARAUTOBAHN
geojson_file_1 = "a44_beide.geojson"
geojson_path_1 = os.path.join(base_input, "geometrien", geojson_file_1)
step_size_default = 2000

#step_size = hf.get_float_input(f'Schrittweite für PV Berechnung [default: {step_size_default}m]: ', step_size_default)
#100, [PV_TYPEN[1]]
print('\n \nPV abfrage zu folgender Geometrie:\n', geojson_file_1)
step_size_1, pv_auswahl_1 = get_pv_configuration(step_size_default, PV_TYPEN)

# hier kannst du auch mehrere Typen übergeben, z.B. [PV_TYPEN[0], PV_TYPEN[3], ...]
# 0 = Windschutzwand, 1 = Schallschutzwand, 2 = Schallschutzwand_Dach, 3 = Böschung
pv_system = PV_System(
	geojson_path=geojson_path_1,
	pvtypes=pv_auswahl_1, #[PV_TYPEN[0],PV_TYPEN[3]],
	step_size=step_size_1,             # Punktabstand in m
	weather_df=weather_df,
	base_output_dir=output_dir,
)

# ------------------------------------------------------------
# 3) Punkte + Azimut für alle gewählten PV-Typen generieren
# ------------------------------------------------------------
pv_points_return_1 = pv_system.generate_pv_points()

print("Berechnete PV-Typen:")
for pv_type in pv_system.pvtypes:
	print(" -", pv_type)

# ------------------------------------------------------------
# 4) Jahresenergie je PV-Typ simulieren + Zeitreihe plotten
# ------------------------------------------------------------
print("\nJahresenergie je PV-Typ:")
for pv_type in pv_system.pvtypes:
	# CSV-Name so, wie ihn generate_pv_points gespeicher hat
	csv_name = f"punkte_{pv_type.id}_{pv_type.name}.csv".replace(" ", "_")
	csv_path = os.path.join(output_dir, csv_name)

	energy_kwh_1, total_ac_1 = pv_system.simulate_pv_type_energy(pv_type, csv_path)
	total_ac_1= total_ac_1.clip(lower=0) /1000
	print(f"  {pv_type.name}: {energy_kwh_1:.1f} kWh")
	res_df[pv_type.name] = total_ac_1.values






#--------------------------------------------------------
#INDUSTRIEGEBIET
#--------------------------------------------------------
df_industrie = pd.DataFrame()
industry_aggregator = IndustryLoadAggregator()

print("Welche Daten sollen genutzt werden?")
print("1) Ohne Wärme/Kälte Stromverbrauch (Nutzung fossiler Energiequellen für Wärme, keine Kälte)")
print("2) Mit Wärme/Kälte Stromverbrauch (Nutzung reversibler Luftwärmepumpen und Geothermie-Sonden)")
mode_choice = input("Auswahl (1 oder 2): ").strip()

print("Verfügbare Unternehmen:")
for i, unternehmen in enumerate(industry_aggregator.UNTERNEHMEN, 1):
	print(f"{i}. {unternehmen}")

auswahl_input = input(
	"Geben Sie die Nummern der Unternehmen ein, die betrachtet werden sollen. \n"
	"(Durch Kommas trennen, Doppelauswahl möglich, Minimal 1 Unternehmen, Maximal 5 Unternehmen, z.B. 1,3,5)\n "
)
selection_indices = industry_aggregator.parse_selection_input(auswahl_input)

if selection_indices is None:
	raise ValueError("Ungültige Auswahl für Industriegebiet. Skript wird beendet.")

df_industrie, csv_path_industrie, plot_path_industrie = industry_aggregator.run(
	mode_choice=mode_choice,                            #JBtemp: Inputs aus IOtypes -> is_heat_cooling_electric aktuell bool, hier str
	selection_indices=selection_indices,                #JBtemp: Inputs aus IOtypes -> companies aktuell list[str], hier list[int]
)

if df_industrie is None:
	raise RuntimeError("Industrie-Lastgang konnte nicht berechnet werden.")

res_df['Last_Industrie [kW]'] = 0 - df_industrie['Gesamtlast [kW]']
print(df_industrie.head())
print(df_industrie.describe())
print(f"CSV gespeichert unter: {csv_path_industrie}")
if plot_path_industrie:
	print(f"Plot erstellt unter: {plot_path_industrie}")
print(res_df.head())
print(res_df.describe())






#--------------------------------------------------------
#ENERGIELANDSCHAFT
#--------------------------------------------------------
# PV-Ausrichtung zentral hier definieren: "horizontal", "vertical" oder "horizontal_tracking"
pv_ausrichtung = "horizontal"      #JBtemp: Input aus IOTypes: el_pv_type aktuell str, hier string -> vergleichen

# Traktorparameter zentral hier definieren
tractor_width_m = 12.0              #JBtemp: sowohl in IOtypes als auch in run merge defaults -> bleibt so
tractor_length_m = 15.0             #JBtemp: sowohl in IOtypes als auch in run merge defaults -> bleibt so
tractor_turn_radius_m = 9.0         #JBtemp: sowohl in IOtypes als auch in run merge defaults -> bleibt so

#agri PV code für geojson und agri pv länge
agri_result = main(
	interactive=True,
	output_dir="./outputs",
	pv_ausrichtung=pv_ausrichtung,
	tractor_width_m=tractor_width_m,
	tractor_length_m=tractor_length_m,
	tractor_turn_radius_m=tractor_turn_radius_m,
)
agri_pv_laenge = agri_result.get("metadata").get('total_rows_length_m')

agri_pv_ausrichtung = agri_result.get("ausrichtung")
print('Ausrichtung: ', agri_pv_ausrichtung)

a = agri_pv_ausrichtung.lower()
print(a)

if a == "horizontal":
	pv_auswahl_2 = [PV_TYPEN[6]]
	module_pro_meter = 2
elif a == "horizontal_tracking":
	pv_auswahl_2 = [PV_TYPEN[4]]
	module_pro_meter = 2
elif a == "vertical":
	pv_auswahl_2 = [PV_TYPEN[5]]
	module_pro_meter = 1
else:
	pv_auswahl_2 = [PV_TYPEN[6]]
	module_pro_meter = 2
	print('Agri PV Typ unbestimmt, Berechnung basierend auf geneigter PV ohne Tracking')


if agri_result.get("success"):
	print("✓ Verarbeitung erfolgreich abgeschlossen!")
	print(f'Länge der PV Reihen: {agri_pv_laenge:.1f}')
else:
	print(f"✗ Verarbeitung abgebrochen: {agri_result.get('error')}")


#INPUT für PV Baukasten - ENERGIELANDSCHAFT
geojson_file_2 = "Agri_PV_Centroid.geojson"
geojson_path_2 = os.path.join(base_input, "geometrien", geojson_file_2)
step_size_default = 1000

#step_size = hf.get_float_input(f'Schrittweite für PV Berechnung [default: {step_size_default}m]: ', step_size_default)
#100, [PV_TYPEN[1]]
print('\n \nPV abfrage zu folgender Geometrie:\n', geojson_file_2)
#step_size_2, pv_auswahl_2 = get_pv_configuration(step_size_default, PV_TYPEN)

# hier kannst du auch mehrere Typen übergeben, z.B. [PV_TYPEN[0], PV_TYPEN[3], ...]
# 0 = Windschutzwand, 1 = Schallschutzwand, 2 = Schallschutzwand_Dach, 3 = Böschung
pv_system = PV_System(
	geojson_path=geojson_path_2,
	pvtypes=pv_auswahl_2, #[PV_TYPEN[0],PV_TYPEN[3]],
	step_size=step_size_default,             # Punktabstand in m
	weather_df=weather_df,
	base_output_dir=output_dir,
)

# ------------------------------------------------------------
# 3) Punkte + Azimut für alle gewählten PV-Typen generieren
# ------------------------------------------------------------
pv_points_return_2 = pv_system.generate_pv_points()

print("Berechnete PV-Typen:")
for pv_type in pv_system.pvtypes:
	print(" -", pv_type)

# ------------------------------------------------------------
# 4) Jahresenergie je PV-Typ simulieren + Zeitreihe plotten
# ------------------------------------------------------------
# CSV-Name so, wie ihn generate_pv_points gespeicher hat
csv_name = f"punkte_{pv_type.id}_{pv_type.name}.csv".replace(" ", "_")
csv_path = os.path.join(output_dir, csv_name)

print('PV Simulation:')
energy_kwh_2, total_ac_2 = pv_system.simulate_pv_type_energy(pv_type, csv_path)
print(f"  {pv_type.name}: {energy_kwh_2:.1f} kWh")

total_ac_2.clip(lower=0)

agri_pv_energy = energy_kwh_2*agri_pv_laenge*module_pro_meter
print('Module pro Meter: ',module_pro_meter)
print(f'Energielandschaft Gesamtproduktion: {agri_pv_energy:.2f} kWh')

agri_pv_total_ac = total_ac_2*agri_pv_laenge*module_pro_meter

res_df['Agri_PV'] = agri_pv_total_ac.values

agri_pv_total_ac.plot()
plt.show()

power_15min = agri_pv_total_ac.resample("15min").interpolate("linear")

print(res_df.head())