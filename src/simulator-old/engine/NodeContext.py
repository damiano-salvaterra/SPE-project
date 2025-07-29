from engine.Scheduler import Scheduler
from engine.RandomManager import RandomManager
from engine.Event import Event
from simulator.engine.topology import Topology, CartesianCoordinate

'''
This class implements a Facade for the Node class to the simulation context.
It provides a unified interface for to the scheduler, random manager and channel model.
'''
class NodeContext():
    def __init__(self, topology : Topology, position: CartesianCoordinate, scheduler: Scheduler, random_manager: RandomManager) -> None: 
        self.topology = topology
        self.position = position
        self.scheduler = scheduler
        self.random_manager = random_manager



    def link_budget(self, this_node_id: str, other_node_id: str , Pt_dBm: float = 0) -> float:
        '''
        Proxy to the channel model to compute the link budget to a node.
        '''
        pass
