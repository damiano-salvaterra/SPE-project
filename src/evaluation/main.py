# src/evaluation/main.py

import sys
import os
from typing import Optional, TYPE_CHECKING
import functools

# --- Python Path Setup ---
# This ensures that the script can find the 'simulator' package when run as a module.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# --- Simulator Imports ---
from simulator.engine.Kernel import Kernel
from simulator.environment.geometry import CartesianCoordinate
from simulator.applications.Application import Application
from simulator.entities.protocols.common.packets import NetPacket, Frame_802154
from simulator.engine.common.Event import Event

if TYPE_CHECKING:
    from simulator.entities.physical.devices.nodes import StaticNode
    from simulator.entities.protocols.common.Layer import Layer

# ======================================================================================
# TEST APPLICATION: PingPongApp
# ======================================================================================

class PingPongApp(Application):
    """
    A simple application to test the network stack.
    - The 'pinger' node sends a "PING" message.
    - The 'ponger' node receives the "PING" and replies with a "PONG".
    """
    def __init__(self, host: Optional["StaticNode"], is_pinger: bool = False, peer_addr: Optional[bytes] = None):
        super().__init__()
        self.host = host
        self.is_pinger = is_pinger
        self.peer_addr = peer_addr
        self.ping_count = 0

    def start(self):
        """Called by the main script to start the application's logic."""
        log(self, "Application started.")
        if self.is_pinger:
            # The pinger waits for the network to form, then sends the first PING.
            initial_send_time = 30.0  # Wait for TARP beacons to establish routes.
            log(self, f"Scheduling first PING at t={initial_send_time:.2f}s.")
            
            # Create a simulation event to trigger the generate_traffic method.
            start_ping_event = Event(time=initial_send_time, blame=self, callback=self.generate_traffic)
            self.host.context.scheduler.schedule(start_ping_event)

    def generate_traffic(self):
        """
        Implements the abstract method from the Application base class.
        This method is responsible for creating and sending a packet.
        """
        if not self.peer_addr:
            return

        self.ping_count += 1
        payload_str = f"PING #{self.ping_count} from {self.host.id}"
        packet = NetPacket(APDU=payload_str.encode('utf-8'))
        
        log(self, f">>> Sending '{payload_str}' to {self.peer_addr.hex()}.")
        
        # Pass the packet to the network layer for routing and transmission.
        self.host.net.send(packet, destination=self.peer_addr)

    def receive(self, packet: NetPacket, sender_addr: bytes):
        """
        Handles an incoming packet from the network layer.
        If it's a PING, it replies with a PONG.
        """
        payload_str = packet.APDU.decode('utf-8', errors='ignore')
        log(self, f"<<< Received '{payload_str}' from {sender_addr.hex()}.")

        # If this node is the 'ponger' and receives a PING, it replies.
        if "PING" in payload_str and not self.is_pinger:
            reply_payload_str = f"PONG in response to '{payload_str}'"
            reply_packet = NetPacket(APDU=reply_payload_str.encode('utf-8'))
            
            log(self, f">>> Replying with '{reply_payload_str}' to {sender_addr.hex()}.")
            
            # Send the PONG back to the original sender.
            self.host.net.send(reply_packet, destination=sender_addr)

# ======================================================================================
# UTILITY FUNCTION FOR LOGGING
# ======================================================================================

def log(instance: object, message: str):
    """A standardized logging function for cleaner output."""
    time = instance.host.context.scheduler.now()
    name = instance.host.id
    print(f"[{time:.6f}s] [{name}] {message}")

# ======================================================================================
# MAIN SIMULATION SETUP
# ======================================================================================

def run_simulation():
    """Configures and runs the entire simulation scenario."""
    
    print("--- Starting Network Stack Test: Ping-Pong ---")

    # 1. Initialize the simulation Kernel
    # The root_seed ensures that the simulation is repeatable.
    kernel = Kernel(root_seed=12345)

    # 2. Bootstrap the physical environment
    # These parameters model a typical 2.4 GHz low-power wireless channel.
    kernel.bootstrap(
        seed=12345,
        dspace_step=1, dspace_npt=100, freq=2.4e9, filter_bandwidth=2e6,
        coh_d=50, shadow_dev=4.0, pl_exponent=2.5, d0=1.0, fading_shape=1.0
    )

    # 3. Create the network nodes
    print("\n--- Creating Network Nodes ---")
    
    addr_node_A = b'\x00\x01'
    addr_node_B = b'\x00\x02'

    # Create nodes without applications first. This is a clean pattern.
    node_A = kernel.add_node(
        node_id="Node-A (Pinger)",
        position=CartesianCoordinate(10, 10),
        app=None,
        linkaddr=addr_node_A,
        is_sink=True  # Let's make the pinger the TARP sink/root for simplicity.
    )
    node_B = kernel.add_node(
        node_id="Node-B (Ponger)",
        position=CartesianCoordinate(40, 10), # 30 meters away
        app=None,
        linkaddr=addr_node_B
    )

    # 4. Create and assign applications to the nodes
    # This two-step process (create node, then create/assign app) is robust.
    app_A = PingPongApp(host=node_A, is_pinger=True, peer_addr=addr_node_B)
    node_A.app = app_A

    app_B = PingPongApp(host=node_B, is_pinger=False, peer_addr=addr_node_A)
    node_B.app = app_B
    
    # 5. Start the applications
    # This will schedule the initial events.
    app_A.start()
    app_B.start()

    # 6. Run the simulation
    print("\n--- Running Simulation ---")
    kernel.run(until=6000.0) # Run for 60 seconds to observe the message exchange.

    # 7. Print final results
    print("\n--- Simulation Finished ---")
    print(f"Final simulation time: {kernel.context.scheduler.now():.6f}s")
    print(f"Events remaining in queue: {kernel.context.scheduler.get_queue_length()}")


