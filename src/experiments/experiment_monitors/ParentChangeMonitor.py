import pandas as pd
from typing import TYPE_CHECKING

from simulator.engine.common.Monitor import Monitor
from simulator.entities.protocols.net.common.tarp_signals import TARPParentChangeSignal

# Avoid circular import issues at type-checking time
if TYPE_CHECKING:
    from simulator.entities.common import Entity, EntitySignal


class ParentChangeMonitor(Monitor):
    """
    Monitor that track the end-to-end latency of a application packets.
    Has to be registered to application entities
    """

    def __init__(self, monitor_name: str = "ParChg", verbose=True):
        super().__init__(monitor_name=monitor_name, verbose=verbose)

        
    def update(self, entity: "Entity", signal: "EntitySignal"):
        """
        Called by the app when a signal is emitted.
        """
        # We only care about signals that have the get_log_data method
        if not hasattr(signal, "get_log_data"):
            return

        if not isinstance(signal, TARPParentChangeSignal):
            return  # consider only this kind of signals

        self.log.append(
            {
                "timestamp" : signal.timestamp,
                "node" : entity.host._linkaddr.hex(),
                "old_parent" : signal.old_parent.hex(),
                "new_parent" : signal.new_parent.hex(),
                "reactive" : 1 if "reactive" in signal.descriptor.lower() else 0
            }
        )

        if self.verbose:
            print(
                f"[PARENT_CHANGE_MONITOR] [{signal.timestamp:.6f}s] [{entity.host.id}] has changed parent from {signal.old_parent.hex()} to {signal.new_parent.hex()}. Reactive: {True if "reactive" in signal.descriptor.lower() else False} "
            )

    
       