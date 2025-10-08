"""
Signals for TARP protocol events
"""

from simulator.entities.common import EntitySignal


class TARPForwardingSignal(EntitySignal):
    """
    Signal emitted when TARP forwards a packet.
    Contains information about the packet routing.
    """

    def __init__(
        self,
        descriptor: str,
        timestamp: float,
        received_from: bytes,
        original_source: bytes,
        destination: bytes,
        forwarding_to: bytes,
        packet_type: str,
    ):
        super().__init__(descriptor=descriptor, timestamp=timestamp)
        self.received_from = received_from
        self.original_source = original_source
        self.destination = destination
        self.forwarding_to = forwarding_to
        self.packet_type = packet_type


class TARPReceiveSignal(EntitySignal):
    """
    Signal emitted when TARP receives a packet destined for this node.
    """

    def __init__(
        self,
        descriptor: str,
        timestamp: float,
        received_from: bytes,
        original_source: bytes,
        packet_type: str,
    ):
        super().__init__(descriptor=descriptor, timestamp=timestamp)
        self.received_from = received_from
        self.original_source = original_source
        self.packet_type = packet_type
