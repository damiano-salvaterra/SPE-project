"""
Signals for application-level events
"""

from simulator.entities.common import EntitySignal
from simulator.entities.protocols.common.packets import NetPacket


class AppStartSignal(EntitySignal):
    """
    Signal emitted when the application's start() method is called.
    """
    def __init__(
        self,
        descriptor: str,
        timestamp: float,
    ):
        super().__init__(descriptor=descriptor, timestamp=timestamp)


class AppSendSignal(EntitySignal):
    """
    Signal emitted when the application sends a PING or PONG packet.
    """
    def __init__(
        self,
        descriptor: str,
        timestamp: float,
        packet_type: str, # "PING" or "PONG"
        seq_num: int,
        destination: bytes,
    ):
        super().__init__(descriptor=descriptor, timestamp=timestamp)
        self.packet_type = packet_type
        self.seq_num = seq_num
        self.destination = destination


class AppReceiveSignal(EntitySignal):
    """
    Signal emitted when the application receives a PING or PONG packet.
    """
    def __init__(
        self,
        descriptor: str,
        timestamp: float,
        packet_type: str, # "PING" or "PONG"
        seq_num: int,
        source: bytes,
    ):
        super().__init__(descriptor=descriptor, timestamp=timestamp)
        self.packet_type = packet_type
        self.seq_num = seq_num
        self.source = source


class AppTimeoutSignal(EntitySignal):
    """
    Signal emitted when a PING times out waiting for a PONG.
    """
    def __init__(
        self,
        descriptor: str,
        timestamp: float,
        seq_num: int,
    ):
        super().__init__(descriptor=descriptor, timestamp=timestamp)
        self.seq_num = seq_num


class AppSendFailSignal(EntitySignal):
    """
    Signal emitted when the application layer tries to send a packet
    but the network layer rejects it (e.g., no route).
    """
    def __init__(
        self,
        descriptor: str,
        timestamp: float,
        packet_type: str,
        seq_num: int,
        reason: str,
    ):
        super().__init__(descriptor=descriptor, timestamp=timestamp)
        self.packet_type = packet_type
        self.seq_num = seq_num
        self.reason = reason