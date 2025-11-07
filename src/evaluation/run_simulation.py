# src/evaluation/run_simulation.py
import sys
import os
import argparse
import numpy as np
import traceback

# --- Python Path Setup ---
# This ensures we can import the simulator modules from the 'src' directory
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC_ROOT = os.path.join(PROJECT_ROOT, "src")
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

# --- Simulator Imports ---
from simulator.engine.Kernel import Kernel  # noqa: E402
from simulator.engine.random import RandomManager, RandomGenerator  # noqa: E402
from simulator.environment.topology_factory import TopologyFactory  # noqa: E402
from simulator.entities.applications.PingPongApplication import (  # noqa: E402
    PingPongApp,
)
from simulator.entities.applications.PoissonTrafficApplication import (  # noqa: E402
    PoissonTrafficApplication,
)
from simulator.entities.applications.common.app_monitor import (  # noqa: E402
    ApplicationMonitor,
)
from simulator.entities.protocols.net.common.tarp_monitor import (  # noqa: E402
    TARPMonitor,
)
from evaluation.utils.plotting import plot_scenario  # noqa: E402

# ======================================================================================
# Helper Functions
# ======================================================================================


def get_channel_params(channel_name: str) -> dict:
    """Returns parameters for the requested channel presets."""
    # Base: 2.4 GHz, 2 MHz BW, d0=1.0m
    base_params = {"freq": 2.4e9, "filter_bandwidth": 2e6, "d0": 1.0}

    # Stable: Low path loss, low shadowing, high coherence distance (stable shadowing)
    stable = base_params.copy()
    stable.update(
        {"coh_d": 50, "shadow_dev": 2.0, "pl_exponent": 2.0, "fading_shape": 3.0}
    )

    # Lossy: Medium path loss, medium shadowing, medium coherence distance
    lossy = base_params.copy()
    lossy.update(
        {"coh_d": 20, "shadow_dev": 5.0, "pl_exponent": 3.8, "fading_shape": 1.5}
    )

    # Unstable: High path loss, high shadowing, low coherence distance (variable shadowing)
    unstable = base_params.copy()
    unstable.update(
        {"coh_d": 10, "shadow_dev": 6.0, "pl_exponent": 4.0, "fading_shape": 0.75}
    )

    params_map = {"stable": stable, "lossy": lossy, "unstable": unstable}
    return params_map.get(channel_name, lossy)


def calculate_bounds_and_params(node_positions, padding=50, dspace_step=1.0) -> int:
    """Calculates the DSpace 'npt' parameter required to contain the topology."""
    if not node_positions:
        return 200  # Fallback
    min_x = min(p.x for p in node_positions)
    max_x = max(p.x for p in node_positions)
    min_y = min(p.y for p in node_positions)
    max_y = max(p.y for p in node_positions)
    # Find the largest absolute coordinate (from center 0,0) required, including padding
    max_abs_coord = max(
        abs(min_x - padding),
        abs(max_x + padding),
        abs(min_y - padding),
        abs(max_y + padding),
    )
    # Calculate npt needed for this half-width. +2 for safety buffer.
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
# MAIN EXECUTION
# ======================================================================================


