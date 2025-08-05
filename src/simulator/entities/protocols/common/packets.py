from typing import Optional, Any
from abc import ABC, abstractmethod

'''
This module implments the Packet class and subclasses
'''

class Packet(ABC):
     on_air_duration = 0.0 #default, just for polymorphism
     def __init__(self, data: Optional[Any]):
        super().__init__()
        self.data = data
         
class Frame_802154(Packet):
    on_air_duration = 4.83 * 1e-3# gross estimate of the longest packet duration (SHR + PHR + MAC Header + FCS + payload) for 802.15.4 @ 2.4Ghz, 250 kbps
                            # maximum packet size is 127 bytes, we keep this size for worst case scenario. TODO: verify this
    broadcast_linkaddr = bytes([0xFF, 0xFF])
    daddr_detection_time = 896 *1e-6 # time for receiving and decoding the destination address, starting from the reception of the preamble

    
    def __init__(self, seqn: int, saddr: bytes, daddr: bytes, requires_ack: bool = False, data: Optional[Any] = None):
        self.seqn = seqn
        self.saddr = saddr # source address
        self.daddr = daddr # destination address
        self._requires_ack = requires_ack # false if it is broadcast
        self._data = data


class Ack_802154(Packet):
    on_air_duration = 928 * 1e-6 # duration of the ack packet (SHR + PHR + MAC Header + FCS + payload)
    ack_detection_time = 160 * 1e-6 #time required to successfully detect an ack  at the receiver. TODO: reference?
    
    def __init__(self, seqn: int):
        self.seqn = seqn

