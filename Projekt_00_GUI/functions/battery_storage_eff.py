import pandas as pd


class BatteryStorage:
    """
    Einfache Batteriespeicher-Simulation.

    Idee:
    - Eingang ist ein Lastgang / eine Bilanz in kW
    - positive Werte  -> Überschuss, Batterie kann laden
    - negative Werte  -> Defizit, Batterie kann entladen
    - Ergebnis ist ein neuer Lastgang:
        * 0, wenn Batterie alles ausgleichen kann
        * >0, wenn trotz voller Batterie noch Überschuss ins Netz geht
        * <0, wenn trotz leerer Batterie noch Strom aus dem Netz benötigt wird

    Erweiterung:
    - maximale Lade- und Entladeleistung über C-Faktor
    """

    def __init__(
        self,
        capacity_kwh: float,
        initial_soc_kwh: float = 0.0,
        charge_efficiency: float = 1.0,
        discharge_efficiency: float = 1.0,
        max_charge_c: float = 1.0,
        max_discharge_c: float = 1.0,
    ):
        self.capacity_kwh = capacity_kwh
        self.initial_soc_kwh = initial_soc_kwh
        self.charge_efficiency = charge_efficiency
        self.discharge_efficiency = discharge_efficiency

        # C-Faktor -> maximale Leistung in kW
        self.max_charge_kw = capacity_kwh * max_charge_c
        self.max_discharge_kw = capacity_kwh * max_discharge_c

    def simulate(self, balance_series: pd.Series, timestep_hours: float = 1.0) -> pd.DataFrame:
        """
        Simuliert den Speicher auf Basis einer Bilanz in kW.

        Parameter
        ---------
        balance_series : pd.Series
            Bilanz in kW:
            > 0 = Überschuss
            < 0 = Defizit
        timestep_hours : float
            Länge eines Zeitschritts in Stunden, z. B.
            1.0 für Stundenwerte
            0.25 für 15-Minuten-Werte

        Rückgabe
        --------
        pd.DataFrame mit:
        - balance_kw: ursprüngliche Bilanz
        - battery_power_kw: Lade-/Entladeleistung der Batterie
                            > 0 = Batterie lädt
                            < 0 = Batterie entlädt
        - soc_kwh: Ladezustand der Batterie
        - new_balance_kw: neue Bilanz nach Batterie
                          > 0 = Einspeisung ins Netz
                          < 0 = Netzbezug
                          = 0 = Batterie konnte vollständig ausgleichen
        """

        soc = self.initial_soc_kwh

        battery_power_list = []
        soc_list = []
        new_balance_list = []

        for balance_kw in balance_series:
            # Energie dieses Zeitschritts in kWh
            balance_kwh = balance_kw * timestep_hours

            # Leistungsgrenzen für diesen Zeitschritt als Energie
            max_charge_kwh_step = self.max_charge_kw * timestep_hours
            max_discharge_kwh_step = self.max_discharge_kw * timestep_hours

            # Fall 1: Überschuss -> Batterie laden
            if balance_kwh > 0:
                # Von der Bilanzseite kann nur begrenzt Energie in den Speicher fließen:
                # 1. durch vorhandenen Überschuss
                # 2. durch max. Ladeleistung
                input_energy_for_charging = min(balance_kwh, max_charge_kwh_step)

                # So viel davon kommt wegen Wirkungsgrad tatsächlich im Speicher an
                energy_to_battery = input_energy_for_charging * self.charge_efficiency

                # Freier Speicherplatz
                free_capacity = self.capacity_kwh - soc

                # Tatsächlich speicherbare Energie
                charged_kwh = min(energy_to_battery, free_capacity)

                # SOC erhöhen
                soc += charged_kwh

                # Wie viel Energie musste dafür auf der Eingangsseite genutzt werden?
                input_used_for_charging = charged_kwh / self.charge_efficiency

                # Restüberschuss geht ins Netz
                remaining_kwh = balance_kwh - input_used_for_charging

                # Batterie-Leistung positiv = laden
                battery_power_kw = input_used_for_charging / timestep_hours
                new_balance_kw = remaining_kwh / timestep_hours

            # Fall 2: Defizit -> Batterie entladen
            elif balance_kwh < 0:
                needed_kwh = abs(balance_kwh)

                # Begrenzung der entnehmbaren Energie:
                # 1. was gebraucht wird
                # 2. was die Leistung zulässt
                # 3. was im Speicher vorhanden ist
                max_deliverable_kwh = min(
                    max_discharge_kwh_step,
                    soc * self.discharge_efficiency
                )

                # Tatsächlich von der Batterie gelieferte Energie
                delivered_kwh = min(needed_kwh, max_deliverable_kwh)

                # Dafür muss mehr Energie aus der Batterie entnommen werden
                energy_removed_from_soc = delivered_kwh / self.discharge_efficiency
                soc -= energy_removed_from_soc

                # Restdefizit, das aus dem Netz kommen muss
                remaining_kwh = needed_kwh - delivered_kwh

                # Batterie-Leistung negativ = entladen
                battery_power_kw = -delivered_kwh / timestep_hours
                new_balance_kw = -remaining_kwh / timestep_hours

            # Fall 3: exakt 0
            else:
                battery_power_kw = 0.0
                new_balance_kw = 0.0

            battery_power_list.append(battery_power_kw)
            soc_list.append(soc)
            new_balance_list.append(new_balance_kw)

        result_df = pd.DataFrame(index=balance_series.index)
        result_df["balance_kw"] = balance_series
        result_df["battery_power_kw"] = battery_power_list
        result_df["soc_kwh"] = soc_list
        result_df["new_balance_kw"] = new_balance_list

        return result_df

    def get_stats(self, result_df: pd.DataFrame, timestep_hours: float = 1.0) -> dict:
        """
        Einfache Kennzahlen aus dem Simulationsergebnis.
        """
        grid_import_kwh = abs(result_df.loc[result_df["new_balance_kw"] < 0, "new_balance_kw"].sum()) * timestep_hours
        grid_export_kwh = result_df.loc[result_df["new_balance_kw"] > 0, "new_balance_kw"].sum() * timestep_hours

        battery_charge_kwh = result_df.loc[result_df["battery_power_kw"] > 0, "battery_power_kw"].sum() * timestep_hours
        battery_discharge_kwh = abs(result_df.loc[result_df["battery_power_kw"] < 0, "battery_power_kw"].sum()) * timestep_hours

        final_soc = result_df["soc_kwh"].iloc[-1] if not result_df.empty else self.initial_soc_kwh

        return {
            "grid_import_kwh": grid_import_kwh,
            "grid_export_kwh": grid_export_kwh,
            "battery_charge_kwh": battery_charge_kwh,
            "battery_discharge_kwh": battery_discharge_kwh,
            "final_soc_kwh": final_soc,
            "final_soc_percent": (final_soc / self.capacity_kwh) * 100 if self.capacity_kwh > 0 else 0.0,
            "max_charge_kw": self.max_charge_kw,
            "max_discharge_kw": self.max_discharge_kw,
        }