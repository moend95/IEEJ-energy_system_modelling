import pandas as pd
import matplotlib.pyplot as plt


def plot_industry_preview(csv_path, selected_columns=None, start="2017-03-05"):
    """
    Vorschauplot der ausgewählten Industrie-Lastgänge aus der CSV.
    """

    df = pd.read_csv(csv_path, sep=";")
    df["Time stamp"] = pd.to_datetime(df["Time stamp"])
    df.set_index("Time stamp", inplace=True)

    if selected_columns is not None and len(selected_columns) > 0:
        df = df[selected_columns]

    df_week = df.loc[start:].iloc[:7 * 24 * 4]

    fig, ax = plt.subplots(figsize=(15, 7))

    for column in df_week.columns:
        ax.plot(df_week.index, df_week[column], label=column)

    ax.set_title(f"Lastgänge Industriegebiet – Woche ab {start}")
    ax.set_xlabel("Zeit")
    ax.set_ylabel("Leistung [kW]")
    ax.legend()
    ax.grid(True)
    fig.tight_layout()

    return fig


def plot_industry_annual_energy(csv_path, ordered_columns=None, title="Jahresenergie pro Unternehmen"):
    """
    Balkendiagramm der Jahresenergie in vorgegebener Reihenfolge.
    """

    df = pd.read_csv(csv_path, sep=";")
    df["Time stamp"] = pd.to_datetime(df["Time stamp"])
    df.set_index("Time stamp", inplace=True)

    if ordered_columns is not None:
        df = df[ordered_columns]

    annual_energy = df.sum() * 0.25  # 15-min Raster -> kWh

    colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]

    fig, ax = plt.subplots(figsize=(12, 6))

    bars = ax.bar(
        annual_energy.index,
        annual_energy.values,
        color=colors[:len(annual_energy)]
    )

    ax.set_title(title)
    ax.set_ylabel("Energie [kWh]")
    ax.set_xlabel("Unternehmen")
    ax.grid(axis="y")
    ax.legend(bars, annual_energy.index)

    plt.xticks(rotation=45)
    fig.tight_layout()

    return fig

# Green energy hub
import os
import pandas as pd
import matplotlib.pyplot as plt

def _read_green_hub_timeseries(csv_path):
    """
    Liest eine Green-Energy-Hub-CSV robust ein.
    Erwartet:
    - eine Zeitspalte
    - eine Leistungsspalte
    """

    df = pd.read_csv(csv_path)

    # mögliche Zeitspalten
    time_candidates = ["time", "Time", "timestamp", "Timestamp", "time_input_year", "date", "Date"]

    # mögliche Leistungsspalten
    value_candidates = [
        "power_kW", "power_MW",
        "P (kW)", "P (MW)", "P new (MW)", "P [MW]",
        "power_mw", "power", "load", "value"
    ]

    time_col = None
    for c in time_candidates:
        if c in df.columns:
            time_col = c
            break

    if time_col is None:
        time_col = df.columns[0]

    value_col = None
    for c in value_candidates:
        if c in df.columns:
            value_col = c
            break

    if value_col is None:
        # erste numerische Spalte außer Zeit nehmen
        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        numeric_cols = [c for c in numeric_cols if c != time_col]
        if not numeric_cols:
            raise ValueError(f"Keine geeignete Leistungsspalte in {csv_path} gefunden.")
        value_col = numeric_cols[0]

    # Zeitspalte parsen: z. B. "01-01 00:15" -> "2022-01-01 00:15"
    time_values = df[time_col].astype(str).str.strip()
    parsed_time = pd.to_datetime(
        "2022-" + time_values,
        format="%Y-%m-%d %H:%M",
        errors="coerce"
    )

    if parsed_time.isna().all():
        raise ValueError(
            f"Zeitspalte in {csv_path} konnte nicht geparst werden. "
            f"Beispielwerte: {time_values.head().tolist()}"
        )

    df[time_col] = parsed_time
    df = df.set_index(time_col)

    series = pd.to_numeric(df[value_col], errors="coerce")
    return series


