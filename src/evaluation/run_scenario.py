# src/evaluation/run_scenario.py
import sys
import os
import argparse
import numpy as np
import traceback
from typing import List, Dict, Any, Optional, Tuple

# --- Python Path Setup ---
# Ensures the script can find the 'simulator' and 'evaluation' modules
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC_ROOT = os.path.join(PROJECT_ROOT, "src")
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

from simulator.engine.Kernel import Kernel
from simulator.entities.applications.PingPongApplication import PingPongApp
from simulator.entities.applications.PoissonTrafficApplication import PoissonTrafficApplication
from simulator.entities.applications.Application import Application
from simulator.environment.geometry import CartesianCoordinate
from simulator.engine.random import RandomManager, RandomGenerator
from simulator.engine.common.Monitor import Monitor
from simulator.environment.topology_factory import TopologyFactory

from simulator.entities.applications.common.app_monitor import ApplicationMonitor
from simulator.entities.protocols.net.common.tarp_monitor import TARPMonitor
from evaluation.utils.plotting import plot_scenario
from evaluation.utils.simulation_logger import SimulationLogger
from evaluation.utils.simulation_result import SimulationResult

# ======================================================================================
# CONSTANTS
# ======================================================================================
TOPOLOGY_RNG_STREAM = "TOPOLOGY_GENERATION_STREAM"
DEFAULT_PADDING_METERS = 10.0
PLOT_FIGSIZE = (13, 10)

# ======================================================================================
# HELPER FUNCTIONS (Unchanged, as this logic is necessary)
# ======================================================================================

def calculate_bounds_and_params(node_positions, padding=DEFAULT_PADDING_METERS, dspace_step=1.0, logger=None):
    """
    Calculates the bounding box of the topology and determines the DSpace
    parameters (npt) needed to contain it with 0-centering.
    """
    if not node_positions:
        return 200 # Default fallback

    # Find extremes
    min_x = min(p.x for p in node_positions)
    max_x = max(p.x for p in node_positions)
    min_y = min(p.y for p in node_positions)
    max_y = max(p.y for p in node_positions)

    # Apply padding
    min_x_pad = min_x - padding
    max_x_pad = max_x + padding
    min_y_pad = min_y - padding
    max_y_pad = max_y + padding

    # Largest absolute coordinate required from the center (0,0)
    max_abs_coord = max(abs(min_x_pad), abs(max_x_pad), abs(min_y_pad), abs(max_y_pad))

    # Compute npt needed for this half-width
    half_n = int(np.ceil(max_abs_coord / dspace_step)) + 2
    dspace_npt = half_n * 2

    def log(msg):
        if logger:
            logger.log(msg)
        else:
            print(msg)
    
    log(f"Topology bounds (unpadded): X=[{min_x:.1f}, {max_x:.1f}], Y=[{min_y:.1f}, {max_y:.1f}]")
    log(f"Max absolute coordinate (padded): {max_abs_coord:.1f}")
    log(f"Calculated DSpace params: step={dspace_step}, npt={dspace_npt} (Grid will span approx. [{-half_n*dspace_step:.1f}, {half_n*dspace_step-dspace_step:.1f}])")

    return dspace_npt

def get_channel_params(channel_name: str) -> dict:
    """Returns a dictionary of channel parameters given a key"""
    
    # Base parameters (stable)
    stable_params = {"freq": 2.4e9, "filter_bandwidth": 2e6, "coh_d": 50, "shadow_dev": 2.0, "pl_exponent": 2, "d0": 1.0, "fading_shape": 3.0,}
    medium_params = {"freq": 2.4e9, "filter_bandwidth": 2e6, "coh_d": 30, "shadow_dev": 4.0, "pl_exponent": 3.5, "d0": 1.0, "fading_shape": 1.5}
    medium_lossy_params = {"freq": 2.4e9, "filter_bandwidth": 2e6, "coh_d": 20, "shadow_dev": 5.0, "pl_exponent": 3.8, "d0": 1.0, "fading_shape": 1.5}
    harsh_unstable_params = {"freq": 2.4e9, "filter_bandwidth": 2e6, "coh_d": 15, "shadow_dev": 5.0, "pl_exponent": 4.0, "d0": 1.0, "fading_shape": 1.0}
    harsh_params = {"freq": 2.4e9, "filter_bandwidth": 2e6, "coh_d": 10, "shadow_dev": 6.0, "pl_exponent": 4.0, "d0": 1.0, "fading_shape": 0.75}

    params_map = {
        "stable": stable_params,
        "medium": medium_params,
        "medium_lossy": medium_lossy_params,
        "harsh_unstable": harsh_unstable_params,
        "harsh": harsh_params,
    }
    
    return params_map.get(channel_name, harsh_params).copy()

