# old weather functions
import pandas as pd
import numpy as np
from datetime import datetime
import matplotlib.pyplot as plt

from wetterdienst.provider.dwd.observation import (
    DwdObservationRequest,
    DwdObservationResolution,
    DwdObservationPeriod,
    DwdObservationParameter
)

from pvlib.solarposition import get_solarposition
from pvlib.irradiance import dni


def fetch_weather_data(
    coords=(51.08579, 6.47554),
    start="2022-01-01",
    end="2022-12-31",
    station_id=None,
    auto_select=True,
    min_quality=0.95,
    save_path=None,
    plot_date=None,
    plot_range=None
):
    start_date = datetime.fromisoformat(start)
    end_date = datetime.fromisoformat(end)

    parameters = [
        DwdObservationParameter.MINUTE_10.SOLAR.RADIATION_GLOBAL,
        DwdObservationParameter.MINUTE_10.SOLAR.RADIATION_SKY_SHORT_WAVE_DIFFUSE,
        DwdObservationParameter.MINUTE_10.TEMPERATURE_AIR.TEMPERATURE_AIR_MEAN_200,
        DwdObservationParameter.MINUTE_10.WIND.WIND_SPEED
    ]

    request = DwdObservationRequest(
        parameter=parameters,
        resolution=DwdObservationResolution.MINUTE_10,
        period=DwdObservationPeriod.HISTORICAL,
        start_date=start_date,
        end_date=end_date
    )

# Wenn station_id gegeben wird diese direkt als Abfrageobjekt weiter verwendet und unter request.filter_by_station_id() aufgerufen um dessen Wetterdaten zu bekommen.
    if station_id:
        stations_info = request.filter_by_station_id(station_id)
        valid_station_id = station_id
# Wenn keine Station-ID übergeben wurde, werden jetzt 15 nächstgelegene Wetterstationen zu den gegebenen Koordinaten gesucht:
    else:
        stations_info = request.filter_by_rank(latlon=coords, rank=15)
        df_top = stations_info.df.to_pandas().head(15) # Konvertiere die Ergebnisliste in ein pandas-DataFrame
        if not auto_select:
            print(df_top[["station_id", "name", "distance"]])
            valid_station_id = input("Bitte geben Sie eine station_id ein: ")
# Wenn auto_select=True, dann soll selbst eine geeignete Station ausgewählt werden – basierend auf Datenqualität
        else:
            # Definierte Liste von Wetterparametern, die verfügbar und qualitativ gut sein müssen:
            required_parameters = [
                "radiation_global",
                "radiation_sky_short_wave_diffuse",
                "temperature_air_mean_200",
                "wind_speed"
            ]
            for sid in df_top["station_id"]: #  Starte eine Schleife über die 15 besten Stationen
                try:                         # Versuche, für jede Station die Wetterdaten zu laden. (Falls ein Fehler auftritt, geh zur nächsten Station)
                    station_data = request.filter_by_station_id(sid)        # Lade die Messdaten der aktuellen Station
                    df = station_data.values.all().df.to_pandas()           # Alle Wetterwerte als DataFrame laden
                    if df.empty:                                            # Wenn die Station gar keine Daten liefert, gehe zur nächsten (continue)
                        continue
                    df["value"] = df["value"].replace(-999, np.nan)                                             #  Ersetze fehlerhafte Daten (hier: -999) durch NaN (fehlender Wert)
                    grouped = df.groupby("parameter")["value"].apply(lambda x: x.notna().mean())                # Für jeden Wetterparameter: Berechne den Prozentsatz gültiger Werte (z.B. 95% der Datenpunkte für radiation_global sind gültig)
                    if all(p in grouped.index and grouped[p] >= min_quality for p in required_parameters):      # Prüfung auf Qualität der Werte: Alle geforderten Werte sind für mindestens 95% der Datenpunkte gültig?
                        valid_station_id = sid
                        break                                                                                   # Diese Station ist geeignet → Station-ID speichern und Schleife abbrechen
                except:                                                                                         # falls nicht überspringen und nächste Station anschauen
                    continue
            else:
                raise ValueError("Keine geeignete Wetterstation gefunden.")     # Falls keine einzige Station geeignet ist → Fehlermeldung ausgeben.

        stations_info = request.filter_by_station_id(valid_station_id)

    df = stations_info.values.all().df.to_pandas()
    df["value"] = df["value"].replace(-999, np.nan)
    df["date"] = pd.to_datetime(df["date"])
    df.set_index("date", inplace=True)
    df = df.pivot(columns="parameter", values="value")
    df.rename(columns={
        "radiation_global": "ghi",
        "radiation_sky_short_wave_diffuse": "dhi",
        "temperature_air_mean_200": "temp_air",
        "wind_speed": "wind_speed"
    }, inplace=True)

    # Temperatur von Kelvin in °C umrechnen (DWD liefert in K) - PVlib erwartet °C später
    for col in ["temp_air"]:
        if col in df.columns:
            df[col] = df[col] - 273.15

    # Strahlung in W/m² umrechnen (DWD liefert in J/m²), (600s = 10min), (cm^2 - m^2 = * 10.000) - wenn J/cm^2 wären = * 16.67 W/m^2
    for col in ["ghi", "dhi"]:
        if col in df.columns:
            df[col] = df[col] / 600  # J/m² auf W/m² umrechnen

    df = df.resample("10T").interpolate("time")

    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC").tz_convert("Europe/Berlin")
    else:
        df.index = df.index.tz_convert("Europe/Berlin")

