from simulator.engine.common.Event import Event


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

class PhyPacketTypeDetectionEvent(Event):
    pass

class PhyDaddrDetectionEvent(Event):
    pass