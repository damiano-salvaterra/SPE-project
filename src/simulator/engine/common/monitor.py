import pandas as pd
from typing import List, TYPE_CHECKING
from abc import ABC, abstractmethod

# Avoid circular import issues at type-checking time
if TYPE_CHECKING:
    from simulator.entities.common import Entity, EntitySignal


class Monitor(ABC):
    """
    Base class for evaluation monitors.
    """

    def __init__(self, verbose: bool = True):
        self.log: List[dict] = []
        self.verbose = verbose

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
            # Return an empty DataFrame if the log is empty
            return pd.DataFrame()
        return pd.DataFrame(self.log)

    def reset(self):
        """Resets the monitor's internal log."""
        self.log = []