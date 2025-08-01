from simulator.entities.protocols.common.Layer import Layer
from entities.physical.devices.Node import Node


class TARP(Layer):
    def __init__(self, host: Node):
        super().__init__(self)
        self.host = host