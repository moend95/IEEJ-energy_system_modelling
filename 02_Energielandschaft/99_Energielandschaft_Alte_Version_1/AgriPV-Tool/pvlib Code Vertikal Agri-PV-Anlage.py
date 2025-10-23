
"""
Created on Wed Jul 31 19:44:32 2024

@author: pister
"""

import pandas as pd
from pvlib import pvsystem
from pvlib import location
from pvlib import modelchain
from pvlib.temperature import TEMPERATURE_MODEL_PARAMETERS as PARAMS
from pvlib.bifacial.pvfactors import pvfactors_timeseries
import matplotlib.pyplot as plt
import warnings

# Shapely-Warnungen beim Import von pvfactors unterdrücken
warnings.filterwarnings(action='ignore', module='pvfactors')

# Wetterdaten laden
file_path = 'pvlib_TMY_Demoflaeche.csv'
weather_data = pd.read_csv(file_path)

# Zeit-Spalte in datetime konvertieren
weather_data['Unnamed: 0'] = pd.to_datetime(weather_data['Unnamed: 0'])
weather_data.set_index('Unnamed: 0', inplace=True)

# Standort und Zeitmerkmale definieren
lat, lon = 51.079928, 6.490433  # Standortdaten: Tagebau
tz = 'Europe/Berlin'
altitude = 80
times = weather_data.index

# System definieren
axis_tilt = 90  # Vertikal
axis_azimuth = 90  # Nach Osten ausgerichtet
gcr = 0.07
pvrow_height = 3
pvrow_width = 300
albedo = 0.4
bifaciality = 0.85

# Temperaturparameter laden
temp_model_parameters = PARAMS['sapm']['open_rack_glass_glass']

# Benutzerdefinierte PV-Modulparameter
custom_module = {
    'A0': 0.9428,
    'A1': 0.02753,
    'A2': -0.002848,
    'A3': -0.0001439,
    'A4': 2.219e-05,
    'B0': 1.0,
    'B1': -0.00261,  
    'B2': 0.0003279,
    'B3': -1.458e-05,
    'B4': 2.654e-07,
    'B5': -1.732e-09,
    'C0': 1.0116,
    'C1': -0.0116,  
    'C2': -0.07993,
    'C3': -8.79359,
    'C4': 0.993,
    'C5': float('nan'),
    'C6': float('nan'),
    'C7': float('nan'),
    'FD': 1,
    'IXO': 2.22,
    'IXXO': 1.37,
    'Impo': 10.97,
    'Vmpo': 35.1,
    'Voco': 42,
    'Mbvoc': -0.105,
    'Mbvmp': -0.105,  
    'N': 1,
    'Cells_in_Series': 12,
    'Parallel_Strings': 10,
    'Aisc': 0.004632,  
    'Isco': 11.62,
    'Aimp': -0.004404,
    'Bvoco': -0.13048,
    'Bvmpo': -0.105,
    'Area': 1.85 
}

# Benutzerdefinierte Wechselrichterparameter
custom_inverter = {
    'Name': 'SUN2000-60KTL-M0',
    'Paco': 60000,  
    'Pdco': 66000,  
    'Vdco': 600,    
    'C0': -2.91984e-08,  
    'C1': 1.3e-05,       
    'C2': -0.000421,     
    'C3': -0.000925,     
    'Pso': 2,            
    'Pnt': 2,            
    'Vdcmax': 1100,      
    'Idcmax': 132,       
    'Mppt_low': 200,     
    'Mppt_high': 1000,   
    'CEC_Date': float('nan')  
}

# Standort erstellen und Sonnenpositionsdaten abrufen
site_location = location.Location(lat, lon, tz=tz, altitude=altitude, name='Tagebau')
solar_position = site_location.get_solarposition(times)

# Montagesystem definieren (in diesem Fall feststehend)
fixed_mount = pvsystem.FixedMount(surface_tilt=axis_tilt, surface_azimuth=axis_azimuth)

# Von der pvfactors-Umrechnung Vorder- und Rückseitenbestrahlung erhalten
irrad = pvfactors_timeseries(solar_position['azimuth'],
                             solar_position['apparent_zenith'],
                             fixed_mount.surface_azimuth,
                             fixed_mount.surface_tilt,
                             axis_azimuth,
                             times,
                             weather_data['dni'],
                             weather_data['dhi'],
                             gcr,
                             pvrow_height,
                             pvrow_width,
                             albedo,
                             n_pvrows=3,
                             index_observed_pvrow=1
                             )

