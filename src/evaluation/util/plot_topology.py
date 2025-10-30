import matplotlib.pyplot as plt
from adjustText import adjust_text

def plot_topology(
    info_dict,
    title="Network Topology",
    save_path=None,
    figsize=12,
):
    # Make figure wider for linear topologies
    plt.figure(figsize=(figsize, figsize)) 
    
    handles = []  # To store handles for legend items
    labels = []   # To store labels for legend items

    # Define markers and colors consistently
    marker_map = {'sink': 'X', 'pinger': '^', 'ponger': 's', 'node': 'o'}
    color_map = {'sink': 'purple', 'pinger': 'green', 'ponger': 'red', 'node': 'blue'}
    label_map = {'sink': 'Sink/Root', 'pinger': 'Pinger', 'ponger': 'Ponger', 'node': 'Node'}
    plotted_labels = set()

    # List to collect text objects for adjust_text
    text_objects = []
    
    # We will pass these to adjust_text so it knows where the
    # markers are and can automatically avoid them.
    x_coords = []
    y_coords = []

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

        scatter = plt.scatter(
            position.x, 
            position.y, 
            marker=marker, 
            color=color, 
            s=100, 
            zorder=5, 
            alpha=0.6
        )
        # -------------------------------------------

        # Add the node's x and y coordinates to our lists
        x_coords.append(position.x)
        y_coords.append(position.y)

        # Create text object at the exact marker position
        txt = plt.text(
            position.x,
            position.y,
            f"{node_id}\n0x{addr_hex}", # Your newline format
            fontsize=9,
            ha="center", # Center horizontally
            va="center", # Center vertically
            zorder=6
        )
        text_objects.append(txt)

        # Add legend entry only once per type
        if label not in plotted_labels:
            # The legend entry should be fully opaque
            handles.append(plt.scatter([], [], marker=marker, color=color, s=100, alpha=1.0))
            labels.append(label)
            plotted_labels.add(label)

    # Pass coordinates to adjust_text to avoid markers
    adjust_text(
        text_objects,
        x=x_coords,  # Pass the list of marker x-coordinates
        y=y_coords,  # Pass the list of marker y-coordinates
        only_move={'points':'y', 'text':'y'}, # Force only vertical movement
        arrowprops=dict(arrowstyle='-', color='gray', lw=0.5, alpha=0.7),
        zorder=7
    )

    plt.title(title)
    plt.xlabel("X Position")
    plt.ylabel("Y Position")
    plt.grid(True)
    
    
    plt.tight_layout(rect=[0, 0, 1, 0.96]) # Make room for title

    # Create legend from collected handles and labels
    if handles:
        plt.legend(handles, labels, title="Legend", loc="upper right", bbox_to_anchor=(1.15, 1.0))

    if save_path:
        plt.savefig(save_path, bbox_inches='tight') # Use tight bbox for legend
        print(f"Physical topology plot saved to {save_path}")
        plt.close()  # Close the figure after saving
    else:
        plt.show()

