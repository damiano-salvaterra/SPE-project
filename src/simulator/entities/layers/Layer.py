from abc import ABC, abstractmethod

class Layer(ABC):
    """
    Abstract base class for all layers in the simulator.
    Each layer should implement at least the "send" and "receive" methods.
    """

    @abstractmethod
    def send(destination, payload):
        pass
    @abstractmethod
    def receive(sender, payload):
        pass
        
    