import math
import numpy as np
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Tuple
from simulator.environment.geometry import CartesianCoordinate


# --- Strategy Interface ---


class TopologyStrategy(ABC):
    """
    Abstract base class (Strategy) for a topology generator: each strategy must implement the generate_positions method
    """

    @abstractmethod
    def generate_positions(self, **kwargs) -> List[CartesianCoordinate]:
        """
        Generates a list of CartesianCoordinates for nodes.
        Accepts specific parameters for each topology
        """
        pass


# --- Concrete Strategies ---


class LinearTopology(TopologyStrategy):
    """Generates nodes in a straight line."""

    def generate_positions(self, **kwargs) -> List[CartesianCoordinate]:
        num_nodes: int = kwargs.get("num_nodes", 10)
        node_distance: float = kwargs.get("node_distance", 10.0)
        start_x: float = kwargs.get("start_x", 0.0)
        start_y: float = kwargs.get("start_y", 0.0)

        positions = []
        for i in range(num_nodes):
            x = start_x + i * node_distance
            y = start_y
            positions.append(CartesianCoordinate(x, y))
        return positions


class RingTopology(TopologyStrategy):
    """Generates nodes distributed on a circle."""

    def generate_positions(self, **kwargs) -> List[CartesianCoordinate]:
        num_nodes: int = kwargs.get("num_nodes", 10)
        radius: float = kwargs.get("radius", 100.0)
        center_x: float = kwargs.get("center_x", 0.0)
        center_y: float = kwargs.get("center_y", 0.0)

        positions = []
        for i in range(num_nodes):
            angle = 2 * math.pi * i / num_nodes
            x = center_x + radius * math.cos(angle)
            y = center_y + radius * math.sin(angle)
            positions.append(CartesianCoordinate(x, y))
        return positions


class GridTopology(TopologyStrategy):
    """Generates nodes in a 2D grid."""

    def generate_positions(self, **kwargs) -> List[CartesianCoordinate]:
        grid_shape: Tuple[int, int] = kwargs.get("grid_shape", (5, 5))
        node_distance: float = kwargs.get("node_distance", 20.0)
        start_x: float = kwargs.get("start_x", 0.0)
        start_y: float = kwargs.get("start_y", 0.0)

        positions = []
        rows, cols = grid_shape
        for r in range(rows):
            for c in range(cols):
                x = start_x + c * node_distance
                y = start_y + r * node_distance
                positions.append(CartesianCoordinate(x, y))
        return positions


class RandomTopology(TopologyStrategy):
    """Generates nodes randomly within a bounding box.
    requires a RNG"""

    def generate_positions(self, **kwargs) -> List[CartesianCoordinate]:
        num_nodes: int = kwargs.get("num_nodes", 10)
        area_box: Tuple[float, float, float, float] = kwargs.get(
            "area_box", (-100, 100, -100, 100)
        )
        rng: np.random.Generator = kwargs.get("rng")

        if rng is None:
            raise ValueError("RandomTopology requires an Numpy 'rng' in kwargs")

        min_x, max_x, min_y, max_y = area_box
        positions = []
        for _ in range(num_nodes):
            x = rng.uniform(min_x, max_x)
            y = rng.uniform(min_y, max_y)
            positions.append(CartesianCoordinate(x, y))
        return positions


class StarTopology(TopologyStrategy):
    """Generates one central hub and N-1 spoke nodes around it."""

    def generate_positions(self, **kwargs) -> List[CartesianCoordinate]:
        num_nodes: int = kwargs.get("num_nodes", 11)
        radius: float = kwargs.get("radius", 100.0)
        center_x: float = kwargs.get("center_x", 0.0)
        center_y: float = kwargs.get("center_y", 0.0)

        positions = []
        # Add hub
        positions.append(CartesianCoordinate(center_x, center_y))

        num_spokes = num_nodes - 1
        if num_spokes > 0:
            for i in range(num_spokes):
                angle = 2 * math.pi * i / num_spokes  # spokes are on a circle
                x = center_x + radius * math.cos(angle)
                y = center_y + radius * math.sin(angle)
                positions.append(CartesianCoordinate(x, y))
        return positions