def create_topology_assets(
    app_name: str,
    topology_name: str, 
    num_nodes: int, 
    topo_rng: np.random.Generator,
    logger=None
) -> Tuple[List[CartesianCoordinate], Optional[int], Optional[int], int]:
    """
    Generates node positions and (if applicable) Pinger/Ponger indices.
    
    Returns:
        (node_positions, pinger_idx, ponger_idx, num_nodes)
        Note: num_nodes is returned in case the topology modified the count.
    """
    def log(msg):
        if logger:
            logger.log(msg)
        else:
            print(msg)

    log(f"\n--- Generating '{topology_name}' topology positions... ---")
    
    factory = TopologyFactory()
    
    # Parameters to pass to the strategy for topology creation
    topo_params = {"num_nodes": num_nodes, "rng": topo_rng}
    pinger_idx = None
    ponger_idx = None
    
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
            log(f"Note: Grid topology requested {num_nodes}, creating a {side}x{side} grid with {actual_num_nodes} nodes.")
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
        log(f"Note: Topology generator adjusted node count to {actual_num_nodes}")
        num_nodes = actual_num_nodes
        
    # check on pinger/ponger indices (if they were set)
    if pinger_idx is not None and pinger_idx >= num_nodes: pinger_idx = num_nodes - 1
    if ponger_idx is not None and ponger_idx >= num_nodes: ponger_idx = num_nodes - 1
    if pinger_idx is not None and pinger_idx == ponger_idx:
        pinger_idx = 0 if pinger_idx > 0 else 1
    
    return node_positions, pinger_idx, ponger_idx, num_nodes

# ======================================================================================
# SINGLE SIMULATION FUNCTION (Unchanged, as this logic is necessary)
# ======================================================================================

