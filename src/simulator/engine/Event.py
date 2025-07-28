from typing import Optional, Any
from abc import abstractmethod

'''
This class implements the base Event class for the simulator.
It provides an interface for the scheduler.
Real events inherits from this class and they are implemented in each module.
'''
class Event:
    def __init__(self, string_id: str, time: float, priority: int = 0, blame: Optional[Any] = None, observer: Optional[Any] = None, log_event: bool = False):
        self._unique_id = None # unique id assigned by the scheduler
        self.string_id = string_id  # A string identifier for the event
        self.time = time  # The time at which the event occurs
        self.priority = priority  # Priority of the event, lower values are processed first
        self.blame = blame  # blame source, if any
        self.observer = observer  # Observer for the event, if any (we should implement an EventReceive for each observer that may handle events, otherwise the scheduler needs to handle every possibile type of event)
        self.log_event = log_event # flag to log the event if true

    def __str__(self) -> str:
        return f"Event(id={self.id}, string_id='{self.string_id}', time={self.time}, blame={self.blame})"

    @abstractmethod
    def log_string(self) -> str:
        pass
    
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