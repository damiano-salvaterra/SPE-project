from abc import ABC, abstractmethod
#from simulator.entities.physical.devices.nodes import StaticNode

class Application(ABC):
    """
    Abstract base class for Node application in the simulator.
    """
    def __init__(self):
        super().__init__()
        
        
    @abstractmethod
    def generate_traffic(self):
        pass

        