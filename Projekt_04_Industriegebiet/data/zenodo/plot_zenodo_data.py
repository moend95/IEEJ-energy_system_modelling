# this skript loads the zenodo data from a csv file and creates plots for analysis
import argparse
from typing import Optional, Union
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os

DEFAULT_CSV = os.path.join(os.path.dirname(__file__), "LoadProfile_30IPs_2017.csv")


def read_zenodo_csv(path: str) -> pd.DataFrame:
    """Lädt die CSV-Datei des Zenodo-Datensatzes.

    Die Datei hat eine beschreibende erste Zeile und die Spaltenüberschrift in Zeile 2.
    Trennzeichen ist ';' und das Zeitstempel-Format ist Tag.Monat.Jahr Stunde:Minute:Sekunde.
    """
    df = pd.read_csv(path, sep=';', header=1, parse_dates=[0], dayfirst=True, index_col=0)
    # Stelle sicher, dass der Index wirklich DatetimeIndex ist (robust gegenüber Parsing-Unterschieden)
    try:
        # trim strings and coerce to datetime
        if not isinstance(df.index, pd.DatetimeIndex):
            idx_str = df.index.astype(str).str.strip()
            idx_dt = pd.to_datetime(idx_str, dayfirst=True, errors='coerce')
            if idx_dt.isna().any():
                # Versuch: entferne bekannte Anhängsel (z.B. ' b' bei DST-Duplikaten) mittels Regex-Extract
                extracted = idx_str.str.extract(r'(^\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}:\d{2})', expand=False)
                idx_dt2 = pd.to_datetime(extracted, dayfirst=True, errors='coerce')
                # Fülle dort, wo erstes Parsing fehlschlug
                idx_dt = idx_dt.where(~idx_dt.isna(), idx_dt2)
            if idx_dt.isna().any():
                bad = idx_str[idx_dt.isna()].unique()[:5]
                raise SystemExit(f"Fehler beim Parsen der Zeitstempel (erste fehlerhafte Beispiele): {bad}. Bitte überprüfe das CSV-Format.")
            df.index = idx_dt
    except SystemExit:
        raise
    except Exception as e:
        raise SystemExit(f"Unerwarteter Fehler beim Parsen des Index: {e}")
    # Entferne vollständig leere Spalten (falls vorhanden) und trimme Spaltennamen
    df.columns = [c.strip() for c in df.columns]
    df = df.dropna(axis=1, how='all')
    return df


def parse_time_arg(arg: Optional[str], df: pd.DataFrame) -> Optional[Union[pd.Timestamp, int]]:
    """Parst ein Zeit-Argument.

    Akzeptiert None, eine ganze Zahl (Zeilenindex, 0-basiert) oder ein Datumstring.
    Gibt None, einen Integer (Index) oder einen pd.Timestamp zurück.
    """
    if arg is None:
        return None
    arg = str(arg).strip()
    # Ganzzahl
    if arg.isdigit():
        return int(arg)
    # Versuche Datetime
    try:
        ts = pd.to_datetime(arg, dayfirst=True)
        return ts
    except Exception:
        raise argparse.ArgumentTypeError(f"Unbekanntes Zeitformat: {arg}")


def select_slice(df: pd.DataFrame, start: Optional[Union[pd.Timestamp, int]], end: Optional[Union[pd.Timestamp, int]]) -> pd.DataFrame:
    """Wählt einen DataFrame-Ausschnitt per Index (int) oder per Timestamp aus.

    Robust: bei Timestamp-Inputs wird ein boolesches Masking verwendet, um KeyError zu vermeiden,
    falls der exakte Timestamp nicht im Index vorhanden ist.
    """
    if start is None and end is None:
        return df
    # integer index -> iloc
    if isinstance(start, int) or isinstance(end, int):
        s = start if isinstance(start, int) else 0
        e = end if isinstance(end, int) else None
        return df.iloc[s:e]
    # timestamp slicing: nutze boolesches Masking (robust gegenüber fehlenden exakten Labels)
    idx = df.index
    mask = pd.Series(True, index=idx)
    if start is not None:
        start_ts = pd.to_datetime(start, dayfirst=True)
        mask &= (idx >= start_ts)
    if end is not None:
        end_ts = pd.to_datetime(end, dayfirst=True)
        mask &= (idx <= end_ts)
    return df.loc[mask]


