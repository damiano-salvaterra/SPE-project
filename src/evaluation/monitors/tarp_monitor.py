"""
Monitor for TARP protocol events
"""

from typing import List
import pandas as pd

from simulator.engine.common.monitor import Monitor
from simulator.entities.common import Entity, EntitySignal
from evaluation.signals.tarp_signals import (
    TARPForwardingSignal,
    TARPReceiveSignal,
)


class TARPForwardingMonitor(Monitor):
    """
    Monitor that tracks packet forwarding in the TARP protocol.
    Shows when packets are received and to where they are forwarded.
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
        Processes both TARPForwardingSignal and TARPReceiveSignal.
        """
        # DEBUG: Log every time update is called
        self._update_count += 1
        print(f"[DEBUG][{signal.timestamp:.6f}s][MONITOR TARPForwardingMonitor on {entity.host.id}] update() called. Count: {self._update_count}. Signal type: {type(signal).__name__}")

        if isinstance(signal, TARPForwardingSignal):
            # DEBUG: Log handling forwarding signal
            print(f"[DEBUG][{signal.timestamp:.6f}s][MONITOR TARPForwardingMonitor on {entity.host.id}] Processing TARPForwardingSignal.")
            self._handle_forwarding(entity, signal)
        elif isinstance(signal, TARPReceiveSignal):
             # DEBUG: Log handling receive signal
            print(f"[DEBUG][{signal.timestamp:.6f}s][MONITOR TARPForwardingMonitor on {entity.host.id}] Processing TARPReceiveSignal.")
            self._handle_receive(entity, signal)
        else:
             # DEBUG: Log ignored signal types
            print(f"[DEBUG][{signal.timestamp:.6f}s][MONITOR TARPForwardingMonitor on {entity.host.id}] Ignoring signal type {type(signal).__name__}.")


    def _handle_forwarding(self, entity: Entity, signal: TARPForwardingSignal):
        """Handle forwarding event"""
        log_entry = {
            "time": signal.timestamp,
            "node_id": entity.host.id,
            "event": "FORWARD",
            "received_from": signal.received_from.hex(),
            "original_source": signal.original_source.hex(),
            "destination": signal.destination.hex(),
            "forwarding_to": signal.forwarding_to.hex(),
            "packet_type": signal.packet_type,
        }
        self.log.append(log_entry)
         # DEBUG: Log added entry
        print(f"[DEBUG][{signal.timestamp:.6f}s][MONITOR TARPForwardingMonitor on {entity.host.id}] Forwarding Log entry added: {log_entry}")


        if self.verbose:
            print(
                f"[TARP_MONITOR] [{signal.timestamp:.6f}s] Node {entity.host.id}: "
                f"Packet received from {signal.received_from.hex()}, "
                f"originated from {signal.original_source.hex()}, "
                f"with destination {signal.destination.hex()}, "
                f"forwarding to {signal.forwarding_to.hex()}"
            )

    def _handle_receive(self, entity: Entity, signal: TARPReceiveSignal):
        """Handle receive event (packet destined for this node)"""
        log_entry = {
            "time": signal.timestamp,
            "node_id": entity.host.id,
            "event": "RECEIVE",
            "received_from": signal.received_from.hex(),
            "original_source": signal.original_source.hex(),
            "destination": entity.host.linkaddr.hex(), # Corrected destination
            "forwarding_to": "N/A",
            "packet_type": signal.packet_type,
        }
        self.log.append(log_entry)
         # DEBUG: Log added entry
        print(f"[DEBUG][{signal.timestamp:.6f}s][MONITOR TARPForwardingMonitor on {entity.host.id}] Receive Log entry added: {log_entry}")

        if self.verbose:
            print(
                f"[TARP_MONITOR] [{signal.timestamp:.6f}s] Node {entity.host.id}: "
                f"Packet received from {signal.received_from.hex()}, "
                f"originated from {signal.original_source.hex()}, "
                f"destined to this node (delivered to application)"
            )

    def get_dataframe(self) -> pd.DataFrame:
        # DEBUG: Log dataframe generation
        print(f"[DEBUG][MONITOR TARPForwardingMonitor] get_dataframe() called. Log size: {len(self.log)}.")
        return pd.DataFrame(self.log)