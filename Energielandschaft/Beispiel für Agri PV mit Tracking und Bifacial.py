import matplotlib.pyplot as plt
import pandas as pd
from pvlib import pvsystem, location, modelchain
from pvlib.temperature import TEMPERATURE_MODEL_PARAMETERS as PARAMS
from pvlib.bifacial.pvfactors import pvfactors_timeseries
import warnings

# Warnungen von pvfactors unterdrücken
warnings.filterwarnings(action='ignore', module='pvfactors')

# Wetterdaten einlesen
weather_data = pd.read_csv('./Input/dwd_data_solar_10min_koeln_2020-2023.csv',
                           index_col='datetime', parse_dates=['datetime'])
weather_data = weather_data.loc["2022-01-01 00:00:00":"2022-12-31 23:50:00"]
weather_data = weather_data.resample('h').mean()

# Standortinformationen
lat, lon = 50.9375, 6.9603
tz = 'Europe/Berlin'
times = weather_data.index

# Systemkonfiguration
axis_tilt = 0
axis_azimuth = 180
gcr = 0.35
max_angle = 60
pvrow_height = 3
pvrow_width = 4
albedo = 0.2
bifaciality = 0.75

# Temperaturmodell und Komponenten laden
temp_model_parameters = PARAMS['sapm']['open_rack_glass_glass']
cec_modules = pvsystem.retrieve_sam('CECMod')
cec_module = cec_modules['Canadian_Solar_Inc__CS3W_400P']
cec_inverters = pvsystem.retrieve_sam('cecinverter')
cec_inverter = cec_inverters['Enphase_Energy_Inc___D380_72_240_S1x__240V_']

# Standortobjekt erstellen
site_location = location.Location(lat, lon, tz=tz, name='Köln-Bonn')
solar_position = site_location.get_solarposition(times)
cs = site_location.get_clearsky(times)

# Tracker-Mount erstellen
sat_mount = pvsystem.SingleAxisTrackerMount(axis_tilt=axis_tilt,
                                            axis_azimuth=axis_azimuth,
                                            max_angle=max_angle,
                                            backtrack=True,
                                            gcr=gcr)

# Orientierung berechnen
orientation = sat_mount.get_orientation(solar_position['apparent_zenith'],
                                        solar_position['azimuth'])

# Irradianz mit pvfactors berechnen
irrad = pvfactors_timeseries(solar_position['azimuth'],
                             solar_position['apparent_zenith'],
                             orientation['surface_azimuth'],
                             orientation['surface_tilt'],
                             axis_azimuth,
                             times,
                             cs['dni'],
                             cs['dhi'],
                             gcr,
                             pvrow_height,
                             pvrow_width,
                             albedo,
                             n_pvrows=3,
                             index_observed_pvrow=1)

# DataFrame erstellen
irrad = pd.concat(irrad, axis=1)

# Effektive Irradianz berechnen
irrad['effective_irradiance'] = (
    irrad['total_abs_front'] + (irrad['total_abs_back'] * bifaciality)
)

# PV-Array erstellen
array = pvsystem.Array(mount=sat_mount,
                       module_parameters=cec_module,
                       temperature_model_parameters=temp_model_parameters)

# PV-System erstellen
system = pvsystem.PVSystem(arrays=[array],
                           inverter_parameters=cec_inverter)

# ModelChain erstellen und Simulation durchführen
mc_bifi = modelchain.ModelChain(system, site_location, aoi_model='no_loss')
mc_bifi.run_model_from_effective_irradiance(irrad)

# AC-Leistung pro kWp berechnen
ac_power_per_kwp = ( mc_bifi.results.ac ) / 400 # 1 KWp
print(ac_power_per_kwp)
# plotten
#ac_power_per_kwp.plot()
plt.title('AC Power per kWp')
plt.xlabel('Datetime')
plt.ylabel('AC Power (kW)')


# Feldgrößen und entsprechende Leistungen
felder = {
    'Feld 1: 1806 kW': 3, # 3 ha
    'Feld 2: 2408 kW': 4, # 4 ha
    'Feld 3: 6020 kW': 10,# 10 ha
    'Feld 4: 10234 kW': 17,# 17 ha
    'Feld 5: 12642 kW': 21,# 21 ha
    'Feld 6: 10234 kW': 17,# 17 ha
    'Feld 8: 15652 kW': 26,# 26 ha
    'Feld 9: 18060 kW': 30# 30 ha
}

# Leistung pro Hektar in kWp
leistung_pro_ha = 602  # kWp/ha

# DataFrame für die Felder erstellen
feld_df = pd.DataFrame(index=ac_power_per_kwp.index)

for feld_name, flaeche in felder.items():
    gesamtleistung_kwp = flaeche * leistung_pro_ha
    feld_df[feld_name] = ac_power_per_kwp * gesamtleistung_kwp

feld_df = feld_df.clip(lower=0) # Setze negative Werte auf 0

feld_df.plot()
plt.show()

feld_df.to_csv('IEEJ_Energielandschaft_Agri_PV.csv')

# Ergebnisse anzeigen
print(feld_df.head())