from engine.common.Event import Event
from simulator.network.phy.common.Transmission import Transmission
from typing import Optional, Any
from collections.abc import Callable

from typing import Optional, Any, Callable

'''
This event is scheduled by the PhyLayer and handled by WirelessChannel
'''
class PhyTxStartEvent(Event):
    def __init__(self, time: float, string_id: str = None, priority: int = 0,
                 blame: Optional[Any] = None, callback: Callable = None,
                 log_event: bool = False, **kwargs):
        
        super().__init__(string_id, time, priority, blame, callback, log_event)
        self.transmission = kwargs.get("transmission")

'''
This event is handled by the WirelessChannel and schedulet together with PhyTxStartEvent
'''
class PhyTxEndEvent(Event):
    def __init__(self, time: float, string_id: str = None, priority: int = 0,
             blame: Optional[Any] = None, callback: Callable = None,
             log_event: bool = False, **kwargs):
    
        super().__init__(string_id, time, priority, blame, callback, log_event)
        self.transmission = kwargs.get("transmission")



'''
This event is scheduled by WirelessChannel and handled by the PhyLayer
'''
class PhyRxStartEvent(Event):
    def __init__(self, time: float, string_id: str = None, priority: int = 0,
                 blame: Optional[Any] = None, callback: Callable = None,
                 log_event: bool = False, **kwargs):
        
        super().__init__(string_id, time, priority, blame, callback, log_event)
        self.transmission = kwargs.get("transmission")
        

'''
This event is scheduled together with PhyRxStartEvent and handled by PhyLayer
'''
class PhyRxEndEvent(Event):
    def __init__(self, time: float, string_id: str = None, priority: int = 0,
             blame: Optional[Any] = None, callback: Callable = None,
             log_event: bool = False, **kwargs):
    
        super().__init__(string_id, time, priority, blame, callback, log_event)
        self.transmission = kwargs.get("transmission")
        
