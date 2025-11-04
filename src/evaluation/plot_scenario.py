import sys
import os
import argparse
import matplotlib.pyplot as plt
from adjustText import adjust_text  # Import adjustText for label management
import numpy as np # <-- ADDED IMPORT

# --- Python Path Setup ---
# Standard setup to ensure the simulator modules can be imported
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# --- Simulator Imports ---
from simulator.engine.Kernel import Kernel
from simulator.environment.geometry import CartesianCoordinate
from simulator.environment.propagation.narrowband import NarrowbandChannelModel
from evaluation.util.topology import (
    get_linear_topology_positions,
    get_ring_topology_positions,
)

# ======================================================================================
# HELPER FUNCTION (NEW)
# ======================================================================================

def calculate_bounds_and_params(node_positions, padding=50, dspace_step=1):
    """
    Calculates the bounding box of the topology and determines the DSpace
    parameters (npt) needed to contain it with 0-centering.
    
    The DSpace grid is 0-centered. We find the largest absolute coordinate
    (plus padding) and calculate an 'npt' that ensures the grid
    spans from [-max_coord, +max_coord].
    """
    if not node_positions:
        # Default fallback if no positions
        return 200 # default npt

    min_x = min(p.x for p in node_positions)
    max_x = max(p.x for p in node_positions)
    min_y = min(p.y for p in node_positions)
    max_y = max(p.y for p in node_positions)

    # Apply padding
    min_x_pad = min_x - padding
    max_x_pad = max_x + padding
    min_y_pad = min_y - padding
    max_y_pad = max_y + padding

    # Find the largest absolute coordinate required from the center (0,0)
    # This determines the 'half-width' of the square DSpace
    max_abs_coord = max(abs(min_x_pad), abs(max_x_pad), abs(min_y_pad), abs(max_y_pad))

    # Calculate npt needed for this half-width
    # DSpace grid: np.arange(-half_n, self.npt - half_n)
    # To ensure the grid *includes* +max_abs_coord and -max_abs_coord:
    # We need the max index to be at least ceil(max_abs_coord / dspace_step)
    # Let half_n = ceil(max_abs_coord / dspace_step) + 1 (for safety)
    # Let npt = half_n * 2
    
    half_n = int(np.ceil(max_abs_coord / dspace_step)) + 2 # Add a small safety margin
    dspace_npt = half_n * 2

    print(f"Topology bounds (unpadded): X=[{min_x:.1f}, {max_x:.1f}], Y=[{min_y:.1f}, {max_y:.1f}]")
    print(f"Max absolute coordinate (padded): {max_abs_coord:.1f}")
    print(f"Calculated DSpace params: step={dspace_step}, npt={dspace_npt} (Grid will span approx. [{-half_n*dspace_step}, {half_n*dspace_step-1}])")

    return dspace_npt

