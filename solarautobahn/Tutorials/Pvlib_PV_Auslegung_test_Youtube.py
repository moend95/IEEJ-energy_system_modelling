import pvlib
from pvlib.modelchain import ModelChain         #class model chain importieren
from pvlib.location import Location
from pvlib.pvsystem import PVSystem             #import the PV system we want to simulate
from pvlib.temperature import TEMPERATURE_MODEL_PARAMETERS

import matplotlib.pyplot as plt

import pandas as pd

location = Location(latitude = 51.03384 , longitude = 6.474917, tz='Europe/Berlin', altitude=80, name='Cologne Cathedral')        # hier die punkte entlang der autobahn lesen lassen aber für beispiel hier nur ein koordinatenpunkt

sandia_modules = pvlib.pvsystem.retrieve_sam('SandiaMod')
cec_inverter = pvlib.pvsystem.retrieve_sam('CECInverter')

#----- Datenbank anzeigen ------ #
# Schauen wir uns die verfügbaren Module an
print("Verfügbare Module:")
print(sandia_modules.head())

print("\nAlle Spalten:")
print(sandia_modules.columns)

print("\nInformationen über die Datenbank:")
print(sandia_modules.info())
#
from pvlib.pvsystem import retrieve_sam

# Sandia-Datenbank laden
sandia = retrieve_sam('SandiaMod')

# Suchfunktion
def list_modules_by_keyword(keyword):
    return [name for name in sandia.columns if keyword.lower() in name.lower()]

# Beispiel: alle LONGi-Module finden
print(list_modules_by_keyword("LONGi"))

# Oder: alle Canadian Solar-Module
print(list_modules_by_keyword("Canadian"))


#
#
# # Module und Inverter Daten auslesen
# module = sandia_modules['Canadian_Solar_CS6X_300M__2013_']
# inverter = cec_inverter['ABB__MICRO_0_25_I_OUTD_US_208__208V_']
#
# # Temperaturenmodell parameter
# temperature_parameters = TEMPERATURE_MODEL_PARAMETERS['sapm']['open_rack_glass_glass']
#
# # System definition
# system = PVSystem(surface_tilt=45, surface_azimuth=180,                         # orientation defined
#                   module_parameters=module,inverter_parameters=inverter,        # module and inverter parameters
#                   temperature_model_parameters=temperature_parameters)          # temperature model parameters
#
#                                                                                                                                 # altitude=float, default = 0, from see lvl in meters
# modelchain = ModelChain(system, location)
#
# # clear sky model - hier DWD Wetterdaten verwenden für mein projekt
# times = pd.date_range(start='2021-07-01', end='2021-07-07', freq='1min', tz=location.tz)  # tz=location.tz = location timezone
# clearsky = location.get_clearsky(times)
# clearsky.plot(figsize=(16, 9))
# plt.show()
#
# modelchain.run_model(clearsky) # weatherdata = clearsky
# modelchain.results.ac.plot(figsize=(16, 9)) # ac = active power - energy yield in watt behind inverter - energy yield able to use with this system
# plt.show()