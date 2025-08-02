from protocols.common.packets import Frame_802154
from entities.physical.devices.Node import Node

'''
This class encapulates the physical transmission with some metadata.
NB: it is a physical entity and has no meaning in a "network-packet-way": it is a software object
which only purpose is utility for the physical layer module. refer to packets.py for real network packets'''
class Transmission():
    def __init__(self, transmitter: Node, frame: Frame_802154, transmission_power_dBm: float, unique_id: int = None):
        self.mac_frame = frame
        self.transmitter = transmitter
        self.transmission_power_dBm = transmission_power_dBm
        #self.tx_start = tx_start
        #self.tx_end = tx_end
        self.unique_id = unique_id
