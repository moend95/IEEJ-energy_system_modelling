# Wetterdatenfunktion starten
from solarautobahn.functions_weather_data import fetch_weather_data

# Wetterdaten abrufen und als CSV speichern
df = fetch_weather_data(
    coords=(51.08579, 6.47554),                # Solarautobahn-Koordinaten
    start="2022-01-01",
    end="2022-12-31",
    station_id=None,                           # Automatische Stationswahl
    auto_select=True,
    min_quality=0.95,
    save_path=r"C:\Users\sarah\Documents\GitHub\IEEJ-energy_system_modelling\Input\wetterdaten_solarautobahn_2022.csv",
    plot_date="2022-06-21"                     # Optionaler Plot für einen bestimmten Tag
)

print("Wetterdaten erfolgreich geladen und gespeichert.")







# 1. CSV laden – NICHT mit parse_dates, weil wir es gleich selbst machen
df = pd.read_csv(
    r"C:\Users\sarah\OneDrive\Dokumenty\GitHub\IEEJ-energy_system_modelling\Input\wetterdaten_solarautobahn_2022.csv"
)

# 2. Datum in datetime konvertieren, mit Zeitzone erkennen
df["date"] = pd.to_datetime(df["date"], utc=True)  # Das erkennt +02:00 und wandelt es in UTC

# 3. Zeitzone entfernen (pandas braucht tz-naive Zeiten für viele Funktionen)
df["date"] = df["date"].dt.tz_localize(None)

# 4. Setze 'date' als Index
df.set_index("date", inplace=True)
df.index.name = "datetime"

# Jetzt ist df bereit für pvlib!
weather_data = df


# PV-Modul- und Inverter-Daten laden
temperature_model_parameters = pvlib.temperature.TEMPERATURE_MODEL_PARAMETERS['sapm']['open_rack_glass_glass']
sandia_modules = pvlib.pvsystem.retrieve_sam('cecmod')
cec_inverters = pvlib.pvsystem.retrieve_sam('cecinverter')

sandia_module = sandia_modules['Jinko_Solar__Co___Ltd_JKM400M_72L']
cec_inverter = cec_inverters['ABB__UNO_2_0_I_OUTD_S_US__277V_']

# Punkte und Ausrichtungen laden
# Reihenfolge (Latitude (Breitengrad), Longitude (Längengrad), Ausrichtung (Azimut)
# Punkte und Ausrichtungen aus CSV laden
punkte_df = pd.read_csv(r"C:\Users\sarah\OneDrive\Dokumenty\GitHub\IEEJ-energy_system_modelling\Input\punkte_mit_azimut.csv")
punkte = list(punkte_df.itertuples(index=False, name=None))

# PV-System an jedem Punkt simulieren
# Liste für alle Energieergebnisse
annual_energies = []

for idx, (latitude, longitude, azimut) in tqdm(enumerate(punkte), total=len(punkte), desc="Simuliere PV-Punkte"):

    # Standort definieren
    location = Location(latitude=latitude, longitude=longitude, tz="Europe/Berlin", altitude=80)

    # PVSystem definieren
    system = PVSystem(
        surface_tilt=20,
        surface_azimuth=azimut,
        module_parameters=sandia_module,
        inverter_parameters=cec_inverter,
        temperature_model_parameters=temperature_model_parameters,
        modules_per_string=4,
        strings_per_inverter=1
    )

    # ModelChain aufbauen
    mc = ModelChain(system, location, aoi_model='physical', spectral_model='no_loss', temperature_model='sapm')

    # Simulation ausführen
    mc.run_model(weather_data)

    # Ergebnisse speichern
    results = mc.results.ac

    # Jahresertrag berechnen
    annual_energy_kwh = (results.sum() * (10/60)) / 1000  # 10min Daten in kWh
    annual_energies.append(annual_energy_kwh)

 # Fortschritt ausgeben (nur alle 100 Punkte)
    if idx % 100 == 0:
        print(f"{idx}/{len(punkte)} Punkte verarbeitet...")

# Am Ende alle Einzelresultate aufsummieren:
total_energy_kwh = sum(annual_energies)
print(f"\nGesamter erwarteter Energieertrag entlang der Solarautobahn für das Jahr: {total_energy_kwh:.2f} kWh")