# In pandas DataFrame umwandeln
irrad = pd.concat(irrad, axis=1)

# Effektive Bifacial-Bestrahlung mithilfe der AOI-korrigierten Zeitreihenwerte erstellen
irrad['effective_irradiance'] = (
    irrad['total_abs_front'] + (irrad['total_abs_back'] * bifaciality)
)

# PV-Array mit benutzerdefinierten Modulparametern definieren
module_capacity_kwp = custom_module['Vmpo'] * custom_module['Impo'] / 1000
num_modules_per_string = 26
num_strings = 6
total_modules_per_inverter = num_modules_per_string * num_strings
total_installed_capacity_per_inverter_kwp = module_capacity_kwp * total_modules_per_inverter

# Anzahl der Wechselrichter
number_of_inverters = 315

# Gesamt installierte Leistung in kWp
total_installed_capacity_kwp = total_installed_capacity_per_inverter_kwp * number_of_inverters

array = pvsystem.Array(mount=fixed_mount,
                       module_parameters=custom_module,
                       temperature_model_parameters=temp_model_parameters,
                       strings=num_strings,
                       modules_per_string=num_modules_per_string)

# PV-System mit benutzerdefinierten Wechselrichterparametern erstellen
system = pvsystem.PVSystem(arrays=[array],
                           inverter_parameters=custom_inverter)

# ModelChain erfordert einen Wert für den Parameter aoi_loss. pvfactors
# wendet Oberflächenreflexionsmodelle bei der Berechnung von Vorder- und Rückseitenbestrahlung an,
# daher aoi_model='no_loss' zuweisen, um Doppelzählungen von Reflexionen zu vermeiden.
mc_bifi = modelchain.ModelChain(system, site_location, aoi_model='no_loss')
mc_bifi.run_model_from_effective_irradiance(irrad)

# Ergebnisse der Simulation skalieren
mc_bifi.results.ac *= number_of_inverters

# Systemverluste von 10% hinzufügen
system_loss_factor = 0.9
mc_bifi.results.ac *= system_loss_factor

# Umwandlung der AC-Leistung in MW für die Plot-Darstellung
mc_bifi.results.ac_mw = mc_bifi.results.ac / 1e6

# Ergebnisse in 16:9-Format darstellen
plt.figure(figsize=(16, 9))
mc_bifi.results.ac_mw.plot()
plt.title('AC Leistung des Vertikalen Systems')
plt.xlabel('Zeit')
plt.ylabel('AC Leistung (MW)')
plt.legend(['Bifacial'])
plt.show()

# Ausgabe der installierten Nennleistung in der Konsole
print(f'Installierte Nennleistung: {total_installed_capacity_kwp:.2f} kWp')

# Gesamte generierte Energie in kWh berechnen
total_energy_kwh = mc_bifi.results.ac.sum() / 1000  # Summe der AC-Leistung in kWh
print(f'Gesamte Energieerzeugung im Jahr: {total_energy_kwh:.2f} kWh')

# Spezifische Leistung in kWh/kWp berechnen
specific_yield = total_energy_kwh / total_installed_capacity_kwp
print(f'Spezifische Leistung: {specific_yield:.2f} kWh/kWp')

# Monatliche Energieerzeugung in MWh berechnen
monthly_energy_kwh = mc_bifi.results.ac.resample('M').sum() / 1000  # in kWh
monthly_energy_mwh = monthly_energy_kwh / 1000  # in MWh

# Monatliche Energieerzeugung in MWh ausgeben
print("Monatliche Energieerzeugung (in MWh):")
months = monthly_energy_mwh.index.strftime('%B')
for month, energy in zip(months, monthly_energy_mwh):
    print(f"{month}: {energy:.2f} MWh")

# Monatliche Energieerzeugung in MWh darstellen
plt.figure(figsize=(16, 9))
plt.bar(months, monthly_energy_mwh, color='dodgerblue')
plt.title('Monatliche Energieerzeugung des Vertikalen Systems')
plt.xlabel('Monat')
plt.ylabel('Energieerzeugung in MWh')
plt.xticks(rotation=45)  
plt.tight_layout()  
plt.show()



# # Daten für extrahieren
# july_6th = mc_bifi.results.ac_mw['2021-05-14']

# # Plot results in 16:9 format für den 06.07
# plt.figure(figsize=(16, 9))
# july_6th.plot()
# plt.title('AC Leistung des Vertikalen Systems am 06.07.2021')
# plt.xlabel('Zeit')
# plt.ylabel('AC Leistung (MW)')
# plt.legend(['Bifacial'])
# plt.show()
