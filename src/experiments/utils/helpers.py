import os
import numpy as np
from datetime import datetime
import sys
import json
from typing import Tuple, List, Dict, Any, Optional
from simulator.engine.Kernel import Kernel
from simulator.engine.random.RandomGenerator import RandomGenerator
from simulator.engine.random.RandomManager import RandomManager
from simulator.engine.common.Monitor import Monitor
from simulator.environment.topology_factory import TopologyFactory
from simulator.environment.geometry import CartesianCoordinate


def setup_working_environment(
    out_dir: str, 
    topology: str, 
    num_nodes: int, 
    channel: str, 
    seed: int,
    suffix: Optional[str] = None
) -> str:
    """
    Creates the output directory for a single simulation run.
    An optional suffix can be added to the final run folder name (for antithetic generation, for example)
    """
    
    topo_folder_name = f"{topology}_{num_nodes}N"

    run_folder_name = str(seed)
    if suffix:
        run_folder_name = f"{run_folder_name}_{suffix}"

    run_output_dir = os.path.join(
        out_dir, topo_folder_name, channel, run_folder_name
    )
    os.makedirs(run_output_dir, exist_ok=True)

    run_id = f"Seed: {seed}" + (f" ({suffix})" if suffix else "")
    print(f"--- Starting Run ({run_id}) ---")
    print(f"--- Output Directory: {run_output_dir} ---")
    
    return run_output_dir


def create_topology(topology: str, num_nodes: int, seed: int) -> List[CartesianCoordinate]:
    """Generates the node positions using a dedicated RNG stream."""
    
    # create a dedicated RNG stream for topology generation for reproducibility
    topo_rng_manager = RandomManager(root_seed=seed)
    topo_rng_manager.create_stream(key = "TOPOLOGY_STREAM")
    topo_rng = topo_rng_manager.get_stream(key = "TOPOLOGY_STREAM")
    np_rng_seed = topo_rng.uniform(0, 2**32 - 1)
    np_rng = np.random.default_rng(int(np_rng_seed))

    factory = TopologyFactory()
    
    topo_params = {
        "rng": np_rng,
        "num_nodes": num_nodes,  # Used by linear, grid, random
    }

    node_positions = factory.create_topology(topology, **topo_params)

    return node_positions


def save_results(
    monitors: List[Monitor],
    run_output_dir: str,
):
    base_path = os.path.join(run_output_dir, "log")
    for monitor in monitors:
        monitor.save_to_csv(base_path)
    print(f"Data saved to {run_output_dir}/log_*.csv")


def save_parameters_log(
    all_args_dict: Dict[str, Any],
    bootstrap_params: Dict[str, Any],
    dspace_npt: int,
    num_nodes: int,
    run_output_dir: str,
):
    """Saves all simulation parameters to a text file for reproducibility."""
    params_log_path = os.path.join(run_output_dir, "parameters.txt")

    try:
        with open(params_log_path, 'w') as f:
            f.write("--- Simulation Parameters ---\n")
            f.write(f"Run Start Time: {datetime.now().isoformat()}\n")
            
            f.write("\n[Command Line Arguments]\n")
            for key, value in sorted(all_args_dict.items()):
                f.write(f"{key}: {value}\n")
            
            f.write("\n[Topology & DSpace]\n")
            f.write(f"actual_num_nodes: {num_nodes}\n")
            f.write(f"dspace_npt: {dspace_npt}\n")
            
            f.write("\n[Channel Model Parameters (from bootstrap)]\n")
            for key, value in sorted(bootstrap_params.items()):
                if key not in ["seed", "dspace_npt", "dspace_step"]: #already in args
                    f.write(f"{key}: {value}\n")
        
        print(f"Simulation parameters saved to: {params_log_path}")
    except Exception as e:
        print(
            f"--- ERROR: Failed to write parameters log to {params_log_path} ---",
            file=sys.stderr,
        )
        print(f"{e}", file=sys.stderr)

