import argparse

def setup_arguments() -> argparse.Namespace:
    """Configures and parses command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Run a single network simulation replicate."
    )

    parser.add_argument(
        "--topology",
        type=str,
        default="linear",
        help="Topology name (e.g., linear, ring, grid, random)",
    )
    parser.add_argument(
        "--channel",
        choices=[
            "stable",
            "stable_mid_pl",
            "stable_high_pl",
            "lossy",
            "unstable",
            "ideal",
        ],
        default="lossy",
        help="Channel model",
    )
    parser.add_argument(
        "--tx_power", type=float, default=0, help="Nodes' transmission power in dBm"
    )
    parser.add_argument("--num_nodes", type=int, default=10, help="Number of nodes")
    parser.add_argument(
        "--sim_time", type=float, default=300.0, help="Simulation time in seconds"
    )

    parser.add_argument(
        "--sim_seed", 
        type=int, 
        default=123, 
        help="Root seed for simulation events (traffic, channel, etc.)"
    )
    parser.add_argument(
        "--topo_seed", 
        type=int, 
        default=42, 
        help="Root seed for topology generation (used if topology='random')"
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
        help="Base output directory for the batch",
    )
    parser.add_argument(
        "--antithetic",
        action="store_true",
        help="Run the simulation using antithetic variates",
    )
    return parser.parse_args()