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
    pass
'''
This event is handled by the WirelessChannel and schedulet together with PhyTxStartEvent
'''
class PhyTxEndEvent(Event):
    pass

'''
This event is scheduled by WirelessChannel and handled by the PhyLayer
'''
class PhyRxStartEvent(Event):
    pass

'''
This event is scheduled together with PhyRxStartEvent and handled by PhyLayer
'''
class PhyRxEndEvent(Event):
    pass