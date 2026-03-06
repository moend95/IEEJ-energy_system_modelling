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