# --- Plotting Function (Combined logic) ---
def plot_scenario_with_shadowing(
    kernel: Kernel,
    node_positions: list,
    pinger_idx: int,
    ponger_idx: int,
    title="Network Topology",
    save_path=None,
    figsize=13, # Increased size for legend
):
    """
    Plots the node topology, the underlying shadowing map,
    and the losses on the Pinger-Ponger link.
    
    Args:
        kernel (Kernel): The bootstrapped simulation kernel.
        node_positions (list): List of CartesianCoordinate for all nodes.
        pinger_idx (int): The index of the pinger node.
        ponger_idx (int): The index of the ponger node.
        title (str): The main title for the plot.
        save_path (str): Path to save the figure.
        figsize (int): Figure size.
    """
    
    # --- 1. Get Data from Kernel ---
    # Get the DSpace object to access coordinate grids
    dspace = kernel.dspace
    if dspace is None:
        print("Error: Kernel DSpace is not initialized.")
        return

    # Get the propagation model to access the map and loss functions
    prop_model = kernel.propagation_model
    if prop_model is None or prop_model.shadowing_map is None:
        print("Error: Shadowing map has not been generated in the kernel.")
        return
        
    shadow_map = prop_model.shadowing_map

    # --- 2. Setup Figure ---
    plt.figure(figsize=(figsize, figsize))
    ax = plt.gca()  # Get current axes
    
    # --- 3. Plot Shadowing Map (Background) ---
    # Use pcolormesh to plot the shadowing map using its real coordinates
    # This shows the spatial field of shadowing values.
    # We must use the DSpace X and Y grids, which are 0-centered
    cax = ax.pcolormesh(
        dspace.X, 
        dspace.Y, 
        shadow_map, 
        cmap='viridis',  # 'viridis' is a good perceptually uniform colormap
        zorder=1,        # Put it in the background
        alpha=0.8,       # Make it slightly transparent
        shading='auto'   # Use 'auto' shading
    )
    plt.colorbar(cax, label="Shadowing Attenuation (dB)")

    # --- 4. Plot Topology (Logic adapted from plot_topology.py) ---
    handles = []  # To store handles for legend items
    labels = []   # To store labels for legend items

    # Define markers and colors consistently
    marker_map = {'sink': 'X', 'pinger': '^', 'ponger': 's', 'node': 'o'}
    color_map = {'sink': 'purple', 'pinger': 'green', 'ponger': 'red', 'node': 'blue'}
    label_map = {'sink': 'Sink/Root', 'pinger': 'Pinger', 'ponger': 'Ponger', 'node': 'Node'}
    plotted_labels = set()

    text_objects = []
    x_coords = []
    y_coords = []

    # Create the info_dict needed for the loop
    info_dict = {}
    for i, position in enumerate(node_positions):
        node_id = f"Node-{i+1}" # Use 1-based indexing for ID
        addr = (i + 1).to_bytes(2, "big")
        info_dict[node_id] = {
            "position": position,
            "address": addr,
            "is_pinger": i == pinger_idx,
            "is_ponger": i == ponger_idx,
            "is_sink": i == 0, # Node-1 (index 0) is always sink
        }

    # Loop through nodes and plot them
    for node_id, info in info_dict.items():
        position = info["position"]
        addr = info["address"]
        addr_hex = ''.join([f'{b:02x}' for b in addr])
        is_pinger = info.get("is_pinger", False)
        is_ponger = info.get("is_ponger", False)
        is_sink = info.get("is_sink", False)

        node_type = 'node'  # Default
        if is_sink:
            node_type = 'sink'
        elif is_pinger:
            node_type = 'pinger'
        elif is_ponger:
            node_type = 'ponger'

        marker = marker_map[node_type]
        color = color_map[node_type]
        label = label_map[node_type]

        # Plot the node marker
        ax.scatter(
            position.x, 
            position.y, 
            marker=marker, 
            color=color, 
            s=120, # Slightly larger markers
            zorder=5, 
            alpha=0.9, 
            edgecolors='black' # Add edgecolors for visibility
        )

        # Store coordinates for adjust_text
        x_coords.append(position.x)
        y_coords.append(position.y)

        # Create the text label for the node
        txt = ax.text(
            position.x,
            position.y,
            f"{node_id}\n0x{addr_hex}",
            fontsize=9,
            ha="center",
            va="center",
            zorder=6
        )
        text_objects.append(txt)

        # Store legend items, ensuring no duplicates
        if label not in plotted_labels:
            handles.append(plt.scatter([], [], marker=marker, color=color, s=120, alpha=1.0, edgecolors='black'))
            labels.append(label)
            plotted_labels.add(label)

    # Use adjust_text to move node labels to prevent overlap
    adjust_text(
        text_objects,
        x=x_coords,
        y=y_coords,
        ax=ax,  # Pass the axes object
        only_move={'points':'y', 'text':'y'}, # Move labels vertically
        arrowprops=dict(arrowstyle='-', color='gray', lw=0.5, alpha=0.7),
        zorder=7
    )

    # --- 5. Calculate and Plot Link Losses (New Feature) ---
    pinger_pos = node_positions[pinger_idx]
    ponger_pos = node_positions[ponger_idx]

    # Calculate losses using the kernel's propagation model
    # Note: These methods return positive dB values for loss
    pl_dB = prop_model._path_loss_dB(pinger_pos, ponger_pos)
    sl_dB = prop_model._link_shadowing_loss_dB(pinger_pos, ponger_pos)
    total_loss_dB = prop_model.total_loss_dB(pinger_pos, ponger_pos) # This is pl + sl

    # Calculate midpoint for the label
    mid_x = (pinger_pos.x + ponger_pos.x) / 2
    mid_y = (pinger_pos.y + ponger_pos.y) / 2

    # Draw a line representing the Pinger-Ponger link
    ax.plot(
        [pinger_pos.x, ponger_pos.x], 
        [pinger_pos.y, ponger_pos.y], 
        'r--',  # Red dashed line
        lw=2,
        alpha=0.7, 
        zorder=4
    )
    
    # Create the text string for the link losses
    loss_text = (
        f"Pinger-Ponger Link:\n"
        f"Path Loss: {pl_dB:.2f} dB\n"
        f"Shadowing: {sl_dB:.2f} dB\n"
        f"Total Loss: {total_loss_dB:.2f} dB"
    )
    
    # Add the text with a white background for readability
    ax.text(
        mid_x, 
        mid_y, 
        loss_text, 
        fontsize=10, 
        color='black', 
        ha='center', 
        va='center',
        zorder=10, 
        bbox=dict(facecolor='white', alpha=0.8, pad=0.3, boxstyle='round,pad=0.3')
    )

    # --- 6. Finalize Plot ---
    ax.set_title(title, fontsize=16)
    ax.set_xlabel("X Position (m)")
    ax.set_ylabel("Y Position (m)")
    ax.grid(True, linestyle=':', alpha=0.6, zorder=0)
    
    # Set aspect ratio to equal to avoid spatial distortion
    ax.set_aspect('equal', 'box')
    
    plt.tight_layout(rect=[0, 0, 0.88, 0.96]) # Make room for legend/title

    # Add the legend outside the plot area
    if handles:
        ax.legend(handles, labels, title="Legend", loc="upper left", bbox_to_anchor=(1.02, 1.0))

    if save_path:
        plt.savefig(save_path, bbox_inches='tight')
        print(f"Scenario plot saved to {save_path}")
        plt.close()
    else:
        # Fallback to show plot if no save path is given
        plt.show()

