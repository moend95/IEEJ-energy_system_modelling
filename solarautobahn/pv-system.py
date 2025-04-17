"""
Beispiel für die Simulation eines PV-Systems mit pvlib
Author: Moritz End
"""
import os
import pandas as pd
import pvlib
from pvlib.pvsystem import PVSystem, FixedMount
from pvlib.location import Location
from pvlib.modelchain import ModelChain
from pvlib.temperature import TEMPERATURE_MODEL_PARAMETERS
import matplotlib.pyplot as plt

base_dir = os.path.dirname(os.path.abspath(__file__))
file_path = os.path.join(base_dir, 'weather_data/dwd_data_solar_10min_koeln_2020-2023.csv')
weather_data = pd.read_csv(file_path, index_col='datetime', parse_dates=['datetime'])

weather_data = weather_data.loc["2022-01-01 00:00:00":"2022-12-31 23:50:00"] # Ein Jahr
#weather_data_hourly = weather_data.resample('H').mean() #Für stündliche Daten

# Modellparameter
temperature_model_parameters = pvlib.temperature.TEMPERATURE_MODEL_PARAMETERS['sapm']['open_rack_glass_glass']
sandia_modules = pvlib.pvsystem.retrieve_sam('cecmod')

cec_inverters = pvlib.pvsystem.retrieve_sam('cecinverter')

sandia_module = sandia_modules['Jinko_Solar__Co___Ltd_JKM400M_72L']
cec_inverter = cec_inverters['ABB__UNO_2_0_I_OUTD_S_US__277V_']

# Standort
location = Location(latitude=51.018799, longitude=6.462683)

# DataFrame für die Ergebnisse
results_df = pd.DataFrame(index=weather_data.index)

# PV-Systenm
system = PVSystem(
        surface_tilt=30,
        surface_azimuth=180,
        module_parameters=sandia_module,
        inverter_parameters=cec_inverter,
        temperature_model_parameters=temperature_model_parameters,
        modules_per_string=5, #5 Module, 1 String = 2000 Wp
        strings_per_inverter=1)

 # ModelChain-Objekt
mc = ModelChain(system, location, aoi_model='physical', spectral_model='no_loss', temperature_model='sapm')

# Modell berechnen
mc.run_model(weather_data)

results = (mc.results.ac).to_frame(name='PV Simulation [W]')

# Ergebnisse anzeigen
print(results)

#Ergebnisse plotten
results.plot()
plt.show()


#Validierung mit Spez. Jahresertrag
annual_energy = (results.sum()/6 ) / 1000 # in kWh
spec_energy_yield = annual_energy / 2 # kWh/kWp
print('Spezifischer Jahresertrag:', spec_energy_yield, 'kWh/kWp')