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

    if station_id:
        stations_info = request.filter_by_station_id(station_id)
        valid_station_id = station_id
    else:
        stations_info = request.filter_by_rank(latlon=coords, rank=15)
        df_top = stations_info.df.to_pandas().head(15)

        if not auto_select:
            print(df_top[["station_id", "name", "distance"]])
            valid_station_id = input("Bitte geben Sie eine station_id ein: ")
        else:
            required_parameters = [
                "radiation_global",
                "radiation_sky_short_wave_diffuse",
                "temperature_air_mean_200",
                "wind_speed"
            ]
            for sid in df_top["station_id"]:
                try:
                    station_data = request.filter_by_station_id(sid)
                    df = station_data.values.all().df.to_pandas()
                    if df.empty:
                        continue
                    df["value"] = df["value"].replace(-999, np.nan)
                    grouped = df.groupby("parameter")["value"].apply(lambda x: x.notna().mean())
                    if all(p in grouped.index and grouped[p] >= min_quality for p in required_parameters):
                        valid_station_id = sid
                        break
                except:
                    continue
            else:
                raise ValueError("Keine geeignete Wetterstation gefunden.")

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

    # DNI berechnen
    cos_zenith = np.cos(np.radians(df["zenith"]))
    cos_zenith = np.where(cos_zenith <= 0, np.nan, cos_zenith)  # keine negativen oder 0-Werte

    df["dni"] = (df["ghi"] - df["dhi"]) / cos_zenith

    # Begrenzung: DNI darf niemals größer sein als GHI
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

if __name__ == "__main__":
    df = fetch_weather_data(
        start="2022-01-01",
        end="2022-12-31",
        auto_select=False,
        save_path=r"C:\Users\sarah\Documents\GitHub\IEEJ-energy_system_modelling\Input\test_solarautobahn.csv",
        plot_date="2022-06-21",
        plot_range=("2022-01-01", "2022-12-31")
    )
