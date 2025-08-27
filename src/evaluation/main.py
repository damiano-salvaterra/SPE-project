# src/evaluation/main.py

import sys
import os
from typing import Optional, TYPE_CHECKING


# --- Python Path Setup ---
# This ensures that the script can find the 'simulator' package when run as a module.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# --- Simulator Imports ---
from simulator.engine.common.monitors import PacketMonitor  # noqa: E402
from simulator.engine.Kernel import Kernel  # noqa: E402
from simulator.environment.geometry import CartesianCoordinate  # noqa: E402
from simulator.applications.Application import Application  # noqa: E402
from simulator.entities.protocols.common.packets import (  # noqa: E402
    NetPacket,
    TARPPacket,
    Frame_802154,
)
from simulator.engine.common.Event import Event  # noqa: E402

if TYPE_CHECKING:
    from simulator.entities.physical.devices.nodes import StaticNode

# ======================================================================================
# ENHANCED LOGGING
# ======================================================================================

LOG_LEVEL = os.getenv(
    "LOG_LEVEL", "DEBUG"
).upper()  # run `export LOG_LEVEL=INFO` in your shell for less verbosity


def log(instance: object, message: str, level: str = "INFO"):
    """A standardized logging function for cleaner, time-stamped output."""
    if LOG_LEVEL == "DEBUG" or level == "INFO":
        time = instance.host.context.scheduler.now()
        node_id = instance.host.id
        # Cerca di identificare il layer per un log più chiaro
        layer_name = instance.__class__.__name__
        print(f"[{time:.6f}s] [{node_id}] [{layer_name}] {message}")


def log_event_execution(event: Event):
    """Callback function to log every event as it is executed by the scheduler."""
    if LOG_LEVEL != "DEBUG":
        return

    time = event.time
    blame = type(event.blame).__name__ if event.blame else "Kernel"
    event_type = type(event).__name__

    details = ""
    if hasattr(event, "transmission"):
        packet_type = type(event.transmission.packet).__name__
        details = f" (Packet: {packet_type})"
    elif hasattr(event, "payload"):
        packet_type = type(event.payload).__name__
        details = f" (Payload: {packet_type})"

    print("------------------------------------------------------------------")
    print(f"[{time:.6f}s] [EVENT] Executing {event_type} from {blame}{details}")
    print("------------------------------------------------------------------")


# ======================================================================================
# TEST APPLICATION: PingPongApp (with retry logic)
# ======================================================================================


class PingPongApp(Application):
    """
        An extended application that continuously exchanges PING and PONG messages.
        - The 'pinger' sends a PING.
        - The 'ponger' replies with a PONG.
        - Upon receiving a PONG, the 'pinger' waits for a defined interval
          and then sends the next PING.
    """

    def __init__(
        self,
        host: Optional["StaticNode"],
        is_pinger: bool = False,
        peer_addr: Optional[bytes] = None,
        ping_interval: float = 60.0,
    ):
        super().__init__()
        self.host = host
        self.is_pinger = is_pinger
        self.peer_addr = peer_addr
        self.ping_count = 0
        self.ping_interval = ping_interval  # Intervallo tra la ricezione di un PONG e l'invio del PING successivo

    def start(self):
        """Called by the main script to start the application's logic."""
        log(self, "Application started.")
        if self.is_pinger:
            # Schedula il primissimo PING dopo un ritardo iniziale per permettere
            # alla rete di stabilizzarsi.
            initial_send_time = 30.0
            log(self, f"Scheduling first PING at t={initial_send_time:.2f}s.")
            start_ping_event = Event(
                time=initial_send_time, blame=self, callback=self.generate_traffic
            )
            self.host.context.scheduler.schedule(start_ping_event)

    def generate_traffic(self) -> None:
        """
        Generates and sends a single PING packet.
        If sending fails because no route is available, it reschedules itself to retry.
        """
        if not self.peer_addr:
            return

        self.ping_count += 1
        payload_str = f"PING #{self.ping_count} from {self.host.id}"
        packet = NetPacket(APDU=payload_str.encode("utf-8"))

        log(
            self,
            f">>> Attempting to send '{payload_str}' to {self.peer_addr.hex()}.",
            level="INFO",
        )

        sent_successfully = self.host.net.send(packet, destination=self.peer_addr)

        # --- MODIFIED LOGIC: RETRY ON FAILURE ---
        if not sent_successfully and self.is_pinger:
            retry_interval = 35.0
            retry_time = self.host.context.scheduler.now() + retry_interval
            log(
                self,
                f"Send failed. Retrying PING at t={retry_time:.2f}s.",
                level="INFO",
            )

            retry_event = Event(
                time=retry_time, blame=self, callback=self.generate_traffic
            )
            self.host.context.scheduler.schedule(retry_event)

    def receive(self, packet: NetPacket, sender_addr: bytes):
        """
        Handles an incoming packet from the network layer.
        - If 'ponger', replies to PINGs with PONGs.
        - If 'pinger', schedules the next PING upon receiving a PONG.
        """
        payload_str = packet.APDU.decode("utf-8", errors="ignore")
        log(
            self,
            f"<<< Received '{payload_str}' from {sender_addr.hex()}.",
            level="INFO",
        )

        # Logica per il NODO PONGER (risponde ai PING)
        if "PING" in payload_str and not self.is_pinger:
            reply_payload_str = f"PONG in response to '{payload_str}'"
            reply_packet = NetPacket(APDU=reply_payload_str.encode("utf-8"))
            log(
                self,
                f">>> Replying with '{reply_payload_str}' to {sender_addr.hex()}.",
                level="INFO",
            )
            self.host.net.send(reply_packet, destination=sender_addr)

        # --- NUOVA LOGICA PER IL NODO PINGER (continua il ciclo) ---
        if "PONG" in payload_str and self.is_pinger:
            # Ha ricevuto una risposta, ora schedula il prossimo PING dopo l'intervallo.
            next_ping_time = self.host.context.scheduler.now() + self.ping_interval
            log(
                self, f"PONG received. Scheduling next PING at t={next_ping_time:.2f}s."
            )

            next_ping_event = Event(
                time=next_ping_time, blame=self, callback=self.generate_traffic
            )
            self.host.context.scheduler.schedule(next_ping_event)


