
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
import numpy as np



class Core:
    """
    Core class to manage the simulation context, topology, nodes, and events.
    """
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
        """
        if self.channel_model is None:
            raise ValueError("Channel model must be created before creating the topology.")
        
        self.topology = Topology(channel_model=self.channel_model, random_manager=self.random_manager)
        if node_coords is not None:
            linkaddr_counter = 1  # Start with 1 for incrementing link addresses
            for coord in node_coords:
                linkaddr = linkaddr_counter.to_bytes(2, 'big')  # Convert counter to 2-byte address
                self.topology.spawn_node(node_id=f"node_{coord.x}_{coord.y}", linkaddr=linkaddr, context=NodeContext(
                    topology=self.topology,
                    position=coord,
                    scheduler=self.scheduler,
                    random_manager=self.random_manager
                ))
                linkaddr_counter += 1  # Increment the counter for the next node