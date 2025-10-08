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

    def update(self, entity: Entity, signal: EntitySignal):
        """
        Called by the entity when a signal is emitted.
        Processes both TARPForwardingSignal and TARPReceiveSignal.
        """
        if isinstance(signal, TARPForwardingSignal):
            self._handle_forwarding(entity, signal)
        elif isinstance(signal, TARPReceiveSignal):
            self._handle_receive(entity, signal)

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
            "destination": entity.host.linkaddr.hex(),
            "forwarding_to": "N/A",
            "packet_type": signal.packet_type,
        }
        self.log.append(log_entry)

        if self.verbose:
            print(
                f"[TARP_MONITOR] [{signal.timestamp:.6f}s] Node {entity.host.id}: "
                f"Packet received from {signal.received_from.hex()}, "
                f"originated from {signal.original_source.hex()}, "
                f"destined to this node (delivered to application)"
            )

    def get_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(self.log)
