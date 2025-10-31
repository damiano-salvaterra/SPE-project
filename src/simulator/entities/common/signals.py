from typing import Any


class EntitySignal:
    """
    This class defines standardized signals sent by entities to the monitors
    Entities that generates phenomena that need to be monitored, must create an object
    that inherits from this base class and notify the monitors.
    The concrete monitor that is specific for this type of signal will immplement
    its update() function to filter out all the signal exept of the interested one.
    """

    def __init__(self, descriptor: str, timestamp: float, **kwargs):
        self.descriptor = descriptor
        self.timestamp = timestamp
        self.kwargs = kwargs

    """dunder methods of the mapping protocol need to
        be overridden to allow the conversion in pandas dataframe"""

    def __getitem__(self, key: str) -> Any:
        if key == "descriptor":
            return self.descriptor
        if key == "timestamp":
            return self.timestamp
        # if  not present, raises KeyError
        return self.kwargs[key]

    def __iter__(self):
        yield "descriptor"
        yield "timestamp"
        yield from self.kwargs.keys()

    def __len__(self) -> int:
        # fixed fields + length of kwargs
        return 2 + len(self.kwargs)
