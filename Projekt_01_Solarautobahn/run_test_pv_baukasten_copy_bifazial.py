import os
from pvlib.location import Location
from pvlib.pvsystem import PVSystem
from pvlib.modelchain import ModelChain
from pvlib.bifacial.pvfactors import pvfactors_timeseries
from pvlib import location as pv_location, pvsystem
import pandas as pd
import matplotlib.pyplot as plt

from pv_baukasten_copy_bifazial import PV_System, PV_TYPEN, sandia_modules, cec_inverters, temp_models_sapm
from functions_weather_data import DWDWeatherConfig, DWDWeatherFetcher


def simulate_monofacial_point(pv_type, row, weather_df):
    module_params = sandia_modules[pv_type.module]
    inverter_params = cec_inverters[pv_type.inverter]
    temp_params = temp_models_sapm[pv_type.temp_model]

    loc = Location(row["latitude"], row["longitude"], tz="Europe/Berlin")

    system = PVSystem(
        surface_tilt=row["tilt"],
        surface_azimuth=row["azimut"],
        module_parameters=module_params,
        inverter_parameters=inverter_params,
        temperature_model_parameters=temp_params,
        modules_per_string=pv_type.modules_per_string,
        strings_per_inverter=pv_type.strings_per_inverter,
        albedo=pv_type.albedo  # <--- jetzt genutzt
    )

    mc = ModelChain(system, loc)
    mc.run_model(weather_df)
    return mc.results.ac



def simulate_bifacial_point(pv_type, row, weather_df):
    loc = pv_location.Location(row["latitude"], row["longitude"], tz="Europe/Berlin")
    times = weather_df.index
    solar_position = loc.get_solarposition(times)

    # 1) Orientierung: für Wände besser FixedMount
    mount = pvsystem.FixedMount(
        surface_tilt=float(row["tilt"]),
        surface_azimuth=float(row["azimut"])
    )
    orientation = mount.get_orientation(
        solar_zenith=solar_position['apparent_zenith'],
        solar_azimuth=solar_position['azimuth']
    )

    # 2) pvfactors: nutze DEINE Wetterdaten (dni/dhi) statt clearsky
    irrad = pvfactors_timeseries(
        solar_azimuth=solar_position['azimuth'],
        solar_zenith=solar_position['apparent_zenith'],
        surface_azimuth=orientation['surface_azimuth'],
        surface_tilt=orientation['surface_tilt'],
        axis_azimuth=float(row["azimut"]),
        timestamps=times,
        dni=weather_df['dni'],
        dhi=weather_df['dhi'],
        gcr=pv_type.gcr,
        pvrow_height=pv_type.row_height,
        pvrow_width=pv_type.row_width,
        albedo=pv_type.albedo,
        n_pvrows=3,
        index_observed_pvrow=1,
    )
    irrad = pd.concat(irrad, axis=1)

    # 3) Effective Irradiance bilden
    bifaciality = pv_type.bifaciality if pv_type.bifaciality is not None else 0.65
    irrad['effective_irradiance'] = irrad['total_abs_front'] + irrad['total_abs_back'] * bifaciality

    # 4) System + MC
    module_params = sandia_modules[pv_type.module]
    inverter_params = cec_inverters[pv_type.inverter]
    temp_params = temp_models_sapm[pv_type.temp_model]

    array = pvsystem.Array(
        mount=mount,
        module_parameters=module_params,
        temperature_model_parameters=temp_params,
        # optional: strings/modules je Array, wenn gewünscht
    )
    system = pvsystem.PVSystem(
        arrays=[array],
        inverter_parameters=inverter_params,
        modules_per_string=pv_type.modules_per_string,
        strings_per_inverter=pv_type.strings_per_inverter,
    )

    mc = ModelChain(system, loc, aoi_model='no_loss')

    # 5) Meteo mitgeben, sonst fehlen Temp/Wind
    mc.run_model_from_effective_irradiance(
        effective_irradiance=irrad['effective_irradiance'],
        temp_air=weather_df['temp_air'],
        wind_speed=weather_df['wind_speed']
    )

    return mc.results.ac



def simulate_pv_type_energy(pv_type, points_csv_path, weather_df):
    df_points = pd.read_csv(points_csv_path)

    total_ac = None

    for _, row in df_points.iterrows():
        if getattr(pv_type, "is_bifacial_detailed", False):
            ac = simulate_bifacial_point(pv_type, row, weather_df)
        else:
            ac = simulate_monofacial_point(pv_type, row, weather_df)

        if total_ac is None:
            total_ac = ac
        else:
            total_ac = total_ac + ac

    dt_hours = (weather_df.index[1] - weather_df.index[0]).total_seconds() / 3600.0
    energy_kwh = (total_ac * dt_hours).sum()

    if (not getattr(pv_type, "is_bifacial_detailed", False)) and getattr(pv_type, "bifazial", 0) > 0:
        energy_kwh *= (1 + pv_type.bifazial)

    return energy_kwh, total_ac




if __name__ == "__main__":
    import os
    import pandas as pd
    import matplotlib.pyplot as plt

    # --- Wetterdaten holen ---
    cfg = DWDWeatherConfig(
        coords=(51.08579, 6.47554),
        start="2022-01-01",
        end="2022-12-31",
        station_id=None,
        auto_select=True,
        min_quality=0.95,
        save_path="./Input/wetterdaten_solarautobahn_2022.csv",
    )
    weather_df = DWDWeatherFetcher(cfg).run()

    # --- PV-System & Punkte ---
    base_input = "./Input"
    geojson_path = os.path.join(base_input, "geometrien", "a46_west.geojson")
    output_dir = os.path.join(base_input, "punkte")
    os.makedirs(output_dir, exist_ok=True)

    pv_system = PV_System(
        geojson_path=geojson_path,
        pvtypes=[PV_TYPEN[0]],  # # 0 = ID 1 Windschutzwand, 1 = ID 2 Schallschutzwand, 2 = ID 3 Schallschutzwand_Dach, 3 = ID 4 Böschung, 4 = ID 5 Freifläche_bzw_Agri_geneigt, 5 = ID 6 Agri_vertikal, 6 = ID 7 Haus_Dach
        step_size=4,
        weather_df=weather_df,
        base_output_dir=output_dir,
    )
    results = pv_system.generate_pv_points()

    print("Berechnete PV-Typen:")
    for pv_type in pv_system.pvtypes:
        print(" -", pv_type)

    # --- Simulation für alle Typen ---
    print("\nJahresenergie je PV-Typ:")
    for pv_type in pv_system.pvtypes:
        csv_name = f"punkte_{pv_type.id}_{pv_type.name}.csv".replace(" ", "_")
        csv_path = os.path.join(output_dir, csv_name)

        energy_kwh, total_ac = simulate_pv_type_energy(pv_type, csv_path, weather_df)
        print(f"  {pv_type.name}: {energy_kwh:.1f} kWh")

        # Plot
        plt.figure(figsize=(15, 4))
        plt.plot(total_ac.index, total_ac.values, linewidth=0.6)
        plt.title(f"Jahresverlauf AC-Leistung – {pv_type.name}")
        plt.xlabel("Datum"); plt.ylabel("AC-Leistung [W]")
        plt.grid(True, alpha=0.3)
        plt.tight_layout(); plt.show()