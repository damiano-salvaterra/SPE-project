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
        self.last_log_time = {}

    def update(self, entity: "Entity", signal: "EntitySignal"):
        """
        Periodically log the neighbor table whenever certain events occur.
        """
        if not hasattr(signal, "timestamp"):
            return

        current_time = signal.timestamp
        node_id = entity.host.id

        # Check if enough time has passed since last log
        if (
            node_id not in self.last_log_time
            or (current_time - self.last_log_time[node_id]) >= self.log_interval
        ):

            self.last_log_time[node_id] = current_time

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
                    }
                )

            if self.verbose:
                print(
                    f"[NEIGHBOR_TABLE_MONITOR] [{current_time:.6f}s] [{node_id}] Logged {len(entity.nbr_tbl)} neighbors"
                )
