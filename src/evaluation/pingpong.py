import sys
import os
import argparse
import atexit # Added import for cleanup

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from simulator.engine.Kernel import Kernel  # noqa: E402
from simulator.applications.PingPongApplication import PingPongApp  # noqa: E402
from evaluation.monitors.packet_monitor import PacketMonitor  # noqa: E402
from evaluation.monitors.app_monitor import AppPingMonitor  # noqa: E402
from evaluation.monitors.tarp_monitor import TARPMonitor  # noqa: E402
from evaluation.util.plot_topology import plot_topology  # noqa: E402
from evaluation.util.topology import (  # noqa: E402
    get_linear_topology_positions,
    get_ring_topology_positions,
)

# ======================================================================================
# Global variables to hold original stdout/stderr and the log file handle
original_stdout = sys.stdout
original_stderr = sys.stderr
log_file = None

def setup_logging(log_filename="simulation.log"):
    """Redirects stdout and stderr to a specified log file."""
    global log_file
    try:
        # Create log directory if it doesn't exist
        log_dir = os.path.dirname(log_filename)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        # Open the log file
        log_file = open(log_filename, 'w')
        
        # MODIFICATION: Redirect only stdout to the log file.
        # stderr (for exceptions) will remain on the original console.
        sys.stdout = log_file
        # sys.stderr = log_file # This line is commented out to keep exceptions on the console.
        
        # Register the cleanup function to run at script exit
        atexit.register(cleanup_logging)
        
    except Exception as e:
        # If logging setup fails, print error to original stderr and exit
        original_stderr.write(f"Failed to setup logging to {log_filename}: {e}\n")
        sys.exit(1)

def cleanup_logging():
    """Restores original stdout/stderr and closes the log file."""
    global log_file
    
    # MODIFICATION: Check if log_file was successfully opened before closing
    if log_file:
        # Flush and close the log file
        try:
            log_file.flush()
            log_file.close()
        except Exception as e:
            # If closing fails, report to original stderr
            original_stderr.write(f"Failed to close log file: {e}\n")
    
    # Restore original stdout and stderr
    sys.stdout = original_stdout
    sys.stderr = original_stderr
# ======================================================================================


# ======================================================================================
# MAIN SIMULATION SETUP
# ======================================================================================