# ======================================================================================
# MAIN SIMULATION SETUP
# ======================================================================================


def run_simulation():
    print("--- Starting Network Stack Test: Ping-Pong (STABLE CHANNEL) ---")

    kernel = Kernel(root_seed=12345)

    # AGGIUNTA: Hook per il logging degli eventi
    kernel.context.scheduler.event_execution_callback = log_event_execution

    # --- MODIFIED PARAMETERS FOR "STABLE" DEBUG CHANNEL ---
    # This configuration uses a numerically stable channel with very little
    # randomness to ensure high reliability for debugging protocol logic.
    kernel.bootstrap(
        seed=12345,
        dspace_step=1,
        dspace_npt=100,
        freq=2.4e9,
        filter_bandwidth=2e6,
        coh_d=50,
        shadow_dev=0.1,  # <-- Very low, non-zero shadowing
        pl_exponent=2.1,  # <-- Path loss slightly better than free-space
        d0=1.0,
        fading_shape=20.0,  # <-- High value minimizes fading effects
    )

    print("\n--- Creating Network Nodes ---")
    addr_node_A = b"\x00\x01"
    addr_node_B = b"\x00\x02"

    node_A = kernel.add_node(
        node_id="Node-A (Pinger, Sink)",
        position=CartesianCoordinate(10, 10),
        app=None,
        linkaddr=addr_node_A,
        is_sink=True,
    )
    node_B = kernel.add_node(
        node_id="Node-B (Ponger)",
        position=CartesianCoordinate(40, 10),
        app=None,
        linkaddr=addr_node_B,
        is_sink=False,
    )

    app_A = PingPongApp(host=node_A, is_pinger=True, peer_addr=addr_node_B)
    node_A.app = app_A
    app_B = PingPongApp(host=node_B, is_pinger=False, peer_addr=addr_node_A)
    node_B.app = app_B

    print("\n--- Attaching Packet Monitor ---")
    packet_monitor = PacketMonitor()

    # Collega il monitor al layer fisico di entrambi i nodi.
    kernel.attach_monitor(packet_monitor, "Node-A (Pinger, Sink).phy")
    kernel.attach_monitor(packet_monitor, "Node-B (Ponger).phy")

    app_A.start()
    app_B.start()

    print("\n--- Running Simulation ---")
    kernel.run(until=200.0)

    print("\n\n--- Simulation Finished ---")
    print(f"Final simulation time: {kernel.context.scheduler.now():.6f}s")

    # AGGIUNTA: Stampa dettagliata della coda eventi finale
    scheduler = kernel.context.scheduler
    queue_len = scheduler.get_queue_length()
    print(f"Events remaining in queue: {queue_len}")

    if queue_len > 0:
        print("\n--- First 5 Events in Queue ---")
        # Mostra i primi 5 eventi senza estrarli
        for i, (time, event) in enumerate(sorted(scheduler.event_queue)[:5]):
            print(
                f"{i+1}: t={time * scheduler._time_scale:.6f}s, Event={type(event).__name__}, Blame={type(event.blame).__name__}, Descriptor: {event.descriptor}, Cancelled: {event._cancelled}"
            )

        print("\n--- Last 5 Events in Queue ---")
        # Mostra gli ultimi 5 eventi senza estrarli
        for i, (time, event) in enumerate(sorted(scheduler.event_queue)[-5:]):
            print(
                f"{queue_len - 5 + i + 1}: t={time * scheduler._time_scale:.6f}s, Event={type(event).__name__}, Blame={type(event.blame).__name__}, Descriptor: {event.descriptor}, Cancelled: {event._cancelled}"
            )


if __name__ == "__main__":
    run_simulation()
