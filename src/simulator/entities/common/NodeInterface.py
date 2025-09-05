from typing import Protocol
from simulator.engine.common.SimulationContext import SimulationContext


class NetworkNode(Protocol):
    """
    Interface that defines what network protocols need from their host node.
    This eliminates circular dependencies between protocols and concrete node implementations.
    """

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
    def mac(self):
        """MAC layer reference"""
        ...