def run_single_simulation(
    app_name: str,
    app_params: dict,
    num_nodes: int,
    simulation_time: float,
    root_seed: int,
    bootstrap_params: dict,
    bootstrapped_kernel: Kernel,
    node_positions: list,
    pinger_idx: Optional[int],
    ponger_idx: Optional[int],
    logger: SimulationLogger,
    app_start_delay: float = 120.0
) -> Tuple[ApplicationMonitor, TARPMonitor]:
    """
    Main simulation function. This function is called by the __main__ block
    and contains the core simulation setup and execution logic for *one* run.
    
    Returns:
        A tuple of the key monitors for data extraction.
    """
    logger.log("\n--- Simulation Parameters ---")
    logger.log(f"Application: {app_name}")
    logger.log(f"Root seed: {root_seed}")
    logger.log(f"Network configuration: num_nodes={num_nodes}")
    logger.log(f"Simulation time: {simulation_time}s")
    logger.log(f"Application start delay: {app_start_delay}s")

    logger.log("\n--- Initializing Kernel and Scheduler ---")
    kernel = bootstrapped_kernel
    logger.log("Using provided bootstrapped kernel with parameters:")
    params_str = ", ".join(
        [f"{k}={v}" for k, v in bootstrap_params.items()]
    )
    logger.log(f"Kernel configuration: {params_str}")


    logger.log(f"\n--- Creating Network Nodes and setting up {app_name} ---")
    nodes = {} # Stores {node_id: StaticNode}
    
    # --- Step 1: Create all addresses first ---
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
                logger.log(f"{node_id} (Addr: {addr.hex()}) is PINGER, peer is Node-{ponger_idx+1} (Addr: {peer_addr.hex()})")
            elif is_ponger:
                peer_addr = node_addrs_by_index.get(pinger_idx)
                logger.log(f"{node_id} (Addr: {addr.hex()}) is PONGER, peer is Node-{pinger_idx+1} (Addr: {peer_addr.hex()})")

            app = PingPongApp(
                host=None, 
                is_pinger=is_pinger, 
                peer_addr=peer_addr,
                start_delay=app_start_delay 
            )

        elif app_name == "poisson_traffic": # Changed from "random_traffic"
            app = PoissonTrafficApplication(
                host=None,
                all_nodes=all_nodes_map,
                mean_interarrival_time=app_params.get("mean_interarrival_time", 60.0),
                start_delay=app_start_delay
            )
            if i == 0:
                logger.log(f"{node_id} (Addr: {addr.hex()}) is SINK/ROOT.")
        
        else:
            raise ValueError(f"Unknown application name: {app_name}")
        # -------------------------------------

        node = kernel.add_node(
            node_id=node_id,
            position=node_positions[i],
            app=app,
            linkaddr=addr,
            is_sink=is_sink,
        )
        app.host = node
        nodes[node_id] = node

    logger.log("\n--- Attaching Monitors to all nodes ---")
    app_monitor = ApplicationMonitor(verbose=False) # Verbose logging is now handled by logger
    tarp_monitor = TARPMonitor(verbose=False) # Verbose logging is now handled by logger

    for node in nodes.values():
        node.app.attach_monitor(app_monitor)
        node.net.attach_monitor(tarp_monitor)

    # --- Conditional Application Start Logic ---
    logger.log("\n--- Starting Applications ---")
    if app_name == "pingpong":
        # Only start Pinger and Ponger
        pinger_node_id = f"Node-{pinger_idx + 1}"
        ponger_node_id = f"Node-{ponger_idx + 1}"
        if pinger_node_id in nodes:
            nodes[pinger_node_id].app.start()
        if ponger_node_id in nodes:
            nodes[ponger_node_id].app.start()
        logger.log(f"Started PingPongApp on {pinger_node_id} and {ponger_node_id}.")
        
    elif app_name == "poisson_traffic": # Changed from "random_traffic"
        # Start the application on ALL nodes
        for node in nodes.values():
            node.app.start()
        logger.log(f"Started PoissonTrafficApplication on all {len(nodes)} nodes.")
    # -----------------------------------------

    logger.log("\n--- Running Simulation ---")
    kernel.run(until=simulation_time)

    logger.log("\n\n--- Simulation Finished ---")
    logger.log(f"Final simulation time: {kernel.context.scheduler.now():.6f}s")

    scheduler = kernel.context.scheduler
    queue_len = scheduler.get_queue_length()
    logger.log(f"Events remaining in queue: {queue_len}")

    if queue_len > 0:
        logger.log("\n--- First 5 Events in Queue ---")
        for i, (time, event) in enumerate(sorted(scheduler.event_queue)[:5]):
            logger.log(
                f"{i+1}: t={time * scheduler._time_scale:.6f}s, Event={type(event).__name__}, "
                f"Blame={type(event.blame).__name__}, Descriptor: {event.descriptor}, Cancelled: {event._cancelled}"
            )
            
    # Return monitors for data extraction
    return app_monitor, tarp_monitor

# ======================================================================================
# REFACTORED BATCH EXECUTION FUNCTIONS
# ======================================================================================

def setup_argparse() -> argparse.Namespace:
    """Configures and parses command-line arguments."""
    parser = argparse.ArgumentParser(description="Run a network simulation scenario.")
    
    # --- Application Choice ---
    parser.add_argument(
        "--app",
        type=str,
        choices=["pingpong", "poisson_traffic"],
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
        help="Mean inter-arrival time (in seconds) for PoissonTrafficApplication (default: 60.0)",
    )
    parser.add_argument(
        "--sim_time",
        type=float,
        default=1800.0,
        help="Total simulation time in seconds (default: 1800.0)",
    )
    parser.add_argument(
        "--app_delay",
        type=float,
        default=120.0,
        help="App start delay time in seconds before applications start (default: 120.0)",
    )

    # --- Batch Execution Parameters ---
    parser.add_argument(
        "--num_runs",
        type=int,
        default=1,
        help="Number of simulation runs (replications) to execute (default: 1)",
    )
    parser.add_argument(
        "--base_seed",
        type=int,
        default=12345,
        help="The base seed for the simulation runs. Each run 'i' will use base_seed + i. (default: 12345)",
    )

    return parser.parse_args()

def setup_directories(args: argparse.Namespace) -> Tuple[str, str, str]:
    """Creates and returns paths for logs, plots, and data."""
    RESULTS_ROOT = os.path.join(PROJECT_ROOT, "results")
    APP_DIR = os.path.join(RESULTS_ROOT, args.app)
    
    config_name = f"{args.topology}_{args.channel}_{args.num_nodes}nodes"
    
    log_dir = os.path.join(APP_DIR, "logs", config_name)
    plot_dir = os.path.join(APP_DIR, "plots", config_name)
    data_dir = os.path.join(APP_DIR, "data", config_name)
    
    os.makedirs(log_dir, exist_ok=True)
    os.makedirs(plot_dir, exist_ok=True)
    os.makedirs(data_dir, exist_ok=True)
    
    return log_dir, plot_dir, data_dir, config_name

