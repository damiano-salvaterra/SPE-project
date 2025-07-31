from Layer import Layer
from entities.physical.devices.Node import Node

'''
This class implements the non-beacon enabled 802.15.4 MAC CSMA protocol AS IT IS IMPLEMENTED in ContikiOS.
This means that it may not be strictly compliant to the IEEE 802.15.4 standard MAC.
Reference to the C implementation of the CSMA in ContikiOS (offical repository):
https://github.com/contiki-os/contiki/blob/master/core/net/mac/csma.c
'''

class ContikiOS_MAC_802154(Layer):
    def __init__(self, host: Node):
        super().__init__(self)
        self.host = host