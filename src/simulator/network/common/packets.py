'''
This module implmentes the Packet class and subclasses
'''

class Packet802_15_4():
    packet_max_gross_duration = 0.004064 # gross estimate of the longest packet duration for 802.15.4 @ 2.4Ghz, 250 kbps
                            # maximum packet size is 127 bytes, we keep this size for worst case scenario 
    def __init__(self):
        pass