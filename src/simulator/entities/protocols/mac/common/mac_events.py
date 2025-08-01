from engine.common.Event import Event
from typing import Optional, Any
from collections.abc import Callable

class MacSendReqEvent(Event):
    def __init__(self, time: float, string_id: str = None, priority: int = 0,
                 blame: Optional[Any] = None, callback: Callable = None,
                 log_event: bool = False, **kwargs):
        
        super().__init__(string_id, time, priority, blame, callback, log_event)
        self.frame = kwargs.get("frame")

    def run(self):
        self.callback(self.frame)


class MacACKTimeoutEvent(Event):
    def __init__(self, time: float, string_id: str = None, priority: int = 0,
             blame: Optional[Any] = None, callback: Callable = None,
             log_event: bool = False, **kwargs):
        
        super().__init__(string_id, time, priority, blame, callback, log_event)
        self.retry = kwargs.get("retry")

    def run(self):
        self.callback()