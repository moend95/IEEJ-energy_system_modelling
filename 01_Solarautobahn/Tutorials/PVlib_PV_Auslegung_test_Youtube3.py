import pvlib

from pvlib.modelchain import ModelChain
from pvlib.location import Location
from pvlib.pvsystem import PVSystem, Array, FixedMount
from pvlib.temperature import TEMPERATURE_MODEL_PARAMETERS

import matplotlib.pyplot as plt
import pandas as pd

# Ost-West Ausrichtung berücksichtigen
modules_per_string = 4
strings_per_inverter = 1

latitude = 51.03384
longitude = 6.474917

location = Location(latitude=latitude, longitude=longitude, tz='Europe/Berlin', altitude=60, name='TH Cologne')

sandia_modules = pvlib.pvsystem.retrieve_sam('SandiaMod')
cec_inverters = pvlib.pvsystem.retrieve_sam('CECInverter')

module = sandia_modules['Canadian_Solar_CS6X_300M__2013_']
inverter = cec_inverters['ABB__PVI_3_0_OUTD_S_US__208V_']

temperature_parameters = TEMPERATURE_MODEL_PARAMETERS['sapm']['open_rack_glass_glass']

times = pd.date_range(start='2021-07-01', end='2021-07-07', freq='1min', tz=location.tz)

clearsky = location.get_clearsky(times)

# Korrigierte Array-Definition
arrays = [
    Array(mount=FixedMount(surface_tilt=30, surface_azimuth=270),
          module_parameters=module,
          temperature_model_parameters=temperature_parameters,
          modules_per_string=modules_per_string,
          strings=strings_per_inverter,
          name='Westfacing Array'),

    Array(mount=FixedMount(surface_tilt=30, surface_azimuth=90),
          module_parameters=module,
          temperature_model_parameters=temperature_parameters,
          modules_per_string=modules_per_string,
          strings=strings_per_inverter,
          name='Eastfacing Array')
]

system = PVSystem(arrays=arrays, inverter_parameters=inverter)
modelchain = ModelChain(system, location)

modelchain.run_model(clearsky)

fig, ax = plt.subplots()

modelchain.results.dc[0].p_mp.plot(label=system.arrays[0].name, ax=ax)      #dc = direct current, p_mp = power at maximum power point
modelchain.results.dc[1].p_mp.plot(label=system.arrays[1].name, ax=ax)
modelchain.results.ac.plot(label='Inverter', ax=ax)                         # total energy yield = ac
plt.ylabel('Output [W]')                                                    # ac energy through inverter = ac energy yield
plt.legend()
plt.show()