def log_batch_start(args: argparse.Namespace, log_dir: str, plot_dir: str, data_dir: str, config_name: str):
    """Logs the initial batch configuration to the console."""
    original_stdout = sys.stdout
    original_stdout.write(f"--- Starting Simulation Batch --- \n")
    original_stdout.write(f"Configuration: {config_name}\n")
    original_stdout.write(f"App: {args.app}, Topology: {args.topology}, Channel: {args.channel}\n")
    original_stdout.write(f"Requested Nodes: {args.num_nodes}, Simulation Time: {args.sim_time}s\n")
    original_stdout.write(f"Batch Size: {args.num_runs} runs\n")
    original_stdout.write(f"Base Seed: {args.base_seed}\n")
    original_stdout.write(f"Output Logs: {log_dir}\n")
    original_stdout.write(f"Output Plots: {plot_dir}\n")
    original_stdout.write(f"Output Data: {data_dir}\n")
    original_stdout.write(f"-------------------------------------\n\n")

def generate_scenario_plot(
    kernel: Kernel, 
    args: argparse.Namespace, 
    run_plot_file: str, 
    node_positions: List[CartesianCoordinate],
    pinger_idx: Optional[int], 
    ponger_idx: Optional[int], 
    actual_num_nodes: int,
    logger: SimulationLogger
):
    """Generates and saves the topology/shadowing plot for the first run."""
    logger.log(f"\n--- Generating topology plot with shadowing map ---")
    plot_title = (
        f"Scenario: {args.topology.capitalize()} Topology, "
        f"{args.channel.capitalize()} Channel ({actual_num_nodes} Nodes)\n"
        f"Application: {args.app.capitalize()} (Base Seed: {args.base_seed})"
    )
    
    node_info_for_plot = {}
    links_to_plot = []
    
    for n_idx, pos in enumerate(node_positions):
        node_id = f"Node-{n_idx+1}"
        role = "sink" if n_idx == 0 else "default"
        if args.app == "pingpong":
            if n_idx == pinger_idx: role = "pinger"
            if n_idx == ponger_idx: role = "ponger"
        
        node_info_for_plot[node_id] = {
            "position": pos, "role": role, "addr": (n_idx + 1).to_bytes(2, "big")
        }

    if args.app == "pingpong":
        pinger_id_str = f"Node-{pinger_idx+1}"
        ponger_id_str = f"Node-{ponger_idx+1}"
        links_to_plot = [(pinger_id_str, ponger_id_str)] 
    
    plot_scenario(
        kernel=kernel,
        node_info=node_info_for_plot,
        title=plot_title,
        save_path=run_plot_file,
        links_to_annotate=links_to_plot,
        figsize=PLOT_FIGSIZE
    )
    logger.log(f"--- Plot saved to {run_plot_file} ---")

# ======================================================================================
# SCRIPT EXECUTION (__main__)
# ======================================================================================

