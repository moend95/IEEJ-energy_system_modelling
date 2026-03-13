from core.io_types import GuiInput
from Simulation import run_simulation
import pandas as pd
from itertools import product
import seaborn as sns
import matplotlib.pyplot as plt

pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)


import numpy as np
from matplotlib.colors import TwoSlopeNorm


def plot_scientific_heatmap(heatmap: pd.DataFrame, save_path: str | None = None):
    """
    Wissenschaftliche Heatmap:
    - divergierende Farbskala
    - 0 als neutraler Mittelpunkt
    - saubere Beschriftung
    """

    plot_df = heatmap.copy()

    # Lesbarere Labels erzeugen
    plot_df.index = [f"{geh} | {ind}" for geh, ind in plot_df.index]
    plot_df.columns = [f"{el} | {h}" for el, h in plot_df.columns]

    # Gemeinsame symmetrische Skala um 0
    max_abs = np.nanmax(np.abs(plot_df.to_numpy()))
    norm = TwoSlopeNorm(vmin=-max_abs, vcenter=0, vmax=max_abs)

    plt.figure(figsize=(12, 8))
    ax = sns.heatmap(
        plot_df,
        annot=False,
        fmt=".0f",
        cmap="RdYlGn",#"RdBu_r",   # negativ blau, positiv rot
        norm=norm,
        linewidths=0.5,
        linecolor="lightgray",
        cbar_kws={"label": "Direktnutzungsrate[%]"}
    )

    ax.set_title("Sensitivitätsanalyse - Energiebilanz", pad=12)
    ax.set_xlabel("EnergyLandscape | Highway")
    ax.set_ylabel("GreenEnergyHub | Industry")
    plt.xticks(rotation=45, ha="right")
    plt.yticks(rotation=0)
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches="tight")

    plt.show()


# ---------------------------------------------------
# DEFAULT CONFIG
# ---------------------------------------------------

DEFAULT_CONFIG = {}

# ---------------------------------------------------
# CASE DEFINITIONS      1: Small, 2: Medium, 3: Large
# ---------------------------------------------------

# Welche Szenarien wirklich gerechnet werden sollen
h_cases = [1]#,2,3]
el_cases = [3]#,2,3]
i_cases = [1]#,2,3]
geh_cases = [1]#,2,3]
b_cases = [2]

# Solarautobahn
H_CONFIGS = {
    0: {},
    1: {
        "highways": ["A46"],
        "h_pv_types": [0]               #0: Wind, 1: Schall, 2: Schall Dach, 3: Böschung,
    },

    2: {
        "highways": ["A44", 'A46'],
        "h_pv_types": [1,2]
    },
    3: {
        "highways": ["A44", "A46"],
        "h_pv_types": [1,2,3]
    }
}

# Energielandschaft
EL_CONFIGS = {
    0: {},
    1: {
        "el_build_state": 50,
        "el_pv_type": 5,        #ZUORDNUNG CHECKEN... 6: horizontal mit tracking, 5: vertikal, 4: horizontal (MIT ODER OHNE TRACKING???)
        "tractor_width": 24.0,
        "tractor_length": 15.0,
        "tractor_turn_radius": 9.0
    },
    2: {
        "el_build_state": 50,
        "tractor_width": 12.0,
        "el_pv_type": 6
    },
    3: {
        "el_build_state": 100,
        "tractor_width": 12.0,
        "el_pv_type": 4
    }
}

# Industrie
I_CONFIGS = {
    0: {},
    1: {
        "is_heat_cooling_electric": True,
        "companies": [2, 3, 4, 5, 6]
    },

    2: {
        "companies": [1, 5, 3, 6, 7],
        "is_heat_cooling_electric": True
    },

    3: {
        "companies": [0, 1, 1, 7, 7],
        "is_heat_cooling_electric": True
    }
}

# Green Energy Hub
GEH_CONFIGS = {
    0: {},
    1: {
        "h2_load_scenario": "2022",
        "e_load_scenario": "2022"
    },

    2: {
        "h2_load_scenario": "2050",
        "e_load_scenario": "2050"
    },

    3: {
        "h2_load_scenario": "2030",
        "e_load_scenario": "2030"
    }

}

# Battery
B_CONFIGS = {
    0: {},
    1: {
        "bs_efficiency": 1,
        "bs_energy_kwh": 10000.0,
        # Leistung kann mittels c faktor angegeben werden, default = 1
    },

    2: {
        "bs_efficiency": 1,
        "bs_energy_kwh": 235000.0
    }
}


# ---------------------------------------------------
# INPUT BUILDER
# ---------------------------------------------------

