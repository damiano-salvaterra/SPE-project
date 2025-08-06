from abc import ABC, abstractmethod
from protocols.common.packets import MACFrame
from entities.physical.devices.Node import Node

class Layer(ABC):
    """
    Abstract base class for all layers in the simulator.
    Each layer should implement at least the "send" and "receive" methods.
    """
    def __init__(self, host: Node):
        super().__init__()
        self.host = host
        
    @abstractmethod
    def send(payload: MACFrame):
        pass
    @abstractmethod
    def receive(payload: MACFrame):
        pass
        