def choose_profile_from_input(df: pd.DataFrame) -> str:
    """Interaktive Auswahl eines Profils durch den Nutzer."""
    print("Verfügbare Profile:")
    for i, col in enumerate(df.columns, start=1):
        print(f"{i:2d}: {col}")
    ans = input("Gib die Profilnummer (z.B. 1) oder den Namen (z.B. 'LG 1') ein: ").strip()
    if ans.isdigit():
        n = int(ans)
        if 1 <= n <= len(df.columns):
            return df.columns[n - 1]
        else:
            raise SystemExit("Ungültige Profilnummer.")
    # falls kein digit, versuche exakten Spaltennamen
    if ans in df.columns:
        return ans
    # auch akzeptiere z.B. '1' -> 'LG 1'
    if ans.isdigit():
        name = f"LG {int(ans)}"
        if name in df.columns:
            return name
    raise SystemExit("Profil nicht gefunden.")


def plot_profile(series: pd.Series, title: Optional[str] = None, save: Optional[str] = None):
    plt.figure(figsize=(12, 4))
    series.plot()
    plt.xlabel('Timestamp')
    plt.ylabel('Electric load (kW)')
    if title:
        plt.title(title)
    plt.tight_layout()
    if save:
        plt.savefig(save, dpi=200)
        print(f"Plot gespeichert nach: {save}")
    else:
        plt.show()


def plot_all_profiles(df: pd.DataFrame, start: Optional[Union[pd.Timestamp, int]], end: Optional[Union[pd.Timestamp, int]], save_dir: Optional[str] = None):
    """Plottet alle verfügbaren Profile (LG 1 bis LG 30) in einem Zeitfenster."""
    sub = select_slice(df, start, end)

    # Filtere nur LG-Spalten
    lg_cols = [col for col in sub.columns if col.startswith('LG')]

    if not lg_cols:
        print("Keine LG-Profile gefunden.")
        return

    print(f"Plotte {len(lg_cols)} Profile...")
    for profile_name in lg_cols:
        series = sub[profile_name]
        title = f"Profile {profile_name} ({start} bis {end})"

        if save_dir:
            save_path = os.path.join(save_dir, f"{profile_name}.png")
            plot_profile(series, title=title, save=save_path)
        else:
            plot_profile(series, title=title, save=None)


