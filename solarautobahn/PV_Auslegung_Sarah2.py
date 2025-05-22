import pandas as pd
import numpy as np
from wetterdienst.provider.dwd.observation import (
    DwdObservationRequest,
    DwdObservationResolution,
    DwdObservationPeriod,
    DwdObservationParameter
)

# 1. Standort: Solarautobahn (Koordinaten)
latlon = (51.08579, 6.47554)

# 2. Anfrage definieren
request = DwdObservationRequest(
    parameter=[
        DwdObservationParameter.MINUTE_10.SOLAR.RADIATION_GLOBAL,
        DwdObservationParameter.MINUTE_10.SOLAR.RADIATION_SKY_SHORT_WAVE_DIFFUSE,
        DwdObservationParameter.MINUTE_10.TEMPERATURE_AIR.TEMPERATURE_AIR_MEAN_200,
        DwdObservationParameter.MINUTE_10.WIND.WIND_SPEED
    ],
    resolution=DwdObservationResolution.MINUTE_10,
    period=DwdObservationPeriod.HISTORICAL
)

# 3. Beste Station im Umkreis von Solarautobahn auswählen
stations_info = request.filter_by_rank(latlon=latlon, rank=20)
df_stations = stations_info.df.to_pandas()
df_top20 = df_stations.head(20)  # nur Top 20 behalten
print(df_top20[["station_id", "name", "distance"]])

stations = request.filter_by_station_id("02667")
df = stations.values.all().df.to_pandas()

# 5. Fehlerprüfung
if df.empty:
    raise ValueError("Keine Wetterdaten verfügbar für den angegebenen Standort.")

# 6. Zeitstempel setzen und umstrukturieren
df["date"] = pd.to_datetime(df["date"])
df.set_index("date", inplace=True)
df = df.pivot(columns="parameter", values="value")
df.columns.name = None

# 7. Spalten sinnvoll benennen
df.rename(columns={
    "radiation_global": "ghi",
    "radiation_sky_short_wave_diffuse": "dhi",
    "temperature_air_mean_200": "temp_air",
    "wind_speed": "wind_speed"
}, inplace=True)

# 8. Auf 15-Minuten-Auflösung resamplen
df = df.resample("15T").interpolate("time")

# 9. Optional: Auf Jahr 2022 beschränken
df = df.loc["2022-01-01 00:00:00":"2022-12-31 23:45:00"]

# 10. Ergebnis anzeigen
df.to_csv("wetterdaten_solarautobahn_2022.csv")
print("✅ Datei wurde gespeichert als 'wetterdaten_solarautobahn_2022.csv'")
