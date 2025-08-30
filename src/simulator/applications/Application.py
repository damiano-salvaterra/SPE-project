from abc import ABC, abstractmethod
from simulator.entities.protocols.common.packets import NetPacket


class Application(ABC):
    """
    Abstract base class for Node application in the simulator.
    """

    def __init__(self):
        super().__init__()

    @abstractmethod
    def generate_traffic(self) -> None:
        pass

    @abstractmethod
    def receive(self, packet: NetPacket, sender_addr: bytes) -> None:
        pass
