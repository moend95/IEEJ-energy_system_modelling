import pvlib

from pvlib.modelchain import ModelChain
from pvlib.location import Location
from pvlib.pvsystem import PVSystem
from pvlib.temperature import TEMPERATURE_MODEL_PARAMETERS

import pandas as pd

modules_per_string = 4
strings_per_inverter = 1

latitude = 51.03384
longitude = 6.474917

location = Location(latitude=latitude, longitude=longitude, tz='Europe/Berlin', altitude=60, name='TH Cologne')

sandia_modules = pvlib.pvsystem.retrieve_sam(' SandiaMod')
cec_inverters = pvlib.pvsystem.retrieve_sam('CECInverter')

module = sandia_modules['Canadian_Solar_CS6X_300M__2013_']
inverter = cec_inverter['ABB__MICRO_0_25_I_OUTD_US_208__208V_']

temperature_parameters = TEMPERATURE_MODEL_PARAMETERS['sapm']['open_rack_glass_glass']

system = PVSystem(surface_tilt=30, surface_azimuth=180,
                  module_parameters=module, inverter_parameters=inverter,
                  temperature_model_parameters=temperature_parameters,
                  modules_per_string=modules_per_string,
                  strings_per_inverter=strings_per_inverter)

modelchain = ModelChain(system, location)

times = pd.date_range(start='2021-07-01', end='2021-07-07', freq='1min', tz=location.tz)

clearsky = location.get_clearsky(times)

