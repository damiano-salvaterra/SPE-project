from simulator.entities.common.entity import Entity
from simulator.engine.common.SimulationContext import SimulationContext


class NetworkNode(Entity):
    """
    Interface that defines what network protocols need from their host node.
    This eliminates circular dependencies between protocols and concrete node implementations.
    """

    def __init__(self):
        super().__init__()

    @property
    def id(self) -> str:
        """Node identifier"""
        ...

    @property
    def linkaddr(self) -> bytes:
        """Link layer address"""
        ...

    @property
    def context(self) -> SimulationContext:
        """Simulation context"""
        ...

    @property
    def phy(self) -> Entity:
        ...

    @property
    def rdc(self) -> Entity:
        ...
    @property
    def mac(self) -> Entity:
        ...
    @property
    def net(self) -> Entity:
        ...
    @property
    def app(self) -> Entity:
        ...
