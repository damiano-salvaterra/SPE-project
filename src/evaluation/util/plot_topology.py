import matplotlib.pyplot as plt
from simulator.environment.geometry import CartesianCoordinate


def plot_topology(
    positions: list[CartesianCoordinate],
    title="Network Topology",
    save_path=None,
    figsize=12,
):
    """
    Plots the network topology based on node positions.

    Args:
        positions (list of tuples): List of (x, y) positions for each node.
        title (str): Title of the plot.
        save_path (str or None): If provided, saves the plot to this path.
    """
    plt.figure(figsize=(figsize, figsize))
    x_coords = [coord.x for coord in positions]
    y_coords = [coord.y for coord in positions]
    plt.scatter(x_coords, y_coords)

    for i, coord in enumerate(positions):
        addr = (i + 1).to_bytes(2, "big")
        plt.text(
            coord.x,
            coord.y,
            f"Node-{chr(ord('A') + i)}\n{addr}",
            fontsize=12,
            ha="right",
        )

    plt.title(title)
    plt.xlabel("X Position")
    plt.ylabel("Y Position")
    plt.grid(True)
    plt.axis("equal")
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path)
    else:
        plt.show()
