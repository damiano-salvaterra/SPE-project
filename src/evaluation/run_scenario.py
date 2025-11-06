import sys
import os
import argparse
import numpy as np
import traceback
from typing import List, Dict, Any, Optional

# --- Python Path Setup ---
# 1. Define PROJECT_ROOT as the directory TWO levels up from this file
# (up from 'evaluation', up from 'src')
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# 2. Define SRC_ROOT
SRC_ROOT = os.path.join(PROJECT_ROOT, "src")

# 3. Add SRC_ROOT to sys.path to allow imports like 'from simulator...'
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

# --- Simulator Imports ---
from simulator.engine.Kernel import Kernel  # noqa: E402
from simulator.applications.PingPongApplication import PingPongApp  # noqa: E402
# Import the refactored RandomTrafficApplication
from simulator.applications.RandomTrafficApplication import RandomTrafficApplication  # noqa: E402
from simulator.environment.geometry import CartesianCoordinate # noqa: E402
from simulator.engine.random import RandomManager, RandomGenerator # noqa: E402

# --- Refactored Evaluation Utils Imports ---
from evaluation.monitors.packet_monitor import PacketMonitor  # noqa: E402
from evaluation.monitors.app_monitor import AppPingMonitor  # noqa: E402
from evaluation.monitors.tarp_monitor import TARPMonitor  # noqa: E402
from evaluation.utils.topology_factory import TopologyFactory # noqa: E402
from evaluation.utils.plotting import plot_scenario # noqa: E402


# ======================================================================================
# Global Logging State
# ======================================================================================

# Store original stdout/stderr to restore them on exit
original_stdout = sys.stdout
original_stderr = sys.stderr
log_file = None

def setup_logging(log_filename="simulation.log"):
    """
    Redirects stdout (but not stderr) to a specified log file.
    Exceptions will still print to the original console.
    """
    global log_file
    try:
        # Create log directory if it doesn't exist
        log_dir = os.path.dirname(log_filename)
        # Use exist_ok=True to avoid error if dir already exists
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
            
        # Open the log file
        log_file = open(log_filename, 'w')
        
        # Redirect stdout to the log file
        sys.stdout = log_file
        
    except Exception as e:
        # If logging setup fails, print error to original stderr and exit
        original_stderr.write(f"Failed to setup logging to {log_filename}: {e}\n")
        sys.exit(1)

def cleanup_logging():
    """
    Restores original stdout/stderr and closes the log file.
    This function is safe to call multiple times.
    """
    global log_file
    
    # Check if log_file is valid and open
    if log_file and not log_file.closed:
        try:
            log_file.flush()
            log_file.close()
        except Exception as e:
            # If closing fails, report to original stderr
            original_stderr.write(f"Failed to close log file: {e}\n")
    
    log_file = None # Prevent subsequent close attempts
    
    # Restore original stdout and stderr
    sys.stdout = original_stdout
    sys.stderr = original_stderr

# ======================================================================================
# Helper Functions
# ======================================================================================

def calculate_bounds_and_params(node_positions, padding=50, dspace_step=1.0):
    """
    Calculates the bounding box of the topology and determines the DSpace
    parameters (npt) needed to contain it with 0-centering.
    The dspace_step (point density) is now a parameter.
    """
    if not node_positions:
        return 200 # Default fallback

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
    max_abs_coord = max(abs(min_x_pad), abs(max_x_pad), abs(min_y_pad), abs(max_y_pad))

    # Calculate npt needed for this half-width, based on the step (density)
    half_n = int(np.ceil(max_abs_coord / dspace_step)) + 2 # Add a small safety margin
    dspace_npt = half_n * 2

    print(f"Topology bounds (unpadded): X=[{min_x:.1f}, {max_x:.1f}], Y=[{min_y:.1f}, {max_y:.1f}]")
    print(f"Max absolute coordinate (padded): {max_abs_coord:.1f}")
    print(f"Calculated DSpace params: step={dspace_step}, npt={dspace_npt} (Grid will span approx. [{-half_n*dspace_step:.1f}, {half_n*dspace_step-dspace_step:.1f}])")

    return dspace_npt

