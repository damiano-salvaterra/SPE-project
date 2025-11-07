# src/simulator/entities/protocols/net/common/tarp_monitor.py
import pandas as pd
from typing import TYPE_CHECKING

from simulator.engine.common.Monitor import Monitor

# We don't need to import specific signals, just the base class
from simulator.entities.common.entity_signal import EntitySignal

# Avoid circular import issues at type-checking time
if TYPE_CHECKING:
    from simulator.entities.common import Entity


class TARPMonitor(Monitor):
    """
    Monitor that tracks TARP protocol events.
    It logs the structured data from TARPSignals.
    """

    def __init__(self, monitor_name: str = "tarp", verbose=True):
        super().__init__(monitor_name=monitor_name, verbose=verbose)

    def update(self, entity: "Entity", signal: "EntitySignal"):
        """
        Called by the TARP entity when a signal is emitted.
        Filters for TARP-related signals and logs their data.
        """

        # A simpler check: just try to get the log data.
        if not hasattr(signal, "get_log_data"):
            return

        try:
            # Get the structured data from the signal
            log_data = signal.get_log_data()

            # Add node_id, which is context from the entity
            log_data["node_id"] = entity.host.id

            self.log.append(log_data)

            if self.verbose:
                print(
                    f"[TARP_MONITOR] [{signal.timestamp:.6f}s] [{entity.host.id}] {signal.descriptor}"
                )

        except AttributeError:
            # e.g., signal was emitted by an entity without a .host.id
            return
        except TypeError:
            # Signal was not one we expected (e.g., an AppSignal)
            return
