import pandas as pd
from typing import TYPE_CHECKING

from simulator.engine.common.Monitor import Monitor
from simulator.entities.applications.common.app_signals import (
    AppSendSignal,
    AppReceiveSignal
)
# Avoid circular import issues at type-checking time
if TYPE_CHECKING:
    from simulator.entities.common import Entity, EntitySignal


class PDRMonitor(Monitor):
    """
    Monitor that track the Packet delivery rate of a application packets.
    Has to be registered to application entities.
        """

    def __init__(self, monitor_name: str = "PDR", verbose=True):
        super().__init__(monitor_name=monitor_name, verbose=verbose)
        
        self.sent_packets = {} #Key: (source_addr_str, seq_num, dest_addr_str), value: dict with data

    def update(self, entity: "Entity", signal: "EntitySignal"):
        """
        Called by the app when a signal is emitted
        """
        # We only care about signals that have the get_log_data method
        if not hasattr(signal, "get_log_data"):
            return

        if not isinstance(signal,(AppSendSignal,AppReceiveSignal)):
            return #consider only send and recieve messages
            
        if isinstance(signal, AppSendSignal):
            source_addr_str = str(entity.host._linkaddr)
            dest_addr_str = str(signal.dest_addr)
            
            packet_key = (source_addr_str, signal.seq_num, dest_addr_str)
            
            self.sent_packets[packet_key] = {
                "source_addr": source_addr_str,
                "seq_num": signal.seq_num,
                "dest_addr": dest_addr_str,
                "delivered": 0, # default to packet not delivered
            }
                            
        elif isinstance(signal, AppReceiveSignal):
            source_addr_str = str(signal.source_addr)
            current_host_addr = str(entity.host._linkaddr)
            
            # recreate key for find the matching
            packet_key = (source_addr_str, signal.seq_num, current_host_addr)
            
            # Check if this packet is being tracked, ignore otherwise
            if packet_key in self.sent_packets:
                self.sent_packets[packet_key]["delivered"] = 1 #mark as delivered
                
                if self.verbose:
                    print(
                        f"[PDR_MONITOR] [{signal.timestamp:.6f}s] [{entity.host.id}] Packet #{signal.seq_num} from {source_addr_str} DELIVERED"
                    )

    def save_to_csv(self, base_path: str):
        """
        override the base class method: this class uses a dict for O(1) updates, but the base method requires a list
        """
        # convert records from the dictionary into list
        self.log = list(self.sent_packets.values())
        super().save_to_csv(base_path)