"""
Monitor for application-level events
"""

from typing import List
import pandas as pd

from simulator.engine.common.monitor import Monitor
from simulator.entities.common import Entity, EntitySignal
from evaluation.signals.app_signals import AppPingReceivedSignal


class AppPingMonitor(Monitor):
    """
    Monitor that tracks PING packets received by the application.
    Shows only the original source of the PING, not intermediate forwarders.
    """

    def __init__(self, verbose=True):
        super().__init__()
        self.log: List[dict] = []
        self.verbose = verbose

    def update(self, entity: Entity, signal: EntitySignal):
        """
        Called by the entity when a signal is emitted.
        Only processes AppPingReceivedSignal.
        """
        if not isinstance(signal, AppPingReceivedSignal):
            return

        # Extract payload
        payload = signal.packet.APDU
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8", errors="ignore")

        log_entry = {
            "time": signal.timestamp,
            "receiver_node": entity.host.id,
            "source_node": signal.source_addr.hex(),
            "payload": payload,
        }
        self.log.append(log_entry)

        if self.verbose:
            print(
                f"[APP_MONITOR] [{signal.timestamp:.6f}s] Node {entity.host.id}: "
                + ("PING" if payload.startswith("PING") else "PONG")
                + f" received from node {signal.source_addr.hex()} "
                f"(payload: {payload})"
            )

    def get_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(self.log)
