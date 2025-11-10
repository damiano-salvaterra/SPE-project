import sys
import os
import argparse
import numpy as np
import traceback
from typing import List, Dict, Any, Tuple
from datetime import datetime

# --- Python Path Setup ---
# This ensures we can import the simulator modules from the 'src' directory
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC_ROOT = os.path.join(PROJECT_ROOT, "src")
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

from simulator.engine.Kernel import Kernel
from simulator.engine.random import RandomManager, RandomGenerator
from simulator.engine.common.Monitor import Monitor
from simulator.environment.topology_factory import TopologyFactory
from simulator.environment.geometry import CartesianCoordinate, calculate_bounds_and_params
from simulator.environment.propagation.narrowband import get_channel_params
from simulator.entities.applications.PingPongApplication import PingPongApp
from simulator.entities.applications.PoissonTrafficApplication import (
    PoissonTrafficApplication,
)
from simulator.entities.applications.common.app_monitor import ApplicationMonitor
from simulator.entities.protocols.net.common.tarp_monitor import TARPMonitor
from evaluation.utils.setup_args import setup_arguments
from evaluation.utils.helpers import *
from evaluation.evaluation_monitors.E2ELatencyMonitor import E2ELatencyMonitor
from evaluation.evaluation_monitors.PDRMonitor import PDRMonitor


def bootstrap_kernel(
    args: argparse.Namespace, node_positions: List[CartesianCoordinate]
) -> Tuple[Kernel, Dict[str, Any], int]:
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
    return kernel, bootstrap_params, dspace_npt


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




# ======================================================================================
# MAIN ORCHESTRATOR
# ======================================================================================


def main(plot_topologies: bool):
    """Main function to orchestrate the simulation setup, run, and saving."""

    # Setup
    args = setup_arguments()
    run_output_dir = setup_working_environment(args) #folder for this run

    node_positions = create_topology(args.topology, args.num_nodes, args.seed)
    num_nodes = args.num_nodes

    kernel, bootstrap_params, dspace_npt = bootstrap_kernel(args, node_positions)

    # create nodes and apps
    node_info_for_plot = create_nodes_and_app(
        args, kernel, node_positions, num_nodes
    )

    monitors = attach_monitors(kernel)

    save_parameters_log(
        args,
        bootstrap_params,
        dspace_npt,
        num_nodes,
        run_output_dir,
    )

    log_file_path = os.path.join(run_output_dir, "monitors_log.txt")
    original_stdout = sys.stdout
    is_verbose = any(m.verbose for m in monitors)
    log_file_handle = None

    if is_verbose:
        print(f"Verbose monitors output will be redirected to: {log_file_path}")
        try:
            #redirect monitors output on the file
            log_file_handle = open(log_file_path, 'w')
            sys.stdout = log_file_handle
            
            #run simulation
            run_simulation(kernel, args)

        finally:
            # restore std output
            sys.stdout = original_stdout
            if log_file_handle:
                log_file_handle.close()
            print("Verbose logging finished. Restored stdout.")
    else:
        #if no monitor is verbose, just run
        run_simulation(kernel, args)

    save_results(monitors, run_output_dir)

    # Plot
    if plot_topologies:
        plot_results(
            args,
            kernel,
            node_info_for_plot,
            run_output_dir,
            num_nodes,
        )
    else:
        print("Plotting skipped (ENABLE_PLOTTING is False).")


if __name__ == "__main__":
    try:
        main(plot_topologies=False)
    except Exception as e:
        print(f"\n--- SIMULATION CRASHED ---")
        traceback.print_exc()
        sys.exit(1)  # exit with error code