def build_test_input(h_case=1, el_case=1, i_case=1, geh_case=1, b_case=1):

    cfg = DEFAULT_CONFIG.copy()

    cfg.update(H_CONFIGS[h_case])
    cfg.update(EL_CONFIGS[el_case])
    cfg.update(I_CONFIGS[i_case])
    cfg.update(GEH_CONFIGS[geh_case])
    cfg.update(B_CONFIGS[b_case])

    inp = GuiInput()

    inp.highways = cfg.get("highways", [])
    inp.h_pv_types = cfg.get("h_pv_types", [])

    inp.el_build_state = cfg.get("el_build_state", None)
    inp.el_pv_type = cfg.get("el_pv_type", None)

    inp.tractor_width = cfg.get("tractor_width", None)
    inp.tractor_length = cfg.get("tractor_length", None)
    inp.tractor_turn_radius = cfg.get("tractor_turn_radius", None)

    inp.is_heat_cooling_electric = cfg.get("is_heat_cooling_electric", False)
    inp.companies = cfg.get("companies", [])

    inp.h2_load_scenario = cfg.get("h2_load_scenario", None)
    inp.e_load_scenario = cfg.get("e_load_scenario", None)

    inp.bs_efficiency = cfg.get("bs_efficiency", None)
    inp.bs_energy_kwh = cfg.get("bs_energy_kwh", None)
    inp.bs_power_kw = cfg.get("bs_power_kw", None)

    return inp


# ---------------------------------------------------
# MAIN
# ---------------------------------------------------

def main():

    col_index = pd.MultiIndex.from_tuples(
        [(f"EL{el}",f"H{h}") for el, h in product(el_cases, h_cases)],
        names=["EnergyLandscape","Highway"]
    )
    row_index = pd.MultiIndex.from_tuples(
        [(f"GEH{g}", f"I{i}") for g, i in product(geh_cases, i_cases)],
        names=["GreenEnergyHub", "Industry"]
    )

    heatmap_df = pd.DataFrame(index=row_index, columns=col_index, dtype=float)

    for b_case in b_cases:
        for el_case in el_cases:
            for h_case in h_cases:
                for geh_case in geh_cases:
                    for i_case in i_cases:


                        print(f"\nRunning case: \nh\t\t-  {h_case} "
                              f"\nel\t\t-  {el_case} "
                              f"\ni \t\t-  {i_case} "
                              f"\ngeh \t-  {geh_case}"
                              f"\nb\t\t- {b_case} ")

                        inp = build_test_input(
                            el_case=el_case,
                            h_case=h_case,
                            geh_case=geh_case,
                            i_case=i_case,
                            b_case=b_case
                        )


                        out = run_simulation(inp)

                        prod = out.res_df["Erzeugung_Solarautobahn [kW]"] + out.res_df["Erzeugung_Energielandschaft [kW]"]
                        cons = out.res_df['Last_Industrie [kW]'] + out.res_df["Last_Green_Energy_Hub [kW]"]

                        '''heatmap_df_selfcons.loc[
                            (f"GEH{geh_case}", f"I{i_case}"),
                            (f"EL{el_case}", f"H{h_case}")
                        ] = 100 * np.minimum(prod, cons).sum() / prod.sum()

                        heatmap_df_selfcons.to_excel("outputs/sensi_res_dfs/balance_self_consumption_rate.xlsx")
                        '''


                        heatmap_df.loc[
                            (f"GEH{geh_case}", f"I{i_case}"),
                            (f"EL{el_case}", f"H{h_case}")
                        ] = out.res_df['Bilanz [kW]'].sum()/4 #

                        if not out.bat_df.empty:
                            heatmap_df.loc[
                                (f"GEH{geh_case}", f"I{i_case}"),
                                (f"EL{el_case}", f"H{h_case}")
                            ] = out.bat_df['new_balance_kw'].sum() / 4  # out.res_df['Bilanz [kW]'].sum()/4 #

                        print(heatmap_df)
                        heatmap_df.to_excel("outputs/sensi_res_dfs/bat_balance.xlsx")

                        #Output Lastgang speichern
                        if not out.res_df.empty:
                            filename = f"outputs/sensi_res_dfs/res_df_{el_case}{h_case}{geh_case}{i_case}.csv"
                            out.res_df.to_csv(
                                filename,
                                sep=",",
                                decimal="."
                            )
                            print('-'*50,'\nResults Data Frame:')
                            print("CSV saved:", filename)
                            print('\n',out.res_df.head())
                            print('\n', out.res_df.sum(axis=0))
                            #print('\n', out.res_df.sum().sum())
                            print('\n',out.res_df.describe())

                            if not out.bat_df.empty:
                                print('-'*50,'\nBatterie Data Frame:')
                                print('\n',out.bat_df.head())
                                print('\n',out.bat_df.describe())
                                print('\nStats: \n', {k: round(v, 0) if isinstance(v, float) else v for k, v in out.battery_stats.items()})

                        else:
                            print("res_df empty")



    #manualle heat map
    plt.figure(figsize=(10, 8))
    sns.heatmap(
        heatmap_df,
        annot=True,  # Werte anzeigen
        fmt=".0f",  # Ganzzahlen
        cmap="RdYlGn"  # Farbskala

    )
    plt.title("Balance Avg. Neg. Power Sensitivity")
    plt.tight_layout()
    plt.savefig("outputs/sensi_res_dfs/balance_self_consumption_rate.png", dpi=300)
    plt.show()





    plot_scientific_heatmap(
        heatmap_df,
        save_path="outputs/sensi_res_dfs/balance_self_consumption_rate.png"
    )


# ---------------------------------------------------
# SCRIPT ENTRY
# ---------------------------------------------------

if __name__ == "__main__":
    main()
