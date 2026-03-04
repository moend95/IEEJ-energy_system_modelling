import pandas as pd


class BatteryStorageEff:
    """
    Simuliert einen Stromspeicher basierend auf einer Energiebilanz mit Effizienzberücksichtigung.

    Die Bilanz wird direkt übergeben (positiv = Überschuss, negativ = Defizit).
    """

    def __init__(self, max_capacity_kwh: float, initial_charge_kwh: float = 0.0,
                 charge_efficiency: float = 1.0, discharge_efficiency: float = 1.0):
        """
        Args:
            max_capacity_kwh: Maximale Speicherkapazität in kWh
            initial_charge_kwh: Anfanglicher Ladezustand in kWh
            charge_efficiency: Effizienz beim Laden (default 1.0, z.B. 0.95 für 95%)
            discharge_efficiency: Effizienz beim Entladen (default 1.0, z.B. 0.95 für 95%)
        """
        self.max_capacity = max_capacity_kwh
        self.current_charge = initial_charge_kwh
        self.charge_efficiency = charge_efficiency
        self.discharge_efficiency = discharge_efficiency

    def process_balance(self, balance_series: pd.Series,
                        timestep_hours: float = 1.0) -> pd.DataFrame:
        """
        Simuliert den Speicher basierend auf einer Energiebilanz.

        Args:
            balance_series: Series mit der Energiebilanz (kW, positiv = Überschuss)
            timestep_hours: Zeitschrittweite in Stunden (für kW zu kWh Umrechnung)

        Returns:
            DataFrame mit Speicherlogik
        """
        result_df = pd.DataFrame({
            'balance_kw': balance_series.values,
            'energy_balance_kwh': balance_series.values * timestep_hours
        })

        storage_charge = []
        energy_to_grid = []
        energy_from_grid = []

        for energy_change in result_df['energy_balance_kwh']:

            if energy_change >= 0:
                # Laden: Überschuss wird gespeichert
                # Mit Effizienz: nur charge_efficiency * energy_change wird gespeichert
                energy_to_store = energy_change * self.charge_efficiency
                new_charge = self.current_charge + energy_to_store

                if new_charge > self.max_capacity:
                    # Speicher überlädt → Überschuss ins Netz
                    storable = self.max_capacity - self.current_charge
                    excess = energy_to_store - storable
                    self.current_charge = self.max_capacity
                    energy_to_grid.append(excess / self.charge_efficiency)  # Rückrechnung
                    energy_from_grid.append(0.0)
                else:
                    # Normal laden
                    self.current_charge = new_charge
                    energy_to_grid.append(0.0)
                    energy_from_grid.append(0.0)

            else:
                # Entladen: Defizit wird aus Speicher gedeckt
                # Mit Effizienz: (1/discharge_efficiency) * deficit muss aus Speicher kommen
                energy_needed = abs(energy_change) / self.discharge_efficiency
                new_charge = self.current_charge - energy_needed

                if new_charge < 0:
                    # Speicher reicht nicht → Energie aus Netz
                    available_from_storage = self.current_charge * self.discharge_efficiency
                    deficit_from_grid = abs(energy_change) - available_from_storage
                    self.current_charge = 0.0
                    energy_to_grid.append(0.0)
                    energy_from_grid.append(deficit_from_grid)
                else:
                    # Normal entladen
                    self.current_charge = new_charge
                    energy_to_grid.append(0.0)
                    energy_from_grid.append(0.0)

            storage_charge.append(self.current_charge)

        result_df['storage_charge_kwh'] = storage_charge
        result_df['energy_to_grid_kwh'] = energy_to_grid
        result_df['energy_from_grid_kwh'] = energy_from_grid

        return result_df

    def get_stats(self, df: pd.DataFrame) -> dict:
        """Gibt eine Zusammenfassung der Speichernutzung zurück"""
        return {
            'energy_to_grid_total': df['energy_to_grid_kwh'].sum(),
            'energy_from_grid_total': df['energy_from_grid_kwh'].sum(),
            'final_charge': self.current_charge,
            'utilization_percent': (self.current_charge / self.max_capacity) * 100,
            'charge_efficiency': self.charge_efficiency,
            'discharge_efficiency': self.discharge_efficiency
        }