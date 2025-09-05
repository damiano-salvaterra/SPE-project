# evaluation/validate_mac_test1.py

import sys
import os

# --- Python Path Setup ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
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
    def __init__(self, host, dest_addr: bytes, time_to_send: float):
        super().__init__()
        self.host = host
        self.dest_addr = dest_addr
        self.time_to_send = time_to_send

    def start(self):
        if self.time_to_send < float("inf"):
            send_event = Event(
                time=self.time_to_send, blame=self, callback=self.send_packet
            )
            self.host.context.scheduler.schedule(send_event)
            print(
                f"[{self.host.context.scheduler.now():.6f}s] [{self.host.id}] [App] Scheduled packet send for t={self.time_to_send:.2f}s."
            )

    def send_packet(self):
        payload_str = f"Test1 from {self.host.id}"
        packet = NetPacket(APDU=payload_str.encode("utf-8"))
        print(
            f"[{self.host.context.scheduler.now():.6f}s] [{self.host.id}] [App] > Sending packet to {self.dest_addr.hex()}."
        )
        self.host.mac.send(payload=packet, nexthop=self.dest_addr)

    def receive(self, payload: NetPacket, tx_addr: bytes):
        if payload is not None and hasattr(payload, "APDU"):
            payload_str = payload.APDU.decode("utf-8", errors="ignore")
            print(
                f"[{self.host.context.scheduler.now():.6f}s] [{self.host.id}] [App] < Received packet: '{payload_str}' from {tx_addr.hex()}."
            )
        # ACKs have no payload (NPDU is None), so we ignore them at the app level for this test.

    def generate_traffic(self):
        pass


# ======================================================================================
# MAIN SIMULATION SETUP
# ======================================================================================


def run_mac_test1():
    print("--- Starting MAC Validation Test 1: Reliable Transmission ---")
    kernel = Kernel(root_seed=12345)
    kernel.bootstrap(
        seed=12345,
        dspace_step=1,
        dspace_npt=100,
        freq=2.4e9,
        filter_bandwidth=2e6,
        coh_d=50,
        shadow_dev=0.1,
        pl_exponent=2.1,
        d0=1.0,
        fading_shape=20.0,
    )

    print("\n--- Creating Network Nodes ---")
    addr_node_A = b"\x00\x01"
    addr_node_B = b"\x00\x02"

    node_A = kernel.add_node("Node-A", CartesianCoordinate(10, 10), None, addr_node_A)
    node_B = kernel.add_node("Node-B", CartesianCoordinate(30, 10), None, addr_node_B)

    app_A = OneShotApp(host=node_A, dest_addr=addr_node_B, time_to_send=1.0)
    app_B = OneShotApp(host=node_B, dest_addr=addr_node_A, time_to_send=float("inf"))
    node_A.app = app_A
    node_B.app = app_B

    # --- FINAL FIX: Re-wire the stack on ALL nodes involved in the test ---
    node_A.net.receive = app_A.receive
    node_B.net.receive = app_B.receive

    app_A.start()
    app_B.start()

    print("\n--- Running Simulation ---")
    kernel.run(until=5.0)
    print("\n\n--- Simulation Finished ---")


if __name__ == "__main__":
    run_mac_test1()
