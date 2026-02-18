import os
import pandas as pd
import matplotlib.pyplot as plt

#HILFSFUNKTIONEN
from merge_teilprojekte_test.functions.hilfsfunktionen import *

#PV IMPORTS
from merge_teilprojekte_test.functions.functions_weather_data import DWDWeatherConfig, DWDWeatherFetcher
from merge_teilprojekte_test.functions.pv_baukasten import PV_System, PV_TYPEN

#INDUSTRIE IMPORT
from merge_teilprojekte_test.functions.Industriegebiet import IndustryLoadAggregator

#ENERGIELANDSCHAFT IMPORT
from merge_teilprojekte_test.functions.Energielandschaft import main



# ------------------------------------------------------------
# 1) Wetterdaten laden (CSV ODER DWD)
# ------------------------------------------------------------
#WETTERDATEN CSV
USE_EXISTING_WEATHER = True
weather_csv = "./functions/inputs/wetter_daten.csv"

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
# Directories
# --------------------------------------------------
base_input = "./functions/inputs"
output_dir = os.path.join(base_input, "punkte")
os.makedirs(output_dir, exist_ok=True)


'''
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
results_1 = pv_system.generate_pv_points()

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
	print(f"  {pv_type.name}: {energy_kwh_1:.1f} kWh")
'''




'''
#--------------------------------------------------------
#INDUSTRIEGEBIET
#--------------------------------------------------------
df_industrie = pd.DataFrame()
df_industrie = IndustryLoadAggregator().run_interactive() #return lastgang als df oder output path
#falls output path, dann die csv einlesen
print(df_industrie.head())
print(df_industrie.describe())
'''



#--------------------------------------------------------
#ENERGIELANDSCHAFT
#--------------------------------------------------------
#agri PV code für geojson und agri pv länge
result = main(interactive=True, output_dir="./outputs")
agri_pv_laenge = result.get("metadata").get('total_rows_length_m')

agri_pv_ausrichtung = result.get("ausrichtung")
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


if result.get("success"):
	print("✓ Verarbeitung erfolgreich abgeschlossen!")
	print(f'Länge der PV Reihen: {agri_pv_laenge:.1f}')
else:
	print(f"✗ Verarbeitung abgebrochen: {result.get('error')}")


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
results_2 = pv_system.generate_pv_points()

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


agri_pv_energy = energy_kwh_2*agri_pv_laenge*module_pro_meter
print('Module pro Meter: ',module_pro_meter)
print(f'Energielandschaft Gesamtproduktion: {agri_pv_energy:.2f} kWh')

agri_pv_total_ac = total_ac_2*agri_pv_laenge*module_pro_meter
agri_pv_total_ac.plot()
plt.show()