class ClusterTreeTopology(TopologyStrategy):
    """
    Generates a recursive cluster-tree of a specified depth.
    - The root (level 0) is at the center.
    - Level 1 nodes ("cluster heads") are placed deterministically on a circle.
    - Each subsequent level (2...depth) is placed randomly in a disk
      around its parent node.
    
    New parameter:
    - depth (int): The total number of levels *below* the root.
      - depth=1: Root -> N cluster heads (star topology).
      - depth=2: Root -> N cluster heads -> M nodes per cluster (original behavior).
      - depth=3: Root -> N_L1 -> M_L2 -> M_L3 ... and so on.
    
    Requires an 'rng' (NumPy Random Generator).
    """

    def generate_positions(self, **kwargs) -> List[CartesianCoordinate]:
        # --- Get Parameters ---

        # New parameter for recursive depth
        # depth=1 means Root + L1 children
        # depth=2 means Root + L1 + L2 children (matches old behavior)
        depth: int = kwargs.get("depth", 2) 
        
        # Parameters for Level 1 (Cluster Heads)
        num_clusters: int = kwargs.get("num_clusters", 3)
        cluster_radius: float = kwargs.get(
            "cluster_radius", 100.0
        )  # Distance of L1 nodes from root
        
        # Parameters for Level 2 and beyond
        # This is the branching factor for all nodes at level 1 and deeper.
        # The original class used (nodes_per_cluster - 1) children.
        nodes_per_cluster: int = kwargs.get("nodes_per_cluster", 5)
        # We subtract 1 to match the original logic (1 head + N-1 children)
        # This is now the branching factor for L2, L3, ...
        children_per_node: int = max(0, nodes_per_cluster - 1) 
        
        node_radius: float = kwargs.get(
            "node_radius", 20.0
        )  # Radius for L2+ child placement
        
        center_x: float = kwargs.get("center_x", 0.0)
        center_y: float = kwargs.get("center_y", 0.0)
        rng: np.random.Generator = kwargs.get("rng")

        # --- Validation ---
        if rng is None:
            raise ValueError(
                "ClusterTreeTopology requires an 'rng' (NumPy Random Generator) in kwargs"
            )
        if depth < 1:
            raise ValueError("Depth must be at least 1.")

        
        positions = []
        
        # --- Add Root (Level 0) ---
        root_pos = CartesianCoordinate(center_x, center_y)
        positions.append(root_pos)

        # --- Recursive Helper Function ---
        def _generate_children_recursive(parent_pos: CartesianCoordinate, current_level: int):
            """
            Generates and appends children for a parent node.
            'current_level' is the level of the *children* being created (starts at 1).
            """
            # Stop recursion if we have reached the maximum depth
            if current_level > depth:
                return

            # --- Determine parameters for this level ---
            if current_level == 1:
                # This is Level 1 (Cluster Heads)
                num_children = num_clusters
                radius = cluster_radius
                placement_is_circular = True # Place on a circle
            else:
                # This is Level 2 or deeper
                num_children = children_per_node
                radius = node_radius
                placement_is_circular = False # Place randomly in a disk

            if num_children == 0:
                return # This node is a leaf node

            # --- Generate Children ---
            for i in range(num_children):
                if placement_is_circular:
                    # Level 1: Place on a deterministic circle
                    angle = 2 * math.pi * i / num_children
                    child_x = parent_pos.x + radius * math.cos(angle)
                    child_y = parent_pos.y + radius * math.sin(angle)
                else:
                    # Level 2+: Place randomly within a disk
                    node_angle = rng.uniform(0, 2 * math.pi)
                    # Use sqrt(uniform) for uniform spatial distribution in a disk
                    node_dist = radius * math.sqrt(rng.uniform(0.0, 1.0))
                    child_x = parent_pos.x + node_dist * math.cos(node_angle)
                    child_y = parent_pos.y + node_dist * math.sin(node_angle)
                
                child_pos = CartesianCoordinate(child_x, child_y)
                positions.append(child_pos)
                
                # --- Recurse for the next level ---
                # This child becomes a parent for the next level
                _generate_children_recursive(child_pos, current_level + 1)

        # --- Start Recursion from the Root ---
        _generate_children_recursive(root_pos, 1)

        return positions


# --- Factory ---


class TopologyFactory:
    """
    Factory class that builds a topology
    """

    def __init__(self):
        self._strategies: Dict[str, TopologyStrategy] = (
            {}
        )  # can register new strategies at runtime
        self._register_default_strategies()

    def _register_default_strategies(self):  # register built-in strategies
        self.register_strategy("linear", LinearTopology())
        self.register_strategy("ring", RingTopology())
        self.register_strategy("grid", GridTopology())
        self.register_strategy("random", RandomTopology())
        self.register_strategy("star", StarTopology())
        self.register_strategy("cluster-tree", ClusterTreeTopology())

    def register_strategy(self, name: str, strategy: TopologyStrategy):
        self._strategies[name.lower()] = strategy

    def create_topology(self, name: str, **kwargs) -> List[CartesianCoordinate]:
        """
        Creates and generates a topology by its registered name, given the stopology-specific parameters.
        returns the list of CartesianCoordinate of the nodes

        """
        strategy = self._strategies.get(name.lower())
        if not strategy:
            raise ValueError(
                f"Topology strategy '{name}' is not registered. "
                f"Available: {list(self._strategies.keys())}"
            )

        print(f"Generating '{name}' topology with params: {kwargs}")
        return strategy.generate_positions(**kwargs)
