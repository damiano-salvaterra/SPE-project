from abc import ABC, abstractmethod
import pandas as pd
from typing import TYPE_CHECKING

from simulator.entities.common.signals import EntitySignal

if TYPE_CHECKING:
    from simulator.entities.common.entity import Entity


class Monitor(ABC):
    """Abstract base class for concrete Monitors"""

    def __init__(self):
        self.records: EntitySignal = []

    @abstractmethod
    def update(self, entity: "Entity", signal: EntitySignal):
        """called by the entity. Concrete monitors will implement the filter logic"""
        pass

    def reset(self):
        """reset monitor state"""
        self.records = []

    def get_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame.from_records(self.records)