def main():
    parser = argparse.ArgumentParser(description='Plot selected load profiles from Zenodo CSV.')
    parser.add_argument('--csv', default=DEFAULT_CSV, help='Pfad zur CSV-Datei (Standard: LoadProfile_20IPs_2016.csv)')
    parser.add_argument('--profile', help="Profil-ID oder Name, z.B. 1 oder 'LG 1' oder 'LG 15'")
    parser.add_argument('--start', help="Startzeitpunkt (Datum wie '01.01.2016 00:15') oder Zeilenindex (0-basiert)")
    parser.add_argument('--end', help="Endzeitpunkt (Datum) oder Zeilenindex (exklusiv)")
    parser.add_argument('--timeframe', choices=['whole', 'day', 'week', 'month'], help='Schnellauswahl des Zeitfensters: whole/day/week/month')
    parser.add_argument('--save', help='Optional: Dateiname, um den Plot zu speichern (z.B. out.png)')
    parser.add_argument('--save-dir', help='Optional: Verzeichnis zum Speichern aller Plots (für Option 31)')
    args = parser.parse_args()

    if not os.path.exists(args.csv):
        raise SystemExit(f"CSV-Datei nicht gefunden: {args.csv}")

    df = read_zenodo_csv(args.csv)

    # Bestimme Profil
    profile_name = None
    if args.profile:
        p = args.profile.strip()
        if p.isdigit():
            profile_name = f"LG {int(p)}"
        else:
            profile_name = p
        if profile_name not in df.columns:
            raise SystemExit(f"Profil '{profile_name}' nicht in CSV vorhanden. Verfügbare Profile: {', '.join(df.columns)}")
    else:
        # interaktiv
        profile_name = choose_profile_from_input(df)

    # Timeframe-Auswahl: whole/day/week/month (interaktiv, falls nicht gesetzt)
    timeframe = args.timeframe
    if timeframe is None:
        print("Wähle ein Zeitfenster:")
        print("  1) whole  - ganzer Zeitraum")
        print("  2) day    - 1 Tag")
        print("  3) week   - 1 Woche")
        print("  4) month  - 1 Monat")
        print("  5) all    - alle 30 LG für 1 Woche plotten")
        print("  6) all_full - alle 30 LG für den gesamten Zeitraum plotten")
        choice = input("Auswahl (1-6): ").strip()
        mapping = {'1': 'whole', '2': 'day', '3': 'week', '4': 'month', '5': 'all', '6': 'all_full'}
        timeframe = mapping.get(choice, 'whole')

    # Parse time args (kann None, int oder Timestamp zurückgeben)
    start_arg = parse_time_arg(args.start, df)
    end_arg = parse_time_arg(args.end, df)

    # Berechne finalen slice basierend auf timeframe
    final_start = None
    final_end = None

    # Wenn user explizit --end übergibt, hat das Vorrang
    if end_arg is not None:
        final_start = start_arg
        final_end = end_arg
    else:
        # Kein explizites Ende, berechne anhand timeframe
        if timeframe == 'whole':
            final_start = None
            final_end = None
        elif timeframe == 'all_full':
            # Alle LG für den gesamten Zeitraum
            final_start = None
            final_end = None
        elif timeframe == 'all':
            # Alle LG für 1 Woche
            if isinstance(start_arg, int):
                s_idx = start_arg
                e_idx = s_idx + 7 * 96
                final_start = s_idx
                final_end = e_idx
            else:
                ts_start = start_arg if start_arg is not None else df.index[0]
                ts_end = ts_start + pd.Timedelta(days=7) - pd.Timedelta(minutes=15)
                final_start = ts_start
                final_end = ts_end
        else:
            # Bestimme Start (Timestamp oder Index)
            if isinstance(start_arg, int):
                s_idx = start_arg
                if timeframe == 'day':
                    e_idx = s_idx + 96
                elif timeframe == 'week':
                    e_idx = s_idx + 7 * 96
                elif timeframe == 'month':
                    e_idx = s_idx + 30 * 96
                else:
                    e_idx = None
                final_start = s_idx
                final_end = e_idx
            else:
                # Timestamp start (oder None -> Verwende 04. Dezember als Standard)
                if start_arg is not None:
                    ts_start = start_arg
                else:
                    # Standard auf 04. Dezember setzen (4.12.2017 für den Datensatz)
                    ts_start = pd.to_datetime('04.12.2017', dayfirst=True)
                
                if timeframe == 'day':
                    ts_end = ts_start + pd.Timedelta(days=1) - pd.Timedelta(minutes=15)
                elif timeframe == 'week':
                    ts_end = ts_start + pd.Timedelta(days=7) - pd.Timedelta(minutes=15)
                elif timeframe == 'month':
                    ts_end = ts_start + pd.DateOffset(months=1) - pd.Timedelta(minutes=15)
                else:
                    ts_end = None
                final_start = ts_start
                final_end = ts_end

    # Wende den Slice an
    if timeframe in ['all', 'all_full']:
        # Plotte alle Profile
        save_dir = args.save_dir
        if not save_dir:
            save_dir = input("Gib das Verzeichnis zum Speichern der Plots ein (oder drücke Enter für Anzeige): ").strip()
            if not save_dir:
                save_dir = None
        plot_all_profiles(df, final_start, final_end, save_dir=save_dir)
    else:
        # Plotte einzelnes Profil
        profile_name = None
        if args.profile:
            p = args.profile.strip()
            if p.isdigit():
                profile_name = f"LG {int(p)}"
            else:
                profile_name = p
            if profile_name not in df.columns:
                raise SystemExit(f"Profil '{profile_name}' nicht in CSV vorhanden. Verfügbare Profile: {', '.join(df.columns)}")
        else:
            # interaktiv
            profile_name = choose_profile_from_input(df)

        sub = select_slice(df, final_start, final_end)

        if profile_name not in sub.columns:
            raise SystemExit(f"Profil '{profile_name}' nicht im ausgewählten Zeitfenster vorhanden.")

        series = sub[profile_name]
        title = f"Profile {profile_name} from {os.path.basename(args.csv)} ({timeframe})"
        plot_profile(series, title=title, save=args.save)


if __name__ == '__main__':
    main()
