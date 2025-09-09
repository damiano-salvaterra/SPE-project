from typing import Optional, Any
from abc import ABC
from enum import Enum
from dataclasses import dataclass


"""
This module implments the Packet class and subclasses
"""


"""Network layer stuff"""

"""Some interfaces. Mostly for future extensibility of the simulator"""


@dataclass
class NetPacket:
    APDU: Optional[Any]  # Application Protocol Data Unit


class TARPHeader(ABC):
    pass


class TARPUnicastType(Enum):
    UC_TYPE_DATA = 0
    UC_TYPE_REPORT = 1


@dataclass
class TARPUnicastHeader(TARPHeader):
    type: TARPUnicastType
    s_addr: bytes
    d_addr: bytes
    hops: int


@dataclass
class TARPBroadcastHeader(TARPHeader):
    epoch: int
    metric_q124: float
    hops: int
    parent: Optional[bytes]


@dataclass
class TARPPacket(NetPacket):
    header: TARPUnicastHeader | TARPBroadcastHeader


"""Mac layer stuff"""


class MACFrame(ABC):
    on_air_duration = 0.0  # default, just for polymorphism

    def __init__(self, NPDU: Optional[NetPacket] = None):
        super().__init__()
        self.NPDU = NPDU  # PDU from upper layer


class Frame_802_15_4(MACFrame):
    on_air_duration = (
        4.83 * 1e-3
    )  # gross estimate of the longest packet duration (SHR + PHR + MAC Header + FCS + payload) for 802.15.4 @ 2.4Ghz, 250 kbps
    # maximum packet size is 127 bytes, we keep this size for worst case scenario. TODO: verify this
    broadcast_linkaddr = bytes([0xFF, 0xFF])
    daddr_detection_time = (
        352 * 1e-6
    )  # time for receiving and decoding the destination address, starting from the reception of the preamble
    # the 2-byte-address ends at byte 11, the on air time of a byte is 32 us

    def __init__(
        self,
        seqn: int,
        tx_addr: bytes,
        rx_addr: bytes,
        requires_ack: bool = False,
        NPDU: Optional[NetPacket] = None,
    ):
        super().__init__(NPDU=NPDU)
        self.seqn = seqn
        self.tx_addr = tx_addr  # transmitter address
        self.rx_addr = rx_addr  # receiver address
        self._requires_ack = requires_ack  # false if it is broadcast


class Ack_802_15_4(MACFrame):
    on_air_duration = (
        352 * 1e-6
    )  # duration of the ack packet (SHR + PHR + MAC Header + FCS + payload)
    ack_detection_time = (
        288 * 1e-6
    )  # time required to successfully detect an ack  at the receiver. TODO: reference?

    # i can detect it afte 9 bytes
    def __init__(self, seqn: int):
        super().__init__(NPDU=None)
        self.seqn = seqn


"""
TODO: we can dynalmically model the length of the aìpackets and define constants like
# Costanti per IEEE 802.15.4 @ 2.4 GHz O-QPSK
BITRATE_BPS = 250000  # 250 kbps
BITS_PER_SYMBOL = 4
SYMBOL_RATE_SPS = BITRATE_BPS / BITS_PER_SYMBOL # 62.5 kSps
TIME_PER_BYTE_S = 8 / BITRATE_BPS # 32 us

# Bytes per componente del frame PHY
PHY_SHR_BYTES = 4 # Preamble
PHY_SFD_BYTES = 1 # Start-of-frame delimiter
PHY_PHR_BYTES = 1 # PHY Header (lunghezza frame)
PHY_OVERHEAD_BYTES = PHY_SHR_BYTES + PHY_SFD_BYTES + PHY_PHR_BYTES

# Bytes per componente del frame MAC
MAC_FCS_BYTES = 2 # Frame Check Sequence

instead of hard coding stuff
"""
