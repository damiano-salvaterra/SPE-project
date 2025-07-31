from network.common.packets import Packet802_15_4
from entities.physical.devices.Node import Node

class Transmission():
    def __init__(self, transmitter: Node, packet: Packet802_15_4, transmission_power: float, unique_id: int = None):
        self.packet = packet
        self.transmitter = transmitter
        self.transmission_power = transmission_power
        #self.tx_start = tx_start
        #self.tx_end = tx_end
        self.unique_id = unique_id