# berechnet für jede Uhrzeit den Zenitwinkel, also wie hoch die Sonne am Himmel steht: - zenith = 0° → Sonne steht senkrecht (Mittag) zenith = 90° → Sonne am Horizont, zenith > 90° → Sonne unter dem Horizont (Nacht),
    solpos = get_solarposition(df.index, latitude=coords[0], longitude=coords[1])
    df["zenith"] = solpos["zenith"]

    # DNI ( DNI = Direct Normal Irradiance) berechnen: DNI = (GHI - DHI)/ cos(zenith) berechnung:
    #Umrechnung und Bedingung für cos(zenith):
    cos_zenith = np.cos(np.radians(df["zenith"]))               # df["zenith"] ist in Grad, np.radians(...) wandelt Grad in Bogenmaß um, weil np.cos() nur Bogenmaß versteht, cos_zenith enthält jetzt den Anteil der Sonnenstrahlung, der "gerade nach unten" trifft
    cos_zenith = np.where(cos_zenith <= 0, np.nan, cos_zenith)  # keine negativen oder 0-Werte / Bei 90° (Sonne am Horizont): cos(90°) = 0

    # DNI berechnen:
    df["dni"] = (df["ghi"] - df["dhi"]) / cos_zenith

    # Bedingung: np.where(condition, if_true, if_false) ist wie eine wenn-dann-sonst-Anweisung: DNI darf niemals größer sein als GHI
    df["dni"] = df["dni"].where(df["dni"] <= df["ghi"], np.nan)

    if save_path:
        df.to_csv(save_path)
        print(f"Datei gespeichert: {save_path}")

    if plot_date is not None:
        day = pd.to_datetime(plot_date)
        df_day = df.loc[day.strftime("%Y-%m-%d")]
        fig, ax1 = plt.subplots()
        ax1.set_ylabel("Strahlung [W/m²]")
        df_day[["ghi", "dhi", "dni"]].plot(ax=ax1)
        ax2 = ax1.twinx()
        ax2.set_ylabel("Zenitwinkel [°]")
        df_day["zenith"].plot(ax=ax2, color="gray", style="--")
        plt.title(f"Solarstrahlung und Sonnenstand am {plot_date}")
        plt.grid()
        plt.show()

    if plot_range is not None:
        start_plot, end_plot = map(pd.to_datetime, plot_range)
        if start_plot.tz is None:
            start_plot = start_plot.tz_localize("Europe/Berlin")
        if end_plot.tz is None:
            end_plot = end_plot.tz_localize("Europe/Berlin")

        df_range = df.loc[start_plot:end_plot]

        fig, ax1 = plt.subplots(figsize=(14, 6))
        df_range[["ghi", "dhi", "dni"]].plot(ax=ax1)
        ax1.set_ylabel("Strahlung [W/m²]")
        plt.title(f"Solarstrahlung im Zeitraum von {start_plot.date()} bis {end_plot.date()}")
        plt.grid()
        plt.tight_layout()
        plt.show()

    return df

# Testdurchlauf:
if __name__ == "__main__":
    df = fetch_weather_data(
        start="2022-01-01",
        end="2022-12-31",
        auto_select=False,
        save_path="../Input/old_test_solarautobahn.csv",
        plot_date="2022-07-20",
        plot_range=("2022-01-01", "2022-12-31")
    )
