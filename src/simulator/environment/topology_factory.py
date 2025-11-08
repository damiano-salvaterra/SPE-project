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
    Generates a one-level cluster-tree: a root, N clusters, M nodes per cluster.
    requires a RNG
    """

    def generate_positions(self, **kwargs) -> List[CartesianCoordinate]:
        num_clusters: int = kwargs.get("num_clusters", 3)
        nodes_per_cluster: int = kwargs.get("nodes_per_cluster", 5)
        cluster_radius: float = kwargs.get(
            "cluster_radius", 100.0
        )  # Distance of clusters from root
        node_radius: float = kwargs.get(
            "node_radius", 20.0
        )  # Radius of nodes within a cluster
        center_x: float = kwargs.get("center_x", 0.0)
        center_y: float = kwargs.get("center_y", 0.0)
        rng: np.random.Generator = kwargs.get("rng")

        if rng is None:
            raise ValueError(
                "ClusterTreeTopology requires an 'rng' (NumPy Random Generator) in kwargs"
            )

        positions = []
        # Add root
        positions.append(CartesianCoordinate(center_x, center_y))

        # Add cluster heads
        cluster_heads = []
        for i in range(num_clusters):
            angle = 2 * math.pi * i / num_clusters  # cluster heads are on a circle
            ch_x = center_x + cluster_radius * math.cos(angle)
            ch_y = center_y + cluster_radius * math.sin(angle)
            cluster_heads.append((ch_x, ch_y))
            positions.append(CartesianCoordinate(ch_x, ch_y))

            # Add nodes within each cluster
            for _ in range(nodes_per_cluster - 1):
                node_angle = rng.uniform(0, 2 * math.pi)
                node_dist = node_radius * math.sqrt(
                    rng.uniform(0.0, 1.0)
                )  # distribute nodes uniformly within the cluster area
                n_x = ch_x + node_dist * math.cos(node_angle)
                n_y = ch_y + node_dist * math.sin(node_angle)
                positions.append(CartesianCoordinate(n_x, n_y))

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