def main(
    num_nodes: int = 2,
    node_distance: int = 30,
    simulation_time: float = 600.0,
    root_seed: int = 12345,
    bootstrap_params: dict = None,
    bootstrapped_kernel: Kernel = None,
    node_positions: list = None,
    topology_plot_path: str = "topology.png",
):
    """
    Main simulation function.

    Args:
        num_nodes (int): The total number of nodes in the linear topology.
        node_distance (int): The distance between adjacent nodes.
        simulation_time (float): The total simulation time in seconds.
        root_seed (int): The root seed for the random number generator.
        bootstrap_params (dict): A dictionary of parameters for bootstrapping a new kernel.
        bootstrapped_kernel (Kernel): An optional pre-bootstrapped kernel instance.
        node_positions (list): A list of CartesianCoordinate objects for node positions.
        topology_plot_path (str): The file path to save the topology plot.
    """
    print("\n--- Simulation Parameters ---")
    print(f"Root seed: {root_seed}")
    print(
        f"Network configuration: num_nodes={num_nodes}, node_distance={node_distance}"
    )
    print(f"Simulation time: {simulation_time}s")

    print("\n--- Initializing Kernel and Scheduler ---")
    kernel = None
    if bootstrapped_kernel:
        kernel = bootstrapped_kernel
        print("Using provided bootstrapped kernel with parameters:")
        if bootstrap_params:
            # Log the actual parameters that were passed in
            params_str = ", ".join(
                [f"{k}={v}" for k, v in bootstrap_params.items() if k != "seed"]
            )
            print(f"Kernel configuration: {params_str}")
        else:
            # Fallback message if for some reason the params weren't passed
            print("Kernel configuration: Parameters not provided for logging.")

    else:
        print(
            "No bootstrapped kernel provided. Creating one with default stable channel parameters."
        )
        # Define and log the default parameters used when main() is called directly
        # NOTE: This default is now corrected to be more attenuating
        default_stable_params = {
            "seed": 12345,
            "dspace_step": 1,
            "dspace_npt": 200,
            "freq": 2.4e9,
            "filter_bandwidth": 2e6,
            "coh_d": 50,
            "shadow_dev": 2.0,
            "pl_exponent": 4.5, # Corrected: Was 3.5, now 4.5
            "d0": 1.0,
            "fading_shape": 3.0,
        }
        params_str = ", ".join(
            [f"{k}={v}" for k, v in default_stable_params.items() if k != "seed"]
        )
        print(f"Kernel configuration: {params_str}")

        kernel = Kernel(root_seed=root_seed)
        kernel.bootstrap(**default_stable_params)

    print(
        "\n--- Creating Network Nodes and setting up PingPongApp ---"
    )
    nodes = {}
    addrs = {}

    # Use the positions and path passed as arguments
    if node_positions is None:
        # Fallback in case no positions are passed
        print("Warning: No node positions provided, defaulting to 15-node ring.")
        positions = get_ring_topology_positions(15, radius=150)
    else:
        positions = node_positions
    
    topology_image_path = topology_plot_path

    # pinger_idx = num_nodes // 4  # node at 1/4 of the ring
    # ponger_idx = (3 * num_nodes) // 4  # node at 3/4 of the ring (opposite side)
    pinger_idx = 1
    ponger_idx = num_nodes - 1
    # plot_topology(positions, title="Network Topology", save_path="topology.png")
    plot_info = {}

    for i in range(num_nodes):
        #node_char = chr(ord("A") + i)
        node_id = f"Node-{i+1}"
        addr = (i + 1).to_bytes(2, "big")

        is_pinger = i == pinger_idx
        is_sink = i == 0  # Node A is the sink/root
        is_ponger = i == ponger_idx

        peer_addr = None
        if is_pinger:
            peer_addr = (ponger_idx + 1).to_bytes(2, "big")
            print(f"Node-{i} is PINGER")
        elif is_ponger:
            peer_addr = (pinger_idx + 1).to_bytes(2, "big")
            print(f"Node-{i} is PONGER")

        app = PingPongApp(host=None, is_pinger=is_pinger, peer_addr=peer_addr)

        node = kernel.add_node(
            node_id=node_id,
            position=positions[i],
            app=app,
            linkaddr=addr,
            is_sink=is_sink,
        )
        app.host = node
        nodes[node_id] = node
        addrs[node_id] = addr
        plot_info[node_id] = {
            "position": positions[i],
            "address": addr,
            "is_pinger": is_pinger,
            "is_ponger": is_ponger,
            "is_sink": is_sink,
        }

    plot_topology(plot_info, title="Network Topology", save_path=topology_image_path)

    print("\n--- Attaching Monitors to all nodes ---")
    # Create monitors
    packet_monitor = PacketMonitor(verbose=False)  # Keep for compatibility
    app_monitor = AppPingMonitor(verbose=True)
    tarp_monitor = TARPMonitor(verbose=True)

    for node_id in nodes:
        # Attach packet monitor to PHY layer (original behavior)
        kernel.attach_monitor(packet_monitor, f"{node_id}.phy")

        # Attach new monitors to application and TARP layers
        nodes[node_id].app.attach_monitor(app_monitor)
        nodes[node_id].net.attach_monitor(tarp_monitor)

    # Start applications
    # Start applications on Pinger and Ponger
    #pinger_node_char = chr(ord("A") + pinger_idx)
    #ponger_node_char = chr(ord("A") + ponger_idx)
    
    nodes[f"Node-{pinger_idx}"].app.start()  # Start the Pinger
    nodes[f"Node-{ponger_idx}"].app.start()  # Start the Ponger

    print("\n--- Running Simulation ---")
    kernel.run(until=simulation_time)

    print("\n\n--- Simulation Finished ---")
    print(f"Final simulation time: {kernel.context.scheduler.now():.6f}s")

    scheduler = kernel.context.scheduler
    queue_len = scheduler.get_queue_length()
    print(f"Events remaining in queue: {queue_len}")

    if queue_len > 0:
        print("\n--- First 10 Events in Queue ---")
        for i, (time, event) in enumerate(sorted(scheduler.event_queue)[:10]):
            print(
                f"{i+1}: t={time * scheduler._time_scale:.6f}s, Event={type(event).__name__}, Blame={type(event.blame).__name__}, Descriptor: {event.descriptor}, Cancelled: {event._cancelled}"
            )

        print("\n--- Last 10 Events in Queue ---")
        for i, (time, event) in enumerate(sorted(scheduler.event_queue)[-10:]):
            print(
                f"{queue_len - 10 + i + 1}: t={time * scheduler._time_scale:.6f}s, Event={type(event).__name__}, Blame={type(event.blame).__name__}, Descriptor: {event.descriptor}, Cancelled: {event._cancelled}"
            )


