from typing import Any, Dict
from simulator.entities.common.entity_signal import EntitySignal


class AppBootstrapSignal(EntitySignal):
    def __init__(self, descriptor: str, timestamp: float):
        super().__init__(timestamp, "APP_BOOTSTRAP", descriptor)

class AppProcessStartSignal(EntitySignal):
    def __init__(self, descriptor: str, timestamp: float):
        super().__init__(timestamp, "APP_PROCESS_START", descriptor)
        
class AppSendSignal(EntitySignal):
    def __init__(
        self,
        descriptor: str,
        timestamp: float,
        packet_type: str,
        seq_num: int,
        dest_addr: bytes,
    ):
        super().__init__(timestamp, "SEND", descriptor)
        self.packet_type = packet_type
        self.seq_num = seq_num
        self.dest_addr = dest_addr.hex()

    def get_log_data(self) -> Dict[str, Any]:
        data = super().get_log_data()
        data.update(
            {"type": self.packet_type, "seq_num": self.seq_num, "dest": self.dest_addr}
        )
        return data


class AppReceiveSignal(EntitySignal):
    def __init__(
        self,
        descriptor: str,
        timestamp: float,
        packet_type: str,
        seq_num: int,
        source_addr: bytes,
        hops: int,
    ):
        super().__init__(timestamp, "RECEIVE", descriptor)
        self.packet_type = packet_type
        self.seq_num = seq_num
        self.source_addr = source_addr.hex()
        self.hops = hops

    def get_log_data(self) -> Dict[str, Any]:
        data = super().get_log_data()
        data.update(
            {
                "type": self.packet_type,
                "seq_num": self.seq_num,
                "source": self.source_addr,
                "hops": self.hops,
            }
        )
        return data


class AppTimeoutSignal(EntitySignal):
    def __init__(self, descriptor: str, timestamp: float, seq_num: int):
        super().__init__(timestamp, "TIMEOUT", descriptor)
        self.seq_num = seq_num

    def get_log_data(self) -> Dict[str, Any]:
        data = super().get_log_data()
        data.update({"seq_num": self.seq_num})
        return data


class AppSendFailSignal(EntitySignal):
    def __init__(
        self,
        descriptor: str,
        timestamp: float,
        packet_type: str,
        seq_num: int,
        reason: str,
    ):
        super().__init__(timestamp, "SEND_FAIL", descriptor)
        self.packet_type = packet_type
        self.seq_num = seq_num
        self.reason = reason  # Standardized failure reason (e.g., "No Route")

    def get_log_data(self) -> Dict[str, Any]:
        data = super().get_log_data()
        data.update(
            {"type": self.packet_type, "seq_num": self.seq_num, "reason": self.reason}
        )
        return data
