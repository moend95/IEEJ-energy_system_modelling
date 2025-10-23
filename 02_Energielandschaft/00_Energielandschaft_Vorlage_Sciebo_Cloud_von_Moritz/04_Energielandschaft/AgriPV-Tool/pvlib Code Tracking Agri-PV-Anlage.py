# -*- coding: utf-8 -*-
"""
Created on Wed Jul 31 14:33:00 2024

@author: pister
"""
from pvlib.modelchain import ModelChain
from pvlib.location import Location
from pvlib.pvsystem import PVSystem, Array, SingleAxisTrackerMount
from pvlib.temperature import TEMPERATURE_MODEL_PARAMETERS
import matplotlib.pyplot as plt
import pandas as pd


# Standortdaten festlegen
location = Location(latitude=51.079928, 
                    longitude=6.490433, 
                    tz='Europe/Berlin', 
                    altitude=80,
                    name='Tagebau')

# Zeitreihe für die Simulation definieren
times = pd.date_range(start="2021-01-01", 
                      end="2021-12-31", 
                      freq="h", 
                      tz=location.tz)

# Wetterdaten laden
tmy = pd.read_csv("C:\\Users\\johan\\TH_Koeln_Masterprojekt\\IEEJ-energy_system_modelling\\02_Energielandschaft\\00_Energielandschaft_Vorlage_Sciebo_Cloud_von_Moritz\\04_Energielandschaft\\AgriPV-Tool\\pvlib_TMY_Demoflaeche.csv", index_col=0)
tmy.index = pd.to_datetime(tmy.index)

# Custom PV module definieren
custom_module = {
    'A0': 0.9408,
    'A1': 0.054204,
    'A2': -0.011043,
    'A3': 0.0008875,
    'A4': -2.097e-05,
    'B0': 1.0,
    'B1': -0.002438,  
    'B2': 0.0003103,
    'B3': -1.246e-05,
    'B4': 2.11e-07,
    'B5': -1.36e-09,
    'C0': 1.0,
    'C1': 0.009,  
    'C2': 0.091575,
    'C3': -8.79359,
    'C4': 0.993,
    'C5': 0.007,
    'C6': 1.105,
    'C7': -0.105,
    'FD': 1,
    'IXO': 3.16,
    'IXXO': 4.84,
    'Impo': 13.48,
    'Vmpo': 41.92,
    'Voco': 50.60,
    'Mbvoc': -0.1265,
    'Mbvmp': -0.126,  
    'N': 1.35,
    'Cells_in_Series': 24,
    'Parallel_Strings': 6,
    'Aisc': 0.00065,  
    'Isco': 14.23,
    'Aimp': -0.0002,
    'Bvoco': -0.1265,
    'Bvmpo': -0.126,
    'Area': 2.58}

# Custom inverter definieren
inverter = {
    'Name': 'Sungrow SG250HX',
    'Paco': 250000,
    'Pdco': 255000,
    'Vdco': 1160,
    'C0': -2.91984e-08,
    'C1': 1.3e-05,
    'C2': -0.000421,
    'C3': -0.000925,
    'Pso': 2,
    'Pnt': 2,
    'Vdxmax': 1500,
    'Idcmax': 26*12,
    'Mppt_low': 600,
    'Mppt_high': 1500,
    'CEC_Date': float('nan')}

temperature_parameters = TEMPERATURE_MODEL_PARAMETERS['sapm']['open_rack_glass_glass']

# Konfiguration des Single-Axis-Tracking-Systems
mount = SingleAxisTrackerMount(axis_tilt=0,
                               axis_azimuth=180,
                               max_angle=78,
                               backtrack=True)

# Solarpositionen berechnen
sol_pos = location.get_solarposition(times)
orientation = mount.get_orientation(solar_zenith=sol_pos['apparent_zenith'], 
                                    solar_azimuth=sol_pos['azimuth'])

# PV-Array und System konfigurieren
array = Array(mount=mount,
              module_parameters=custom_module,
              temperature_model_parameters=temperature_parameters,
              modules_per_string=32,
              strings=12)

system_sat = PVSystem(arrays=[array], inverter_parameters=inverter)

# ModelChain für das Single-Axis-Tracking-System erstellen
modelchain_sat = ModelChain(system_sat, location)

# Simulation mit den Wetterdaten ausführen
modelchain_sat.run_model(tmy)

number_of_inverters = 97
modelchain_sat.results.ac *= number_of_inverters

# Systemverluste von 10% hinzufügen
system_loss_factor = 0.90
modelchain_sat.results.ac *= system_loss_factor

# Umwandlung der AC Leistung in MW für die Plot-Darstellung
modelchain_sat.results.ac_mw = modelchain_sat.results.ac / 1e6

# Gesamtenergieerzeugung im Jahr in kWh
total_energy_kwh = modelchain_sat.results.ac.sum() / 1000  # W to kWh conversion

# Nennleistung der Anlage in kWp
total_installed_capacity_kwp = custom_module['Vmpo'] * custom_module['Impo']* array.modules_per_string*array.strings * number_of_inverters / 1000  # Annahme: Vmpo und Impo in V und A, daher in kWp umwandeln

# Spezifische Leistung in kWh/kWp
specific_performance = total_energy_kwh / total_installed_capacity_kwp

print(f"Gesamte Energieerzeugung im Jahr: {total_energy_kwh:.2f} kWh")
print(f"Installierte Nennleistung: {total_installed_capacity_kwp:.2f} kWp")
print(f"Spezifische Leistung: {specific_performance:.2f} kWh/kWp")

# Umwandlung der AC Leistung in kWh für jede Stunde und Summierung nach Monat
monthly_energy_kwh = modelchain_sat.results.ac.resample('M').sum() / 1000  # Umrechnung von W in kWh
monthly_energy_mwh = monthly_energy_kwh / 1000  # Umrechnung von kWh in MWh

# Monate als Strings für die Darstellung im Diagramm
months = monthly_energy_mwh.index.strftime('%B')

# Ergebnisse plotten
plt.figure(figsize=(16,9))
modelchain_sat.results.ac_mw.plot()
plt.title('AC Leistung des Single-Axis Tracking Systems')
plt.xlabel('Zeit')
plt.ylabel('AC Leistung (MW)')
plt.legend(['Single-Axis Tracking'])
plt.show()

# Balkendiagramm der monatlichen Energieerzeugung in MWh
plt.figure(figsize=(16, 9))
plt.bar(months, monthly_energy_mwh, color='dodgerblue')
plt.title('Monatliche Energieerzeugung des Single-Axis Tracking Systems')
plt.xlabel('Monat')
plt.ylabel('Energieerzeugung in MWh')
plt.xticks(rotation=45)  # Dreht die Monatsnamen für bessere Lesbarkeit
plt.tight_layout()  # Verbessert die Darstellung
plt.show()

# Ausgabe der monatlichen Energie in der Konsole
for month, energy in zip(months, monthly_energy_mwh):
    print(f"{month}: {energy:.2f} MWh")
