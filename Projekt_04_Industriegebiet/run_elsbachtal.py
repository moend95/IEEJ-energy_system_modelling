import argparse
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
from industrie_sim import IndustrieSim, Company, LoadIO

def plot_results(df: pd.DataFrame):
    """Plottet Jahres- und Wochenverlauf untereinander in einer Figure."""
    if not isinstance(df.index, pd.DatetimeIndex):
        print("Kein Zeitindex vorhanden – Plot übersprungen.")
        return

    answer = input("\nPlots gewünscht? (j/n): ").strip().lower()
    if answer != "j":
        print("Plots übersprungen.")
        return

    # Jahresdaten
    start_year = df.index.min()
    end_year = df.index.max()

    # Wochenausschnitt (erste 7 Tage)
    start_week = start_year
    end_week = start_week + pd.Timedelta(days=7)
    df_week = df.loc[start_week:end_week]

    # Figure mit zwei Subplots (übereinander)
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=False)

    # --- Oberer Plot: Jahresverlauf ---
    axes[0].plot(df.index, df["load_elec_kw"], label="Last (kW)", alpha=0.6)
    axes[0].plot(df.index, df["pv_kw"], label="PV-Erzeugung (kW)", alpha=0.6)
    axes[0].plot(df.index, df["grid_kw"], label="Netzbilanz (+Bezug / -Einspeisung)", alpha=0.6)
    axes[0].set_title(f"Jahresverlauf Strombilanz ({start_year.date()} – {end_year.date()})")
    axes[0].set_ylabel("Leistung [kW]")
    axes[0].legend()
    axes[0].grid(True, linestyle="--", alpha=0.5)

    # --- Unterer Plot: Wochenverlauf ---
    axes[1].plot(df_week.index, df_week["load_elec_kw"], label="Last (kW)", alpha=0.6)
    axes[1].plot(df_week.index, df_week["pv_kw"], label="PV-Erzeugung (kW)", alpha=0.6)
    axes[1].plot(df_week.index, df_week["grid_kw"], label="Netzbilanz (+Bezug / -Einspeisung)", alpha=0.6)
    axes[1].set_title(f"Beispielwoche: {start_week.date()} – {end_week.date()}")
    axes[1].set_xlabel("Zeit")
    axes[1].set_ylabel("Leistung [kW]")
    axes[1].legend()
    axes[1].grid(True, linestyle="--", alpha=0.5)

    plt.tight_layout()
    plt.show()


def main():
    parser = argparse.ArgumentParser(description="Simulation Industriegebiet Elsbachtal")
    parser.add_argument("--company", type=str, default="Unternehmen A")
    parser.add_argument("--dachflaeche", type=float, default=4000.0, help="m²")
    parser.add_argument("--lastgang_csv", type=str, default=None, help="Pfad zu CSV; sonst Standard")
    parser.add_argument("--pv_kwp", type=float, default=None, help="falls None: aus Dachfläche abgeleitet")
    args = parser.parse_args()

    # --- Lastgänge laden ---
    df_loads = LoadIO.read_profiles(args.lastgang_csv)

    # Schrittweite ableiten (h)
    if len(df_loads.index) >= 2:
        step_h = (df_loads.index[1] - df_loads.index[0]).total_seconds() / 3600.0
    else:
        step_h = 0.25

    company = Company(name=args.company, dachflaeche_m2=args.dachflaeche)
    sim = IndustrieSim(company, df_loads, step_h=step_h, pv_kwp=args.pv_kwp)

    # --- Simulation ---
    results = sim.run()
    kpis = sim.compute_kpis(results)

    # --- KPI-Ausgabe ---
    print("\n--- KPIs ---")
    for k, v in kpis.items():
        print(f"{k}: {v}")

    # --- Ergebnisse speichern ---
    out_dir = Path("out")
    out_dir.mkdir(exist_ok=True)
    results_path = out_dir / "bilanz_elsbachtal.csv"
    results.to_csv(results_path)
    print(f"\nErgebnisse gespeichert unter: {results_path}")

    # --- Optional: Plot erstellen ---
    plot_results(results)


if __name__ == "__main__":
    main()
