
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
from typing import List, Any, Optional
import numpy as np

from entities.layers.AppLayer import AppSendEvent

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
        self._bootstrap_engine()



    def _bootstrap_engine(self):
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



    # this funciotn is called at the beginning fromt the orchestrator only once (at the beginning), then all the network traffic it should be scheduled automatically
    # by the nodes and the other components
    def schedule_network_bootstrap(self):
        '''
        This method schedules the first beacon floot from the sink node.
        It should be called after the topology is created and the sink node is set.'''

        #TODO: schedule the first beacon flood from the sink
        sink = self.topology.sink_node
        if sink is None:
            raise ValueError("Sink node must be set before scheduling initial events.")
        sink.net_layer.schedule_beacon()
    

    # this function is called from the orchestrator (the main function) to schedule app events.
    def schedule_app_packet_event(self, source_id: str, dest_id: str, event_time: float, data: Optional[Any]):
        """
        Schedule an application packet event.
        This method creates an AppSendEvent and schedules it in the scheduler.
        """
        if self.topology is None:
            raise ValueError("Topology must be created before scheduling events.")
        if source_id not in self.topology.get_node_ids() or dest_id not in self.topology.get_node_ids():
            raise ValueError(f"Node with ID {source_id} not found in the topology.")
        
        source_node = self.topology.get_node_by_id(source_id)
        destination_node = self.topology.get_node_by_id(dest_id)
        
        event = AppSendEvent(
            node_id=source_id,
            destination=dest_id,
            data=data,
            string_id=f"AppSendEvent_{source_id}_{dest_id}",
            time=event_time,
            log_event=True,
            blame=source_node,  # Blame source is the source node
            observer=destination_node  # Observer is the destination node
        )
        
        self.scheduler.schedule(event)

    
    def step(self):
        '''
        Execute a step in the simulation.
        '''