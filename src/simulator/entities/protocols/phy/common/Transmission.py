from protocols.common.packets import Packet
from entities.physical.devices.Node import Node

'''
This class encapulates the physical transmission with some metadata.
NB: it is a physical entity and has no meaning in a "network-packet-way": it is a software object
which only purpose is utility for the physical layer module. refer to packets.py for real network packets'''
class Transmission():
    def __init__(self, transmitter: Node, packet: Packet, transmission_power_dBm: float, unique_id: int = None):
        self.packet = packet
        self.transmitter = transmitter
        self.transmission_power_dBm = transmission_power_dBm
        #self.tx_start = tx_start
        #self.tx_end = tx_end
        self.unique_id = unique_id
