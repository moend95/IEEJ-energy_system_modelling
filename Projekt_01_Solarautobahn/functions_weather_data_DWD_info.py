from wetterdienst.provider.dwd.observation import DwdObservationResolution

print("Verfügbare Resolutions:")
for r in DwdObservationResolution:
    print(r)

from wetterdienst.provider.dwd.observation import DwdObservationParameter

resolutions_to_check = [
    "MINUTE_1",
    "MINUTE_5",
    "MINUTE_10",
    "HOURLY",
    "SUBDAILY",
    "DAILY",
]

for res in resolutions_to_check:
    print(f"\n--- {res} ---")
    try:
        branch = getattr(DwdObservationParameter, res)
        print("hat Branch:", branch)

        if hasattr(branch, "SOLAR"):
            print("SOLAR vorhanden")
            print(dir(branch.SOLAR))
        else:
            print("kein SOLAR-Zweig")
    except Exception as e:
        print("Fehler:", e)