# evaluation/validate_mac_test2.py

import sys
import os

# --- Python Path Setup ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# --- Simulator Imports ---
from simulator.engine.Kernel import Kernel
from simulator.environment.geometry import CartesianCoordinate
from simulator.applications.Application import Application
from simulator.entities.protocols.common.packets import NetPacket
from simulator.engine.common.Event import Event

# ======================================================================================
# TEST APPLICATION
# ======================================================================================

class OneShotApp(Application):
    def __init__(self, host, dest_addr: bytes, time_to_send: float, payload_name: str, size_bytes: int):
        super().__init__()
        self.host = host
        self.dest_addr = dest_addr
        self.time_to_send = time_to_send
        self.payload = (payload_name.ljust(size_bytes, '#')).encode('utf-8')

    def start(self):
        if self.time_to_send < float('inf'):
            send_event = Event(time=self.time_to_send, blame=self, callback=self.send_packet)
            self.host.context.scheduler.schedule(send_event)

    def send_packet(self):
        packet = NetPacket(APDU=self.payload)
        print(f"[{self.host.context.scheduler.now():.6f}s] [{self.host.id}] [App] > Attempting to send '{self.payload.decode('utf-8','ignore').split('#')[0]}'.")
        self.host.mac.send(payload=packet, nexthop=self.dest_addr)

    def receive(self, payload: NetPacket, tx_addr: bytes):
        if payload is not None and hasattr(payload, 'APDU'):
            payload_str = payload.APDU.decode('utf-8', 'ignore').split('#')[0]
            print(f"[{self.host.context.scheduler.now():.6f}s] [{self.host.id}] [App] < Received packet: '{payload_str}' from {tx_addr.hex()}.")

    def generate_traffic(self):
        pass

# ======================================================================================
# MAIN SIMULATION SETUP
# ======================================================================================

def run_mac_test2():
    print("--- Starting MAC Validation Test 2: Carrier Sense ---")
    kernel = Kernel(root_seed=67890)
    kernel.bootstrap(
        seed=67890, dspace_step=1, dspace_npt=100, freq=2.4e9, filter_bandwidth=2e6,
        coh_d=50, shadow_dev=0.1, pl_exponent=2.1, d0=1.0, fading_shape=20.0
    )

    print("\n--- Creating Network Nodes ---")
    addr_node_A = b'\x00\x01'
    addr_node_B = b'\x00\x02'
    addr_node_C = b'\x00\x03'

    node_A = kernel.add_node("Node-A", CartesianCoordinate(10, 10), None, addr_node_A)
    node_B = kernel.add_node("Node-B", CartesianCoordinate(30, 10), None, addr_node_B)
    node_C = kernel.add_node("Node-C", CartesianCoordinate(50, 10), None, addr_node_C)

    app_A = OneShotApp(node_A, dest_addr=addr_node_B, time_to_send=1.0, payload_name="LONG_PACKET", size_bytes=100)
    app_C = OneShotApp(node_C, dest_addr=addr_node_B, time_to_send=1.001, payload_name="SHORT_PACKET", size_bytes=20)
    app_B = OneShotApp(node_B, dest_addr=addr_node_A, time_to_send=float('inf'), payload_name="", size_bytes=0)

    node_A.app = app_A
    node_B.app = app_B
    node_C.app = app_C

    # --- FINAL FIX: Re-wire the stack on ALL nodes involved in the test ---
    node_A.net.receive = app_A.receive
    node_B.net.receive = app_B.receive
    node_C.net.receive = app_C.receive

    app_A.start()
    app_B.start()
    app_C.start()

    print("\n--- Running Simulation ---")
    kernel.run(until=5.0)
    print("\n\n--- Simulation Finished ---")

if __name__ == "__main__":
    run_mac_test2()