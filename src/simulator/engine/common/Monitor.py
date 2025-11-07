import pandas as pd
import os
from typing import List, TYPE_CHECKING
from abc import ABC, abstractmethod

# Avoid circular import issues at type-checking time
if TYPE_CHECKING:
    from simulator.entities.common import Entity, EntitySignal


class Monitor(ABC):
    """
    Base class for evaluation monitors.
    """

    def __init__(self, monitor_name: str = "base_monitor", verbose: bool = True):
        self.log: List[dict] = []
        self.verbose = verbose
        self.monitor_name = monitor_name

    @abstractmethod
    def update(self, entity: "Entity", signal: "EntitySignal"):
        """
        Called by an entity when a signal is emitted.
        Concrete monitors will implement the filter logic
        and append structured data to self.log.
        """
        pass

    def get_dataframe(self) -> pd.DataFrame:
        """
        Converts the accumulated log into a pandas DataFrame.
        """
        if not self.log:
            return pd.DataFrame()
        
        # create DataFrame and set time as index
        df = pd.DataFrame(self.log)
        if 'time' in df.columns:
            df.set_index('time', inplace=True)
            df.sort_index(inplace=True)
        return df

    def reset(self):
        """Resets the monitor's internal log."""
        self.log = []

    def save_to_csv(self, base_path: str):
        """
        Saves the monitor's data to a CSV file with a given path.
        """
        df = self.get_dataframe()
        
        if df.empty:
            return #useless to save empty files

        # sort data by time index, if there is
        if df.index.name == 'time':
            df.sort_index(inplace=True)

        file_path = f"{base_path}_{self.monitor_name}.csv"
        
        directory = os.path.dirname(file_path)
        if directory and not os.path.exists(directory): #create if directory do not exists
            os.makedirs(directory, exist_ok=True)
            
        df.to_csv(file_path)