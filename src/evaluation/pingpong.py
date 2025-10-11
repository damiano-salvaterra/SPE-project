import sys
import os

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from simulator.engine.Kernel import Kernel  # noqa: E402
from simulator.applications.PingPongApplication import PingPongApp  # noqa: E402
from evaluation.monitors.packet_monitor import PacketMonitor  # noqa: E402
from evaluation.monitors.app_monitor import AppPingMonitor  # noqa: E402
from evaluation.monitors.tarp_monitor import TARPForwardingMonitor  # noqa: E402
from evaluation.util.plot_topology import plot_topology  # noqa: E402
from evaluation.util.topology import (  # noqa: E402
    get_linear_topology_positions,
    get_ring_topology_positions,
)


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
        default_stable_params = {
            "seed": 12345,
            "dspace_step": 1,
            "dspace_npt": 200,
            "freq": 2.4e9,
            "filter_bandwidth": 2e6,
            "coh_d": 50,
            "shadow_dev": 2.0,
            "pl_exponent": 2.0,
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
        "\n--- Creating Network Nodes in linear topology and setting up PingPongApp ---"
    )
    nodes = {}
    addrs = {}

    positions = get_ring_topology_positions(num_nodes, radius=150)

    pinger_idx = 0
    ponger_idx = (num_nodes) // 2  # Middle node is the ponger, the opposite in the ring

    plot_topology(positions, title="Network Topology", save_path="topology.png")

    for i in range(num_nodes):
        node_char = chr(ord("A") + i)
        node_id = f"Node-{node_char}"
        addr = (i + 1).to_bytes(2, "big")

        is_pinger = i == pinger_idx
        is_sink = i == 0  # Node A is the sink/root
        is_ponger = i == ponger_idx

        peer_addr = None
        if is_pinger:
            peer_addr = (ponger_idx + 1).to_bytes(2, "big")
            print(f"Node-{node_char} is PINGER")
        elif is_ponger:
            peer_addr = (pinger_idx + 1).to_bytes(2, "big")
            print(f"Node-{node_char} is PONGER")

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

    print("\n--- Attaching Monitors to all nodes ---")
    # Create monitors
    packet_monitor = PacketMonitor(verbose=False)  # Keep for compatibility
    app_monitor = AppPingMonitor(verbose=True)
    tarp_monitor = TARPForwardingMonitor(verbose=True)

    for node_id in nodes:
        # Attach packet monitor to PHY layer (original behavior)
        kernel.attach_monitor(packet_monitor, f"{node_id}.phy")

        # Attach new monitors to application and TARP layers
        nodes[node_id].app.attach_monitor(app_monitor)
        nodes[node_id].net.attach_monitor(tarp_monitor)

    # Start applications
    nodes["Node-A"].app.start()
    nodes[f"Node-{chr(ord('A') + num_nodes - 1)}"].app.start()

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

    kernel_seed = 12345
    bootstrap_params = {
        "seed": 12345,
        "dspace_step": 1,
        "dspace_npt": 200,
        "freq": 2.4e9,
        "filter_bandwidth": 2e6,
        "coh_d": 7,  # Reduced coherence distance for a less stable channel
        "shadow_dev": 6.0,  # Increased shadow deviation for more spatial variation
        "pl_exponent": 4.0,  # Higher path loss exponent to simulate more obstruction
        "d0": 1.0,
        "fading_shape": 0.5,  # Lower value to introduce severe, rapid fading
    }

    num_nodes = 10
    node_distance = 5  # I can reduce this to make the channel easier
    simulation_time = 600.0

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
    )

    ## using the default kernel
    # main(num_nodes=num_nodes,
    #     node_distance=node_distance,
    #     simulation_time=simulation_time,
    #     root_seed=kernel_seed,
    #     bootstrap_params=bootstrap_params, # Pass the params for logging
    #    )
