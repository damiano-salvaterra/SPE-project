from typing import List, Any, TYPE_CHECKING
if TYPE_CHECKING:
    from simulator.engine.common.Monitor import Monitor

'''
This base class is the base class of any entiy. It makes
the entity observable (in the design pattern observer sense),
and allows to attach/detach Monitors that gathers statistics
'''

class EntitySignal:
    '''
    This class defines standardized signals sent by entities to the monitors
    Entities that generates phenomena that need to be monitored, must create an object
    that inherits from this base class and notify the monitors.
    The concrete monitor that is specific for this type of signal will immplement
    its update() function to filter out all the signal exept of the interested one.
    '''
    def __init__(self, descriptor: str, timestamp: float, **kwargs):
        self.descriptor = descriptor
        self.timestamp = timestamp
        self.kwargs = kwargs


    '''dunder methods of the mapping protocol need to
        be overridden to allow the conversion in pandas dataframe'''
    def __getitem__(self, key: str) -> Any:
        if key == "descriptor":
            return self.descriptor
        if key == "timestamp":
            return self.timestamp
        # if  not present, raises KeyError
        return self.kwargs[key]

    def __iter__(self):
        yield "descriptor"
        yield "timestamp"
        yield from self.kwargs.keys()

    def __len__(self) -> int:
        # fixed fields + length of kwargs
        return 2 + len(self.kwargs)


class Entity:
    def __init__(self):
        self._monitors: List["Monitor"] = []


    def attach_monitor(self, monitor: Any):
        '''
        attach monitor to this entity
        '''

        if monitor not in self._monitors: # if already attached, ignor
            self._monitors.append(monitor)


    def detach_monitor(self, monitor: Any):
        '''
        detach monitor from this entity
        '''
        if monitor in self._monitors: #if monitor is not attached, do nothing
            self._monitors.remove(monitor)

    def _notify_monitors(self, signal: EntitySignal):
        if not self._monitors: # if no monitor are attached, return
            return
        
        for monitor in self._monitors:
            monitor.update(entity = self, signal = signal)
