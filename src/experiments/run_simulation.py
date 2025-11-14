import sys
import os
import argparse
import numpy as np
import traceback
from typing import List, Dict, Any, Tuple
from datetime import datetime

# --- Python Path Setup ---
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC_ROOT = os.path.join(PROJECT_ROOT, "src")
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

from simulator.engine.Kernel import Kernel
from simulator.engine.common.Monitor import Monitor
from simulator.environment.geometry import CartesianCoordinate, calculate_bounds_and_params
from simulator.environment.propagation.narrowband import get_channel_params
from simulator.entities.applications.PoissonTrafficApplication import (
    PoissonTrafficApplication,
)
from simulator.entities.applications.common.app_monitor import ApplicationMonitor
from simulator.entities.protocols.net.common.tarp_monitor import TARPMonitor
from experiments.utils.setup_args import setup_arguments
from src.experiments.utils.helpers import (
    setup_working_environment,
    create_topology,
    save_parameters_log,
    save_results
)
from experiments.experiment_monitors.E2ELatencyMonitor import E2ELatencyMonitor
from experiments.experiment_monitors.PDRMonitor import PDRMonitor
from experiments.experiment_monitors.InterarrivalTimeMonitor import InterarrivalTimeMonitor


def bootstrap_kernel(
    sim_seed: int,
    antithetic: bool,
    dspace_step: float,
    channel: str,
    node_positions: List[CartesianCoordinate],
) -> Tuple[Kernel, Dict[str, Any], int]:
    """Initializes and bootstraps the simulation kernel."""

    kernel = Kernel(root_seed=sim_seed, antithetic=antithetic)
    dspace_npt = calculate_bounds_and_params(
        node_positions, dspace_step=dspace_step
    )
    bootstrap_params = get_channel_params(channel)
    
    bootstrap_params.update(
        {"seed": sim_seed, "dspace_npt": dspace_npt, "dspace_step": dspace_step}
    )
    
    kernel.bootstrap(**bootstrap_params)
    return kernel, bootstrap_params, dspace_npt


def create_nodes_and_app(
    mean_interarrival: float,
    app_delay: float,
    tx_power: float,
    kernel: Kernel,
    node_positions: List[CartesianCoordinate],
    actual_num_nodes: int,
) -> Dict[str, Dict[str, Any]]:
    """Creates all nodes, instantiates their applications, and sets roles."""

    node_addrs_by_index = {
        i: (i + 1).to_bytes(2, "big") for i in range(actual_num_nodes)
    }
    all_nodes_map = {f"Node-{i+1}": addr for i, addr in node_addrs_by_index.items()}

    node_info = {}

    for i in range(actual_num_nodes):
        node_id = f"Node-{i+1}"
        addr = node_addrs_by_index[i]
        is_sink = i == 0
        role = "sink" if is_sink else "default"

        app_instance = PoissonTrafficApplication(
            host=None,
            all_nodes=all_nodes_map,
            mean_interarrival_time=mean_interarrival,
            start_delay=app_delay,
        )

        node = kernel.add_node(node_id, node_positions[i], app_instance, addr, is_sink)
        node.phy.transmission_power_dBm = tx_power
        app_instance.host = node
        node_info[node_id] = {
            "position": node_positions[i],
            "role": role,
            "addr": addr,
        }
    return node_info


def attach_monitors(kernel: Kernel, verbose: bool = False) -> List[Monitor]:
    """Creates and attaches simulation monitors to all nodes."""

    app_mon = ApplicationMonitor(monitor_name="app", verbose=verbose)
    lat_monitor = E2ELatencyMonitor(monitor_name="e2eLat", verbose=verbose)
    pdr_monitor = PDRMonitor(monitor_name="PDR", verbose=verbose)
    tarp_mon = TARPMonitor(monitor_name="tarp", verbose=verbose)
    it_mon = InterarrivalTimeMonitor(monitor_name="IT", verbose=verbose)
    
    monitors = [lat_monitor, pdr_monitor, app_mon, tarp_mon, it_mon] 

    for node in kernel.nodes.values():
        node.app.attach_monitor(app_mon)
        node.app.attach_monitor(lat_monitor)
        node.app.attach_monitor(pdr_monitor)
        node.app.attach_monitor(it_mon)
        node.net.attach_monitor(tarp_mon)

    return monitors


