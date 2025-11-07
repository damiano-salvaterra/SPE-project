# File: debug_link_budget.py
#
# This script runs a minimal 2-node simulation to test the link budget
# and calibrate the required transmission power (TX_POWER_DBM) against
# the channel model and the TARP protocol's RSSI threshold.
#

import sys
import os
import numpy as np
from typing import Dict

# --- Python Path Setup ---
# This ensures we can import the simulator modules from the 'src' directory
# !! ADJUST '..' if you place this script outside the 'evaluation' folder !!
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_ROOT = os.path.join(PROJECT_ROOT, "src")
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

# --- Simulator Imports ---
from simulator.engine.Kernel import Kernel
from simulator.environment.geometry import CartesianCoordinate
from simulator.entities.physical.devices.static_node import StaticNode
from simulator.entities.protocols.phy.SimplePhyLayer import SimplePhyLayer
from simulator.entities.protocols.radio_dc.NullRDC import NullRDC
from simulator.entities.protocols.mac.ContikiOS_MAC_802154 import ContikiOS_MAC_802154_Unslotted
from simulator.entities.protocols.net.tarp import TARPProtocol
from simulator.entities.applications.Application import Application
from simulator.engine.common.Monitor import Monitor
from simulator.entities.common.entity_signal import EntitySignal
from simulator.entities.common import Entity

# ==============================================================================
# --- Test Parameters (ADJUST THESE) ---
# ==============================================================================
#
# This is the power (in dBm) the nodes will transmit with.
# Your default was 0.0. Try 5.0, 10.0, or 20.0 to see the effect.
TX_POWER_DBM = 5.0

# The distance between the sink and the receiver node.
DISTANCE_METERS = 20.0

# The channel model to test (this is one of the failing ones).
CHANNEL_NAME = "harsh"

# Short duration, just to capture the first beacon(s).
SIM_TIME_SEC = 5.0

# Fixed seed for a reproducible channel (shadowing map).
SEED = 12345

# This is the hardcoded threshold from TARPParameters.py
TARP_RSSI_LOW_THR = -85.0
# ==============================================================================


# Helper function copied from run_simulation.py to get channel params
def get_channel_params(channel_name: str) -> Dict:
    """Returns parameters for the requested channel presets."""
    base_params = {"freq": 2.4e9, "filter_bandwidth": 2e6, "d0": 1.0}
    stable = base_params.copy()
    stable.update({"coh_d": 50, "shadow_dev": 2.0, "pl_exponent": 2.0, "fading_shape": 3.0})
    lossy = base_params.copy()
    lossy.update({"coh_d": 20, "shadow_dev": 5.0, "pl_exponent": 3.8, "fading_shape": 1.5})
    unstable = base_params.copy()
    unstable.update({"coh_d": 10, "shadow_dev": 6.0, "pl_exponent": 4.0, "fading_shape": 0.75})
    params_map = {"stable": stable, "lossy": lossy, "unstable": unstable}
    return params_map.get(channel_name, lossy)

# 1. Custom Node to allow setting Tx Power
# We must override the default StaticNode to inject our Tx Power parameter,
# as the original StaticNode hardcodes it to the default of 0.
class CustomTxNode(StaticNode):
    def __init__(
        self,
        node_id: str,
        linkaddr: bytes,
        position: CartesianCoordinate,
        application: Application,
        context,
        tx_power: float, # <-- Our new parameter
        is_sink=False,
    ):
        # We call NetworkNode init, not StaticNode init, to build the stack manually
        super(StaticNode, self).__init__()
        self._id = node_id
        self._linkaddr = linkaddr
        self.position = position
        self._context = context

        # *** This is the critical change ***
        # Pass the tx_power to the SimplePhyLayer constructor
        self.phy = SimplePhyLayer(self, transmission_power_dBm=tx_power)

        # The rest of the stack is initialized as normal
        self.rdc = NullRDC(self)
        self._mac = ContikiOS_MAC_802154_Unslotted(self)
        self.net = TARPProtocol(self, sink=is_sink)
        self.app = application

        # Manually link app host, since we overrode __init__
        self.app.host = self

# 2. Dummy Application
# We need a minimal application to satisfy the node's init requirements
class DummyApp(Application):
    """A minimal Application that does nothing."""
    def start(self):
        # print(f"DummyApp started on {self.host.id}")
        pass # Does nothing
    def generate_traffic(self):
        pass # Does nothing
    def receive(self, packet, sender_addr, hops=-1):
        print(f"[{self.host.context.scheduler.now():.6f}s] Node {self.host.id} received App packet from {sender_addr.hex()}")
        pass # Does nothing

