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


# ---------------- Konfiguration ----------------

@dataclass
class DWDWeatherConfig:
    coords: Tuple[float, float] = (51.08579, 6.47554)
    start: str = "2022-01-28"
    end: str   = "2022-01-28"
    station_id: Optional[str] = None
    auto_select: bool = True
    min_quality: float = 0.95
    tz: str = "Europe/Berlin"
    save_path: Optional[str] = None
    plot_date: Optional[str] = None
    plot_range: Optional[Tuple[str, str]] = None


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
        if "temp_air" in df.columns:
            df["temp_air"] = df["temp_air"] - 273.15
        for col in ["ghi", "dhi"]:
            if col in df.columns:
                df[col] = df[col] / 600.0  # J/m² pro 10min -> W/m²

        # 3) auf ein sauberes 10-min Raster bringen
        df = df.resample("10T").interpolate("time")

        # 4) Zeitzone
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC").tz_convert(self.cfg.tz)
        else:
            df.index = df.index.tz_convert(self.cfg.tz)

        # 5) Solarposition
        solpos = get_solarposition(df.index, latitude=self.cfg.coords[0], longitude=self.cfg.coords[1])
        df["zenith"] = solpos["zenith"]
        cosz = np.cos(np.radians(df["zenith"]))

        # 6) DNI berechnen (tagsüber), physikalische Schranken
        cosz_safe = np.where(cosz <= 0.0, np.nan, cosz)  # Nacht -> NaN
        df["dni"] = (df.get("ghi", np.nan) - df.get("dhi", np.nan)) / cosz_safe
        if "ghi" in df.columns:
            df["dni"] = df["dni"].where(df["dni"] <= df["ghi"], np.nan)

        # --- NEU: kleine Lücken in DNI zeitlich interpolieren (z.B. bis 3 Ticks = 30 min) ---
        # Nur am Tag interpolieren, Nacht bleibt NaN:
        daylight = (cosz > 0) & df["ghi"].notna() & (df["ghi"] > 0)
        dni_series = df["dni"].copy()
        dni_series[~daylight] = np.nan
        df["dni"] = dni_series.interpolate(method="time", limit=1000)  # <= hier Limit anpassen, z.B. 2..6

        # Nach-Absicherung der Schranken nach der Interpolation:
        if "ghi" in df.columns:
            mask = df["dni"] > df["ghi"]
            df.loc[mask, "dni"] = df.loc[mask, "ghi"]
        df.loc[df["dni"] < 0, "dni"] = 0
        # --- ENDE NEU ---

        cols = ["ghi", "dhi", "dni", "temp_air", "wind_speed", "zenith"]
        return df[[c for c in cols if c in df.columns]]

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
        import pandas as pd

        def _tz_localize_safe(ts, tz):
            ts = pd.to_datetime(ts)
            if getattr(ts, "tzinfo", None) is None:
                # Neuer Versuch: neuere pandas (falls verfügbar)
                try:
                    return ts.tz_localize(tz, nonexistent="shift_forward", ambiguous="NaT")
                except TypeError:
                    # Rückfall: ältere pandas kennen die Argumente nicht
                    return ts.tz_localize(tz)
            return ts

        start_ts = _tz_localize_safe(start_plot, tz)
        end_ts = _tz_localize_safe(end_plot, tz)

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


# --------- Beispiel-Aufruf ----------

if __name__ == "__main__":
    cfg = DWDWeatherConfig(
        start="2022-01-01",
        end="2022-12-31",
        auto_select=True,
        save_path="./Input/test_solarautobahn.csv",
        plot_date="2022-07-20",
        plot_range=("2022-01-01", "2022-12-31"),
    )
    df = DWDWeatherFetcher(cfg).run()
