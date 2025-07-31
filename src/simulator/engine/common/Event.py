from typing import Optional, Any
from collections.abc import Callable
from abc import abstractmethod

'''
This class implements the base Event class for the simulator.
It provides an interface for the scheduler.
Real events inherits from this class and they are implemented in each module.
'''
class Event:
    def __init__(self, time: float, string_id: str = None, priority: int = 0, blame: Optional[Any] = None, callback: Callable = None, log_event: bool = False, **kwargs):
        self._unique_id = None # unique id assigned by the scheduler
        self.time = time  # The time at which the event occurs
        self.string_id = string_id  # A string identifier for the event
        self.priority = priority  # Priority of the event, lower values are processed first
        self.blame = blame  # blame source, if any
        self.callback = callback  # Callback for the event
        self.log_event = log_event # flag to log the event if true
        self.kwargs = kwargs

    def __str__(self) -> str:
        return f"Event(id={self.id}, string_id='{self.string_id}', time={self.time}, blame={self.blame})"

    @abstractmethod
    def log_string(self) -> str:
        pass

    def run(self):
        if self.callback is not None:
            self.callback(**self.kwargs)
    
    def __lt__(self, other: "Event") -> bool:
        '''
        Overloads the < operator to compare events
        '''
        if not isinstance(other, Event):
            return NotImplemented
        
        # Compare event times first
        if self.time != other.time:
            return self.time < other.time
        
        # Compare event priorities if times are equal
        if self.priority != other.priority:
            return self.priority < other.priority
        
        # If times and priorities are equal, compare by unique_id
        return self.id < other.id