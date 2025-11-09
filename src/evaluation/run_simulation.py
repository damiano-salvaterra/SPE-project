# src/evaluation/run_simulation.py
import sys
import os
import argparse
import numpy as np
import traceback
from typing import List, Dict, Any, Tuple

# --- Python Path Setup ---
# This ensures we can import the simulator modules from the 'src' directory
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC_ROOT = os.path.join(PROJECT_ROOT, "src")
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

# --- Simulator Imports ---
from simulator.engine.Kernel import Kernel
from simulator.engine.random import RandomManager, RandomGenerator
from simulator.engine.common.Monitor import Monitor
from simulator.environment.topology_factory import TopologyFactory
from simulator.environment.geometry import CartesianCoordinate
from simulator.entities.applications.PingPongApplication import PingPongApp
from simulator.entities.applications.PoissonTrafficApplication import (
    PoissonTrafficApplication,
)
from simulator.entities.applications.common.app_monitor import ApplicationMonitor
from simulator.entities.protocols.net.common.tarp_monitor import TARPMonitor
from evaluation.utils.plotting import plot_scenario
from evaluation.evaluation_monitors.E2ELatencyMonitor import E2ELatencyMonitor
from evaluation.evaluation_monitors.PDRMonitor import PDRMonitor


# ======================================================================================
# --- Plotting Configuration ---
# ======================================================================================
# Set to True to generate and save the scenario plot at the end of the run.
# Set to False to skip plotting (e.g., for faster batch runs).
ENABLE_PLOTTING = False

# ======================================================================================
# Helper Functions
# ======================================================================================


def get_channel_params(channel_name: str) -> dict:
    """returns a dict of channel parameters from presets"""
    base_params = {"freq": 2.4e9, "filter_bandwidth": 2e6, "d0": 1.0}

    # Stable: Low path loss, low shadowing, high coherence distance
    stable = base_params.copy()
    stable.update(
        {"coh_d": 50, "shadow_dev": 2.0, "pl_exponent": 2.0, "fading_shape": 3.0}
    )

    # Lossy: Medium path loss, medium shadowing, medium coherence distance
    lossy = base_params.copy()
    lossy.update(
        {"coh_d": 20, "shadow_dev": 5.0, "pl_exponent": 3.8, "fading_shape": 1.5}
    )

    # Lossy_low_pl: like lossy but low pl
    # Lossy: Medium path loss, medium shadowing, medium coherence distance
    lossy_low_pl = base_params.copy()
    lossy_low_pl.update(
        {"coh_d": 20, "shadow_dev": 5.0, "pl_exponent": 2.0, "fading_shape": 1.5}
    )

    # Unstable: High path loss, high shadowing, low coherence distance
    unstable = base_params.copy()
    unstable.update(
        {"coh_d": 10, "shadow_dev": 6.0, "pl_exponent": 4.0, "fading_shape": 0.75}
    )

    # High_pl: like stable channel but higher path loss
    high_pl = base_params.copy()
    high_pl.update(
        {"coh_d": 50, "shadow_dev": 2.0, "pl_exponent": 3.5, "fading_shape": 3.0}
    )

    # No shadowing, minimal fading, minimal path loss, very stable
    ideal = base_params.copy()
    ideal.update(
        {"coh_d": 1000.0, "shadow_dev": 0.0, "pl_exponent": 2.0, "fading_shape": 50.0}
    )

    params_map = {
        "stable": stable, 
        "lossy": lossy, 
        "unstable": unstable, 
        "high_pl" : high_pl, 
        "lossy_low_pl" : lossy_low_pl,
        "ideal": ideal
    }
    return params_map.get(channel_name, ideal)


def calculate_bounds_and_params(node_positions, padding=50, dspace_step=1.0) -> int:
    """Compute the DSpace 'npt' parameter required to contain the topology."""
    if not node_positions:
        return 200  # Fallback
    min_x = min(p.x for p in node_positions)
    max_x = max(p.x for p in node_positions)
    min_y = min(p.y for p in node_positions)
    max_y = max(p.y for p in node_positions)
    max_abs_coord = max(
        abs(min_x - padding),
        abs(max_x + padding),
        abs(min_y - padding),
        abs(max_y + padding),
    )
    half_n = int(np.ceil(max_abs_coord / dspace_step)) + 2
    dspace_npt = half_n * 2

    print(
        f"Topology bounds: X=[{min_x:.1f}, {max_x:.1f}], Y=[{min_y:.1f}, {max_y:.1f}]"
    )
    print(
        f"DSpace params: step={dspace_step}, npt={dspace_npt} (Grid span approx. [{-half_n*dspace_step:.1f}, {half_n*dspace_step-dspace_step:.1f}])"
    )
    return dspace_npt


