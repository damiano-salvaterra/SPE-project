"""
Signals for TARP protocol events
"""

from simulator.entities.common import EntitySignal

class TARPUnicastSendSignal(EntitySignal):
    """
    Signal emitted when TARP sends a packet.
    Contains information about the packet being sent.
    """

    def __init__(
        self,
        descriptor: str,
        timestamp: float,
        destination: bytes,
        packet_type: str,
    ):
        super().__init__(descriptor=descriptor, timestamp=timestamp)
        self.destination = destination
        self.packet_type = packet_type

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


class TARPUnicastReceiveSignal(EntitySignal):
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


class TARPDropSignal(EntitySignal):
    """
    Signal emitted when TARP drops a packet.
    """

    def __init__(
        self,
        descriptor: str,
        timestamp: float,
        destination: bytes,
        packet_type: str,

    ):
        super().__init__(descriptor=descriptor, timestamp=timestamp)
        self.destination = destination
        self.packet_type = packet_type
class TARPBroadcastSendSignal(EntitySignal):
    """
    Signal emitted when TARP sends a beacon.
    """

    def __init__(
        self,
        descriptor: str,
        timestamp: float,
    ):
        super().__init__(descriptor=descriptor, timestamp=timestamp)

class TARPBroadcastReceiveSignal(EntitySignal):
    """
    Signal emitted when TARP receives a beacon.
    """

    def __init__(
        self,
        descriptor: str,
        timestamp: float,
        source: bytes,
    ):
        super().__init__(descriptor=descriptor, timestamp=timestamp)
        self.source = source

class TARPParentChangeSignal(EntitySignal):
    """
    Signal emitted when TARP changes its parent node.
    """

    def __init__(
        self,
        descriptor: str,
        timestamp: float,
        old_parent: bytes,
        new_parent: bytes,
    ):
        super().__init__(descriptor=descriptor, timestamp=timestamp)
        self.old_parent = old_parent
        self.new_parent = new_parent