if __name__ == "__main__":
    run_simulation()
# src/evaluation/main.py

import sys
import os
from typing import Optional, TYPE_CHECKING

# --- Python Path Setup ---
# This ensures that the script can find the 'simulator' package when run as a module.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# --- Simulator Imports ---
from simulator.engine.Kernel import Kernel
from simulator.environment.geometry import CartesianCoordinate
from simulator.applications.Application import Application
from simulator.entities.protocols.common.packets import NetPacket
from simulator.engine.common.Event import Event

if TYPE_CHECKING:
    from simulator.entities.physical.devices.nodes import StaticNode

# ======================================================================================
# TEST APPLICATION: PingPongApp
# ======================================================================================

class PingPongApp(Application):
    """
    A simple application to test the network stack.
    - The 'pinger' node sends a "PING" message after a delay.
    - The 'ponger' node receives the "PING" and replies with a "PONG".
    """
    def __init__(self, host: Optional["StaticNode"], is_pinger: bool = False, peer_addr: Optional[bytes] = None):
        super().__init__()
        self.host = host
        self.is_pinger = is_pinger
        self.peer_addr = peer_addr
        self.ping_count = 0

    def start(self):
        """Called by the main script to start the application's logic."""
        log(self, "Application started.")
        if self.is_pinger:
            # The pinger waits for the network to form (TARP beacons) before sending.
            initial_send_time = 30.0
            log(self, f"Scheduling first PING at t={initial_send_time:.2f}s.")
            
            # Create a simulation event to trigger the message sending.
            start_ping_event = Event(time=initial_send_time, blame=self, callback=self.generate_traffic)
            self.host.context.scheduler.schedule(start_ping_event)

    def generate_traffic(self):
        """
        Implements the abstract method from the Application base class.
        This is where a packet is created and sent.
        """
        if not self.peer_addr:
            return

        self.ping_count += 1
        payload_str = f"PING #{self.ping_count} from {self.host.id}"
        packet = NetPacket(payload=payload_str.encode('utf-8'))
        
        log(self, f">>> Sending '{payload_str}' to {self.peer_addr.hex()}.")
        
        # Pass the packet to the network layer for routing and transmission.
        self.host.net.send(packet, destination=self.peer_addr)

    def receive(self, packet: NetPacket, sender_addr: bytes):
        """
        Handles an incoming packet from the network layer.
        If it's a PING, it replies with a PONG.
        """
        payload_str = packet.payload.decode('utf-8', errors='ignore')
        log(self, f"<<< Received '{payload_str}' from {sender_addr.hex()}.")

        # If this node is the 'ponger' and receives a PING, it replies.
        if "PING" in payload_str and not self.is_pinger:
            reply_payload_str = f"PONG in response to '{payload_str}'"
            reply_packet = NetPacket(payload=reply_payload_str.encode('utf-8'))
            
            log(self, f">>> Replying with '{reply_payload_str}' to {sender_addr.hex()}.")
            
            # Send the PONG back to the original sender.
            self.host.net.send(reply_packet, destination=sender_addr)

# ======================================================================================
# UTILITY FUNCTION FOR LOGGING
# ======================================================================================

def log(instance: object, message: str):
    """A standardized logging function for cleaner, time-stamped output."""
    time = instance.host.context.scheduler.now()
    node_id = instance.host.id
    print(f"[{time:.6f}s] [{node_id}] {message}")

# ======================================================================================
# MAIN SIMULATION SETUP
# ======================================================================================

def run_simulation():
    """Configures and runs the entire simulation scenario."""
    
    print("--- Starting Network Stack Test: Ping-Pong ---")

    # 1. Initialize the simulation Kernel
    kernel = Kernel(root_seed=12345)

    # 2. Bootstrap the physical environment
    kernel.bootstrap(
        seed=12345,
        dspace_step=1, dspace_npt=100, freq=2.4e9, filter_bandwidth=2e6,
        coh_d=50, shadow_dev=4.0, pl_exponent=2.5, d0=1.0, fading_shape=1.0
    )

    # 3. Create the network nodes
    print("\n--- Creating Network Nodes ---")
    
    addr_node_A = b'\x00\x01'
    addr_node_B = b'\x00\x02'

    # The 'is_sink' flag is important for TARP's tree formation.
    node_A = kernel.add_node(
        node_id="Node-A (Pinger, Sink)",
        position=CartesianCoordinate(10, 10),
        app=None,
        linkaddr=addr_node_A,
        is_sink=True
    )
    node_B = kernel.add_node(
        node_id="Node-B (Ponger)",
        position=CartesianCoordinate(40, 10), # 30 meters away
        app=None,
        linkaddr=addr_node_B,
        is_sink=False
    )

    # 4. Create and assign applications to the nodes
    app_A = PingPongApp(host=node_A, is_pinger=True, peer_addr=addr_node_B)
    node_A.app = app_A

    app_B = PingPongApp(host=node_B, is_pinger=False, peer_addr=addr_node_A)
    node_B.app = app_B
    
    # 5. Start the applications, which will schedule the initial events
    app_A.start()
    app_B.start()

    # 6. Run the simulation
    print("\n--- Running Simulation ---")
    kernel.run(until=60.0) # Run for 60 seconds to observe the message exchange.

    # 7. Print final results
    print("\n--- Simulation Finished ---")
    print(f"Final simulation time: {kernel.context.scheduler.now():.6f}s")
    print(f"Events remaining in queue: {kernel.context.scheduler.get_queue_length()}")


if __name__ == "__main__":
    run_simulation()