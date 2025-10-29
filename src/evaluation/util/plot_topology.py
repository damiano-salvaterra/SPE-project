# src/evaluation/util/plot_topology.py
import matplotlib.pyplot as plt
from simulator.environment.geometry import CartesianCoordinate
# --- Add this line ---
from typing import List, Dict, Tuple, Optional
# ----------------------

# --- Keep existing plot_topology function ---
def plot_topology(
    info_dict,
    title="Network Topology",
    save_path=None,
    figsize=12,
):
    # ... (Keep existing implementation) ...
    plt.figure(figsize=(figsize, figsize))
    handles = [] # To store handles for legend items
    labels = []  # To store labels for legend items

    # Define markers and colors consistently
    marker_map = {'sink': 'X', 'pinger': '^', 'ponger': 's', 'node': 'o'}
    color_map = {'sink': 'purple', 'pinger': 'green', 'ponger': 'red', 'node': 'blue'}
    label_map = {'sink': 'Sink/Root', 'pinger': 'Pinger', 'ponger': 'Ponger', 'node': 'Node'}
    plotted_labels = set()


    for node_id, info in info_dict.items():
            position = info["position"]
            addr = info["address"]
            addr_hex = ''.join([f'{b:02x}' for b in addr])
            is_pinger = info.get("is_pinger", False)
            is_ponger = info.get("is_ponger", False)
            is_sink = info.get("is_sink", False)

            node_type = 'node' # Default
            if is_sink:
                node_type = 'sink'
            elif is_pinger:
                 node_type = 'pinger'
            elif is_ponger:
                 node_type = 'ponger'

            marker = marker_map[node_type]
            color = color_map[node_type]
            label = label_map[node_type]

            # Plot node
            scatter = plt.scatter(position.x, position.y, marker=marker, color=color, s=100, zorder=5)
            plt.text(
                position.x,
                position.y + 5, # Adjust offset slightly
                f"{node_id}: 0x{addr_hex}", # Corrected label format
                fontsize=9, # Slightly smaller font
                ha="center",
                zorder=6
            )

            # Add legend entry only once per type
            if label not in plotted_labels:
                # Create a dummy scatter for the legend handle (prevents plotting extra points)
                handles.append(plt.scatter([], [], marker=marker, color=color, s=100))
                labels.append(label)
                plotted_labels.add(label)

    plt.title(title)
    plt.xlabel("X Position")
    plt.ylabel("Y Position")
    plt.grid(True)
    plt.axis("equal")
    # Adjust layout *before* legend if needed
    plt.tight_layout(rect=[0, 0, 1, 0.96]) # Adjust rect to make space for title

    # Create legend from collected handles and labels
    if handles:
        plt.legend(handles, labels, title="Legend", loc="upper right", bbox_to_anchor=(1.15, 1.0)) # Adjust anchor slightly

    if save_path:
        plt.savefig(save_path, bbox_inches='tight') # Use bbox_inches='tight' for legend
        print(f"Physical topology plot saved to {save_path}")
        plt.close() # Close the figure after saving
    else:
        plt.show()

# --- Keep NEW plot_logical_topology function ---
def plot_logical_topology(
    timestamp: float,
    links: List[Tuple[bytes, bytes]], # Now List and Tuple are defined
    node_info: Dict[str, Dict],      # Now Dict is defined
    ax: plt.Axes,
    title_prefix: str = "Logical Topology",
):
    """
    Plots a snapshot of the TARP logical topology on a given Axes object.

    Args:
        timestamp (float): Simulation time for this snapshot.
        links (List[Tuple[bytes, bytes]]): List of (child_addr, parent_addr) links.
        node_info (Dict[str, Dict]): Info dict mapping node_id to {'position': CartesianCoordinate, 'address': bytes, ...}.
        ax (plt.Axes): The matplotlib Axes object to plot on.
        title_prefix (str): Prefix for the subplot title.
    """
    # ... (Keep the rest of the plot_logical_topology function implementation) ...
    # 1. Create mapping from address back to position and ID for easier lookup
    addr_to_pos = {info['address']: info['position'] for info in node_info.values()}
    addr_to_id = {info['address']: node_id for node_id, info in node_info.items()}

    # 2. Plot all nodes with labels (similar to plot_topology, but on the provided ax)
    marker_map = {'sink': 'X', 'pinger': '^', 'ponger': 's', 'node': 'o'}
    color_map = {'sink': 'purple', 'pinger': 'green', 'ponger': 'red', 'node': 'blue'}

    for node_id, info in node_info.items():
        position = info["position"]
        addr = info["address"]
        is_pinger = info.get("is_pinger", False)
        is_ponger = info.get("is_ponger", False)
        is_sink = info.get("is_sink", False)

        node_type = 'node' # Default
        if is_sink:
            node_type = 'sink'
        elif is_pinger:
             node_type = 'pinger'
        elif is_ponger:
             node_type = 'ponger'

        marker = marker_map[node_type]
        color = color_map[node_type]

        ax.scatter(position.x, position.y, marker=marker, color=color, s=80, zorder=5) # Slightly smaller markers
        ax.text(
            position.x,
            position.y + 4, # Adjust offset
            f"0x{''.join([f'{b:02x}' for b in addr])}", # Show only address for less clutter
            fontsize=7, # Smaller font
            ha="center",
            zorder=6
        )

    # 3. Draw lines for parent-child links
    for child_addr, parent_addr in links:
        child_pos = addr_to_pos.get(child_addr)
        parent_pos = addr_to_pos.get(parent_addr)

        if child_pos and parent_pos:
            # Draw line from parent to child
            ax.plot(
                [parent_pos.x, child_pos.x],
                [parent_pos.y, child_pos.y],
                color='gray',
                linestyle='-',
                linewidth=0.8,
                zorder=1 # Draw lines behind nodes
            )
            # Optional: Add an arrow head (can make plot cluttered)
            # ax.annotate('', xy=(child_pos.x, child_pos.y), xytext=(parent_pos.x, parent_pos.y),
            #             arrowprops=dict(arrowstyle="->", color='gray', lw=0.8))


    # 4. Set subplot title and labels
    ax.set_title(f"{title_prefix} @ t={timestamp:.2f}s", fontsize=10)
    ax.set_xlabel("X Position", fontsize=8)
    ax.set_ylabel("Y Position", fontsize=8)
    ax.tick_params(axis='both', which='major', labelsize=7)
    ax.grid(True, linestyle='--', linewidth=0.5)
    ax.axis('equal') # Keep aspect ratio consistent