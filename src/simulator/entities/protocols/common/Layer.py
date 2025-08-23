from abc import ABC, abstractmethod
from typing import Optional, Any, TYPE_CHECKING
#from simulator.entities.physical.devices.nodes import StaticNode
if TYPE_CHECKING:
    from simulator.entities.physical.devices.nodes import StaticNode # solves the problem of the circular import of StaticNode

class Layer(ABC):
    """
    Abstract base class for all layers in the simulator.
    Each layer should implement at least the "send" and "receive" methods.
    """
    def __init__(self, host: "StaticNode"):
        super().__init__()
        self.host = host
        
    @abstractmethod
    def send(payload: Any, destination: Optional[Any] = None):
        pass
    @abstractmethod
    def receive(payload: Any, sender: Optional[Any] = None):
        pass
        