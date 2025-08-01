from engine.common.Event import Event
from protocols.phy.common.Transmission import Transmission
from entities.physical.media.WirelessChannel import WirelessChannel
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

    def run(self, transmission: Transmission):
        self.callback(self.transmission)
'''
This event is handled by the WirelessChannel and schedulet together with PhyTxStartEvent
'''
class PhyTxEndEvent(Event):
    def __init__(self, time: float, string_id: str = None, priority: int = 0,
             blame: Optional[Any] = None, callback: Callable = None,
             log_event: bool = False, callback2: Callable = None, **kwargs):
    
        super().__init__(string_id, time, priority, blame, callback, log_event)
        self.callback2 = callback2
        self.transmission_cb1 = kwargs.get("transmission")


    def run(self, transmission: Transmission):
        self.callback(self.transmission_cb1)
        self.callback2()

'''
This event is scheduled by WirelessChannel and handled by the PhyLayer
'''
class PhyRxStartEvent(Event):
    def __init__(self, time: float, string_id: str = None, priority: int = 0,
                 blame: Optional[Any] = None, callback: Callable = None,
                 log_event: bool = False, **kwargs):
        
        super().__init__(string_id, time, priority, blame, callback, log_event)
        self.transmission = kwargs.get("transmission")
        self.channel = kwargs.get("channel_subject")
        
    def run(self, transmission: Transmission, channel_subject = WirelessChannel):
        self.callback(transmission, channel_subject)

'''
This event is scheduled together with PhyRxStartEvent and handled by PhyLayer
'''
class PhyRxEndEvent(Event):
    def __init__(self, time: float, string_id: str = None, priority: int = 0,
             blame: Optional[Any] = None, callback: Callable = None,
             log_event: bool = False, **kwargs):
    
        super().__init__(string_id, time, priority, blame, callback, log_event)
        self.channel = kwargs.get("channel_subject")
        
    def run(self, transmission: Transmission, channel_subject = WirelessChannel):
            self.callback(transmission, channel_subject)