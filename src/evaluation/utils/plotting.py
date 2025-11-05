import matplotlib.pyplot as plt
from adjustText import adjust_text
import numpy as np
from typing import List, Dict, Any, Optional, Tuple

# Import simulator components for type hinting and functionality
from simulator.engine.Kernel import Kernel
from simulator.environment.geometry import CartesianCoordinate

# Define consistent plotting styles
MARKER_MAP = {
    'sink': 'X',
    'pinger': '^',
    'ponger': 's',
    'default': 'o'
}
COLOR_MAP = {
    'sink': 'purple',
    'pinger': 'green',
    'ponger': 'red',
    'default': 'blue'
}
LABEL_MAP = {
    'sink': 'Sink/Root',
    'pinger': 'Pinger',
    'ponger': 'Ponger',
    'default': 'Node'
}
Z_ORDER = {
    'shadowing': 1,
    'grid': 2,
    'link_line': 4, # Z-order for link line (now unused)
    'node': 5,
    'node_label': 6,
    'link_annot': 7  # Z-order for link annotation (now unused)
}

def plot_scenario(
    kernel: Optional[Kernel],
    node_info: Dict[str, Dict[str, Any]],
    title: str = "Network Scenario",
    save_path: Optional[str] = None,
    links_to_annotate: Optional[List[Tuple[str, str]]] = None,
    figsize: Tuple[int, int] = (12, 10)
):
    """
    Plots the complete network scenario.
    
    - If 'kernel' is provided, plots the shadowing map as a background.
    - Plots all nodes based on their positions and roles from 'node_info'.
    - If 'links_to_annotate' is provided, this function will check
      node positions but will no longer draw lines or annotations.
      
    Args:
        kernel: The bootstrapped simulation kernel. If None,
                no shadowing map or link losses will be plotted.
        node_info: A dictionary mapping node_id to its info.
                   e.g., {"Node-1": {"position": pos, "role": "sink", "addr": b'\x00\x01'}}
        title: The main title for the plot.
        save_path: Path to save the figure. If None, plt.show() is called.
        links_to_annotate: A list of (node_id_1, node_id_2) tuples.
                           (This is kept for API compatibility but no longer draws.)
        figsize: The (width, height) of the figure.
    """
    
    plt.figure(figsize=figsize)
    ax = plt.gca()
    
    prop_model = None
    cbar = None # Initialize cbar for potential later adjustments
    if kernel and kernel.dspace and kernel.propagation_model:
        prop_model = kernel.propagation_model
        shadow_map = prop_model.shadowing_map
        dspace = kernel.dspace
        
        if shadow_map is not None:
            # --- 1. Plot Shadowing Map (Background) ---
            print("Plotting shadowing map from kernel.")
            cax = ax.pcolormesh(
                dspace.X, 
                dspace.Y, 
                shadow_map, 
                cmap='viridis',
                zorder=Z_ORDER['shadowing'],
                alpha=0.8,
                shading='auto'
            )
            # Store the colorbar object
            cbar = plt.colorbar(cax, label="Shadowing Attenuation (dB)")

    # --- 2. Plot Nodes ---
    handles, plotted_labels = {}, set()
    text_objects, x_coords, y_coords = [], [], []

    for node_id, info in node_info.items():
        pos = info.get("position")
        if not pos:
            print(f"Warning: Node '{node_id}' has no position info. Skipping.")
            continue
            
        role = info.get("role", "default")
        addr = info.get("addr", b'')
        addr_hex = addr.hex()

        marker = MARKER_MAP.get(role, MARKER_MAP['default'])
        color = COLOR_MAP.get(role, COLOR_MAP['default'])
        label = LABEL_MAP.get(role, LABEL_MAP['default'])

        ax.scatter(
            pos.x, pos.y,
            marker=marker, 
            color=color, 
            s=120,
            zorder=Z_ORDER['node'], 
            alpha=0.9, 
            edgecolors='black'
        )
        
        x_coords.append(pos.x)
        y_coords.append(pos.y)

        # Create text label
        txt = ax.text(
            pos.x, pos.y,
            f"{node_id}\n0x{addr_hex}",
            fontsize=9,
            ha="center", va="center",
            zorder=Z_ORDER['node_label']
        )
        text_objects.append(txt)

        # Store legend items
        if label not in plotted_labels:
            handles[label] = plt.scatter(
                [], [], marker=marker, color=color, s=120,
                alpha=1.0, edgecolors='black'
            )
            plotted_labels.add(label)

    # --- 3. Adjust Text Labels ---
    if text_objects:
        adjust_text(
            text_objects,
            x=x_coords, y=y_coords, ax=ax,
            only_move={'points':'y', 'text':'y'},
            arrowprops=dict(arrowstyle='-', color='gray', lw=0.5, alpha=0.7),
            zorder=Z_ORDER['node_label']
        )

    # --- 4. Plot and Annotate Links (MODIFIED) ---
    if links_to_annotate and prop_model:
        # We still iterate to check for warnings, but do not plot
        for n1_id, n2_id in links_to_annotate:
            pos1 = node_info.get(n1_id, {}).get("position")
            pos2 = node_info.get(n2_id, {}).get("position")
            
            if not pos1 or not pos2:
                print(f"Warning: Cannot find positions for link {n1_id}-{n2_id}. Skipping.")
                continue
            
            pass # Keep the loop structure but do nothing

    # --- 5. Finalize Plot (MODIFIED for layout) ---
    ax.set_title(title, fontsize=16)
    ax.set_xlabel("X Position (m)")
    ax.set_ylabel("Y Position (m)")
    ax.grid(True, linestyle=':', alpha=0.6, zorder=Z_ORDER['grid'])
    ax.set_aspect('equal', 'box')
    
    # MODIFICATION:
    # Adjust tight_layout rect. [left, bottom, right, top]
    # We increase the 'bottom' margin to make room for the horizontal legend.
    # We keep the 'right' margin as-is for the colorbar.
    plt.tight_layout(rect=[0.05, 0.1, 0.95, 0.95]) 

    if handles:
        # MODIFICATION:
        # Move the legend to be *below* the plot (ax.set_xlabel)
        # 'loc="upper center"' anchors the top-center of the legend box
        # 'bbox_to_anchor=(0.5, -0.1)' places that anchor at
        #   (50% of axes width, -10% of axes height below the axes)
        # 'ncol' makes all legend items horizontal
        ax.legend(
            handles.values(), handles.keys(),
            title="Legend", 
            loc="upper center",
            bbox_to_anchor=(0.5, -0.1), # Position *below* the plot
            ncol=len(handles),          # Arrange horizontally
            fancybox=True, shadow=True
        )

    if save_path:
        print(f"Saving scenario plot to {save_path}")
        # Use bbox_inches='tight' to ensure the legend below is included
        plt.savefig(save_path, bbox_inches='tight')
        plt.close()
    else:
        plt.show()