# --- Main execution block (adapted from pingpong.py) ---
if __name__ == "__main__":
    
    # --- Setup Argparse ---
    parser = argparse.ArgumentParser(description="Plot PingPong scenario with shadowing and link losses.")
    parser.add_argument(
        "--topology", type=str, choices=["linear", "ring"],
        default="ring", help="Network topology type (default: ring)"
    )
    parser.add_argument(
        "--channel", type=str, choices=["stable", "medium", "harsh"],
        default="harsh", help="Channel model type (default: harsh)"
    )
    args = parser.parse_args()

    print(f"--- Generating plot for {args.topology} topology and {args.channel} channel ---")

    kernel_seed = 12346

    # --- Channel Parameter Dictionaries (Copied from pingpong.py) ---
    stable_params = {
        "seed": 12346, "dspace_step": 1, "dspace_npt": 200, "freq": 2.4e9,
        "filter_bandwidth": 2e6, "coh_d": 50, "shadow_dev": 2.0,
        "pl_exponent": 2, "d0": 1.0, "fading_shape": 3.0,
    }
    medium_params = {
        "seed": 12346, "dspace_step": 1, "dspace_npt": 200, "freq": 2.4e9,
        "filter_bandwidth": 2e6, "coh_d": 30, "shadow_dev": 4.0,
        "pl_exponent": 3.5, "d0": 1.0, "fading_shape": 1.5,
    }
    harsh_params = {
        "seed": 12346, "dspace_step": 1, "dspace_npt": 200, "freq": 2.4e9,
        "filter_bandwidth": 2e6, "coh_d": 10, "shadow_dev": 6.0,
        "pl_exponent": 4.0, "d0": 1.0, "fading_shape": 0.75,
    }

    # Select channel parameters based on args
    if args.channel == "stable":
        bootstrap_params = stable_params
    elif args.channel == "medium":
        bootstrap_params = medium_params
    else: # harsh
        bootstrap_params = harsh_params

    # --- Topology Parameters ---
    num_nodes = 20
    node_distance = 10  # For linear topology
    
    plots_dir = "plots" # Define plots directory
    if not os.path.exists(plots_dir):
        os.makedirs(plots_dir)

    # === REFACTORED LOGIC START ===
    
    print(f"\n--- Generating '{args.topology}' topology positions... ---")
    # 1. Generate Node Positions FIRST
    if args.topology == "linear":
        # Linear topology, 0-centered
        total_length = (num_nodes - 1) * node_distance
        start_x = -(total_length / 2)
        start_y = 0 
            
        node_positions = get_linear_topology_positions(
            num_nodes, node_distance, start_x=start_x, start_y=start_y, increase_y=False
        )
        pinger_idx = 1 # Node-2
        ponger_idx = num_nodes - 1 # Last node
    else: # ring
        # Ring topology, 0-centered
        node_positions = get_ring_topology_positions(num_nodes, radius=150, center_x=0, center_y=0)
        pinger_idx = num_nodes // 4
        ponger_idx = (3 * num_nodes) // 4
        
    # 2. Calculate DSpace parameters FROM topology
    print("\n--- Calculating Dynamic DSpace Parameters ---")
    dspace_step = 1 # Fix step to 1m for simplicity
    padding_meters = 50 # Add 50m padding around the topology bounds
    dspace_npt = calculate_bounds_and_params(node_positions, padding=padding_meters, dspace_step=dspace_step)

    # 3. Update bootstrap_params with dynamic values
    bootstrap_params['dspace_npt'] = dspace_npt
    bootstrap_params['dspace_step'] = dspace_step
    # The seed is already set based on the channel type

    # 4. Bootstrap Kernel (REQUIRED to get the map)
    print(f"\nBootstrapping kernel with seed {kernel_seed} to generate shadowing map...")
    kernel = Kernel(root_seed=kernel_seed)
    kernel.bootstrap(**bootstrap_params)
    print("Kernel bootstrapped.")

    # === REFACTORED LOGIC END ===


    # --- Define file path and title ---
    plot_path = os.path.join(plots_dir, f"scenario_plot_{args.topology}_{args.channel}.png")
    plot_title = f"Scenario: {args.topology.capitalize()} Topology, {args.channel.capitalize()} Channel"

    # --- Generate Plot ---
    print(f"Generating plot and saving to {plot_path}...")
    plot_scenario_with_shadowing(
        kernel=kernel,
        node_positions=node_positions,
        pinger_idx=pinger_idx,
        ponger_idx=ponger_idx,
        title=plot_title,
        save_path=plot_path
    )
    print("Done.")
