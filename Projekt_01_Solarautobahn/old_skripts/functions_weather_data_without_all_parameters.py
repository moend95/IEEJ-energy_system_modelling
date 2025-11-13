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
    start: str = "2022-01-01"
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
    """Klassenbasierte Version des früheren fetch_weather_data (bleibt bei 10-min-Auflösung)."""

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
        ]

    # --------- öffentlicher Einstiegspunkt ----------
    def run(self) -> pd.DataFrame:
        """Lädt und verarbeitet DWD-Daten (10-min-Auflösung)."""
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
        if "temp_air" in df.columns:
            df["temp_air"] = df["temp_air"] - 273.15
        for col in ["ghi", "dhi"]:
            if col in df.columns:
                df[col] = df[col] / 600.0  # J/m² pro 10 min → W/m²

        # 3) auf 10-min-Raster bringen
        df = df.resample("10T").interpolate("time")

        # 4) Zeitzone
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC").tz_convert(self.cfg.tz)
        else:
            df.index = df.index.tz_convert(self.cfg.tz)

        # 5) Solarposition
        solpos = get_solarposition(df.index, latitude=self.cfg.coords[0], longitude=self.cfg.coords[1])
        df["zenith"] = solpos["zenith"]
        df["elevation"] = 90 - df["zenith"]
        cosz = np.cos(np.radians(df["zenith"]))

        # 6) Masken
        daylight = (df["elevation"] > 0) & df["ghi"].notna() & (df["ghi"] > 0)
        valid_sun = (df["elevation"] >= self.cfg.min_elevation_deg) & (cosz > 0)

        # 7) DNI berechnen
        if self.cfg.use_dirint:
            dni_vals = dirint(
                ghi=df["ghi"].values,
                solar_zenith=df["zenith"].values,
                times=df.index,
                pressure=None,
                temp_dew=None
            )
            dni = pd.Series(dni_vals, index=df.index)
            dni.loc[~valid_sun] = 0.0
        else:
            df["dhi"] = np.minimum(df["dhi"], df["ghi"])
            dni = pd.Series(np.nan, index=df.index, dtype=float)
            idx = valid_sun
            dni.loc[idx] = (df.loc[idx, "ghi"] - df.loc[idx, "dhi"]) / cosz[idx]
            dni.loc[~valid_sun] = 0.0

        # 8) Obergrenze: extraterrestrische Normalstrahlung
        doy = df.index.dayofyear.values
        i0 = get_extra_radiation(doy)
        dni = np.minimum(dni.values, i0)
        dni = pd.Series(dni, index=df.index)

        # 9) Nachsorge
        dni = dni.clip(lower=0)
        dni.loc[~daylight] = 0.0

        # 10) Interpolation
        dni_interp = dni.copy()
        dni_interp[~daylight] = np.nan
        dni_interp = dni_interp.interpolate(method="time", limit=self.cfg.dni_interp_limit)
        dni = dni_interp.fillna(0.0)

        df["dni"] = dni
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
    def plot_range(df, start_plot: str, end_plot: str, tz: str = "Europe/Berlin"):
        def _tz_localize_safe(ts, tz):
            ts = pd.to_datetime(ts)
            if getattr(ts, "tzinfo", None) is None:
                try:
                    return ts.tz_localize(tz, nonexistent="shift_forward", ambiguous="NaT")
                except TypeError:
                    return ts.tz_localize(tz)
            return ts

        start_ts = _tz_localize_safe(start_plot, tz)
        end_ts = _tz_localize_safe(end_plot, tz)
        df_range = df.loc[start_ts:end_ts]

        fig, ax1 = plt.subplots(figsize=(14, 6))
        cols = [c for c in ["ghi", "dhi", "dni"] if c in df_range.columns]
        df_range[cols].plot(ax=ax1)
        ax1.set_ylabel("Strahlung [W/m²]")
        plt.title(f"Solarstrahlung von {start_ts.date()} bis {end_ts.date()}")
        plt.grid()
        plt.tight_layout()
        plt.show()


# --------- Beispiel-Aufruf ----------
if __name__ == "__main__":
    cfg = DWDWeatherConfig(
        start="2022-01-01",
        end="2022-12-31",
        auto_select=True,
        save_path="../Input/test_solarautobahn.csv",
        plot_date="2022-07-20",
        plot_range=("2022-01-01", "2022-12-31"),
    )
    df = DWDWeatherFetcher(cfg).run()
