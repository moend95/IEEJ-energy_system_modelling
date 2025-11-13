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
    )

    mc = ModelChain(system, loc)
    mc.run_model(weather_df)
    ac = mc.results.ac  # Zeitreihe in W
    return ac


def simulate_bifacial_point(pv_type, row, weather_df):
    # Standort
    loc = pv_location.Location(row["latitude"], row["longitude"], tz="Europe/Berlin")
    times = weather_df.index

    # Sonnenstand & Clearsky (oder du nimmst deine gemessenen dni/dhi statt cs)
    solar_position = loc.get_solarposition(times)
    cs = loc.get_clearsky(times)

    axis_azimuth = pv_type.azimut  # z.B. 90°
    axis_tilt = 0                  # je nach Konzept, hier erstmal 0

    sat_mount = pvsystem.SingleAxisTrackerMount(
        axis_tilt=axis_tilt,
        axis_azimuth=axis_azimuth,
        max_angle=60,
        backtrack=True,
        gcr=pv_type.gcr,
    )

    orientation = sat_mount.get_orientation(
        solar_position['apparent_zenith'],
        solar_position['azimuth'],
    )

    irrad = pvfactors_timeseries(
        solar_position['azimuth'],
        solar_position['apparent_zenith'],
        orientation['surface_azimuth'],
        orientation['surface_tilt'],
        axis_azimuth,
        times,
        cs['dni'],      # oder weather_df['dni'], wenn du DWD statt clearsky willst
        cs['dhi'],
        pv_type.gcr,
        pv_type.row_height,
        pv_type.row_width,
        pv_type.albedo,
        n_pvrows=3,
        index_observed_pvrow=1,
    )
    irrad = pd.concat(irrad, axis=1)

    irrad['effective_irradiance'] = (
        irrad['total_abs_front'] + irrad['total_abs_back'] * pv_type.bifaciality
    )

    module_params = sandia_modules[pv_type.module]
    inverter_params = cec_inverters[pv_type.inverter]
    temp_params = temp_models_sapm[pv_type.temp_model]

    array = pvsystem.Array(
        mount=sat_mount,
        module_parameters=module_params,
        temperature_model_parameters=temp_params,
    )

    system = pvsystem.PVSystem(
        arrays=[array],
        inverter_parameters=inverter_params,
        modules_per_string=pv_type.modules_per_string,
        strings_per_inverter=pv_type.strings_per_inverter,
    )

    mc = ModelChain(system, loc, aoi_model='no_loss')
    mc.run_model_from_effective_irradiance(irrad)

    ac = mc.results.ac
    return ac


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



    print("\nJahresenergie je PV-Typ:")
    for pv_type in pv_system.pvtypes:
        csv_name = f"punkte_{pv_type.id}_{pv_type.name}.csv".replace(" ", "_")
        csv_path = os.path.join(output_dir, csv_name)

        # HIER: total_ac wirklich entgegennehmen
        energy_kwh, total_ac = simulate_pv_type_energy(pv_type, csv_path, weather_df)
        print(f"  {pv_type.name}: {energy_kwh:.1f} kWh")

        # Jahresplot
        plt.figure(figsize=(15, 5))
        plt.plot(total_ac.index, total_ac.values, linewidth=0.5)
        plt.title(f"Jahresverlauf AC-Leistung – {pv_type.name}")
        plt.xlabel("Datum")
        plt.ylabel("AC-Leistung [W]")
        plt.grid(True)
        plt.tight_layout()
        plt.show()
