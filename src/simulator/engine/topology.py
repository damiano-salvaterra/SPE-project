from typing import Tuple, List, Dict

from NodeContext import NodeContext
from RandomManager import RandomManager
from entities.Node import Node
from models.channelModel import ChannelModel, CartesianCoordinate


'''This class implements the network topology and provides methods
to set up the links. This class is mainly a helper for node spawing and
to maintain a structure with all the possibile links with related rngs.
'''
class Topology:

    class Link:
        def __init__(self, node1_id: str, node2_id: str) -> None:
            node_A, node_B = sorted([node1_id, node2_id])  # get ordered node IDs to avoid duplicates
            self.node1_id = node_A
            self.node2_id = node_B
            self.link_id = f"{node_A}<->{node_B}" 
            self.rng = None  # random number generator for this link, to be set later

        def __eq__(self, other: object) -> bool:
            if not isinstance(other, Topology.Link):
                return NotImplemented
            return {self.node1_id, self.node2_id} == {other.node1_id, other.node2_id}
        
    def __init__(self, channel_model: ChannelModel, random_manager: RandomManager) -> None:
        self.model = channel_model # Channel model to use for link budget calculations
        self.random_manager = random_manager
        self._links = Dict[Tuple[str, str],Topology.Link] # dict of Link objects. Key: (node_id1, node_id2), Value: Link
        self.node_contexts: Dict[str, NodeContext] = {} # Key: node ID, Value: NodeContext
    

    def set_link(self, node1_id: str, node2_id: str) -> Link:
        '''
        Creates or retrieves a unique link between two nodes, independent of the order of the nodes.
        '''
        link_key = tuple(sorted([node1_id, node2_id]))
        if link_key not in self._links:
            new_link = Topology.Link(node1_id, node2_id)
            new_link.rng = self.random_manager.get_stream(new_link.link_id)  # get the RNG for this link
            self._links[link_key] = new_link
        return self._links[link_key]

    def get_link(self, node1_id: str, node2_id: str) -> Link:
        '''
        Returns the link independently of the order of the nodes.
        '''
        link_key = tuple(sorted([node1_id, node2_id]))
        if link_key not in self._links:
            self._links[link_key] = self.set_link(node1_id, node2_id)  # Use set_link to ensure uniqueness
        return self._links[link_key]


    def spawn_node(self, node_id: str, context: NodeContext) -> Node:
        '''
        Spawns a new node in the topology with the given context.
        The context contains the channel model, node position, scheduler, and random manager.
        '''
        if node_id in self.node_contexts:
            raise ValueError(f"Node with ID {node_id} already exists in the topology")
        # Check if a node already exists at the given position
        for existing_node_id, existing_context in self.node_contexts.items():
            if context.node_position == existing_context.node_position:
                raise ValueError(f"A node already exists at position {context.position} with node ID {existing_node_id}")
        
        node = Node(node_id, context)
        self.node_contexts[node_id] = context
        # add a link from this node to every other node in the topology (for SINR computation, mainly)
        for other_node_id in self.node_contexts.keys():
            if other_node_id != node_id:
                self.set_link(node_id, other_node_id)  # Use set_link to ensure unique link creation

        return node
    


    def remove_node_from_topology(self, node_id: str) -> bool:
        '''
        Removes a node from the topology by its ID.
        If the node does not exist, it returns False.
        Otherwise, it removes the node and all associated links and returns True.
        '''
        if node_id not in self.node_contexts.keys():
            return False
        
        # Remove the NodeContext
        self.node_contexts.pop(node_id, None) 

        # Remove all links associated with the node
        new_links = {k: v for k, v in self._links.items() if node_id not in k}
        self._links = new_links
        
        return True


    def add_link(self, node1_id: str, node2_id: str) -> bool:
        '''
        Adds a link between two nodes in the topology.
        If the link already exists, it returns False.
        Otherwise, it creates a new Link object, creates an RNG for it, and adds it to the links dictionary.
        '''
        if node1_id == node2_id:
            raise ValueError("Cannot create a link between the same node")
        
        link_key = tuple(sorted([node1_id, node2_id]))
        if link_key in self._links:
            return False
        
        self.set_link(node1_id, node2_id)  # Use set_link to ensure unique link creation
        return True


    def compute_link_budget(self, node1_id: str, node2_id: str, Pt_dBm) -> float:
        context1 = self.node_contexts[node1_id]
        context2 = self.node_contexts[node2_id]
        link = self.get_link(node1_id, node2_id)

        lb = self.model.link_budget(A = context1.position, B = context2.position, Pt_dBm = Pt_dBm, link_rng = link.rng)

        return lb