# 3. Custom Monitor
# This monitor will intercept and print the beacon RSSI
class BeaconRssiMonitor(Monitor):
    def __init__(self, monitor_name: str = "BeaconMonitor", verbose=True):
        super().__init__(monitor_name=monitor_name, verbose=verbose)
        self.beacon_received = False
        self.rssi_values = []

    def update(self, entity: "Entity", signal: "EntitySignal"):
        # We only care about signals from the TARP protocol
        if not isinstance(entity, TARPProtocol):
            return

        # We only care about Beacon Received events ("BC_RECV")
        if hasattr(signal, "event_type") and signal.event_type == "BC_RECV":
            self.beacon_received = True
            rssi = getattr(signal, "rssi", -float('inf'))
            self.rssi_values.append(rssi)
            
            print("\n--- BEACON RECEIVED ---")
            print(f"  Time: {signal.timestamp:.6f}s")
            print(f"  Node: {entity.host.id}")
            print(f"  Source: {getattr(signal, 'source', 'N/A')}")
            print(f"  Received RSSI: {rssi:.2f} dBm")
            print(f"  TARP Threshold: {TARP_RSSI_LOW_THR:.2f} dBm")

            if rssi < TARP_RSSI_LOW_THR:
                print(f"  RESULT: FAILED. Beacon RSSI is BELOW the TARP threshold. It will be ignored by TARP.")
            else:
                print(f"  RESULT: SUCCESS. Beacon RSSI is ABOVE the TARP threshold. It will be processed.")
            print("-----------------------\n")

# 4. Main test function
def run_test():
    print("=============================================================")
    print("--- Starting Link Budget Calibration Test ---")
    print(f"  Tx Power: {TX_POWER_DBM} dBm")
    print(f"  Distance: {DISTANCE_METERS} m")
    print(f"  Channel: {CHANNEL_NAME}")
    print(f"  TARP Min RSSI: {TARP_RSSI_LOW_THR} dBm")
    print("=============================================================\n")

    # 1. Init Kernel
    kernel = Kernel(root_seed=SEED)

    # 2. Bootstrap Kernel
    # We need a DSpace large enough to hold our nodes
    dspace_step = 1.0
    # Calculate npt to be 0-centered and contain the node
    dspace_npt = int(DISTANCE_METERS * 2) + 50 # Make it large enough
    
    bootstrap_params = get_channel_params(CHANNEL_NAME)
    bootstrap_params.update({
        "seed": SEED,
        "dspace_npt": dspace_npt,
        "dspace_step": dspace_step
    })
    
    print(f"Bootstrapping kernel with {CHANNEL_NAME} channel and seed {SEED}...")
    kernel.bootstrap(**bootstrap_params)
    print("Kernel bootstrapped. Shadowing map generated.")

    # 3. Create Nodes
    print(f"Creating nodes at (0,0) and ({DISTANCE_METERS}, 0)...")
    
    # Create a dummy app instance for the sink
    sink_app = DummyApp()
    sink_node = CustomTxNode(
        node_id="Node-1",
        linkaddr=(1).to_bytes(2, "big"),
        position=CartesianCoordinate(0.0, 0.0),
        application=sink_app,
        context=kernel.context,
        tx_power=TX_POWER_DBM,  # <-- Using our test parameter
        is_sink=True
    )
    # Manually add node to kernel lists (since we used a custom class)
    kernel.nodes[sink_node.id] = sink_node
    kernel.channel.nodes.append(sink_node)
    sink_node.phy.connect_transmission_media(kernel.channel)

    # Create a dummy app instance for the receiver
    rx_app = DummyApp()
    rx_node = CustomTxNode(
        node_id="Node-2",
        linkaddr=(2).to_bytes(2, "big"),
        position=CartesianCoordinate(DISTANCE_METERS, 0.0),
        application=rx_app,
        context=kernel.context,
        tx_power=TX_POWER_DBM, # <-- Using our test parameter
        is_sink=False
    )
    # Manually add node to kernel lists
    kernel.nodes[rx_node.id] = rx_node
    kernel.channel.nodes.append(rx_node)
    rx_node.phy.connect_transmission_media(kernel.channel)
    
    # 4. Attach Monitor
    print("Attaching custom beacon monitor to Node-2...")
    rssi_mon = BeaconRssiMonitor()
    # We attach to the NET layer (TARP) of the receiving node
    kernel.attach_monitor(rssi_mon, "Node-2.net")

    # 5. Start Applications
    # This is necessary to initialize the DummyApp
    sink_node.app.start()
    rx_node.app.start()

    # 6. Run Simulation
    # The sink node (Node-1) will automatically schedule its first beacon
    # on startup because it's a sink (see TARPProtocol._bootstrap_TARP)
    print(f"\nRunning simulation for {SIM_TIME_SEC} seconds...")
    kernel.run(until=SIM_TIME_SEC)
    
    print("--- Simulation Finished ---")
    
    if not rssi_mon.beacon_received:
        print("\n--- TEST FAILED ---")
        print("Node-2 did NOT receive any beacon.")
        print("This could mean:")
        print(" 1. The beacon was lost entirely (fading/shadowing was too high).")
        print(" 2. The signal was below the PHY correlator threshold (-95 dBm).")
        print(f" 3. The simulation time ({SIM_TIME_SEC}s) was too short (try increasing).")
        print("\nACTION: Try increasing TX_POWER_DBM significantly and run again.")
        print("---------------------\n")
    else:
        print(f"\nTest complete. {len(rssi_mon.rssi_values)} beacon(s) were received and analyzed.")
        print("See RSSI report(s) above.")


if __name__ == "__main__":
    try:
        run_test()
    except Exception as e:
        print(f"\n--- SIMULATION CRASHED ---")
        import traceback
        traceback.print_exc()