from typing import Optional

'''
This class implements the base Event class for the simulator.
It provides an interface for the scheduler.
Real events inherits from this class and they are implemented in each module.
'''
class Event:
    def __init__(self, unique_id: int, string_id: str, time: float, priority: int = 0, blame: Optional[str] = None):
        self.id = unique_id
        self.string_id = string_id  # A string identifier for the event
        self.time = time  # The time at which the event occurs
        self.blame = blame  # blame source, if any

    def __str__(self) -> str:
        return f"Event(id={self.id}, string_id='{self.string_id}', time={self.time}, blame={self.blame})"

    
    
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