def get_channel_params(channel_name: str) -> dict:
    """Returns a dictionary of channel parameters for a given name."""
    
    # Base parameters (stable)
    stable_params = {
        "freq": 2.4e9, "filter_bandwidth": 2e6, "coh_d": 50,
        "shadow_dev": 2.0, "pl_exponent": 2, "d0": 1.0, "fading_shape": 3.0,
    }

    # Realistic, unstable multi-hop
    medium_params = {
        "freq": 2.4e9, "filter_bandwidth": 2e6, "coh_d": 30,
        "shadow_dev": 4.0, "pl_exponent": 3.5, "d0": 1.0, "fading_shape": 1.5,
    }

    # Bridge the gap between 'medium' and 'harsh'
    medium_lossy_params = {
        "freq": 2.4e9, "filter_bandwidth": 2e6, "coh_d": 20,
        "shadow_dev": 5.0, "pl_exponent": 3.8, "d0": 1.0, "fading_shape": 1.5,
    }

    # A bit less broken than 'harsh', focusing on instability
    harsh_unstable_params = {
        "freq": 2.4e9, "filter_bandwidth": 2e6, "coh_d": 15,
        "shadow_dev": 5.0, "pl_exponent": 4.0, "d0": 1.0, "fading_shape": 1.0,
    }

    # Very unstable multi-hop
    harsh_params = {
        "freq": 2.4e9, "filter_bandwidth": 2e6, "coh_d": 10,
        "shadow_dev": 6.0, "pl_exponent": 4.0, "d0": 1.0, "fading_shape": 0.75,
    }

    params_map = {
        "stable": stable_params,
        "medium": medium_params,
        "medium_lossy": medium_lossy_params,
        "harsh_unstable": harsh_unstable_params,
        "harsh": harsh_params,
    }
    
    return params_map.get(channel_name, harsh_params).copy()

# ======================================================================================
# MAIN SIMULATION FUNCTION
# ======================================================================================

