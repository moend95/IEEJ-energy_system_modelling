import pandas as pd
import os

base_path = r"C:\Users\sarah\OneDrive\Dokumenty\GitHub\IEEJ-energy_system_modelling\Projekt_03_Green_Energy_Hub\A_Wasserstofftankstelle_Lastprofile\2050"

# --- 1) BEV (2030: KOMMA-getrennt) ---
bev_in = os.path.join(base_path, "BEV_load_el_15min_mw.csv")
bev = pd.read_csv(bev_in)  # <-- kein sep=";" !

bev["time_input_year"] = pd.to_datetime(bev["time_input_year"])

bev_clean = pd.DataFrame({
    "timestamp": bev["time_input_year"].dt.strftime("%m-%d %H:%M"),
    "power_kW": bev["P (MW)"] * 1000
})

bev_out = os.path.join(base_path, "BEV_load_el_15min_mw_clean.csv")
bev_clean.to_csv(bev_out, index=False)
print("BEV_load_el_15min_mw_clean.csv erstellt")


# --- 2) Electrolyzer ---
ely_in = os.path.join(base_path, "Electrolyzer_output.csv")
ely = pd.read_csv(ely_in)

ely["time"] = pd.to_datetime(ely["time"])

ely_clean = pd.DataFrame({
    "timestamp": ely["time"].dt.strftime("%m-%d %H:%M"),
    "power_kW": ely["P_ac"]
})

ely_out = os.path.join(base_path, "Electrolyzer_output_clean.csv")
ely_clean.to_csv(ely_out, index=False)
print("Electrolyzer_output_clean.csv erstellt")