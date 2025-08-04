import heapq
from config import SCHEDULER_TIME_SCALE
from typing import Optional, List

from simulator.engine.common.Event import Event

#TODO: fix the singleton implementation

class Scheduler:
    _instance: Optional["Scheduler"] = None ## "" is a forward reference (class is not defined yet)

    def __init__(self) -> None:
        if Scheduler._instance is not None:
            raise Exception("Use the 'init()' method to get the instance of this class.")
        self._time_scale = SCHEDULER_TIME_SCALE # time scale for the scheduler, to avoid floating point precision issues
        self._instance.event_queue: List[Event] = []
        self._instance._current_time: float = 0.0 # Current simulation time, to avoid to schedule past events
        self.last_event_id: int = 0 # Unique ID for each event, to avoid collisions


    @classmethod
    def init(cls) -> "Scheduler":
        if cls._instance is None:
            cls._instance = cls.__new__(cls) # create Singleton instance
            Scheduler.__init__(cls._instance) # initialize the instance
        return cls._instance

    def schedule(self, event: Event) -> float:
        """
        Schedule an event.
        """
        #assign a unique id
        self.last_event_id += 1
        event._unique_id = self.last_event_id
        #convert time to the scheduler time scale
        event.time = event.time / self._time_scale

        if event.time < self._current_time:
            raise ValueError(f"Cannot schedule event in the past: event.time={event.time} [scheduler time scale] < current_time={self.current_time} [scheduler time scale]")

        heapq.heappush(self.event_queue, event)  # heapq implements a min-heap, so the smallest
        # (accordingly to the overloaded "<" in the Event class")
        # event will be at the root
        return event.time
    
    def unschedule(self, event: Event) -> bool:
        '''Removes an event from the schedule'''
        event._cancelled = True
        return True



    def peek_next_event(self) -> Optional[Event]:
        """
        Get the next event from the queue.
        """
        if self.event_queue:
            return self.event_queue[0]
        else:
            return None
        
        
    def run_next_event(self) -> None:
        '''Run the next event'''
        if self.event_queue:
            event = heapq.heapop(self.event_queue)
            if not event._cancelled:
                self._current_time = event.time # update simulation time
                #convert time back to seconds
                event.time = event.time * self._time_scale
                event.run()


    def now(self) -> float:
        return self._current_time

    def is_empty(self) -> bool:
        """
        Check if the event queue is empty.
        """
        return len(self.event_queue) == 0

    def get_queue_length(self) -> int:
        """
        Get the length of the event queue.
        """
        return len(self.event_queue)

    def flush(self) -> None:
        """
        Flush the event queue.
        """
        self.event_queue = []