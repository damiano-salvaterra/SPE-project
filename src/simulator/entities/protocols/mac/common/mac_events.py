from engine.common.Event import Event
from typing import Optional, Any
from collections.abc import Callable

class MacSendReqEvent(Event):
    pass


class MacACKTimeoutEvent(Event):
    pass

class MacACKSendEvent(Event):
    pass