def main(
    app_name: str,
    app_params: dict,
    num_nodes: int,
    simulation_time: float,
    root_seed: int,
    bootstrap_params: dict,
    bootstrapped_kernel: Kernel,
    node_positions: list,
    pinger_idx: Optional[int], # Can be None if not applicable
    ponger_idx: Optional[int], # Can be None if not applicable
):
    """
    Main simulation function. This function is called by the __main__ block
    and contains the core simulation setup and execution logic.
    """
    print("\n--- Simulation Parameters ---")
    print(f"Application: {app_name}")
    print(f"Root seed: {root_seed}")
    print(f"Network configuration: num_nodes={num_nodes}")
    print(f"Simulation time: {simulation_time}s")

    print("\n--- Initializing Kernel and Scheduler ---")
    kernel = bootstrapped_kernel
    print("Using provided bootstrapped kernel with parameters:")
    params_str = ", ".join(
        [f"{k}={v}" for k, v in bootstrap_params.items()]
    )
    print(f"Kernel configuration: {params_str}")


    print(f"\n--- Creating Network Nodes and setting up {app_name} ---")
    nodes = {} # Stores {node_id: StaticNode}
    
    # --- Step 1: Create all addresses first ---
    # This is required so RandomTrafficApplication can be initialized
    # with a complete map of all possible destinations.
    node_addrs_by_index = {i: (i + 1).to_bytes(2, "big") for i in range(num_nodes)}
    all_nodes_map = {
        f"Node-{i+1}": addr for i, addr in node_addrs_by_index.items()
    }

    # --- Step 2: Create nodes and applications ---
    for i in range(num_nodes):
        node_id = f"Node-{i+1}"
        addr = node_addrs_by_index[i]
        is_sink = (i == 0)  # Node-1 (index 0) is always the sink/root
        app: Application = None

        # --- Conditional Application Setup ---
        if app_name == "pingpong":
            is_pinger = (i == pinger_idx)
            is_ponger = (i == ponger_idx)
            peer_addr = None
            
            if is_pinger:
                peer_addr = node_addrs_by_index.get(ponger_idx)
                print(f"{node_id} (Addr: {addr.hex()}) is PINGER, peer is Node-{ponger_idx+1} (Addr: {peer_addr.hex()})")
            elif is_ponger:
                peer_addr = node_addrs_by_index.get(pinger_idx)
                print(f"{node_id} (Addr: {addr.hex()}) is PONGER, peer is Node-{pinger_idx+1} (Addr: {peer_addr.hex()})")

            app = PingPongApp(host=None, is_pinger=is_pinger, peer_addr=peer_addr)

        elif app_name == "random_traffic":
            app = RandomTrafficApplication(
                host=None,
                all_nodes=all_nodes_map,
                mean_interarrival_time=app_params.get("mean_interarrival_time", 60.0)
            )
            if i == 0:
                print(f"{node_id} (Addr: {addr.hex()}) is SINK/ROOT.")
        
        else:
            raise ValueError(f"Unknown application name: {app_name}")
        # -------------------------------------

        # This call will raise a ValueError if a node is outside
        # the DSpace bounds defined by dspace_npt and dspace_step
        node = kernel.add_node(
            node_id=node_id,
            position=node_positions[i],
            app=app,
            linkaddr=addr,
            is_sink=is_sink,
        )
        # CRITICAL: Assign the fully constructed node to the application
        app.host = node
        nodes[node_id] = node

    print("\n--- Attaching Monitors to all nodes ---")
    packet_monitor = PacketMonitor(verbose=False)
    # AppPingMonitor will correctly handle "DATA" packet types
    # from RandomTrafficApplication
    app_monitor = AppPingMonitor(verbose=True) 
    tarp_monitor = TARPMonitor(verbose=True)

    for node in nodes.values():
        kernel.attach_monitor(packet_monitor, f"{node.id}.phy")
        node.app.attach_monitor(app_monitor)
        node.net.attach_monitor(tarp_monitor)

    # --- Conditional Application Start Logic ---
    print("\n--- Starting Applications ---")
    if app_name == "pingpong":
        # Only start Pinger and Ponger
        pinger_node_id = f"Node-{pinger_idx + 1}"
        ponger_node_id = f"Node-{ponger_idx + 1}"
        if pinger_node_id in nodes:
            nodes[pinger_node_id].app.start()
        if ponger_node_id in nodes:
            nodes[ponger_node_id].app.start()
        print(f"Started PingPongApp on {pinger_node_id} and {ponger_node_id}.")
        
    elif app_name == "random_traffic":
        # Start the application on ALL nodes
        for node in nodes.values():
            node.app.start()
        print(f"Started RandomTrafficApplication on all {len(nodes)} nodes.")
    # -----------------------------------------

    print("\n--- Running Simulation ---")
    kernel.run(until=simulation_time)

    print("\n\n--- Simulation Finished ---")
    print(f"Final simulation time: {kernel.context.scheduler.now():.6f}s")

    scheduler = kernel.context.scheduler
    queue_len = scheduler.get_queue_length()
    print(f"Events remaining in queue: {queue_len}")

    if queue_len > 0:
        print("\n--- First 5 Events in Queue ---")
        for i, (time, event) in enumerate(sorted(scheduler.event_queue)[:5]):
            print(
                f"{i+1}: t={time * scheduler._time_scale:.6f}s, Event={type(event).__name__}, "
                f"Blame={type(event.blame).__name__}, Descriptor: {event.descriptor}, Cancelled: {event._cancelled}"
            )

# ======================================================================================
# SCRIPT EXECUTION (__main__)
# ======================================================================================

