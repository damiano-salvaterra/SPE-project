import pandas as pd
from typing import TYPE_CHECKING

from simulator.engine.common.Monitor import Monitor
from simulator.entities.applications.common.app_signals import (
    AppStartSignal,
    AppSendSignal,
    AppReceiveSignal,
    AppTimeoutSignal,
    AppSendFailSignal
)

# Avoid circular import issues at type-checking time
if TYPE_CHECKING:
    from simulator.entities.common import Entity, EntitySignal


class ApplicationMonitor(Monitor):
    """
    Monitor that tracks PingPong application events (send, receive, timeout, fail).
    Inherits from BaseMonitor to log structured data.
    """

    def __init__(self, verbose=True):
        super().__init__(verbose=verbose)

    def update(self, entity: "Entity", signal: "EntitySignal"):
        """
        Called by the application entity when a signal is emitted.
        Filters for specific App signals and logs them.
        """
        # App signals are emitted by the Application, which is hosted on a Node.
        # We get the node_id from the entity's host attribute.
        try:
            current_time = signal.timestamp
            node_id = entity.host.id
            log_entry = {"time": current_time, "node_id": node_id}
            print_msg = None
        except AttributeError:
            # Signal was emitted by an entity without a .host.id, ignore it.
            return

        if isinstance(signal, AppStartSignal):
            log_entry.update({
                "event": "APP_START",
                "details": "Application started"
            })
            print_msg = "Application started."

        elif isinstance(signal, AppSendSignal):
            log_entry.update({
                "event": "SEND",
                "type": signal.packet_type,
                "seq_num": signal.seq_num,
                "dest": signal.destination.hex()
            })
            print_msg = f"Sent {signal.packet_type} #{signal.seq_num} to {signal.destination.hex()}"
        
        elif isinstance(signal, AppReceiveSignal):
            log_entry.update({
                "event": "RECEIVE",
                "type": signal.packet_type,
                "seq_num": signal.seq_num,
                "source": signal.source.hex(),
                "hops": signal.hops 
            })
            print_msg = f"Received {signal.packet_type} #{signal.seq_num} from {signal.source.hex()}, Hops={signal.hops}"

        elif isinstance(signal, AppTimeoutSignal):
            log_entry.update({
                "event": "TIMEOUT",
                "seq_num": signal.seq_num
            })
            print_msg = f"PING #{signal.seq_num} timed out."

        elif isinstance(signal, AppSendFailSignal):
            log_entry.update({
                "event": "SEND_FAIL",
                "type": signal.packet_type,
                "seq_num": signal.seq_num,
                "reason": signal.reason
            })
            print_msg = f"Failed to send {signal.packet_type} #{signal.seq_num} (Reason: {signal.reason})"
        
        else:
            # Ignore other signals
            return

        self.log.append(log_entry)

        if self.verbose and print_msg:
            print(f"[APP_MONITOR] [{current_time:.6f}s] [{node_id}] {print_msg}")