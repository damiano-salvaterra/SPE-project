import argparse
import os
import numpy as np
from datetime import datetime
import sys
import json
from typing import Tuple, List, Dict, Any
from evaluation.utils.plotting import plot_scenario
from simulator.engine.Kernel import Kernel
from simulator.engine.random.RandomGenerator import RandomGenerator
from simulator.engine.random.RandomManager import RandomManager
from simulator.engine.common.Monitor import Monitor
from simulator.environment.topology_factory import TopologyFactory
from simulator.environment.geometry import CartesianCoordinate


def setup_working_environment(args: argparse.Namespace) -> str:
    """Creates the unique output directory for this specific run."""

    topo_folder_name = f"{args.topology}_{args.num_nodes}N"

    # Create seed-specific directory
    run_output_dir = os.path.join(
        args.out_dir,
        args.app,
        topo_folder_name,
        args.channel,
        f"{args.seed}_antithetic" if args.antithetic else str(args.seed),
    )
    os.makedirs(run_output_dir, exist_ok=True)

    print(f"--- Starting Run (Seed: {args.seed}) ---")
    print(f"--- Output Directory: {run_output_dir} ---")
    return run_output_dir


def create_topology(
    topology: str, num_nodes: int, seed: int
) -> Tuple[List[CartesianCoordinate], int]:
    """Generates the node positions using a dedicated RNG stream."""

    # create a dedicated RNG stream for topology generation for reproducibility
    topo_rng_manager = RandomManager(root_seed=seed)
    topo_rng = RandomGenerator(topo_rng_manager, "TOPOLOGY_STREAM")
    np_rng_seed = topo_rng.uniform(0, 2**32 - 1)
    np_rng = np.random.default_rng(int(np_rng_seed))

    factory = TopologyFactory()

    #
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
    args: argparse.Namespace,
    bootstrap_params: Dict[str, Any],
    dspace_npt: int,
    num_nodes: int,
    run_output_dir: str,
):
    """Saves all simulation parameters to a JSON file for reproducibility."""
    params_log_path = os.path.join(run_output_dir, "parameters.json")

    # Build a JSON-serializable structure
    try:
        params = {
            "run_start_time": datetime.now().isoformat(),
            "command_line_arguments": {},
            "topology_and_dspace": {
                "actual_num_nodes": int(num_nodes),
                "dspace_npt": int(dspace_npt),
            },
            "channel_model_parameters": {},
        }

        # Command line args: convert Namespace to dict
        for key, value in sorted(vars(args).items()):
            # Ensure basic JSON serialization by converting unknown types to string
            try:
                json.dumps({key: value})
                params["command_line_arguments"][key] = value
            except (TypeError, OverflowError):
                params["command_line_arguments"][key] = str(value)

        # Bootstrap params: exclude items already in args
        for key, value in sorted(bootstrap_params.items()):
            if key in ["seed", "dspace_npt", "dspace_step"]:
                continue
            try:
                json.dumps({key: value})
                params["channel_model_parameters"][key] = value
            except (TypeError, OverflowError):
                params["channel_model_parameters"][key] = str(value)

        with open(params_log_path, "w") as f:
            json.dump(params, f, indent=2)

        print(f"Simulation parameters saved to: {params_log_path}")
    except Exception as e:
        print(
            f"--- ERROR: Failed to write parameters log to {params_log_path} ---",
            file=sys.stderr,
        )
        print(f"{e}", file=sys.stderr)


def plot_results(
    args: argparse.Namespace,
    kernel: Kernel,
    node_info: Dict[str, Dict[str, Any]],
    run_output_dir: str,
    num_nodes: int,
):
    """Generates and saves the scenario plot."""
    # plot_path will be, e.g., ".../seed/run_scenario.png"
    plot_path = os.path.join(run_output_dir, "scenario.png")
    plot_title = (
        f"Scenario:{args.topology.capitalize()} Topology, {args.channel.capitalize()} Channel ({num_nodes} Nodes)\n"
        f"Seed: {args.seed}, App: {args.app.capitalize()}"
    )
    plot_scenario(kernel, node_info, plot_title, plot_path, figsize=(12, 10))
    print(f"Plot saved to {plot_path}")
