import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import pvlib

# Pfad zur Datei
dateipfad = 'produkt_zehn_min_sd_20200101_20231231_15000.txt'

# Einlesen der Datei
df = pd.read_csv(
    dateipfad,
    sep=';',
    parse_dates=['MESS_DATUM'],
    date_parser=lambda x: pd.to_datetime(x, format='%Y%m%d%H%M')
)

# Umbenennen der Spalten für Klarheit
df.rename(columns={
    'MESS_DATUM': 'datetime',
    'DS_10': 'dni_j_cm2',
    'GS_10': 'ghi_j_cm2'
}, inplace=True)

df.set_index('datetime', inplace=True)

# Entfernen von Zeilen mit fehlenden Werten in den relevanten Spalten
df.dropna(subset=['dni_j_cm2', 'ghi_j_cm2'], inplace=True)

# Umrechnung von 1 J/cm² auf W/m² über 10 Minuten (600 Sekunden)
# 1 J/ (cm²*600s) -> 1 Ws/ (0.001m²*600s) = 1,67 W/m²
df['dni'] = df['dni_j_cm2'] * 16.7
df['ghi'] = df['ghi_j_cm2'] * 16.7


df.drop(columns=['dni_j_cm2', 'ghi_j_cm2', 'STATIONS_ID','  QN', 'SD_10', 'LS_10', 'eor'], inplace=True)

df[['dni', 'ghi']] = df[['dni', 'ghi']].where(df[['dni', 'ghi']] >= 0, np.nan)
# NaN-Werte linear interpolieren
df[['dni', 'ghi']] = df[['dni', 'ghi']].interpolate(method='linear')

#diffuse Strahlung berechnen
#Standortdefinition
lat =  50.8645
long = 7.1575

#Sonnenposition berechnen
solpos = pvlib.solarposition.get_solarposition(df.index,lat, long)

theta_z = solpos['zenith']


df['dhi'] = df['ghi'] - (df['dni'] * np.cos(np.radians(theta_z)))

print(df)

df.to_csv('solardata_koeln-bonn_10min_2020-2023.csv', index=True)

df['dhi'].plot()
plt.show()