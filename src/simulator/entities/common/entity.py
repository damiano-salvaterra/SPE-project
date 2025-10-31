from typing import List, TYPE_CHECKING

from simulator.entities.common.signals import EntitySignal

if TYPE_CHECKING:
    from simulator.engine.common.monitor import Monitor


class Entity:
    """
    This base class is the base class of any entiy. It makes
    the entity observable (in the design pattern observer sense),
    and allows to attach/detach Monitors that gathers statistics
    """

    def __init__(self):
        self._monitors: List["Monitor"] = []

    def attach_monitor(self, monitor: "Monitor"):
        """
        attach monitor to this entity
        """

        if monitor not in self._monitors:  # if already attached, ignore
            self._monitors.append(monitor)

    def detach_monitor(self, monitor: "Monitor"):
        """
        detach monitor from this entity
        """
        if monitor in self._monitors:  # if monitor is not attached, do nothing
            self._monitors.remove(monitor)

    def _notify_monitors(self, signal: EntitySignal):
        if not self._monitors:  # if no monitor are attached, return
            return

        for monitor in self._monitors:
            monitor.update(entity=self, signal=signal)
