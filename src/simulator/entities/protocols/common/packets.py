from typing import Optional, Any
from abc import ABC, abstractmethod

'''
This module implments the Packet class and subclasses
'''

class Packet(ABC):
     def __init__(self, data: Optional[Any]):
        super().__init__()
        self.data = data
         

class Frame802_15_4(Packet):
    packet_max_gross_duration = 0.004064 # gross estimate of the longest packet duration for 802.15.4 @ 2.4Ghz, 250 kbps
                            # maximum packet size is 127 bytes, we keep this size for worst case scenario 
    broadcast_linkaddr = bytes([0xFF, 0xFF])
    
    def __init__(self, linkaddr: bytes, data: Optional[Any] = None):
        self.linkaddr = linkaddr
        self.data = data