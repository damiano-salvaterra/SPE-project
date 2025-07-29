from abc import ABC, abstractmethod
from Node import Node 

class Layer(ABC):
    """
    Abstract base class for all layers in the simulator.
    Each layer should implement at least the "send" and "receive" methods.
    """
    def __init__(self, node: Node):
        super().__init__()
        self.node = node
        
    @abstractmethod
    def send(destination, payload):
        pass
    @abstractmethod
    def receive(sender, payload):
        pass
        
    