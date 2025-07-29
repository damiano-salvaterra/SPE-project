from Layer import Layer
from entities.physical.devices.Node import Node


class MAC802_15_4(Layer):
    def __init__(self, host: Node):
        super().__init__(self)
        self.host = host