from abc import ABC, abstractmethod
from typing import Optional, Any
from simulator.entities.common.NodeInterface import NetworkNode


class Layer(ABC):
    """
    Abstract base class for all layers in the simulator.
    Each layer should implement at least the "send" and "receive" methods.
    """

    def __init__(self, host: NetworkNode):
        super().__init__()
        self.host = host

    @abstractmethod
    def send(payload: Any, destination: Optional[Any] = None):
        pass

    @abstractmethod
    def receive(payload: Any, sender: Optional[Any] = None):
        pass
