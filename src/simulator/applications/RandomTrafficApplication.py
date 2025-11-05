import sys
from typing import Optional, Dict, List, Any

from simulator.applications.Application import Application
from simulator.entities.common import NetworkNode
from simulator.entities.protocols.common.packets import NetPacket
from simulator.engine.common.Event import Event
from simulator.engine.random import RandomGenerator
from evaluation.signals.app_signals import (
    AppStartSignal,
    AppSendSignal,
    AppReceiveSignal,
    AppSendFailSignal
)

class RandomTrafficApplication(Application):
    """
    An application that generates network traffic to random destinations
    with exponentially distributed inter-arrival times (a Poisson process).
    
    This refactored version:
    1. Complies with the Application base class and signal/monitor system.
    2. Initializes the RNG and destination list in start() to avoid host=None errors.
    3. Continuously schedules packet sends to form a Poisson process.
    """

    def __init__(
        self,
        host: Optional[NetworkNode],
        all_nodes: Dict[str, bytes],
        mean_interarrival_time: float = 60.0
    ):
        """
        Initializes the application.
        
        Args:
            host: The node hosting this application (will be None at init).
            all_nodes: A dictionary mapping all node_ids (str) to their 
                       linkaddrs (bytes).
            mean_interarrival_time: The mean time (in seconds) between packet
                                  sends (the 'scale' parameter for the
                                  exponential distribution).
        """
        super().__init__()
        self.host = host
        self._all_nodes = all_nodes
        self.mean_interarrival_time = mean_interarrival_time
        
        # Will be initialized in start()
        self.rng: Optional[RandomGenerator] = None
        self.destinations: List[bytes] = []
        self.packet_counter = 0

    def start(self):
        """
        Called by the main script to start the application's logic.
        This is where we initialize components that depend on the host.
        """
        if self.host is None:
            raise ValueError("Application host has not been set before start()")

        # 1. Initialize RNG stream for this application
        rng_id = f"NODE:{self.host.id}/RANDOM_TRAFFIC_APP"
        self.host.context.random_manager.create_stream(rng_id)
        self.rng = self.host.context.random_manager.get_stream(rng_id)

        # 2. Populate the list of possible destinations (all nodes except self)
        self.destinations = [
            addr for node_id, addr in self._all_nodes.items()
            if node_id != self.host.id
        ]
        
        # 3. Emit start signal
        signal = AppStartSignal(
            descriptor=f"[{self.host.id}] RandomTrafficApp started.",
            timestamp=self.host.context.scheduler.now(),
        )
        self._notify_monitors(signal)
        
        if not self.destinations:
            print(f"[{self.host.context.scheduler.now():.6f}s] [{self.host.id}] "
                  f"RandomTrafficApp: No destinations to send to.", file=sys.stderr)
            return

        # 4. Schedule the first packet send
        self._schedule_next_send()

    def _schedule_next_send(self):
        """
        Schedules the next _send_packet_and_reschedule event using an 
        exponential delay to model a Poisson process.
        """
        if self.rng is None:
            return # Not started

        # Get the delay until the next packet
        interarrival_time = self.rng.exponential(scale=self.mean_interarrival_time)
        
        next_send_time = self.host.context.scheduler.now() + interarrival_time

        send_event = Event(
            time=next_send_time,
            blame=self,
            callback=self._send_packet_and_reschedule
        )
        self.host.context.scheduler.schedule(send_event)

    def _send_packet_and_reschedule(self):
        """
        Creates and sends a single packet, then schedules the next one.
        This function is the callback for the scheduled Event.
        """
        if not self.destinations or self.rng is None:
            print(f"[{self.host.context.scheduler.now():.6f}s] [{self.host.id}] "
                  f"RandomTrafficApp: Cannot send, no destinations or RNG.", file=sys.stderr)
            return

        # 1. Select a random destination
        dest_addr = self.rng.choice(self.destinations)
        self.packet_counter += 1
        
        # 2. Create payload and packet
        payload_str = f"DATA #{self.packet_counter} from {self.host.id}"
        packet = NetPacket(APDU=payload_str.encode("utf-8"))

        # 3. Try to send
        # --- REMOVED try...except block ---
        # Any exception here (e.g., from TARP) will halt the simulation
        # for debugging, which is the desired behavior.
        send_success = self.host.net.send(packet, destination=dest_addr)

        # 4. Emit signals based on outcome
        if send_success:
            signal = AppSendSignal(
                descriptor=f"[{self.host.id}] Sent DATA #{self.packet_counter} to {dest_addr.hex()}",
                timestamp=self.host.context.scheduler.now(),
                packet_type="DATA",
                seq_num=self.packet_counter,
                destination=dest_addr,
            )
            self._notify_monitors(signal)
        else:
            signal = AppSendFailSignal(
                descriptor=f"[{self.host.id}] Failed to send DATA #{self.packet_counter} (No Route)",
                timestamp=self.host.context.scheduler.now(),
                packet_type="DATA",
                seq_num=self.packet_counter,
                reason="No Route",
            )
            self._notify_monitors(signal)
            
        # 5. Schedule the next packet send to continue the process
        self._schedule_next_send()

    def receive(self, packet: NetPacket, sender_addr: bytes, hops: int = -1):
        """
        Handles an incoming packet from the network layer.
        (Complies with Application base class and PingPongApp signature)
        """
        payload_str = packet.APDU
        if isinstance(payload_str, bytes):
            payload_str = payload_str.decode("utf-8", errors="ignore")

        # Try to parse sequence number
        seq_num = -1
        try:
            if "DATA #" in payload_str:
                seq_num = int(payload_str.split("#")[1].split(" ")[0])
        except (IndexError, ValueError, TypeError):
            pass # Failed to parse, seq_num remains -1

        # Emit receive signal
        signal = AppReceiveSignal(
            descriptor=f"[{self.host.id}] Received DATA #{seq_num} from {sender_addr.hex()}",
            timestamp=self.host.context.scheduler.now(),
            packet_type="DATA",
            seq_num=seq_num,
            source=sender_addr,
            hops=hops
        )
        self._notify_monitors(signal)

    def generate_traffic(self) -> None:
        """
        This method is required by the base class but not used directly.
        The 'start()' method begins the traffic generation loop.
        """
        pass