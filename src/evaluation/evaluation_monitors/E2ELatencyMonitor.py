import pandas as pd
from typing import TYPE_CHECKING

from simulator.engine.common.Monitor import Monitor
from simulator.entities.applications.common.app_signals import (
    AppSendSignal,
    AppReceiveSignal,
)

# Avoid circular import issues at type-checking time
if TYPE_CHECKING:
    from simulator.entities.common import Entity, EntitySignal


class E2ELatencyMonitor(Monitor):
    """
    Monitor that track the end-to-end latency of a application packets.
    Has to be registered to application entities
    """

    def __init__(self, monitor_name: str = "e2eLat", verbose=True):
        super().__init__(monitor_name=monitor_name, verbose=verbose)

        self.sent_packets = (
            {}
        )  # Key: (source_addr_str, seq_num), value: timestamp of the send event

    def update(self, entity: "Entity", signal: "EntitySignal"):
        """
        Called by the app when a signal is emitted.
        """
        # We only care about signals that have the get_log_data method
        if not hasattr(signal, "get_log_data"):
            return

        if not isinstance(signal, (AppSendSignal, AppReceiveSignal)):
            return  # consider only send and recieve messages

        if isinstance(signal, AppSendSignal):
            source_addr_str = str(entity.host._linkaddr)
            packet_key = (source_addr_str, signal.seq_num)

            # Store the send time
            self.sent_packets[packet_key] = signal.timestamp

        elif isinstance(signal, AppReceiveSignal):
            source_addr_str = str(signal.source_addr)
            packet_key = (source_addr_str, signal.seq_num)

            # pop the packet from the dictionary (no longer needed here)
            send_time = self.sent_packets.pop(packet_key, None)

            if send_time is not None:  # if the packet was tracked, compute latency
                latency = signal.timestamp - send_time

                # log the entry
                self.log.append(
                    {
                        "source_addr": source_addr_str,
                        "seq_num": signal.seq_num,
                        "send_time": send_time,
                        "receive_time": signal.timestamp,
                        "latency": latency,
                    }
                )

                if self.verbose:
                    print(
                        f"[E2E_LATENCY_MONITOR] [{signal.timestamp:.6f}s] [{entity.host.id}] Packet #{signal.seq_num} from {source_addr_str} Latency: {latency:.6f}s"
                    )
