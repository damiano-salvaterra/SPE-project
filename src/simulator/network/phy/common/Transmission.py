from packets import Packet
from entities.physical.devices.Node import Node

class Transmission():
    def __init__(self, transmitter: Node, packet: Packet, power: float, unique_id: int):
        self.packet = packet
        self.transmitter = transmitter
        self.power = power
        self.unique_id = unique_id