def plot_green_hub_weekly_profiles(base_dir, h2_year=None, e_year=None, start="2022-03-05"):
    """
    Beispielwoche des Green Energy Hub:
    - optional Elektrolyseur aus dem gewählten H2-Szenario
    - optional BEV-Last aus dem gewählten Elektro-Szenario
    """

    fig, ax = plt.subplots(figsize=(15, 7))
    plotted_anything = False

    # -------------------------------------------------
    # BEV laden und plotten, falls gewählt
    # -------------------------------------------------
    if e_year not in [None, "Keine"]:
        bev_path = os.path.join(base_dir, str(e_year), "BEV_load_el_15min.csv")
        bev = _read_green_hub_timeseries(bev_path)

        try:
            bev_week = bev.loc[start:].iloc[:7 * 24 * 4]
        except Exception:
            bev_week = bev.iloc[:7 * 24 * 4]

        ax.plot(bev_week.index, bev_week.values, label=f"BEV {e_year}")
        plotted_anything = True

    # -------------------------------------------------
    # Elektrolyseur laden und plotten, falls gewählt
    # -------------------------------------------------
    if h2_year not in [None, "Keine"]:
        ely_path = os.path.join(base_dir, str(h2_year), "Electrolyzer_output.csv")
        ely = _read_green_hub_timeseries(ely_path)

        try:
            ely_week = ely.loc[start:].iloc[:7 * 24 * 4]
        except Exception:
            ely_week = ely.iloc[:7 * 24 * 4]

        ax.plot(ely_week.index, ely_week.values, linestyle="--", label=f"Elektrolyseur {h2_year}")
        plotted_anything = True

    # -------------------------------------------------
    # Falls gar nichts gewählt wurde
    # -------------------------------------------------
    if not plotted_anything:
        ax.text(
            0.5, 0.5,
            "Keine Green-Energy-Hub-Daten ausgewählt.",
            ha="center",
            va="center",
            transform=ax.transAxes
        )

    ax.set_title("Beispielhafte Wochenprofile des Green Energy Hub")
    ax.set_xlabel("Zeit")
    ax.set_ylabel("Leistung [kW]")
    ax.grid(True)

    if plotted_anything:
        ax.legend()

    fig.tight_layout()
    return fig

def plot_green_hub_annual_energy(base_dir, years=("2022", "2030", "2050")):
    """
    Gruppiertes Balkendiagramm:
    Jahresstromverbrauch von BEV-Ladesäulen und Elektrolyseur
    für 2022 / 2030 / 2050.
    """
    years = [str(y) for y in years]

    bev_energy = []
    ely_energy = []

    for year in years:
        bev_path = os.path.join(base_dir, year, "BEV_load_el_15min.csv")
        ely_path = os.path.join(base_dir, year, "Electrolyzer_output.csv")

        bev = _read_green_hub_timeseries(bev_path)
        ely = _read_green_hub_timeseries(ely_path)

        # kW bei 15-min Raster -> kWh mit *0.25 -> MWh mit /1000
        bev_energy.append(bev.sum() * 0.25 / 1000)
        ely_energy.append(ely.sum() * 0.25 / 1000)

    x = range(len(years))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar([i - width / 2 for i in x], bev_energy, width=width, label="BEV-Ladesäulen")
    ax.bar([i + width / 2 for i in x], ely_energy, width=width, label="Elektrolyseur")

    ax.set_title("Jährlicher Stromverbrauch des Green Energy Hub")
    ax.set_xlabel("Szenariojahr")
    ax.set_ylabel("Energie [MWh]")
    ax.set_xticks(list(x))
    ax.set_xticklabels(years)
    ax.grid(axis="y")
    ax.legend()
    fig.tight_layout()

    return fig