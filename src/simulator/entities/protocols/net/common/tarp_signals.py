# src/simulator/entities/protocols/net/common/tarp_signals.py
from typing import Any, Dict, Optional
from simulator.entities.common import EntitySignal


class TARPUnicastSendSignal(EntitySignal):
    """
    Signal emitted when TARP *originates* a unicast packet.
    """

    def __init__(
        self,
        descriptor: str,
        timestamp: float,
        packet_type: str,
        original_source: bytes,
        final_dest: bytes,
        tx_hop: bytes,
        rx_hop: bytes,
    ):
        super().__init__(timestamp, "UC_SEND", descriptor)
        self.packet_type = packet_type
        self.orig_src = original_source.hex()
        self.final_dest = final_dest.hex()
        self.tx_hop = tx_hop.hex()
        self.rx_hop = rx_hop.hex()

    def get_log_data(self) -> Dict[str, Any]:
        data = super().get_log_data()
        data.update(
            {
                "type": self.packet_type,
                "orig_src": self.orig_src,
                "final_dest": self.final_dest,
                "tx_hop": self.tx_hop,
                "rx_hop": self.rx_hop,
            }
        )
        return data


class TARPForwardingSignal(EntitySignal):
    """
    Signal emitted when TARP *forwards* a unicast packet.
    """

    def __init__(
        self,
        descriptor: str,
        timestamp: float,
        packet_type: str,
        original_source: bytes,
        final_dest: bytes,
        prev_hop: bytes,
        tx_hop: bytes,
        rx_hop: bytes,
    ):
        super().__init__(timestamp, "FORWARD", descriptor)
        self.packet_type = packet_type
        self.orig_src = original_source.hex()
        self.final_dest = final_dest.hex()
        self.prev_hop = prev_hop.hex()
        self.tx_hop = tx_hop.hex()
        self.rx_hop = rx_hop.hex()

    def get_log_data(self) -> Dict[str, Any]:
        data = super().get_log_data()
        data.update(
            {
                "type": self.packet_type,
                "orig_src": self.orig_src,
                "final_dest": self.final_dest,
                "prev_hop": self.prev_hop,
                "tx_hop": self.tx_hop,
                "rx_hop": self.rx_hop,
            }
        )
        return data


class TARPUnicastReceiveSignal(EntitySignal):
    """
    Signal emitted when TARP *receives* a unicast packet for itself.
    """

    def __init__(
        self,
        descriptor: str,
        timestamp: float,
        packet_type: str,
        original_source: bytes,
        final_dest: bytes,
        tx_hop: bytes,
        rx_hop: bytes,
        report_content: Optional[str] = None,
    ):
        super().__init__(timestamp, "UC_RECV", descriptor)
        self.packet_type = packet_type
        self.orig_src = original_source.hex()
        self.final_dest = final_dest.hex()
        self.tx_hop = tx_hop.hex()
        self.rx_hop = rx_hop.hex()
        self.report_content = report_content  # Specific for reports

    def get_log_data(self) -> Dict[str, Any]:
        data = super().get_log_data()
        data.update(
            {
                "type": self.packet_type,
                "orig_src": self.orig_src,
                "final_dest": self.final_dest,
                "tx_hop": self.tx_hop,
                "rx_hop": self.rx_hop,
            }
        )
        if self.report_content:
            data["report_content"] = self.report_content
        return data


class TARPDropSignal(EntitySignal):
    """
    Signal emitted when TARP drops a packet.
    """

    def __init__(
        self,
        descriptor: str,
        timestamp: float,
        packet_type: str,
        original_source: bytes,
        final_dest: bytes,
        reason: str,
    ):
        super().__init__(timestamp, "DROP", descriptor)
        self.packet_type = packet_type
        self.orig_src = original_source.hex()
        self.final_dest = final_dest.hex()
        self.reason = reason  # Standardized reason (e.g., "No Route", "Unknown Sender")

    def get_log_data(self) -> Dict[str, Any]:
        data = super().get_log_data()
        data.update(
            {
                "type": self.packet_type,
                "orig_src": self.orig_src,
                "final_dest": self.final_dest,
                "reason": self.reason,
            }
        )
        return data


class TARPBroadcastSendSignal(EntitySignal):
    """
    Signal emitted when TARP sends a beacon.
    """

    def __init__(
        self, descriptor: str, timestamp: float, epoch: int, metric: float, hops: int
    ):
        super().__init__(timestamp, "BC_SEND", descriptor)
        self.epoch = epoch
        self.metric = metric
        self.hops = hops

    def get_log_data(self) -> Dict[str, Any]:
        data = super().get_log_data()
        data.update({"epoch": self.epoch, "metric": self.metric, "hops": self.hops})
        return data


class TARPBroadcastReceiveSignal(EntitySignal):
    """
    Signal emitted when TARP receives a beacon.
    """

    def __init__(self, descriptor: str, timestamp: float, source: bytes, rssi: float):
        super().__init__(timestamp, "BC_RECV", descriptor)
        self.source = source.hex()
        self.rssi = rssi

    def get_log_data(self) -> Dict[str, Any]:
        data = super().get_log_data()
        data.update({"source": self.source, "rssi": self.rssi})
        return data


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
        super().__init__(timestamp, "PARENT_CHANGE", descriptor)
        self.old_parent = old_parent.hex() or "None"
        self.new_parent = new_parent.hex() or "None"

    def get_log_data(self) -> Dict[str, Any]:
        data = super().get_log_data()
        data.update({"old_parent": self.old_parent, "new_parent": self.new_parent})
        return data