def setup_argparse() -> argparse.Namespace:
    """Configures and parses command-line arguments."""
    parser = argparse.ArgumentParser(description="Run a network simulation scenario.")
    
    # --- Application Choice ---
    parser.add_argument(
        "--app",
        type=str,
        choices=["pingpong", "random_traffic"],
        default="pingpong",
        help="The application to run on the nodes (default: pingpong)",
    )

    # --- Scenario Parameters ---
    parser.add_argument(
        "--topology",
        type=str,
        choices=["linear", "ring", "grid", "random", "star", "cluster-tree"],
        default="ring",
        help="Network topology type (default: ring)",
    )
    parser.add_argument(
        "--channel",
        type=str,
        choices=["stable", "medium", "medium_lossy", "harsh_unstable", "harsh"], 
        default="harsh",
        help="Channel model type (default: harsh)",
    )
    parser.add_argument(
        "--num_nodes",
        type=int,
        default=20,
        help="Number of nodes in the topology (default: 20)",
    )
    parser.add_argument(
        "--dspace_step",
        type=float, 
        default=1.0,
        help="Distance (meters) between DSpace grid points (density control). (default: 1.0)",
    )
    
    # --- Application-Specific Parameters ---
    parser.add_argument(
        "--mean_interarrival",
        type=float,
        default=60.0,
        help="Mean inter-arrival time (in seconds) for RandomTrafficApplication (default: 60.0)",
    )

    return parser.parse_args()


def create_topology_assets(
    app_name: str, # Added to control pinger/ponger logic
    topology_name: str, 
    num_nodes: int, 
    channel_name: str,
    plots_dir: str, # Pass the *base* plots directory
    topo_rng: np.random.Generator
) -> tuple:
    """
    Generates node positions and (if applicable) Pinger/Ponger indices.
    
    Returns:
        (node_positions, pinger_idx, ponger_idx, plot_path, num_nodes)
        Note: num_nodes is returned in case the topology modified the count.
    """
    print(f"\n--- Generating '{topology_name}' topology positions... ---")
    
    # Use the provided plots_dir, and create a "topology" subdirectory within it
    topo_plots_dir = os.path.join(plots_dir, "topology")
    
    factory = TopologyFactory()
    
    # Parameters to pass to the strategy
    topo_params = {"num_nodes": num_nodes, "rng": topo_rng}
    pinger_idx = None # Default to None
    ponger_idx = None # Default to None
    
    # --- Define parameters and pinger/ponger logic for each topology ---
    if topology_name == "linear":
        topo_params["node_distance"] = 10
        total_length = (num_nodes - 1) * topo_params["node_distance"]
        topo_params["start_x"] = -(total_length / 2) # Center it
        if app_name == "pingpong":
            pinger_idx = 1 if num_nodes > 1 else 0
            ponger_idx = num_nodes - 1
            
    elif topology_name == "grid":
        side = int(np.ceil(np.sqrt(num_nodes)))
        topo_params["grid_shape"] = (side, side)
        actual_num_nodes = side * side
        if num_nodes != actual_num_nodes:
            print(f"Note: Grid topology requested {num_nodes}, creating a {side}x{side} grid with {actual_num_nodes} nodes.")
            num_nodes = actual_num_nodes
            topo_params["num_nodes"] = actual_num_nodes
        topo_params["node_distance"] = 30
        if app_name == "pingpong":
            pinger_idx = 1 if num_nodes > 1 else 0
            ponger_idx = num_nodes - 1
        
    elif topology_name == "random":
        side_length = num_nodes * 7
        topo_params["area_box"] = (-side_length, side_length, -side_length, side_length)
        if app_name == "pingpong":
            pinger_idx = 1 if num_nodes > 1 else 0
            ponger_idx = num_nodes - 1

    elif topology_name == "star":
        topo_params["radius"] = 100
        if app_name == "pingpong":
            pinger_idx = 1 if num_nodes > 1 else 0
            ponger_idx = num_nodes - 1
        
    elif topology_name == "cluster-tree":
        if num_nodes == 5:
            topo_params["num_clusters"] = 2
            topo_params["nodes_per_cluster"] = 2
        else:
            topo_params["num_clusters"] = 3
            topo_params["nodes_per_cluster"] = num_nodes // 3
        topo_params["cluster_radius"] = 100
        topo_params["node_radius"] = 30
        if app_name == "pingpong":
            pinger_idx = 1 # First cluster head
            ponger_idx = num_nodes - 1 # Last node in last cluster

    else: # Default for "ring"
        topo_params["radius"] = 150
        if app_name == "pingpong":
            pinger_idx = num_nodes // 4
            ponger_idx = (3 * num_nodes) // 4
            if pinger_idx == 0: pinger_idx = 1 # Avoid sink
            if ponger_idx == 0: ponger_idx = num_nodes - 1
    
    # --- Generate positions using the factory ---
    node_positions = factory.create_topology(topology_name, **topo_params)
    
    # Final check on node count
    actual_num_nodes = len(node_positions)
    if num_nodes != actual_num_nodes:
        print(f"Note: Topology generator adjusted node count to {actual_num_nodes}")
        num_nodes = actual_num_nodes
        
    # Final check on pinger/ponger indices (if they were set)
    if pinger_idx is not None and pinger_idx >= num_nodes: pinger_idx = num_nodes - 1
    if ponger_idx is not None and ponger_idx >= num_nodes: ponger_idx = num_nodes - 1
    if pinger_idx is not None and pinger_idx == ponger_idx:
        pinger_idx = 0 if pinger_idx > 0 else 1

    # Create plots directory
    if not os.path.exists(topo_plots_dir):
        os.makedirs(topo_plots_dir, exist_ok=True)
        print(f"Created directory: {topo_plots_dir}")
        
    plot_path = os.path.join(topo_plots_dir, f"{topology_name}_{channel_name}_{num_nodes}nodes_scenario.png")
    
    return node_positions, pinger_idx, ponger_idx, plot_path, num_nodes


