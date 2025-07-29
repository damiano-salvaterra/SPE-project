from abc import ABC, abstractmethod
from entities.physical.devices.Node import Node
from typing import Optional, Any

class Application(ABC):
    """
    Abstract base class for Node application in the simulator.
    """
    def __init__(self):
        super().__init__()
        
        
    @abstractmethod
    def generate_traffic_data(destination: Node = None, payload: Optional[Any] = Node):
        pass

        