from typing import List
import pandas as pd

from simulator.engine.common.monitor import Monitor
from simulator.entities.common import Entity, EntitySignal


class PacketMonitor(Monitor):
    """
    A monitor that logs packet information for post-simulation analysis
    and can also print information in real-time for debugging.
    """

    def __init__(self, verbose=True):
        self.log: List[dict] = []
        self.verbose = verbose

    def update(self, entity: Entity, signal: EntitySignal):
        packet = signal.packet
        event_type = signal.event_type

        packet_type = type(packet).__name__
        seqn = getattr(packet, "seqn", "N/A")

        tx_addr_bytes = getattr(packet, "tx_addr", None)
        rx_addr_bytes = getattr(packet, "rx_addr", None)

        tx_addr = tx_addr_bytes.hex() if isinstance(tx_addr_bytes, bytes) else "N/A"
        rx_addr = rx_addr_bytes.hex() if isinstance(rx_addr_bytes, bytes) else "N/A"

        # --- Data Logging ---
        apdu = getattr(packet, "APDU", None)
        if isinstance(apdu, bytes):
            apdu = apdu.decode("utf-8", errors="ignore")

        npdu = getattr(packet, "NPDU", None)

        log_entry = {
            "time": signal.timestamp,
            "node_id": entity.host.id,
            "event": event_type,
            "packet_type": packet_type,
            "seqn": seqn,
            "tx_addr": tx_addr,
            "rx_addr": rx_addr,
            "payload": apdu if apdu is not None else npdu,
        }
        self.log.append(log_entry)

        # --- Real-time printing (optional) ---
        if self.verbose:
            packet_info = f"Type={packet_type}, Seqn={seqn}, Tx={tx_addr}, Rx={rx_addr}, Payload={log_entry['payload']}"
            print(
                f"MONITOR [{signal.timestamp:.6f}s] [{entity.host.id}]"
                f" - Event: {event_type}, Packet: {packet_info}"
            )

    def get_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(self.log)