if __name__ == "__main__":
    
    # MODIFICATION: Encapsulate the main run in a try/except/finally block.
    # This ensures that exceptions are printed to the original stderr (console)
    # and logging is always cleaned up, even on a crash.
    log_filename = "simulation.log" # Default
    plot_path = "topology.png"     # Default

    try:
        # --- Setup Argparse ---
        parser = argparse.ArgumentParser(description="Run PingPong simulation scenario.")
        parser.add_argument(
            "--topology",
            type=str,
            choices=["linear", "ring"],
            default="ring",
            help="Network topology type (default: ring)",
        )
        parser.add_argument(
            "--channel",
            type=str,
            # MODIFICATION: Added "medium" channel choice
            choices=["stable", "medium", "harsh"], 
            default="harsh",
            help="Channel model type (default: harsh)",
        )
        args = parser.parse_args()

        # --- Setup logging ---
        # Define log directory and filename based on args
        log_dir = "logs"
        log_filename = os.path.join(log_dir, f"log_{args.topology}_{args.channel}.txt")
        
        # Print initial message to original console
        original_stdout.write(f"--- Simulation starting... --- \n")
        original_stdout.write(f"Topology: {args.topology}, Channel: {args.channel}\n")
        original_stdout.write(f"Redirecting all stdout to: {log_filename}\n")
        # MODIFICATION: Notify user that exceptions will go to console
        original_stdout.write(f"All exceptions will be printed to this console.\n")

        
        # Redirect stdout (stderr remains on console)
        setup_logging(log_filename)

        print(f"\n--- Selected Configuration (from log) ---")
        print(f"Topology: {args.topology}")
        print(f"Channel: {args.channel}")

        kernel_seed = 12345

        # --- Scenario A (Stable): Multi-Hop with high-quality links ---
        # MODIFICATION: Increased pl_exponent from 3.5 to 4.5 to force multi-hop
        stable_params = {
            "seed": 12345,
            "dspace_step": 1,
            "dspace_npt": 200,
            "freq": 2.4e9,
            "filter_bandwidth": 2e6,
            "coh_d": 50,      # Stable shadowing (high spatial correlation)
            "shadow_dev": 2.0,  # Low shadowing variance
            "pl_exponent": 2,   
            "d0": 1.0,
            "fading_shape": 3.0,  # Rician fading (stable links)
        }

        # --- NEW: Scenario C (Medium): Realistic, unstable multi-hop ---
        medium_params = {
            "seed": 12345,
            "dspace_step": 1,
            "dspace_npt": 200,
            "freq": 2.4e9,
            "filter_bandwidth": 2e6,
            "coh_d": 30,          # Medium spatial correlation
            "shadow_dev": 4.0,    # Medium shadowing variance
            "pl_exponent": 3.5,   # High attenuation (between stable and harsh)
            "d0": 1.0,
            "fading_shape": 1.5,  # Nakagami fading (m=1.5)
        }

        # --- Scenario B (Harsh): Dynamic and very unstable multi-hop ---
        harsh_params = {
            "seed": 12345,
            "dspace_step": 1,
            "dspace_npt": 200,
            "freq": 2.4e9,
            "filter_bandwidth": 2e6,
            "coh_d": 10,      # Highly variable shadowing (low spatial correlation)
            "shadow_dev": 6.0,  # High shadowing variance
            "pl_exponent": 4.0,   # Severe signal attenuation
            "d0": 1.0,
            "fading_shape": 0.75, # Almost-Rayleigh fading (very unstable links)
        }

        # Select channel parameters based on args
        if args.channel == "stable":
            bootstrap_params = stable_params
        # MODIFICATION: Added logic for "medium" channel
        elif args.channel == "medium": 
            bootstrap_params = medium_params
        else:  # harsh
            bootstrap_params = harsh_params

        num_nodes = 10
        # MODIFICATION: Increased node_distance from 35 to 60 to ensure multi-hop
        node_distance = 10
        simulation_time = 1200.0

        plots_dir = "plots" # Define plots directory
        
        # Create plots directory if it doesn't exist
        if not os.path.exists(plots_dir):
            os.makedirs(plots_dir)
            print(f"Created directory: {plots_dir}")

        # Select node positions based on args
        if args.topology == "linear":
            node_positions = get_linear_topology_positions(
                num_nodes, node_distance, start_x=50, start_y=100, increase_y=False
            )
            # MODIFICATION: Added channel to plot filename for uniqueness
            plot_path = os.path.join(plots_dir, f"{args.topology}_{args.channel}_topology.png")
        else:  # ring
            # MODIFICATION: Increased radius from 150 to 250 and adjusted center
            node_positions = get_ring_topology_positions(num_nodes, radius=250, center_x=250, center_y=250)
            # MODIFICATION: Added channel to plot filename for uniqueness
            plot_path = os.path.join(plots_dir, f"{args.topology}_{args.channel}_topology.png")


        # Bootstrap the kernel with given parameters
        kernel = Kernel(root_seed=kernel_seed)
        kernel.bootstrap(**bootstrap_params)

        # Pass the bootstrapped kernel and its parameters to the main function
        main(
            num_nodes=num_nodes,
            node_distance=node_distance,
            simulation_time=simulation_time,
            root_seed=kernel_seed,
            bootstrap_params=bootstrap_params,  # Pass the params for logging
            bootstrapped_kernel=kernel,
            node_positions=node_positions,  # Pass positions
            topology_plot_path=plot_path,  # Pass plot path
        )
        
        # If successful, print success message to original console
        original_stdout.write(f"--- Simulation finished successfully. ---\n")
        original_stdout.write(f"--- Log saved to {log_filename} ---\n")
        original_stdout.write(f"--- Plot saved to {plot_path} ---\n")

    except Exception as e:
        # MODIFICATION: If any exception occurs, print it to the original stderr
        original_stderr.write("\n\n" + "="*60 + "\n")
        original_stderr.write("--- SIMULATION CRASHED WITH AN EXCEPTION ---\n")
        original_stderr.write("="*60 + "\n")
        import traceback
        traceback.print_exc(file=original_stderr)
        original_stderr.write("="*60 + "\n")
        original_stderr.write(f"--- STDOUT log file is incomplete: {log_filename} ---\n")
        
    finally:
        # MODIFICATION: Explicitly call cleanup_logging here.
        # atexit can be unreliable in some exception cases.
        cleanup_logging()