# weather_dwd.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple, List
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

from wetterdienst.provider.dwd.observation import (
    DwdObservationRequest,
    DwdObservationResolution,
    DwdObservationPeriod,
    DwdObservationParameter,
)
from pvlib.solarposition import get_solarposition
from pvlib.irradiance import dirint, get_extra_radiation



# ---------------- Konfiguration ----------------

@dataclass
class DWDWeatherConfig:
    coords: Tuple[float, float] = (51.08579, 6.47554)
    start: str = "2022-01-28"
    end: str   = "2022-12-31"
    station_id: Optional[str] = None
    auto_select: bool = True
    min_quality: float = 0.95
    tz: str = "Europe/Berlin"
    save_path: Optional[str] = None
    plot_date: Optional[str] = None
    plot_range: Optional[Tuple[str, str]] = None

    use_dirint: bool = True              # robustes Modell aus GHI statt (GHI-DHI)/cosz
    min_elevation_deg: float = 3.5       # unterhalb nicht invertieren (Rauschsperre)
    dni_interp_limit: int = 3            # max. 3 Ticks à 10 min Lücken füllen

# ---------------- Hauptklasse ----------------

class DWDWeatherFetcher:
    """Klassenbasierte Version des früheren fetch_weather_data (bleibt bei 10 min-Auflösung)."""

    REQUIRED_PARAMETERS = [
        "radiation_global",
        "radiation_sky_short_wave_diffuse",
        "temperature_air_mean_200",
        "wind_speed",
    ]

    RENAME_MAP = {
        "radiation_global": "ghi",
        "radiation_sky_short_wave_diffuse": "dhi",
        "temperature_air_mean_200": "temp_air",
        "wind_speed": "wind_speed",
        "temperature_dew_point_mean_200": "temp_dew",  # K Taupunkt
        "pressure_air_site": "pressure_pa",  # Pa Luftdruck
        "humidity": "rel_hum",  # % relative feuchte
    }

    def __init__(self, cfg: DWDWeatherConfig):
        self.cfg = cfg
        self._request = DwdObservationRequest(
            parameter=self._parameters(),
            resolution=DwdObservationResolution.MINUTE_10,
            period=DwdObservationPeriod.HISTORICAL,
            start_date=datetime.fromisoformat(cfg.start),
            end_date=datetime.fromisoformat(cfg.end),
        )



    @staticmethod
    def _parameters() -> List[DwdObservationParameter]:
        return [
            DwdObservationParameter.MINUTE_10.SOLAR.RADIATION_GLOBAL,
            DwdObservationParameter.MINUTE_10.SOLAR.RADIATION_SKY_SHORT_WAVE_DIFFUSE,
            DwdObservationParameter.MINUTE_10.TEMPERATURE_AIR.TEMPERATURE_AIR_MEAN_200,
            DwdObservationParameter.MINUTE_10.WIND.WIND_SPEED,
            DwdObservationParameter.MINUTE_10.TEMPERATURE_AIR.PRESSURE_AIR_SITE,    # Luft Druck
            DwdObservationParameter.MINUTE_10.TEMPERATURE_AIR.TEMPERATURE_DEW_POINT_MEAN_200, # Taupunkt
            DwdObservationParameter.MINUTE_10.TEMPERATURE_AIR.HUMIDITY,  # relative Feuchte
        ]

    # --------- öffentlicher Einstiegspunkt ----------

    def run(self) -> pd.DataFrame:
        """Lädt und verarbeitet DWD-Daten (bleibt bei 10 min)."""
        station_id = self._select_station()
        df = self._fetch_dataframe(station_id)
        df = self._postprocess(df)
        self._maybe_save(df)
        self._maybe_plot(df)
        return df

    # --------- Stationswahl ----------

    def _select_station(self) -> str:
        if self.cfg.station_id:
            return self.cfg.station_id

        stations_info = self._request.filter_by_rank(latlon=self.cfg.coords, rank=15)
        df_top = stations_info.df.to_pandas().head(15)

        if not self.cfg.auto_select:
            print(df_top[["station_id", "name", "distance"]])
            return input("Bitte station_id eingeben: ")

        for sid in df_top["station_id"]:
            try:
                station_data = self._request.filter_by_station_id(sid)
                df = station_data.values.all().df.to_pandas()
                if df.empty:
                    continue
                df["value"] = df["value"].replace(-999, np.nan)
                grouped = df.groupby("parameter")["value"].apply(lambda x: x.notna().mean())
                if all(p in grouped.index and grouped[p] >= self.cfg.min_quality for p in self.REQUIRED_PARAMETERS):
                    return str(sid)
            except Exception:
                continue
        raise ValueError("Keine geeignete Wetterstation gefunden.")

    # --------- Daten abrufen ----------

    def _fetch_dataframe(self, station_id: str) -> pd.DataFrame:
        stations_info = self._request.filter_by_station_id(station_id)
        df = stations_info.values.all().df.to_pandas()
        if df.empty:
            raise ValueError(f"Station {station_id} lieferte keine Daten.")
        return df

    # --------- Aufbereitung ----------

    def _postprocess(self, df_raw: pd.DataFrame) -> pd.DataFrame:
        df = df_raw.copy()

        # 1) Pivot & Spaltennamen
        df["value"] = df["value"].replace(-999, np.nan)
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").pivot(columns="parameter", values="value")
        df.rename(columns=self.RENAME_MAP, inplace=True)

        # 2) Einheiten

        # Temperaturen K -> °C
        if "temp_air" in df.columns:
            df["temp_air"] = df["temp_air"] - 273.15
        if "temp_dew" in df.columns:
            df["temp_dew"] = df["temp_dew"] - 273.15

        # Druck Pa -> hPa
        # if "pressure_pa" in df.columns:
        #    df["pressure_hpa"] = df["pressure_pa"] / 100.0 - wir brauchen Pa nicht hPa

        # Strahlung J/m² pro 10min -> W/m²
        for col in ["ghi", "dhi"]:
            if col in df.columns:
                df[col] = df[col] / 600

        # 3) auf ein sauberes 10-min Raster bringen
        df = df.resample("10T").interpolate("time")

        # 4) Zeitzone: lokale Europe/Berlin-Zeit annehmen und Info entfernen
        if df.index.tz is not None:
            df.index = df.index.tz_convert(None)

        df = df.sort_index()

        # 5) Solarposition
        solpos = get_solarposition(df.index, latitude=self.cfg.coords[0], longitude=self.cfg.coords[1])
        df["zenith"] = solpos["zenith"]
        df["elevation"] = 90 - df["zenith"]  # Sonnenhöhe α
        cosz = np.cos(np.radians(df["zenith"]))

        # 6) Tages-/Qualitätsmasken
        daylight = (df["elevation"] > 0) & df["ghi"].notna() & (df["ghi"] > 0)
        valid_sun = (df["elevation"] >= self.cfg.min_elevation_deg) & (cosz > 0)

        # 7) DNI berechnen
        if self.cfg.use_dirint:
            # A) ROBUST: DNI nur aus GHI + Sonnengeometrie (kein DHI nötig)
            dni_vals = dirint(
                ghi=df["ghi"].values,  # Global horizontal irradiance [W/m²]
                solar_zenith=df["zenith"].values,  # Zenitwinkel [°]
                times=df.index,  # Zeitstempel (tz-aware)
                pressure=df["pressure_hpa"].values if "pressure_hpa" in df.columns else None,  # hPa
                temp_dew=df["temp_dew"].values if "temp_dew" in df.columns else None  # °C
            )
            dni = pd.Series(dni_vals, index=df.index)

            # sehr niedrige Sonnenstände auf 0 setzen (Rauschsperre)
            dni.loc[~valid_sun] = 0.0
        else:
            # B) KLASSISCH: Inversion aus GHI und DHI
            # DHI nie größer als GHI zulassen (plausibel clippen):
            df["dhi"] = np.minimum(df["dhi"], df["ghi"])

            dni = pd.Series(np.nan, index=df.index, dtype=float)
            # nur bei ausreichender Sonnenhöhe invertieren
            idx = valid_sun
            dni.loc[idx] = (df.loc[idx, "ghi"] - df.loc[idx, "dhi"]) / cosz[idx]
            # Nacht und sehr niedrige Sonnenstände: 0
            dni.loc[~valid_sun] = 0.0

        # 8) Physikalische Obergrenze: extraterrestrische Normalstrahlung (I0)
        doy = df.index.dayofyear.values  # 1..365/366
        i0 = get_extra_radiation(doy)  # [W/m²] auf senkrechter Fläche über Atmosphäre
        dni = np.minimum(dni.values, i0)  # DNI ≤ I0
        dni = pd.Series(dni, index=df.index)

        # 9) Nachsorge: keine negativen, nachts NaN → 0
        dni = dni.clip(lower=0)  # DNI ≥ 0
        dni.loc[~daylight] = 0.0  # nachts 0

        # 10) Nur kurze Lücken am Tag interpolieren
        dni_interp = dni.copy()
        dni_interp[~daylight] = np.nan  # nachts NICHT interpolieren
        dni_interp = dni_interp.interpolate(method="time", limit=self.cfg.dni_interp_limit)
        dni = dni_interp.fillna(0.0)  # verbleibende NaNs (z. B. Nacht) zu 0

        df["dni"] = dni

        # 11) Nach Zeitzonen-Konvertierung auf gewünschten lokalen Zeitraum begrenzen
        start_local = pd.Timestamp(self.cfg.start)
        end_local = pd.Timestamp(self.cfg.end)
        df = df.loc[start_local:end_local]

        return df





    # --------- Save & Plot ----------

    def _maybe_save(self, df: pd.DataFrame) -> None:
        if self.cfg.save_path:
            df.to_csv(self.cfg.save_path)
            print(f"Datei gespeichert: {self.cfg.save_path}")

    def _maybe_plot(self, df: pd.DataFrame) -> None:
        if self.cfg.plot_date:
            self.plot_day(df, self.cfg.plot_date)
        if self.cfg.plot_range:
            self.plot_range(df, *self.cfg.plot_range)

    @staticmethod
    def plot_day(df: pd.DataFrame, plot_date: str) -> None:
        day = pd.to_datetime(plot_date)
        df_day = df.loc[day.strftime("%Y-%m-%d")]
        fig, ax1 = plt.subplots()
        ax1.set_ylabel("Strahlung [W/m²]")
        df_day[["ghi", "dhi", "dni"]].plot(ax=ax1)
        ax2 = ax1.twinx()
        ax2.set_ylabel("Zenit [°]")
        df_day["zenith"].plot(ax=ax2, style="--", color="gray")
        plt.title(f"Solarstrahlung & Sonnenstand am {plot_date}")
        plt.grid()
        plt.show()

    @staticmethod
    def plot_range(df, start_plot: str, end_plot: str):
        start_ts = pd.to_datetime(start_plot)
        end_ts = pd.to_datetime(end_plot)

        df_range = df.loc[start_ts:end_ts]

        import matplotlib.pyplot as plt
        fig, ax1 = plt.subplots(figsize=(14, 6))
        cols = [c for c in ["ghi", "dhi", "dni"] if c in df_range.columns]
        df_range[cols].plot(ax=ax1)
        ax1.set_ylabel("Strahlung [W/m²]")
        plt.title(f"Solarstrahlung von {start_ts.date()} bis {end_ts.date()}")
        plt.grid()
        plt.tight_layout()
        plt.show()