# ======================================================================================
# Simulation Setup Functions
# ======================================================================================


def setup_arguments() -> argparse.Namespace:
    """Configures and parses command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Run a single network simulation replicate."
    )
    parser.add_argument(
        "--app",
        choices=["pingpong", "poisson_traffic"],
        default="pingpong",
        help="Application to run",
    )
    parser.add_argument(
        "--topology",
        type=str,
        default="linear",
        help="Topology name (e.g., linear, ring, grid, random)",
    )
    parser.add_argument(
        "--channel",
        choices=["stable", "lossy", "lossy_low_pl", "unstable", "high_pl", "ideal"],
        default="lossy",
        help="Channel model",
    )
    parser.add_argument(
        "--tx_power", type=int, default=0, help="Nodes' transmission power in dBm"
    )
    parser.add_argument("--num_nodes", type=int, default=10, help="Number of nodes")
    parser.add_argument(
        "--sim_time", type=float, default=300.0, help="Simulation time in seconds"
    )
    parser.add_argument(
        "--seed", type=int, default=123, help="Root seed for this replication"
    )
    
    # --- Topology Parameters ---
    #
    parser.add_argument(
        "--depth",
        type=int,
        default=2,
        help="Depth of the cluster-tree topology (default: 2)",
    )
    parser.add_argument(
        "--num_clusters",
        type=int,
        default=3,
        help="Number of L1 clusters for cluster-tree (default: 3)",
    )
    parser.add_argument(
        "--nodes_per_cluster",
        type=int,
        default=5,
        help="Nodes per cluster (branching factor) for L2+ (default: 5)",
    )
    parser.add_argument(
        "--cluster_radius",
        type=float,
        default=100.0,
        help="Radius for L1 cluster head placement (default: 100.0)",
    )
    parser.add_argument(
        "--node_radius",
        type=float,
        default=20.0,
        help="Radius for L2+ node placement (default: 20.0)",
    )
    # --- End Topology Parameters ---
    
    parser.add_argument(
        "--app_delay", type=float, default=60.0, help="Delay before applications start"
    )
    parser.add_argument(
        "--mean_interarrival",
        type=float,
        default=60.0,
        help="Mean inter-arrival time for PoissonTrafficApp",
    )
    parser.add_argument(
        "--dspace_step",
        type=float,
        default=1.0,
        help="Resolution of the DSpace grid (meters)",
    )
    parser.add_argument(
        "--out_dir",
        type=str,
        default="results/run",
        help="Base output directory for the batch",
    )
    return parser.parse_args()


def setup_environment(args: argparse.Namespace) -> str:
    """Creates the unique output directory for this specific run."""
    
    # --- MODIFIED: Use num_nodes for non-cluster topologies only ---
    if args.topology == "cluster-tree":
        # Name the folder based on the cluster parameters
        # Note: This doesn't calculate the exact node count, but it's descriptive
        topo_folder_name = f"{args.topology}_d{args.depth}_c{args.num_clusters}_n{args.nodes_per_cluster}"
    else:
        # Original behavior for other topologies
        topo_folder_name = f"{args.topology}_{args.num_nodes}nodes"
    # --- END MODIFICATION ---

    # Create the final, seed-specific directory
    # NEW STRUCTURE: <out_dir>/<app>/<topo_nodes>/<channel>/<seed>/
    run_output_dir = os.path.join(
        args.out_dir, args.app, topo_folder_name, args.channel, str(args.seed)
    )
    os.makedirs(run_output_dir, exist_ok=True)

    print(f"--- Starting Run (Seed: {args.seed}) ---")
    print(f"--- Output Directory: {run_output_dir} ---")
    return run_output_dir


def create_topology(args: argparse.Namespace) -> Tuple[List[CartesianCoordinate], int]:
    """Generates the node positions using a dedicated RNG stream."""
    # Use a dedicated RNG stream for topology generation for reproducibility
    topo_rng_manager = RandomManager(root_seed=args.seed)
    topo_rng = RandomGenerator(topo_rng_manager, "TOPOLOGY_STREAM")
    np_rng_seed = topo_rng.uniform(0, 2**32 - 1)
    np_rng = np.random.default_rng(int(np_rng_seed))

    factory = TopologyFactory()
    
    # --- MODIFIED: Pass all topology params from args to the factory ---
    #
    topo_params = {
        "rng": np_rng,
        "num_nodes": args.num_nodes, # Used by linear, grid, random
        "depth": args.depth, # Used by cluster-tree
        "num_clusters": args.num_clusters, # Used by cluster-tree
        "nodes_per_cluster": args.nodes_per_cluster, # Used by cluster-tree
        "cluster_radius": args.cluster_radius, # Used by cluster-tree
        "node_radius": args.node_radius, # Used by cluster-tree
    }
    # --- END MODIFICATION ---
    
    node_positions = factory.create_topology(args.topology, **topo_params)
    actual_num_nodes = len(node_positions)
    
    # --- NEW: Update num_nodes arg if it was auto-calculated ---
    # This ensures DSpace calculation uses the *actual* node count
    if args.topology == "cluster-tree":
        print(f"Cluster-tree topology generated {actual_num_nodes} nodes.")
        args.num_nodes = actual_num_nodes
    # --- END NEW ---
    
    return node_positions, actual_num_nodes


def bootstrap_kernel(
    args: argparse.Namespace, node_positions: List[CartesianCoordinate]
) -> Kernel:
    """Initializes and bootstraps the simulation kernel."""
    kernel = Kernel(root_seed=args.seed, antithetic=False)
    dspace_npt = calculate_bounds_and_params(
        node_positions, dspace_step=args.dspace_step
    )
    bootstrap_params = get_channel_params(args.channel)
    bootstrap_params.update(
        {"seed": args.seed, "dspace_npt": dspace_npt, "dspace_step": args.dspace_step}
    )
    kernel.bootstrap(**bootstrap_params)
    return kernel


def create_nodes_and_app(
    args: argparse.Namespace,
    kernel: Kernel,
    node_positions: List[CartesianCoordinate],
    actual_num_nodes: int,
) -> Dict[str, Dict[str, Any]]:
    """Creates all nodes, instantiates their applications, and sets roles."""
    node_addrs_by_index = {
        i: (i + 1).to_bytes(2, "big") for i in range(actual_num_nodes)
    }
    all_nodes_map = {f"Node-{i+1}": addr for i, addr in node_addrs_by_index.items()}

    pinger_idx, ponger_idx = None, None
    node_info_for_plot = {}

    for i in range(actual_num_nodes):
        node_id = f"Node-{i+1}"
        addr = node_addrs_by_index[i]
        is_sink = i == 0
        app_instance = None
        role = "sink" if is_sink else "default"

        if args.app == "pingpong":
            if pinger_idx is None:
                pinger_idx = 1 if actual_num_nodes > 1 else 0
            if ponger_idx is None:
                ponger_idx = actual_num_nodes - 1
            if pinger_idx == 0:
                pinger_idx = 1  # Pinger cannot be sink

            is_pinger = i == pinger_idx
            peer_addr = node_addrs_by_index.get(ponger_idx) if is_pinger else None
            app_instance = PingPongApp(
                host=None,
                is_pinger=is_pinger,
                peer_addr=peer_addr,
                start_delay=args.app_delay,
            )
            if is_pinger:
                role = "pinger"
            if i == ponger_idx:
                role = "ponger"
        else:  # poisson_traffic
            app_instance = PoissonTrafficApplication(
                host=None,
                all_nodes=all_nodes_map,
                mean_interarrival_time=args.mean_interarrival,
                start_delay=args.app_delay,
            )

        node = kernel.add_node(node_id, node_positions[i], app_instance, addr, is_sink)
        # Set the transmission power from args
        node.phy.transmission_power_dBm = args.tx_power
        app_instance.host = node
        node_info_for_plot[node_id] = {
            "position": node_positions[i],
            "role": role,
            "addr": addr,
        }
    return node_info_for_plot


def attach_monitors(kernel: Kernel) -> List[Monitor]:
    """Creates and attaches simulation monitors to all nodes."""
 
    app_mon = ApplicationMonitor(monitor_name="app", verbose=True)
    lat_monitor = E2ELatencyMonitor(monitor_name="e2eLat", verbose=True)
    pdr_monitor = PDRMonitor(monitor_name="PDR", verbose=True)
    tarp_mon = TARPMonitor(monitor_name="tarp", verbose=True)
    
    monitors = [lat_monitor, pdr_monitor, app_mon, tarp_mon] 

    for node in kernel.nodes.values():
        node.app.attach_monitor(app_mon)
        node.app.attach_monitor(lat_monitor)
        node.app.attach_monitor(pdr_monitor)
        node.net.attach_monitor(tarp_mon)

    return monitors


def run_simulation(kernel: Kernel, args: argparse.Namespace):
    """Starts applications and runs the simulation."""
    print("\n--- Starting applications ---")
    for node in kernel.nodes.values():
        node.app.start()

    print(f"\n--- Running simulation for {args.sim_time}s (Seed: {args.seed}) ---")
    kernel.run(until=args.sim_time)
    print(f"--- Simulation finished at {kernel.context.scheduler.now():.6f}s ---")


def save_results(
    monitors: List[Monitor],
    run_output_dir: str,
    base_filename: str,
):
    base_path = os.path.join(run_output_dir, base_filename)
    for monitor in monitors:
        monitor.save_to_csv(base_path)  # Creates .../run_<monitor_name>.csv
    print(f"Data saved to {run_output_dir}/{base_filename}_*.csv")


def plot_results(
    args: argparse.Namespace,
    kernel: Kernel,
    node_info: Dict[str, Dict[str, Any]],
    run_output_dir: str,
    base_filename: str,
    actual_num_nodes: int,
):
    """Generates and saves the scenario plot."""
    # plot_path will be, e.g., ".../seed/run_scenario.png"
    plot_path = os.path.join(run_output_dir, f"{base_filename}_scenario.png")
    plot_title = (
        f"Scenario:{args.topology.capitalize()} Topology, {args.channel.capitalize()} Channel ({actual_num_nodes} Nodes)\n"
        f"Seed: {args.seed}, App: {args.app.capitalize()}"
    )
    plot_scenario(kernel, node_info, plot_title, plot_path, figsize=(12, 10))
    print(f"Plot saved to {plot_path}")


# ======================================================================================
# MAIN ORCHESTRATOR
# ======================================================================================


def main():
    """Main function to orchestrate the simulation setup, run, and saving."""

    # Setup
    args = setup_arguments()
    # The dir for this specific run, e.g., .../app/topo/chan/seed/
    run_output_dir = setup_environment(args)
    # A static filename prefix for files *within* that directory
    base_filename = "log"

    node_positions, actual_num_nodes = create_topology(args)

    kernel = bootstrap_kernel(args, node_positions)

    # Nodes and Applications
    node_info_for_plot = create_nodes_and_app(
        args, kernel, node_positions, actual_num_nodes
    )

    monitors = attach_monitors(kernel)

    # --- NEW: Redirect stdout if any monitor is verbose ---
    log_file_path = os.path.join(run_output_dir, "monitor_log.txt")
    original_stdout = sys.stdout
    is_verbose = any(m.verbose for m in monitors)
    log_file_handle = None

    if is_verbose:
        # We print this message to the *original* stdout (console)
        # before redirecting.
        print(f"Verbose monitor output will be redirected to: {log_file_path}")
        try:
            log_file_handle = open(log_file_path, 'w')
            # Redirect stdout to the log file
            sys.stdout = log_file_handle
            
            # Now, run the simulation. All monitor prints
            # (and other prints) will go to the file.
            run_simulation(kernel, args)

        finally:
            # *Always* restore stdout, even if the simulation crashes
            sys.stdout = original_stdout
            if log_file_handle:
                log_file_handle.close()
            # Print to console to confirm restoration
            print("Verbose logging finished. Restored stdout.")
    else:
        # If no monitor is verbose, run the simulation normally.
        # All prints will go to the console.
        run_simulation(kernel, args)
    # --- END OF NEW LOGGING BLOCK ---

    # This 'save_results' print will go to the console (stdout restored)
    save_results(monitors, run_output_dir, base_filename)

    # Plot
    if ENABLE_PLOTTING:
        plot_results(
            args,
            kernel,
            node_info_for_plot,
            run_output_dir,
            base_filename,
            actual_num_nodes,
        )
    else:
        print("Plotting skipped (ENABLE_PLOTTING is False).")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # This print will go to the console (stdout should be restored)
        print(f"\n--- SIMULATION CRASHED ---")
        traceback.print_exc()
        sys.exit(1)  # Exit with an error code