if __name__ == "__main__":
    
    # Define placeholder paths
    log_filename = "simulation.log"
    plot_path = "topology.png"
    
    try:
        # 1. Parse Arguments
        args = setup_argparse()
        num_nodes = args.num_nodes

        KERNEL_SEED = 12346
        simulation_time = 1800.0 # 30 minutes
        app_name = args.app

        # 2. Setup Logging and Output Directories
        # NEW: Create structured output paths
        RESULTS_ROOT = os.path.join(PROJECT_ROOT, "results")
        APP_DIR = os.path.join(RESULTS_ROOT, app_name)
        log_dir = os.path.join(APP_DIR, "logs")
        plots_dir = os.path.join(APP_DIR, "plots") # Base plots dir
        
        log_filename = os.path.join(log_dir, f"log_{args.topology}_{args.channel}_{num_nodes}nodes.txt")
        
        original_stdout.write(f"--- Simulation starting... --- \n")
        original_stdout.write(f"App: {app_name}, Topology: {args.topology}, Channel: {args.channel}, Nodes: {num_nodes}\n")
        original_stdout.write(f"Redirecting all stdout to: {log_filename}\n")
        original_stdout.write(f"All exceptions will be printed to this console.\n")
        
        setup_logging(log_filename)

        print(f"\n--- Selected Configuration (from log) ---")
        print(f"Application: {app_name}")
        print(f"Topology: {args.topology}")
        print(f"Channel: {args.channel}")
        print(f"Num Nodes: {num_nodes}")
        print(f"Seed: {KERNEL_SEED}")
        print(f"DSpace Grid Step (Density): {args.dspace_step}m")
        if app_name == "random_traffic":
            print(f"App Param (mean_interarrival): {args.mean_interarrival}s")

        
        # 3. Create a dedicated RNG for topology generation
        topo_rng_manager = RandomManager(root_seed=KERNEL_SEED)
        topo_rng = RandomGenerator(topo_rng_manager, "TOPOLOGY_GENERATION_STREAM")
        np_rng_seed = topo_rng.uniform(0, 2**32 - 1)
        np_rng = np.random.default_rng(int(np_rng_seed))


        # 4. Get Topology Assets (Positions, Pinger/Ponger IDs)
        # Pass app_name to control pinger/ponger generation
        node_positions, pinger_idx, ponger_idx, plot_path, num_nodes = create_topology_assets(
            app_name, args.topology, num_nodes, args.channel, plots_dir, np_rng
        )
        
        # 5. Calculate DSpace NPT
        print("\n--- Calculating DSpace NPT from Topology and Step ---")
        padding_meters = 10
        dspace_npt = calculate_bounds_and_params(
            node_positions, padding=padding_meters, dspace_step=args.dspace_step
        )

        # 6. Get Channel Parameters & Set DSpace
        bootstrap_params = get_channel_params(args.channel)
        bootstrap_params['dspace_npt'] = dspace_npt
        bootstrap_params['dspace_step'] = args.dspace_step
        bootstrap_params['seed'] = KERNEL_SEED 
        
        # 7. Bootstrap the Kernel
        print("\n--- Bootstrapping Kernel with Dynamic DSpace ---")
        kernel = Kernel(root_seed=KERNEL_SEED)
        kernel.bootstrap(**bootstrap_params)
        
        
        # 8. Generate Topology + Shadowing Plot
        print(f"\n--- Generating topology plot with shadowing map ---")
        plot_title = (
            f"Scenario: {args.topology.capitalize()} Topology, "
            f"{args.channel.capitalize()} Channel ({num_nodes} Nodes)\n"
            f"Application: {app_name.capitalize()}"
        )
        
        # Build the node_info dict required by the plotting function
        node_info_for_plot = {}
        links_to_plot = []
        
        for i, pos in enumerate(node_positions):
            node_id = f"Node-{i+1}"
            role = "default"
            if i == 0:
                role = "sink"
            
            # Role override based on app
            if app_name == "pingpong":
                if i == pinger_idx:
                    role = "pinger"
                if i == ponger_idx:
                    role = "ponger"
            
            node_info_for_plot[node_id] = {
                "position": pos,
                "role": role,
                "addr": (i + 1).to_bytes(2, "big")
            }

        # Define links (only for pingpong)
        if app_name == "pingpong":
            pinger_id_str = f"Node-{pinger_idx+1}"
            ponger_id_str = f"Node-{ponger_idx+1}"
            links_to_plot = [(pinger_id_str, ponger_id_str)] 
        
        plot_scenario(
            kernel=kernel,
            node_info=node_info_for_plot,
            title=plot_title,
            save_path=plot_path,
            links_to_annotate=links_to_plot,
            figsize=(13, 10)
        )
        
        # 9. Run the Simulation
        app_params_dict = {
            "mean_interarrival_time": args.mean_interarrival
        }

        main(
            app_name=app_name,
            app_params=app_params_dict,
            num_nodes=num_nodes,
            simulation_time=simulation_time,
            root_seed=KERNEL_SEED,
            bootstrap_params=bootstrap_params,
            bootstrapped_kernel=kernel,
            node_positions=node_positions,
            pinger_idx=pinger_idx,
            ponger_idx=ponger_idx,
        )
        
        original_stdout.write(f"--- Simulation finished successfully. ---\n")
        original_stdout.write(f"--- Log saved to {log_filename} ---\n")
        original_stdout.write(f"--- Plot saved to {plot_path} ---\n")

    except Exception as e:
        original_stdout.write("\n\n" + "="*60 + "\n")
        original_stdout.write("--- SIMULATION CRASHED WITH AN EXCEPTION ---\n")
        original_stdout.write("="*60 + "\n")
        traceback.print_exc(file=original_stderr)
        original_stdout.write("="*60 + "\n")
        original_stdout.write(f"--- STDOUT log file is incomplete: {log_filename} ---\n")
        
    finally:
        cleanup_logging()