def run_simulation(kernel: Kernel, sim_time: float, sim_seed: int):
    """Starts applications and runs the simulation."""

    print("\n--- Starting applications ---")
    for node in kernel.nodes.values():
        node.app.start()

    print(f"\n--- Running simulation for {sim_time}s (SimSeed: {sim_seed}) ---")
    kernel.run(until=sim_time)
    print(f"--- Simulation finished at {kernel.context.scheduler.now():.6f}s ---")


# ======================================================================================
# Core execution function
# ======================================================================================

def run_single_simulation(
    topology: str,
    channel: str,
    num_nodes: int,
    tx_power: float,
    sim_time: float,
    sim_seed: int,
    antithetic: bool,
    topo_seed: int,
    app_delay: float,
    mean_interarrival: float,
    dspace_step: float,
    out_dir: str,
    verbose: bool = False,

):
    """
    Orchestrates the setup, run, and saving for a single simulation
    """

    run_output_dir = setup_working_environment(
        out_dir, topology, num_nodes, channel, sim_seed,
        "antithetic" if antithetic else None
    )

    node_positions = create_topology(topology, num_nodes, topo_seed)
    actual_num_nodes = len(node_positions)

    kernel, bootstrap_params, dspace_npt = bootstrap_kernel(
        sim_seed, antithetic, dspace_step, channel, node_positions
    )

    node_info = create_nodes_and_app(
        mean_interarrival,
        app_delay,
        tx_power,
        kernel,
        node_positions,
        actual_num_nodes,
    )

    monitors = attach_monitors(kernel, verbose)

    args_dict = {
        "topology": topology, "channel": channel, "num_nodes": num_nodes,
        "tx_power": tx_power, "sim_time": sim_time, "sim_seed": sim_seed, "antithetic": antithetic,
        "topo_seed": topo_seed, "app_delay": app_delay,
        "mean_interarrival": mean_interarrival, "dspace_step": dspace_step,
        "out_dir": out_dir
    }
    save_parameters_log(
        args_dict,
        bootstrap_params,
        dspace_npt,
        actual_num_nodes,
        run_output_dir,
    )

    log_file_path = os.path.join(run_output_dir, "monitors_log.txt")
    original_stdout = sys.stdout
    is_verbose = any(m.verbose for m in monitors)
    log_file_handle = None

    if is_verbose:
        print(f"Verbose monitors output will be redirected to: {log_file_path}")
        try:
            log_file_handle = open(log_file_path, 'w')
            sys.stdout = log_file_handle
            
            run_simulation(kernel, sim_time, sim_seed)

        finally:
            sys.stdout = original_stdout
            if log_file_handle:
                log_file_handle.close()
            print(f"Verbose logging finished for sim_seed={sim_seed}. Restored stdout.")
    else:
        run_simulation(kernel, sim_time, sim_seed)

    save_results(monitors, run_output_dir)



# ======================================================================================
# main (for standalone execution)
# ======================================================================================

def main_standalone():
    """
   used only if __name__ == "__main__"
    """
    try:
        args = setup_arguments()

        run_single_simulation(
            topology=args.topology,
            channel=args.channel,
            num_nodes=args.num_nodes,
            tx_power=args.tx_power,
            sim_time=args.sim_time,
            sim_seed=args.sim_seed,  
            topo_seed=args.topo_seed,
            antithetic=args.antithetic,
            app_delay=args.app_delay,
            mean_interarrival=args.mean_interarrival,
            dspace_step=args.dspace_step,
            out_dir=args.out_dir,
            verbose=args.verbose
        )
    
    except Exception as e:
        print("\n--- SIMULATION CRASHED (STANDALONE) ---")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main_standalone()