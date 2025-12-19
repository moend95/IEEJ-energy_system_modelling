import json
import matplotlib.pyplot as plt
import pandas as pd



open_data_internal_id_1 = 5
file_name = f'open_data_{open_data_internal_id_1}'

# JSON laden
with open(f"{file_name}.json", "r") as f:
    data = json.load(f)

# Werte extrahieren
values = pd.DataFrame()
values['Leistung normiert'] = data["data"][0]["values"]

# Plot
plt.figure(figsize=[15,5])
plt.plot(values['Leistung normiert'][0:167])    # [:] for entire year, [0:23] for one day, [0:167] for one week
plt.xlabel("48 Stunden")
plt.ylabel("Normierter Wert")
plt.grid(True)
plt.show()
