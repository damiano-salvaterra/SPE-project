from simulator.environment.geometry import CartesianCoordinate
import math


def get_linear_topology_positions(
    num_nodes, node_distance, start_x=0, start_y=0, increase_y=False
):
    positions = []
    for i in range(num_nodes):
        if increase_y:
            x = start_x
            y = start_y + i * node_distance
        else:
            x = start_x + i * node_distance
            y = start_y
        positions.append(CartesianCoordinate(x, y))
    return positions


def get_ring_topology_positions(num_nodes, radius=50, center_x=100, center_y=100):

    positions = []
    for i in range(num_nodes):
        # Calculate angle for this node
        angle = 2 * math.pi * i / num_nodes  # Distribute nodes evenly around circle

        # Calculate position
        x = center_x + radius * math.cos(angle)
        y = center_y + radius * math.sin(angle)

        positions.append(CartesianCoordinate(x, y))

    return positions