def main():
    """
    Main execution function.
    """
    # Store original stdout/stderr for crash reporting
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    
    # 1. Parse Arguments
    args = setup_argparse()
    
    # 2. Setup output directories
    log_dir, plot_dir, data_dir, config_name = setup_directories(args)
    
    # 3. Log batch start
    log_batch_start(args, log_dir, plot_dir, data_dir, config_name)

    # --- Batch Execution Loop ---
    all_run_results: List[SimulationResult] = []
    
    for i in range(args.num_runs):
        run_id = i + 1
        run_seed = args.base_seed + i
        
        # Define file paths for this specific run
        run_log_file = os.path.join(log_dir, f"run_{run_id}_seed_{run_seed}.txt")
        run_plot_file = os.path.join(plot_dir, f"run_{run_id}_seed_{run_seed}_scenario.png")
        run_data_file_base = os.path.join(data_dir, f"run_{run_id}_seed_{run_seed}")
        
        logger = None
        
        try:
            # 4. Setup Logging for this run
            logger = SimulationLogger(run_log_file)
            logger.log(f"--- Starting Simulation Run {run_id}/{args.num_runs} (Seed: {run_seed}) ---")

            # 5. Create a dedicated RNG for topology (uses BASE_SEED for consistent topology)
            topo_rng_manager = RandomManager(root_seed=args.base_seed)
            topo_rng = RandomGenerator(topo_rng_manager, TOPOLOGY_RNG_STREAM)
            np_rng_seed = topo_rng.uniform(0, 2**32 - 1)
            np_rng = np.random.default_rng(int(np_rng_seed))

            # 6. Get Topology Assets (Positions, Pinger/Ponger IDs)
            node_positions, pinger_idx, ponger_idx, actual_num_nodes = create_topology_assets(
                args.app, args.topology, args.num_nodes, np_rng, logger
            )
            
            # 7. Calculate DSpace NPT
            logger.log("\n--- Calculating DSpace NPT from Topology and Step ---")
            dspace_npt = calculate_bounds_and_params(
                node_positions, padding=DEFAULT_PADDING_METERS, dspace_step=args.dspace_step, logger=logger
            )

            # 8. Get Channel Parameters & Set DSpace
            bootstrap_params = get_channel_params(args.channel)
            bootstrap_params['dspace_npt'] = dspace_npt
            bootstrap_params['dspace_step'] = args.dspace_step
            bootstrap_params['seed'] = run_seed  # <-- Use the unique seed for this run
            
            # 9. Bootstrap the Kernel
            logger.log("\n--- Bootstrapping Kernel with Dynamic DSpace ---")
            kernel = Kernel(root_seed=run_seed)
            kernel.bootstrap(**bootstrap_params)
            
            # 10. Generate Topology + Shadowing Plot (only for the first run)
            if i == 0:
                generate_scenario_plot(
                    kernel, args, run_plot_file, node_positions, 
                    pinger_idx, ponger_idx, actual_num_nodes, logger
                )
            
            # 11. Run the Simulation
            app_params_dict = {
                "mean_interarrival_time": args.mean_interarrival
            }
            app_mon, tarp_mon = run_single_simulation(
                app_name=args.app,
                app_params=app_params_dict,
                num_nodes=actual_num_nodes,
                simulation_time=args.sim_time,
                root_seed=run_seed,
                bootstrap_params=bootstrap_params,
                bootstrapped_kernel=kernel,
                node_positions=node_positions,
                pinger_idx=pinger_idx,
                ponger_idx=ponger_idx,
                logger=logger,
                app_start_delay=args.app_delay
            )
            
            # 12. Process and Save Results
            logger.log("\n--- Processing and Saving Run Results ---")
            result = SimulationResult(app_monitor=app_mon, tarp_monitor=tarp_mon)
            
            if result.is_valid:
                result.save_to_csv(run_data_file_base)
                all_run_results.append(result)
                logger.log(f"--- Data CSVs saved to {run_data_file_base}_*.csv ---")
            else:
                logger.log("--- No data collected by monitors. ---")
            
            original_stdout.write(f"Run {run_id}/{args.num_runs} (Seed: {run_seed}) FINISHED successfully.\n")

        except Exception as e:
            # Log crash to original console
            original_stdout.write(f"\n\n" + "="*60 + "\n")
            original_stdout.write(f"--- RUN {run_id}/{args.num_runs} (Seed: {run_seed}) CRASHED! ---\n")
            original_stdout.write("="*60 + "\n")
            traceback.print_exc(file=original_stderr)
            original_stdout.write("="*60 + "\n")
            
            # Also log to the specific run's log file if logger is available
            if logger:
                logger.log("\n\n" + "="*60 + "\n")
                logger.log("--- SIMULATION CRASHED WITH AN EXCEPTION ---")
                logger.log("="*60 + "\n")
                logger.log(traceback.format_exc())
                logger.log("="*60 + "\n")
            
        finally:
            if logger:
                logger.close()

    # --- End of Batch ---
    original_stdout.write(f"\n--- Simulation Batch Finished --- \n")
    
    if all_run_results:
        original_stdout.write(f"Successfully completed {len(all_run_results)} runs.\n")
        original_stdout.write("Data saved in subdirectories under:\n")
        original_stdout.write(f"Logs: {log_dir}\n")
        original_stdout.write(f"Plots: {plot_dir}\n")
        original_stdout.write(f"Data: {data_dir}\n")
    else:
        original_stdout.write("Batch finished, but no results were collected.\n")

if __name__ == "__main__":
    main()