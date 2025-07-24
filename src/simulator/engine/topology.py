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
        self.nodes: Dict[Node, CartesianCoordinate] = {} # Key: Node, Value: CartesianCoordinate of the node
        self.transmitting_nodes: List[str] = []  # List of nodes that are currently transmitting
    

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


    def spawn_node(self, node_id: str, linkaddr: bytes, context: NodeContext) -> Node:
        '''
        Spawns a new node in the topology with the given context. linkaddr is a 2 bytes address.
        The context contains the channel model, node position, scheduler, and random manager.
        '''
        if len(linkaddr) != 2:
            raise ValueError("linkaddr must be a 2 bytes address")
        

        if node_id in self.nodes.keys():
            raise ValueError(f"Node with ID {node_id} already exists in the topology")
        
        # Check if a node already exists at the given position
        if context.position in self.nodes.values():
            raise ValueError(f"A node already exists at position {context.position} with node ID {node_id}")

        node = Node(node_id, linkaddr, context)
        self.nodes[node] = context.position
        # add a link from this node to every other node in the topology (for SINR computation, mainly)
        for other_node in self.nodes.keys():
            if other_node.node_id != node_id:
                self.set_link(node_id, other_node.node_id) 
        return node
    


    def remove_node_from_topology(self, node: Node) -> bool:
        '''
        Removes a node from the topology by its ID.
        If the node does not exist, it returns False.
        Otherwise, it removes the node and all associated links and returns True.
        '''
        if node not in self.nodes.keys():
            return False
        
        # Remove the Node
        self.node.pop(node, None) 

        # Remove all links associated with the node
        new_links = {k: v for k, v in self._links.items() if node.node_id not in k}
        self._links = new_links
        
        return True

    def get_node_ids(self) -> List[str]:
        '''
        Returns a list of node IDs in the topology.
        '''
        return [node.node_id for node in self.nodes.keys()]
    
    
    def _add_link(self, node1_id: str, node2_id: str) -> bool:
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

        link = self.get_link(node1_id, node2_id)

        #find positions
        coords = []
        for node in self.nodes.keys():
            if node.node_id == node1_id or node.node_id == node2_id:
                coords.append(self.nodes[node])

        lb = self.model.link_budget(A = coords[0], B = coords[1], Pt_dBm = Pt_dBm, rng = link.rng)
        return lb







