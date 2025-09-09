from abc import ABC, abstractmethod
from typing import Optional, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from simulator.entities.physical.devices.nodes import StaticNode

class Layer(ABC):
    '''
    Abstract base class for all layers in the simulator.
    '''
    def __init__(self, host: "StaticNode"):
        super().__init__()
        self.host = host
        
    @abstractmethod
    def send(self, payload: Any, destination: Optional[Any] = None) -> None:
        pass

    @abstractmethod
    def receive(self, payload: Any, sender_addr: bytes, rssi: float) -> None:
        pass