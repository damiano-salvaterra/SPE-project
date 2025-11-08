# src/simulator/entities/applications/PingPongApplication.py
from typing import Optional

from simulator.entities.applications.Application import Application
from simulator.entities.applications.common.app_signals import (
    AppStartSignal,
    AppSendSignal,
    AppReceiveSignal,
    AppTimeoutSignal,
    AppSendFailSignal,
)
from simulator.entities.protocols.common.packets import NetPacket
from simulator.engine.common.Event import Event

from simulator.entities.common import NetworkNode


class PingPongApp(Application):
    """
    A ping pong application that exchanges ping and pong messages between two nodes (mainly for debug).
    """

    PING_TIMEOUT_DURATION = 35.0  # Time to wait for a PONG before retrying
    PING_RETRY_INTERVAL = (
        15.0  # Interval to wait after a failure/PONG before sending next PING
    )

    def __init__(
        self,
        host: Optional[NetworkNode],
        is_pinger: bool = False,
        peer_addr: Optional[bytes] = None,
        ping_interval: float = 15.0,
        start_delay: float = 120.0,
    ):
        super().__init__()
        self.host = host
        self.is_pinger = is_pinger
        self.peer_addr = peer_addr
        self.ping_count = 0
        self.ping_interval = ping_interval
        self.start_delay = start_delay
        self.ping_timeout_event: Optional[Event] = None
        self._started = False

    def start(self):
        self._started = True

        signal = AppStartSignal(
            descriptor="Application started.",
            timestamp=self.host.context.scheduler.now(),
        )
        self._notify_monitors(signal)

        if self.is_pinger:
            start_ping_event = Event(
                time=self.start_delay, blame=self, callback=self.generate_traffic
            )
            self.host.context.scheduler.schedule(start_ping_event)

    def generate_traffic(self):
        """
        Generates and sends a single PING packet, if sending fails, it reschedules itself to retry
        """
        if not self.peer_addr:
            return

        if not self._started:
            return

        if self.ping_timeout_event and not self.ping_timeout_event._cancelled:
            self.host.context.scheduler.unschedule(self.ping_timeout_event)
            self.ping_timeout_event = None

        self.ping_count += 1
        payload_str = f"PING #{self.ping_count} from {self.host.id}"
        packet = NetPacket(APDU=payload_str)

        send_success = self.host.net.send(packet, destination=self.peer_addr)

        if send_success:  # packet accepted by network protocolm set pong timeout
            signal = AppSendSignal(
                descriptor=f"Sent PING #{self.ping_count} to {self.peer_addr.hex()}",
                timestamp=self.host.context.scheduler.now(),
                packet_type="PING",
                seq_num=self.ping_count,
                dest_addr=self.peer_addr,
            )
            self._notify_monitors(signal)

            timeout_time = (
                self.host.context.scheduler.now() + self.PING_TIMEOUT_DURATION
            )
            self.ping_timeout_event = Event(
                time=timeout_time, blame=self, callback=self._on_ping_timeout
            )
            self.host.context.scheduler.schedule(self.ping_timeout_event)
        else:  # pakcet rejected by lower protocol
            signal = AppSendFailSignal(
                descriptor=f"Failed to send PING #{self.ping_count} (No Route)",
                timestamp=self.host.context.scheduler.now(),
                packet_type="PING",
                seq_num=self.ping_count,
                reason="No Route",
            )
            self._notify_monitors(signal)
            self._on_ping_timeout()  # retry

    def _on_ping_timeout(self):

        if self.ping_timeout_event:
            signal = AppTimeoutSignal(
                descriptor=f"PING #{self.ping_count} timed out.",
                timestamp=self.host.context.scheduler.now(),
                seq_num=self.ping_count,
            )
            self._notify_monitors(signal)
            self.ping_timeout_event = None

        # Schedule the next PING attempt
        retry_time = self.host.context.scheduler.now() + self.PING_RETRY_INTERVAL
        next_ping_event = Event(
            time=retry_time, blame=self, callback=self.generate_traffic
        )
        self.host.context.scheduler.schedule(next_ping_event)

    def receive(self, packet: NetPacket, sender_addr: bytes, hops: int = -1):

        payload_str = packet.APDU
        if isinstance(payload_str, bytes):
            payload_str = payload_str.decode("utf-8", errors="ignore")

        def parse_payload(payload_str):
            try:
                if "PING" in payload_str:
                    pkt_type = "PING"
                    seq_num = int(payload_str.split("#")[1].split(" ")[0])
                elif "PONG" in payload_str:
                    pkt_type = "PONG"
                    seq_num = int(payload_str.split("#")[1].split(" ")[0])
                else:
                    pkt_type = "UNKNOWN"
                    seq_num = -1
            except (IndexError, ValueError, TypeError):
                pkt_type = "UNKNOWN"
                seq_num = -1
            return pkt_type, seq_num

        pkt_type, seq_num = parse_payload(payload_str)

        if pkt_type == "UNKNOWN":
            return  #  do not log unknown packets

        signal = AppReceiveSignal(
            descriptor=f"Received {pkt_type} #{seq_num} from {sender_addr.hex()}",
            timestamp=self.host.context.scheduler.now(),
            packet_type=pkt_type,
            seq_num=seq_num,
            source_addr=sender_addr,
            hops=hops,
        )
        self._notify_monitors(signal)

        # --- Logic for Ponger ---
        if pkt_type == "PING" and not self.is_pinger:
            reply_payload_str = f"PONG #{seq_num} from {self.host.id}"
            reply_packet = NetPacket(APDU=reply_payload_str.encode("utf-8"))

            send_pong_success = self.host.net.send(
                reply_packet, destination=sender_addr
            )

            if send_pong_success:
                signal = AppSendSignal(
                    descriptor=f"Sent PONG #{seq_num} to {sender_addr.hex()}",
                    timestamp=self.host.context.scheduler.now(),
                    packet_type="PONG",
                    seq_num=seq_num,
                    dest_addr=sender_addr,
                )
                self._notify_monitors(signal)
            else:
                signal = AppSendFailSignal(
                    descriptor=f"Failed to send PONG #{seq_num} (No Route)",
                    timestamp=self.host.context.scheduler.now(),
                    packet_type="PONG",
                    seq_num=seq_num,
                    reason="No Route",
                )
                self._notify_monitors(signal)

        # --- Logic for Pinger ---
        if pkt_type == "PONG" and self.is_pinger:
            if self.ping_timeout_event and not self.ping_timeout_event._cancelled:
                self.host.context.scheduler.unschedule(self.ping_timeout_event)
                self.ping_timeout_event = None
            else:
                pass  # pong received after timeout

            next_ping_time = self.host.context.scheduler.now() + self.ping_interval
            next_ping_event = Event(
                time=next_ping_time, blame=self, callback=self.generate_traffic
            )
            self.host.context.scheduler.schedule(next_ping_event)
