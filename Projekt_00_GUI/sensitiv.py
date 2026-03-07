from core.io_types import GuiInput
from Simulation import run_simulation
import pandas as pd
pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)

# ---------------------------------------------------
# DEFAULT CONFIG
# ---------------------------------------------------

DEFAULT_CONFIG = {}

# ---------------------------------------------------
# CASE DEFINITIONS      1: Small, 2: Medium, 3: Large
# ---------------------------------------------------

# Solarautobahn
H_CONFIGS = {
    0: {},
    1: {
        "highways": ["A46"],
        "h_pv_types": [0]               #0: Wind, 1: Schall, 2: Schall Dach, 3: Böschung,
    },

    2: {
        "highways": ["A44", 'A46'],
        "h_pv_types": [0]
    },
    3: {
        "highways": ["A44"],
        "h_pv_types": [0]
    }
}

# Energielandschaft
EL_CONFIGS = {
    0: {},
    1: {
        "el_build_state": 100,
        "el_pv_type": 5,        #ZUORDNUNG CHECKEN... 6: horizontal mit tracking, 5: vertikal, 4: horizontal (MIT ODER OHNE TRACKING???)
        "tractor_width": 24.0,
        "tractor_length": 15.0,
        "tractor_turn_radius": 9.0
    },
    2: {
        "tractor_width": 12.0,
        "el_pv_type": 6
    },
    3: {
        "tractor_width": 12.0,
        "el_pv_type": 4
    }
}

# Industrie
I_CONFIGS = {
    0: {},
    1: {
        "is_heat_cooling_electric": False,
        "companies": [1, 2, 4]
    },

    2: {
        "companies": [5, 5, 6, 6, 7],
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
        "h2_load_scenario": "2030",
        "e_load_scenario": "2030"
    },
}

# Battery
B_CONFIGS = {
    0: {},
    1: {
        "bs_efficiency": 0.95,
        "bs_energy_kwh": 1000.0,
        "bs_power_kw": 500.0
    },

    2: {
        "bs_energy_kwh": 235000.0,
        "bs_power_kw": 1000.0
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

    #Ergebnisse in Heatmap
    # Index-Labels konsistent als Strings (z.B. "[1]", "[2, 3, 4]", ...)
   # row_labels = [str(v) for v in company_selections]
    # Matrix vorbereiten
    #test_matrix = pd.DataFrame(index=row_labels, columns=traktor, dtype=float)


    # erstmal nur eine Variante testen, für die eigentliche Sensitivitätsanalyse [1] -> [1,2]
    for h_case in [1]:
        #row_label = str(y)  # <- wichtig: gleicher Typ wie Index
        #test_matrix_row = []
        for el_case in [2]:
            for i_case in [1]:
                for geh_case in [1]:
                    for b_case in [1]:

                        print(f"\nRunning case: \nh\t\t-  {h_case} \nel\t\t-  {el_case} \ni \t\t-  {i_case} \ngeh \t-  {geh_case} \nb \t\t-  {b_case}")

                        inp = build_test_input(
                            h_case=h_case,
                            el_case=el_case,
                            i_case=i_case,
                            geh_case=geh_case,
                            b_case=b_case
                        )


                        out = run_simulation(inp)
                        #print('PV Reihen Länge: ', round(out.el_pv_length,2))

                        #test_result = x * sum(y)
                        #test_matrix_row.append(test_result)

#Output Lastgang speichern
                        if not out.res_df.empty:
                            filename = f"outputs/sensi_res_dfs/res_df_{h_case}{el_case}{i_case}{geh_case}{b_case}.csv"
                            out.res_df.to_csv(
                                filename,
                                sep=",",
                                decimal="."
                            )
                            print('-'*50,'\nResults Data Frame:')
                            print("CSV saved:", filename)
                            print('\n',out.res_df.head())
                            print('\n',out.res_df.describe())

                            print('-'*50,'\nBatterie Data Frame:')
                            print('\n',out.bat_df.head())
                            print('\n',out.bat_df.describe())

                        else:
                            print("res_df empty")

            #test_matrix.loc[row_label] = test_matrix_row
   # print(test_matrix)


# ---------------------------------------------------
# SCRIPT ENTRY
# ---------------------------------------------------

if __name__ == "__main__":
    main()
