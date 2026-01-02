import json
import matplotlib.pyplot as plt
import pandas as pd


while True:
    try:
        open_data_internal_id_1 = int(
            input("Bitte gib den gewünschten Datensatz an (0–13): ")
        )
        if 0 <= open_data_internal_id_1 <= 13:
            break
        else:
            print("Fehler: Bitte eine Zahl zwischen 0 und 13 eingeben.")
    except ValueError:
        print("Fehler: Bitte eine ganze Zahl eingeben.")

print(f"Gewählter Datensatz: {open_data_internal_id_1}")


#open_data_internal_id_1 = 6
file_name = f'open_data_{open_data_internal_id_1}'

# JSON laden
with open(f"{file_name}.json", "r") as f:
    data = json.load(f)

# Werte extrahieren
values = pd.DataFrame()
values['Leistung normiert'] = data["data"][0]["values"]



print("Es wir die erste Woche des gewähten Datensatzes geplottet.")
# Plot
plt.figure(figsize=[15,5])
plt.plot(values['Leistung normiert'][0:743])    # [:] for entire year, [0:23] for one day, [0:167] for one week, [0:743] for one month
plt.xlabel("48 Stunden")
plt.ylabel("Normierter Wert")
plt.grid(True)
plt.show()
