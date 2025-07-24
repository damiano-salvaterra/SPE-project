
"""should be something like


scheduler = Scheduler.init()
random_manager = RandomManager(seed)
model = ChannelModel(params)
topology = Topology(model, random_manager)

context1 = NodeContext(model, CartesianCoordinate(0, 0), scheduler, random_manager)
addr1 = bytes([0x00, 0x01])  # Example 2-byte address
node1 = topology.spawn_node(id= "something", context1)

context2 = NodeContext(model, CartesianCoordinate(1, 1), scheduler, random_manager)
addr2 = bytes([0x01, 0x02])  # Example 2-byte address
node2 = topology.spawn_node(id = "somethingelse", addr2, context2)


# if you ant to remove a node should be something like
node1.shutdown()  # clean up the node
del context1  # remove the context if needed
topology.remove_node_from_topology(node1.node_id)  # remove the node from the topology


...

"""

from engine.Scheduler import Scheduler
from engine.RandomManager import RandomManager
from models.channelModel import ChannelModel, DSpace
from engine.topology import Topology, CartesianCoordinate
from NodeContext import NodeContext
from typing import List
import numpy as np



class Core:
    """
    Core class to manage the simulation context, topology, nodes, and events.
    """



    class TerminationPolicy:
        def __init__(self):
            self.conditions = []
    
        def add(self, condition):
            """Add a single termination condition."""
            self.conditions.append(condition)
            return self
    
        def any(self):
            """
            Return a predicate that terminates if any condition is True.
            The predicate takes the simulation context and checks the conditions.
            """
            return lambda topology, scheduler, event_count, time_elapsed: any(
                cond(topology, scheduler, event_count, time_elapsed) for cond in self.conditions
            )
    
        def all(self):
            """
            Return a predicate that terminates only if all conditions are True.
            The predicate takes the simulation context and checks the conditions.
            """
            return lambda topology, scheduler, event_count, time_elapsed: all(
                cond(topology, scheduler, event_count, time_elapsed) for cond in self.conditions
            )


    def __init__(self, root_seed, n_workers=1):
        self.root_seed = root_seed
        self.n_workers = n_workers
        self.scheduler = None
        self.random_manager = None
        self.channel_model = None
        self.topology = None
        self.bootstrap_engine()



    def bootstrap_engine(self):
        """
        Initialize the core components of the simulation engine.
        """
        self.scheduler = Scheduler().init()
        self.random_manager = RandomManager(self.root_seed)


    def create_channel_model(self, shadowing_rng: np.random.Generator, dspace_step: int, dspace_npt: int, freq: float, coh_d: float,
                               shadow_dev: float, pl_exponent: float, d0: float, fading_shape: float):
        """
        Create a channel model with the given parameters.
        """

        dspace = DSpace(step=dspace_step, npt=dspace_npt)
        self.channel_model = ChannelModel(
            shadowing_rng=shadowing_rng,
            dspace=dspace,
            freq=freq,
            coh_d=coh_d,
            shadow_dev=shadow_dev,
            pl_exponent=pl_exponent,
            d0=d0,
            fading_shape=fading_shape
        )


    def create_topology(self, node_coords: List[CartesianCoordinate] = None):
        """
        Create the topology with the current channel model and random manager.
        Optionally, pass a list of CartesianCoordinates to initialize nodes in the topology.
        In the topology, the first node of the list is considered the root node.
        """
        if self.channel_model is None:
            raise ValueError("Channel model must be created before creating the topology.")
        
        self.topology = Topology(channel_model=self.channel_model, random_manager=self.random_manager)
        if node_coords is not None:
            linkaddr_counter = 1  # Start with 1 for incrementing link addresses
            for coord in node_coords:
                linkaddr = linkaddr_counter.to_bytes(2, 'big')  # Convert counter to 2-byte address
                root = True if linkaddr_counter == 1 else 0
                self.topology.spawn_node(node_id=f"node_{coord.x}_{coord.y}", linkaddr=linkaddr, root = root, context=NodeContext(
                    topology=self.topology,
                    position=coord,
                    scheduler=self.scheduler,
                    random_manager=self.random_manager
                ))
                if root:
                    self.topology.sink_node = f"node_{coord.x}_{coord.y}"

                linkaddr_counter += 1  # Increment the counter for the next node



    def schedule_initial_event(self):
        #TODO: schedule the first beacon flood from the sink
        sink = self.topology.sink_node
        if sink is None:
            raise ValueError("Sink node must be set before scheduling initial events.")
        initial_event = self.topology.sink_node.net_layer.send_beacon()

    
    def step(self):
        '''
        Execute a step in the simulation.
        '''