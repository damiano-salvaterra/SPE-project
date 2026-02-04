import pandas as pd
from typing import TYPE_CHECKING
from simulator.engine.common.Monitor import Monitor

if TYPE_CHECKING:
    from simulator.entities.common import Entity, EntitySignal


class NeighborTableMonitor(Monitor):
    """
    Monitor that periodically logs the complete neighbor table of each node.
    """

    def __init__(
        self, monitor_name: str = "NeighborTable", verbose=True, log_interval=60.0
    ):
        super().__init__(monitor_name=monitor_name, verbose=verbose)
        self.log_interval = log_interval
        self.log_seq_num = {}

    def update(self, entity: "Entity", signal: "EntitySignal"):
        """
        Log the neighbor table when receiving TARPNeighborTableLogSignal.
        """
        from simulator.entities.protocols.net.common.tarp_signals import (
            TARPNeighborTableLogSignal,
        )

        # Only respond to the specific logging signal
        if not isinstance(signal, TARPNeighborTableLogSignal):
            return

        current_time = signal.timestamp
        node_id = entity.host.id

        self.log_seq_num[node_id] = self.log_seq_num.get(node_id, 0) + 1

        # Log the complete neighbor table
        for neighbor_addr, route in entity.nbr_tbl.items():
            self.log.append(
                {
                    "timestamp": current_time,
                    "node_id": node_id,
                    "neighbor": neighbor_addr.hex(),
                    "type": route.type.name,
                    "nexthop": route.nexthop.hex(),
                    "hops": route.hops,
                    "etx": route.etx,
                    "adv_metric": route.adv_metric,
                    "age": route.age,
                    "log_num": self.log_seq_num[node_id],
                }
            )

        if self.verbose:
            print(
                f"[NEIGHBOR_TABLE_MONITOR] [{current_time:.6f}s] [{node_id}] Logged {len(entity.nbr_tbl)} neighbors"
            )
