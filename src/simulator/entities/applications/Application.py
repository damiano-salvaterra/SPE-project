from abc import ABC, abstractmethod
from simulator.entities.protocols.common.packets import NetPacket
from simulator.entities.common import Entity


class Application(ABC, Entity):
    """
    Abstract base class for Node application in the simulator.
    """

    def __init__(self):
        ABC.__init__(self)
        Entity.__init__(self)

    @abstractmethod
    def generate_traffic(self) -> None:
        pass

    @abstractmethod
    def receive(self, packet: NetPacket, sender_addr: bytes) -> None:
        pass
