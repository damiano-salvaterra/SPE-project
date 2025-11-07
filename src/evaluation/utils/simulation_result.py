# src/evaluation/utils/simulation_result.py
import pandas as pd
from typing import Optional
from simulator.entities.applications.common.app_monitor import ApplicationMonitor
from simulator.entities.protocols.net.common.tarp_monitor import TARPMonitor

class SimulationResult:
    """
    This data class processes and holds the results from simulation monitors.
    Can be extendedto include other monitors.
    """
    
    def __init__(self, 
                 app_monitor: Optional[ApplicationMonitor] = None, 
                 tarp_monitor: Optional[TARPMonitor] = None):
        
        self.app_data = pd.DataFrame()
        self.tarp_data = pd.DataFrame()
        
        if app_monitor and app_monitor.log:
            self.app_data = pd.DataFrame(app_monitor.log)
            if not self.app_data.empty:
                self.app_data.set_index('time', inplace=True) # Set time as index

                
        if tarp_monitor and tarp_monitor.log:
            self.tarp_data = pd.DataFrame(tarp_monitor.log)
            if not self.tarp_data.empty:
                self.tarp_data.set_index('time', inplace=True) # Set time as index

    def save_to_csv(self, base_path: str):
        """
        Saves the result DataFrames to CSV files in the specified path.

        """
        try:
            if not self.app_data.empty:
                self.app_data.to_csv(f"{base_path}_app_data.csv")
            if not self.tarp_data.empty:
                self.tarp_data.to_csv(f"{base_path}_tarp_data.csv")
        except Exception as e:
            print(f"Error saving result CSVs to {base_path}: {e}")

    @property
    def is_valid(self) -> bool:
        return not self.app_data.empty or not self.tarp_data.empty