def main():
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
        choices=["stable", "lossy", "unstable"],
        default="lossy",
        help="Channel model",
    )
    parser.add_argument("--num_nodes", type=int, default=10, help="Number of nodes")
    parser.add_argument(
        "--sim_time", type=float, default=300.0, help="Simulation time in seconds"
    )
    parser.add_argument(
        "--seed", type=int, default=123, help="Root seed for this replication"
    )
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
        help="Output directory for data and plots",
    )
    args = parser.parse_args()

    # 1. Setup Environment
    os.makedirs(args.out_dir, exist_ok=True)
    base_filename = f"{args.app}_{args.topology}_{args.channel}_{args.num_nodes}nodes_seed{args.seed}"
    print(f"--- Starting Run: {base_filename} ---")

    # 2. Create Topology
    # We use a separate RNG for topology, derived from the main seed,
    # to ensure topology generation is a controllable random stream.
    topo_rng_manager = RandomManager(root_seed=args.seed)
    topo_rng = RandomGenerator(topo_rng_manager, "TOPOLOGY_STREAM")
    np_rng_seed = topo_rng.uniform(0, 2**32 - 1)
    np_rng = np.random.default_rng(int(np_rng_seed))  # Many topologies use numpy

    factory = TopologyFactory()
    # Provide common parameters to the factory
    topo_params = {
        "num_nodes": args.num_nodes,
        "rng": np_rng,
        "node_distance": 15,
        "radius": 100,
    }
    node_positions = factory.create_topology(args.topology, **topo_params)
    actual_num_nodes = len(node_positions)

    # 3. Bootstrap Kernel
    # The main seed controls the simulation's core RNG (fading, shadowing, application behavior)
    kernel = Kernel(
        root_seed=args.seed, antithetic=False
    )  # Antithetic variates are handled at the batch level

    dspace_npt = calculate_bounds_and_params(
        node_positions, dspace_step=args.dspace_step
    )
    bootstrap_params = get_channel_params(args.channel)
    bootstrap_params.update(
        {"seed": args.seed, "dspace_npt": dspace_npt, "dspace_step": args.dspace_step}
    )
    kernel.bootstrap(**bootstrap_params)  # This generates the shadowing map

    # 4. Create Nodes & Applications
    node_addrs_by_index = {
        i: (i + 1).to_bytes(2, "big") for i in range(actual_num_nodes)
    }
    all_nodes_map = {f"Node-{i+1}": addr for i, addr in node_addrs_by_index.items()}

    pinger_idx, ponger_idx = None, None  # Specific to pingpong
    node_info_for_plot = {}  # For the final plot

    for i in range(actual_num_nodes):
        node_id = f"Node-{i+1}"
        addr = node_addrs_by_index[i]
        is_sink = i == 0  # Node 0 (ID Node-1) is always the sink
        app_instance = None
        role = "sink" if is_sink else "default"

        if args.app == "pingpong":
            # Set pinger/ponger indices if not set, avoiding the sink
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
        app_instance.host = node
        node_info_for_plot[node_id] = {
            "position": node_positions[i],
            "role": role,
            "addr": addr,
        }

    # 5. Attach Monitors
    app_mon = ApplicationMonitor(monitor_name="app", verbose=False)
    tarp_mon = TARPMonitor(monitor_name="tarp", verbose=False)
    for node in kernel.nodes.values():
        node.app.attach_monitor(app_mon)
        node.net.attach_monitor(tarp_mon)

    # 6. Start Applications
    print("\n--- Starting applications ---")
    for node in kernel.nodes.values():
        node.app.start()

    # 7. Run Simulation
    print(f"\n--- Running simulation for {args.sim_time}s (Seed: {args.seed}) ---")
    kernel.run(until=args.sim_time)
    print(f"--- Simulation finished at {kernel.context.scheduler.now():.6f}s ---")

    # 8. Save Results
    app_mon.save_to_csv(os.path.join(args.out_dir, base_filename))
    tarp_mon.save_to_csv(os.path.join(args.out_dir, base_filename))
    print(f"Data saved to {args.out_dir}/{base_filename}_*.csv")

    # 9. Plot Scenario
    plot_path = os.path.join(args.out_dir, f"{base_filename}_scenario.png")
    plot_title = f"Scenario: {args.topology.capitalize()} Topo, {args.channel.capitalize()} Channel ({actual_num_nodes} Nodes)\nSeed: {args.seed}, App: {args.app.capitalize()}"
    plot_scenario(kernel, node_info_for_plot, plot_title, plot_path, figsize=(12, 10))
    print(f"Plot saved to {plot_path}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n--- SIMULATION CRASHED ---")
        traceback.print_exc()
        sys.exit(1)  # Exit with an error code
