from typing import Any, Dict


class EntitySignal:
    """
    This class defines standardized signals sent by entities to the monitors
    Entities that generates phenomena that need to be monitored, must create an object
    that inherits from this base class and notify the monitors.
    The concrete monitor that is specific for this type of signal will immplement
    its update() function to filter out all the signal exept of the interested one.
    """

    def __init__(self, timestamp: float, event_type: str, descriptor: str):
        self.timestamp = timestamp
        self.event_type = event_type
        self.descriptor = descriptor # For human-readable logs, not for CSV data.
        
    def get_log_data(self) -> Dict[str, Any]:
        """
        returns signal data as dictionary(ready to be converted in Pandas Dataframe row).
        Each signal mustoverride this method to include its own specific data
        """
        return {
            "time": self.timestamp,
            "event": self.event_type
        }