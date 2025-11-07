# src/simulator/applications/PoissonTrafficApplication.py
import sys
from typing import Optional, Dict, List, Any

from simulator.entities.applications.Application import Application
from simulator.entities.common import NetworkNode
from simulator.entities.protocols.common.packets import NetPacket
from simulator.engine.common.Event import Event
from simulator.engine.random import RandomGenerator
from simulator.entities.applications.common.app_signals import (
    AppStartSignal,
    AppSendSignal,
    AppReceiveSignal,
    AppSendFailSignal,
)


class PoissonTrafficApplication(Application):
    """
    Application that generates network traffic to random destinations
    with a poisson process

    """

    def __init__(
        self,
        host: Optional[NetworkNode],
        all_nodes: Dict[str, bytes],
        mean_interarrival_time: float = 60.0,
        start_delay: float = 120.0,
    ):
        super().__init__()
        self.host = host
        self._all_nodes = all_nodes
        self.mean_interarrival_time = mean_interarrival_time
        self.start_delay = start_delay

        self.rng: Optional[RandomGenerator] = (
            None  # initialized in start() since is host dependent
        )
        self.destinations: List[bytes] = []
        self.packet_counter = 0

    def start(self):

        if self.host is None:
            raise ValueError("Application host has not been set before start()")

        # Init RNG stream for this application
        rng_id = f"NODE:{self.host.id}/RANDOM_TRAFFIC_APP"
        self.host.context.random_manager.create_stream(rng_id)
        self.rng = self.host.context.random_manager.get_stream(rng_id)

        # Populate the list of possible destinations
        self.destinations = [
            addr for node_id, addr in self._all_nodes.items() if node_id != self.host.id
        ]

        signal = AppStartSignal(
            descriptor=f"RandomTrafficApp started.",
            timestamp=self.host.context.scheduler.now(),
        )
        self._notify_monitors(signal)

        if not self.destinations:
            # Log to stdeerr
            print(
                f"[{self.host.context.scheduler.now():.6f}s] [{self.host.id}] "
                f"RandomTrafficApp: No destinations to send to.",
                file=sys.stderr,
            )
            return

        # Add a random jitter to the delay
        # to prevent all nodes from sending at the same time
        initial_jitter = self.rng.uniform(low=0.0, high=30.0)
        initial_send_time = self.start_delay + initial_jitter

        start_traffic_event = Event(
            time=initial_send_time,
            blame=self,
            callback=self._send_packet_and_reschedule,  # this starts the poisson prccess
        )
        self.host.context.scheduler.schedule(start_traffic_event)

    def _schedule_next_send(self):
        if self.rng is None:
            return  # Not started

        interarrival_time = self.rng.exponential(scale=self.mean_interarrival_time)

        next_send_time = self.host.context.scheduler.now() + interarrival_time

        send_event = Event(
            time=next_send_time, blame=self, callback=self._send_packet_and_reschedule
        )
        self.host.context.scheduler.schedule(send_event)

    def _send_packet_and_reschedule(self):
        """
        Creates and sends a single packet, then schedules the next one
        """
        if not self.destinations or self.rng is None:
            print(
                f"[{self.host.context.scheduler.now():.6f}s] [{self.host.id}] "
                f"RandomTrafficApp: Cannot send, no destinations or RNG.",
                file=sys.stderr,
            )
            return

        # select a random destination
        dest_addr = self.rng.choice(self.destinations)
        self.packet_counter += 1

        payload_str = f"DATA #{self.packet_counter} from {self.host.id}"
        packet = NetPacket(APDU=payload_str.encode("utf-8"))

        send_success = self.host.net.send(packet, destination=dest_addr)

        if send_success:
            signal = AppSendSignal(
                descriptor=f"Sent DATA #{self.packet_counter} to {dest_addr.hex()}",
                timestamp=self.host.context.scheduler.now(),
                packet_type="DATA",
                seq_num=self.packet_counter,
                destination=dest_addr,
            )
            self._notify_monitors(signal)
        else:
            signal = AppSendFailSignal(
                descriptor=f"Failed to send DATA #{self.packet_counter} (No Route)",
                timestamp=self.host.context.scheduler.now(),
                packet_type="DATA",
                seq_num=self.packet_counter,
                reason="No Route",
            )
            self._notify_monitors(signal)

        # schedule the next packet send
        self._schedule_next_send()

    def receive(self, packet: NetPacket, sender_addr: bytes, hops: int = -1):

        payload_str = packet.APDU
        if isinstance(payload_str, bytes):
            payload_str = payload_str.decode("utf-8", errors="ignore")

        # try to parse sequence number
        seq_num = -1
        try:
            if "DATA #" in payload_str:
                seq_num = int(payload_str.split("#")[1].split(" ")[0])
        except (IndexError, ValueError, TypeError):
            pass

        signal = AppReceiveSignal(
            descriptor=f"Received DATA #{seq_num} from {sender_addr.hex()}",
            timestamp=self.host.context.scheduler.now(),
            packet_type="DATA",
            seq_num=seq_num,
            source=sender_addr,
            hops=hops,
        )
        self._notify_monitors(signal)

    def generate_traffic(self) -> None:
        """
        This method is required by the base class but not used: the 'start()' method begins the traffic generation loop.
        """
        pass
