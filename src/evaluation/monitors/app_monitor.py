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
        # DEBUG: Add counter for update calls
        self._update_count = 0

    def update(self, entity: Entity, signal: EntitySignal):
        """
        Called by the entity when a signal is emitted.
        Only processes AppPingReceivedSignal.
        """
        # DEBUG: Log every time update is called
        self._update_count += 1
        print(f"[DEBUG][{signal.timestamp:.6f}s][MONITOR AppPingMonitor on {entity.host.id}] update() called. Count: {self._update_count}. Signal type: {type(signal).__name__}")

        if not isinstance(signal, AppPingReceivedSignal):
            # DEBUG: Log ignored signal types
            print(f"[DEBUG][{signal.timestamp:.6f}s][MONITOR AppPingMonitor on {entity.host.id}] Ignoring signal type {type(signal).__name__}.")
            return

        # DEBUG: Log processing of correct signal type
        print(f"[DEBUG][{signal.timestamp:.6f}s][MONITOR AppPingMonitor on {entity.host.id}] Processing AppPingReceivedSignal.")

        # Extract payload
        payload = signal.packet.APDU
        if isinstance(payload, bytes):
             # DEBUG: Log payload decoding
            print(f"[DEBUG][{signal.timestamp:.6f}s][MONITOR AppPingMonitor on {entity.host.id}] Decoding payload from bytes.")
            payload = payload.decode("utf-8", errors="ignore")

        log_entry = {
            "time": signal.timestamp,
            "receiver_node": entity.host.id,
            "source_node": signal.source_addr.hex(),
            "payload": payload,
        }
        self.log.append(log_entry)
         # DEBUG: Log added entry
        print(f"[DEBUG][{signal.timestamp:.6f}s][MONITOR AppPingMonitor on {entity.host.id}] Log entry added: {log_entry}")


        if self.verbose:
            print(
                f"[APP_MONITOR] [{signal.timestamp:.6f}s] Node {entity.host.id}: "
                + ("PING" if payload.startswith("PING") else "PONG")
                + f" received from node {signal.source_addr.hex()} "
                f"(payload: {payload})"
            )

    def get_dataframe(self) -> pd.DataFrame:
        # DEBUG: Log dataframe generation
        print(f"[DEBUG][MONITOR AppPingMonitor] get_dataframe() called. Log size: {len(self.log)}.")
        return pd.DataFrame(self.log)