# Wärmepumpe für Industriegebiet 

# Annahmen 
# Heizstunden (Volllaststunden Durchschnitt Deutschland) = 2.000 Stunden/Jahr 
# Luft-Wasser-Wärmepumpe JAZ = 2,5
# Fläche in m2 = 503.000 m2
# Neubau-Werkhalle (gedämmt) ab 2010 = 60 – 80 Heizlast pro m² (W/m²)
# Heizlast pro m² (W/m²) = 70 W/m2

Heizlast = 70 # W/m2
Heizstunden = 2000 # Stunden/Jahr
JAZ = 2.5
Flaeche = 503000 # m2

Heizleistung = Flaeche * Heizlast / 1000

Verbrauch = (Heizleistung / JAZ) * Heizstunden

print("Verbrauch der Wärmepumpe im Industriegebiet:", Verbrauch, "kWh/Jahr")

