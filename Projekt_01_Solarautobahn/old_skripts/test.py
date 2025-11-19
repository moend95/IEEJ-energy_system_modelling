# check_env_solarposition.py
import sys
import pandas as pd

import numpy as np
import pvlib
import wetterdienst
import matplotlib

from pvlib.solarposition import get_solarposition

print("Python :", sys.version)
print("pvlib  :", pvlib.__version__)
print("pandas :", pd.__version__)
print("numpy  :", np.__version__)
print("matplotlib:", matplotlib.__version__)
print("wetterdienst:", wetterdienst.__version__)

# Fester Test-Zeitraum
times = pd.date_range(
    "2022-07-20 00:00",
    "2022-07-20 23:50",
    freq="10min",
    tz="Europe/Berlin",
)

lat, lon = 51.08579, 6.47554

solpos = get_solarposition(times, lat, lon)

print("\nSolarposition describe():")
print(solpos[["apparent_zenith", "apparent_elevation"]].describe())

print("\nSolarposition zur Mittagszeit:")
print(solpos.loc["2022-07-20 12:00:00+02:00"])

# damit man notfalls direkt vergleichen kann
solpos.to_csv("solarpos_test.csv")
print("\nsolarpos_test.csv geschrieben.")
