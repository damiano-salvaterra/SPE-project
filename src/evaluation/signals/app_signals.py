"""
Signals for application-level events
"""

from simulator.entities.common import EntitySignal
from simulator.entities.protocols.common.packets import NetPacket


class AppPingReceivedSignal(EntitySignal):
    """
    Signal emitted when a PING packet is received by an application.
    Contains information about the original source of the PING.
    """

    def __init__(
        self,
        descriptor: str,
        timestamp: float,
        packet: NetPacket,
        source_addr: bytes,
    ):
        super().__init__(descriptor=descriptor, timestamp=timestamp)
        self.packet = packet
        self.source_addr = source_addr
