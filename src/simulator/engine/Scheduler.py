import heapq

from simulator.engine.config import SCHEDULER_TIME_SCALE
from simulator.engine.common.Event import Event


class Scheduler:
    """
    Manages the event queue for the discrete-event simulation.
    It is a standard class; the Kernel ensures a single instance is used per simulation.
    The public API works in seconds, while an internal time scale is used for precision.
    """

    def __init__(self):
        self.event_queue = []
        self._current_time_internal = 0.0  # Time in internal scale (e.g., ms)
        self.last_event_id = 0
        self._time_scale = SCHEDULER_TIME_SCALE

    def schedule(self, event: Event) -> None:
        """Schedules an event. The event's time is expected in seconds."""
        self.last_event_id += 1
        event._unique_id = self.last_event_id

        # Convert time from seconds to the internal time scale for storage
        event_time_internal = event.time / self._time_scale

        if event_time_internal < self._current_time_internal:
            current_time_s = self.now()
            raise ValueError(
                f"Cannot schedule event in the past: event_time={event.time}s < current_time={current_time_s}s"
            )

        # The event tuple in the heap stores the internal time for correct sorting
        heapq.heappush(self.event_queue, (event_time_internal, event))

    def unschedule(self, event: Event) -> bool:
        """Marks an event as cancelled so it will not be executed."""
        event._cancelled = True
        return True

    def run_next_event(self) -> None:
        """Pops the next event, updates simulation time, and runs it."""
        if self.event_queue:
            internal_time, event = heapq.heappop(self.event_queue)

            if not event._cancelled:
                self._current_time_internal = internal_time

                # Restore the original time in seconds before executing the callback
                event.time = self.now()
                event.run()

    def now(self) -> float:
        """Returns the current simulation time in SECONDS."""
        return self._current_time_internal * self._time_scale

    def is_empty(self) -> bool:
        return len(self.event_queue) == 0

    def get_queue_length(self) -> int:
        return len(self.event_queue)

    def flush(self) -> None:
        """Resets the scheduler to its initial state."""
        self.event_queue = []
        self._current_time_internal = 0.0
        self.last_event_id = 0
