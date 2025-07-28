import pandas as pd
import numpy as np
from datetime import datetime
from wetterdienst.provider.dwd.observation import (
    DwdObservationRequest,
    DwdObservationResolution,
    DwdObservationPeriod,
    DwdObservationParameter
)
from pvlib.solarposition import get_solarposition
from pvlib.irradiance import dni
import matplotlib.pyplot as plt

def fetch_weather_data(
    coords=(51.08579, 6.47554),
    start="2022-01-01",
    end="2022-12-31",
    station_id=None,    # Stations ID angeben; Wenn = None, wird die Station automatisch bestimmt
    auto_select=True,
    min_quality=0.95,
    save_path=None,     # Ort zum Abspeichern hier angeben
    plot_date=None      # hier Datum eingeben das geplottet werden soll wenn man Strahlungsdaten ansehen möchte
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

# Wenn Station ID angegeben werden dessen Daten direkt verwendet und rest übersprungen
    if station_id:
        stations_info = request.filter_by_station_id(station_id)
        valid_station_id = station_id
# Falls keine Station ID übergeben wurde, wird anhand der Koordinaten (coords)
# welche die 15 (rank = 15) nächstliegenden Stationen sind und ausgewertet:
    else:
        stations_info = request.filter_by_rank(latlon=coords, rank=15)
        df_top = stations_info.df.to_pandas().head(15)
# Benutzer wird Liste angezeigt, wenn auto_select = False
# Station manuell eintippen:
        if not auto_select:
            print(df_top[["station_id", "name", "distance"]])
            valid_station_id = input("Bitte geben Sie eine station_id ein: ")
# Wenn auto_select = True, dann wählt das Programm automatisch die beste Station aus:
        else:
            required_parameters = [
                "radiation_global",
                "radiation_sky_short_wave_diffuse",
                "temperature_air_mean_200",
                "wind_speed"
            ]
# geht alle 15 Stationen nacheinander durch:
            for sid in df_top["station_id"]:
                try:
                    station_data = request.filter_by_station_id(sid)
                    df = station_data.values.all().df.to_pandas()
                    if df.empty:
                        continue
                    # Fehlerhafte Daten (z.B. -999) werden durch NaN ersetzt (also "nicht vorhanden")
                    df["value"] = df["value"].replace(-999, np.nan)
                    # genug  gültige Werte vorhanden? min_quality=0.95, dann wird Station ausgewählt; Schleife wird abgebrochen (break)
                    grouped = df.groupby("parameter")["value"].apply(lambda x: x.notna().mean())
                    if all(p in grouped.index and grouped[p] >= min_quality for p in required_parameters):
                        valid_station_id = sid
                        break
                # Wenn nicht erfüllt wird Fehler ausgegeben:
                except:
                    continue
            else:
                raise ValueError("Keine geeignete Wetterstation gefunden.")

        stations_info = request.filter_by_station_id(valid_station_id)

# lädt alle Wetterdaten für die gewählte Station und Zeitraum als DataFrame
    df = stations_info.values.all().df.to_pandas()
    df["value"] = df["value"].replace(-999, np.nan)
    df["date"] = pd.to_datetime(df["date"]) # Konvertiert Datumsspalte zu einem datetime-Objekt
    df.set_index("date", inplace=True)
    df = df.pivot(columns="parameter", values="value")
    df.rename(columns={
        "radiation_global": "ghi",
        "radiation_sky_short_wave_diffuse": "dhi",
        "temperature_air_mean_200": "temp_air",
        "wind_speed": "wind_speed"
    }, inplace=True)
    # Umrechnung der Strahlungsdaten von J/cm² → W/m² (bei 600s = 10min) wobei ich denke die Daten sind bereits in J/m^2, deswegen nur /600 nicht * 16,67
    for col in ["ghi", "dhi"]:
        if col in df.columns:
            df[col] = df[col] / 600

# Zeitreihe auf ein neues Zeitraster umrechnen ("10T") = alle 10 Minuten
    df = df.resample("10T").interpolate("time")
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC").tz_convert("Europe/Berlin")
    else:
        df.index = df.index.tz_convert("Europe/Berlin")
    # get_solarposition(...) = Funktion aus der pvlib-Bibliothek berechnet zu jedem Zeitstempel den Sonnenstand basierend auf: Zeit (df.index)
    solpos = get_solarposition(df.index, latitude=coords[0], longitude=coords[1])
    # Zenith Wert wird gespeichert in neuen Spalte:
    df["zenith"] = solpos["zenith"]
    # DNI = Direct Normal Irradiance = direkte Sonnenstrahlung berechnen aus ghi, dhi und zenith:
    # mask = ...notna().all(axis=1) Filtert alle Zeilen, wo ghi, dhi und zenith nicht leer sind und berechnet dann, Sonst → np.nan (also „kein Wert“)
    mask = df[["ghi", "dhi", "zenith"]].notna().all(axis=1)
    df["dni"] = np.where(
        mask,
        dni(ghi=df["ghi"], dhi=df["dhi"], zenith=df["zenith"]),
        np.nan
    )

    if save_path:
        df.to_csv(save_path)
        print(f"Datei gespeichert: {save_path}")

    if plot_date:
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

    return df

# um funktions-skript hier zu testen: muss man rausnehmen wenn run skript steht
if __name__ == "__main__":
    df = fetch_weather_data(
        start="2022-01-01",
        end="2022-12-31",
        auto_select=False,
        save_path=r"C:\Users\sarah\Documents\GitHub\IEEJ-energy_system_modelling\Input\test_solarautobahn.csv",
        plot_date="2022-06-21"
    )
