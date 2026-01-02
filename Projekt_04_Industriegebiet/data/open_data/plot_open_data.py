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

# python
def choose_timeframe(series):
    total = len(series)
    points_per_day = 24
    menu = (
        "Wähle den Zeitraum zum Plotten:\n"
        "1) Ganzes Jahr\n"
        "2) 1 Tag (24 Werte)\n"
        "3) 1 Woche (7 Tage)\n"
        "4) 1 Monat (31 Tage)\n"
        "5) Benutzerdefiniert (Start + Länge)\n"
        "Eingabe (1-5): "
    )

    while True:
        choice = input(menu).strip()
        if choice not in {"1", "2", "3", "4", "5"}:
            print("Ungültige Auswahl. Bitte 1–5 eingeben.")
            continue

        if choice == "1":
            start, end = 0, total
            label = "Ganzes Jahr"
        elif choice == "2":
            start, end = 0, min(points_per_day, total)
            label = "1 Tag"
        elif choice == "3":
            start, end = 0, min(points_per_day * 7, total)
            label = "1 Woche"
        elif choice == "4":
            start, end = 0, min(points_per_day * 31, total)
            label = "1 Monat"
        else:  # Benutzerdefiniert
            try:
                s = int(input(f"Startindex (0 bis {total-1}): ").strip())
                if not (0 <= s < total):
                    print("Startindex außerhalb des gültigen Bereichs.")
                    continue
                length = int(input("Länge in Stunden (positive ganze Zahl): ").strip())
                if length <= 0:
                    print("Länge muss positiv sein.")
                    continue
                start, end = s, min(s + length, total)
                label = f"Benutzerdefiniert: Index {start} bis {end-1}"
            except ValueError:
                print("Bitte ganze Zahlen eingeben.")
                continue

        if start >= end:
            print("Leerer Bereich gewählt. Bitte neu wählen.")
            continue

        return slice(start, end), label

# Verwendung (nachdem 'values' geladen wurde):
series = values['Leistung normiert']
time_slice, xlabel = choose_timeframe(series)

plt.figure(figsize=[15, 5])
plt.plot(series[time_slice])
plt.xlabel(xlabel)
plt.ylabel("Normierter Wert")
plt.grid(True)
plt.show()


'''
print("Es wir die erste Woche des gewähten Datensatzes geplottet.")
# Plot
plt.figure(figsize=[15,5])
plt.plot(values['Leistung normiert'][0:743])    # [:] for entire year, [0:23] for one day, [0:167] for one week, [0:743] for one month
plt.xlabel("48 Stunden")
plt.ylabel("Normierter Wert")
plt.grid(True)
plt.show()
'''