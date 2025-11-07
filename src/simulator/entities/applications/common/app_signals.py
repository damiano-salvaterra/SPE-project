from typing import Any, Dict
from simulator.entities.common.entity_signal import EntitySignal

class AppStartSignal(EntitySignal):
    def __init__(self, descriptor: str, timestamp: float):
        super().__init__(timestamp, "APP_START", descriptor)

class AppSendSignal(EntitySignal):
    def __init__(self, descriptor: str, timestamp: float, 
                 packet_type: str, seq_num: int, destination: bytes):
        super().__init__(timestamp, "SEND", descriptor)
        self.packet_type = packet_type
        self.seq_num = seq_num
        self.dest = destination.hex()

    def get_log_data(self) -> Dict[str, Any]:
        data = super().get_log_data()
        data.update({
            "type": self.packet_type,
            "seq_num": self.seq_num,
            "dest": self.dest
        })
        return data

class AppReceiveSignal(EntitySignal):
    def __init__(self, descriptor: str, timestamp: float, 
                 packet_type: str, seq_num: int, source: bytes, hops: int):
        super().__init__(timestamp, "RECEIVE", descriptor)
        self.packet_type = packet_type
        self.seq_num = seq_num
        self.source = source.hex()
        self.hops = hops

    def get_log_data(self) -> Dict[str, Any]:
        data = super().get_log_data()
        data.update({
            "type": self.packet_type,
            "seq_num": self.seq_num,
            "source": self.source,
            "hops": self.hops
        })
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
    def __init__(self, descriptor: str, timestamp: float, 
                 packet_type: str, seq_num: int, reason: str):
        super().__init__(timestamp, "SEND_FAIL", descriptor)
        self.packet_type = packet_type
        self.seq_num = seq_num
        self.reason = reason  # Standardized failure reason (e.g., "No Route")

    def get_log_data(self) -> Dict[str, Any]:
        data = super().get_log_data()
        data.update({
            "type": self.packet_type,
            "seq_num": self.seq_num,
            "reason": self.reason
        })
        return data