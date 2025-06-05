import pandas as pd
import numpy as np
from wetterdienst.provider.dwd.observation import (
    DwdObservationRequest,
    DwdObservationResolution,
    DwdObservationPeriod,
    DwdObservationParameter
)

from pvlib.solarposition import get_solarposition
from pvlib.irradiance import dni


# 1. Standort: Solarautobahn (Koordinaten)
latlon = (51.08579, 6.47554)

# Zeige alle verfügbaren Parameter für MINUTE_10
#for group in DwdObservationParameter.MINUTE_10:
#    print(f"Gruppe: {group}")
#    for param in group:
#        print(f"   → {param}")

# 2. Anfrage definieren - da muss noch direkte Strahlung berechnet werden!
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

# 3. Station im Umkreis von Solarautobahn auswählen - Filter hinzufügen: -9.9999999 = fehlerhafte Daten, J/cm^2 in Watt umrechnen! Interpolieren-Code Moritz als Vorlage!
stations_info = request.filter_by_rank(latlon=latlon, rank=15)
df_stations = stations_info.df.to_pandas()
df_top = df_stations.head(15)  # nur Top 15 behalten oder so
print(df_top[["station_id", "name", "distance"]])

# 4. Funktion zur Auswahl der besten Station
required_parameters = [
    "radiation_global",
    "radiation_sky_short_wave_diffuse",
    "temperature_air_mean_200",
    "wind_speed"
]

# 5. Station im Umkreis automatisch nach Datenqualität auswählen
def get_valid_station_df(request, station_ids, min_quality=0.8): # definierte Funktion: prüft eine Liste von Stationen (station_ids) und gibt die erste zurück, die alle geforderten Parameter mit mindestens 80% gültigen Werten hat.
    for station_id in station_ids:                               # Die Funktion geht alle Stationen nacheinander durch (momentan top 15)
        try:
            station_data = request.filter_by_station_id(station_id) #try-Block damit Code bei Fehler nicht abbricht und zur nächsten Station springt
            df = station_data.values.all().df.to_pandas()           # Hier wird die aktuelle Station abgefragt

            if df.empty:                                            # wenn keine Daten vorliegen wird Station wieder übersprungen
                continue

            df["value"] = df["value"].replace(-9.9999990, np.nan)  # Die fehlerhaften Werte -9.9999990 werden durch NaN ersetzt

            # Prüfen, ob alle geforderten Parameter mit ausreichender Qualität vorhanden sind:
            grouped = df.groupby("parameter")["value"].apply(lambda x: x.notna().mean())            # gruppiert die Daten nach Wetterparameter (ghi, dhi, temp), "x.notna().mean()": berechnet für jeden Parameter den Anteil an gültigen Werten
            if all(p in grouped.index and grouped[p] >= min_quality for p in required_parameters):  # es wird geprüft, ob alle geforderten Parameter vorhanden sind und mind.gualität haben
                print(f" Station {station_id} erfüllt Kriterien.")                                  # Die erste passende Station wird zurückgegeben
                return df, station_id

        except Exception as e:
            print(f" ! Fehler bei Station {station_id}: {e}")       # Falls irgendetwas schiefgeht, wird die Fehlermeldung ausgegeben, aber die nächste Station geprüft.
            continue

    raise ValueError("Keine geeignete Wetterstation mit allen Parametern und ausreichender Qualität gefunden.")     # Wenn keine einzige Station passt, wird ein Fehler ausgelöst.

# 5.2 Auswahl durchführen
top_station_ids = df_top["station_id"].tolist()                         # df_top = Tabelle mit Top15 Stationen
df, valid_station_id = get_valid_station_df(request, top_station_ids)   # get_valid_station_df() Funktion aufrufen, um die beste Station zu finden.
print(f"Verwendete Station: {valid_station_id}")

# 6. Zeitstempel setzen und umstrukturieren
df["date"] = pd.to_datetime(df["date"])                 # Zeitspalte als Zeitobjekt umwandeln
df.set_index("date", inplace=True)                      # "date" wird Index (Zeitreihe)
df = df.pivot(columns="parameter", values="value")      # Spalten: parameter-Namen, Zellen: Werte
df.columns.name = None                                  # entfernt Zusatznamen aus Spaltenüberschrift

# 7. Spalten sinnvoll benennen
df.rename(columns={
    "radiation_global": "ghi",
    "radiation_sky_short_wave_diffuse": "dhi",
    "temperature_air_mean_200": "temp_air",
    "wind_speed": "wind_speed"
}, inplace=True)

# 8. Einheitenumrechnung: J/cm² → W/m² (bei 600s = 10min)
for col in ["ghi", "dhi"]:
    if col in df.columns:
        df[col] = df[col] * 10000 / 600  # = 16.67

# 9. Resample auf 10-Minuten-Zeitraster und lineare Interpolation
df = df.resample("10T").interpolate("time")


# 10. Zenitwinkel (Sonnenstand) korrekt berechnen
from pvlib.solarposition import get_solarposition
from pvlib.irradiance import dni

# 11. Zeitzone korrekt setzen
df.index = df.index.tz_convert("Europe/Berlin")

solpos = get_solarposition(df.index, latitude=latlon[0], longitude=latlon[1])
df["zenith"] = solpos["zenith"]

# 12. DNI nur berechnen, wenn zenith < 90 und Daten gültig
mask = df[["ghi", "dhi", "zenith"]].notna().all(axis=1)
df["dni"] = np.where(
    mask,
    dni(ghi=df["ghi"], dhi=df["dhi"], zenith=df["zenith"]),
    np.nan
)
# 13. Ergebnis speichern
df.to_csv(r"C:\Users\sarah\OneDrive\Dokumenty\GitHub\IEEJ-energy_system_modelling\Input\wetterdaten_solarautobahn_2022.csv", index=True)
print("Datei gespeichert: wetterdaten_solarautobahn_2022.csv")

print(df.index[:5])
print(df.index.tz)  # Muss z.B. Europe/Berlin anzeigen


import matplotlib.pyplot as plt


# Erster einfacher Plot: zeigt die Strahlungswerte (ghi, dhi, dni) im Tagesverlauf
df[["ghi", "dhi", "dni"]].loc["2022-06-21 04:00":"2022-06-21 22:00"].plot()
plt.ylabel("W/m²")
plt.title("Strahlungsdaten am 21. Juni 2022 (Solarautobahn)")
plt.grid() # Raster hinzufügen
plt.show() # plot anzeigen

#Zweiter Plot: Strahlung und Zenitwinkel (Sonnenstand) gleichzeitig darstellen
fig, ax1 = plt.subplots()

ax1.set_ylabel("Strahlung [W/m²]")
df[["ghi", "dhi", "dni"]].loc["2022-06-21"].plot(ax=ax1)

#zweite Y-Achse – für Zenitwinkel in Grad
ax2 = ax1.twinx() # 0° = Sonne steht am höchsten (bei 0= im Zenith = in den Tropne möglich), <90° Sonne ist über dem Horizont, > 90° Sonne ist unter dem Horizont (Nacht)
ax2.set_ylabel("Zenitwinkel [°]")
# Zenitwinkel als gestrichelte graue Linie über den Tag
df["zenith"].loc["2022-06-21"].plot(ax=ax2, color="gray", style="--") #graue gestrichelte Linie

plt.title("Solarstrahlung und Sonnenstand am 21. Juni 2022")
plt.grid()
plt.show()
