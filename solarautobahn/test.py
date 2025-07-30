import pandas as pd
import matplotlib.pyplot as plt

# Datei einlesen
csv_path = r"C:\Users\sarah\Documents\GitHub\IEEJ-energy_system_modelling\Input\pv_ertrag_ergebnisse.csv"
df = pd.read_csv(csv_path)

# Prüfen, ob die Spalte 'annual_energy_kwh' vorhanden ist
if "annual_energy_kwh" not in df.columns:
    raise ValueError("Spalte 'annual_energy_kwh' nicht gefunden!")

# Plot erstellen
plt.figure(figsize=(12, 6))
plt.bar(range(len(df)), df["annual_energy_kwh"])
plt.xlabel("Punkt-Index")
plt.ylabel("Jahresertrag [kWh]")
plt.title("PV-Jahresertrag pro Punkt")
plt.grid(True)
plt.tight_layout()
plt.show()