def plot_single_series(df: pd.DataFrame, col: str, title: str = None):
    if col not in df.columns:
        print(f"Spalte '{col}' nicht im DataFrame.")
        return
    ax = df[col].plot(figsize=(12,4))
    ax.set_title(title or col.upper())
    ax.set_ylabel("Strahlung [W/m²]")
    ax.set_xlabel("Zeit")
    ax.grid(True)
    plt.tight_layout()
    plt.show()



# --------- Beispiel-Aufruf ----------


if __name__ == "__main__":
    cfg = DWDWeatherConfig(
        start="2018-01-01 00:00",
        end="2018-12-31 23:50",
        auto_select=True,
        save_path="inputs/Wetterdaten_10min_DWD/wetter_daten_2018_10min.csv",
        plot_date="2018-07-20",
        plot_range=("2018-01-01", "2018-12-31"),
        use_dirint= True,
    )
    df = DWDWeatherFetcher(cfg).run()

    # Aufrufbeispiele:
    plot_single_series(df, "dni",  "Direktstrahlung (DNI)")
    plot_single_series(df, "ghi",  "Globalstrahlung (GHI)")
    plot_single_series(df, "dhi",  "Diffusstrahlung (DHI)")


    # ------------------------test Monatssummen ---------------------------------



    # ------------------------------
    # Monats-Energie aus 10-min-Daten (W/m²) → kWh/m²
    # ------------------------------

    df_rad = df[["ghi", "dhi", "dni"]].clip(lower=0)

    # 10 Minuten = 10/60 h; W → Wh → kWh ⇒ Faktor = 1/6000
    factor = (10/60)/1000   # oder: 1/6000


    # Monatssummen bilden
    monthly = pd.DataFrame({
        "ghi": df_rad["ghi"].resample("M").sum() * factor,
        "dhi": df_rad["dhi"].resample("M").sum() * factor,
        "dni": df_rad["dni"].resample("M").sum() * factor,
    })

    monthly.index = monthly.index.to_period("M")
    print(monthly)

    # ------------------------------
    # Plotten
    # ------------------------------
    monthly.plot(kind="bar", figsize=(12,5))
    plt.ylabel("Monatssumme [kWh/m²]")
    plt.title("Monatssummen der Strahlung (kWh/m²)")
    plt.grid(axis="y", linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.show()


