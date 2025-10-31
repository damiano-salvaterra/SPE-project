from typing import Optional

from simulator.applications.Application import Application
from evaluation.signals.app_signals import (
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
    A ping pong application that exchanges ping and pong messages between two nodes.
    This version is refactored to use the monitoring system instead of print().
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
    ):
        super().__init__()
        self.host = host
        self.is_pinger = is_pinger
        self.peer_addr = peer_addr
        self.ping_count = 0
        self.ping_interval = ping_interval  # Used as interval *after* a PONG is received
        self.ping_timeout_event: Optional[Event] = None
        self._started = False

    def start(self):
        """Called by the main script to start the application's logic"""
        self._started = True
        
        signal = AppStartSignal(
            descriptor=f"[{self.host.id}] Application started.",
            timestamp=self.host.context.scheduler.now(),
        )
        self._notify_monitors(signal)

        if self.is_pinger:
            initial_send_time = 120.0
            start_ping_event = Event(
                time=initial_send_time, blame=self, callback=self.generate_traffic
            )
            self.host.context.scheduler.schedule(start_ping_event)

    def generate_traffic(self):
        """
        Generates and sends a single PING packet.
        If sending fails because no route is available, it reschedules itself to retry.
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

        send_success = False
        try:
            send_success = self.host.net.send(packet, destination=self.peer_addr)
        except Exception:
            send_success = False  # Ensure it's false on exception

        if send_success:
            # --- Packet was accepted by TARP, set a PONG timeout ---
            signal = AppSendSignal(
                descriptor=f"[{self.host.id}] Sent PING #{self.ping_count} to {self.peer_addr.hex()}",
                timestamp=self.host.context.scheduler.now(),
                packet_type="PING",
                seq_num=self.ping_count,
                destination=self.peer_addr,
            )
            self._notify_monitors(signal)
            
            timeout_time = self.host.context.scheduler.now() + self.PING_TIMEOUT_DURATION
            self.ping_timeout_event = Event(
                time=timeout_time, blame=self, callback=self._on_ping_timeout
            )
            self.host.context.scheduler.schedule(self.ping_timeout_event)
        else:
            # --- Packet was REJECTED by TARP (e.g., no route/no parent) ---
            signal = AppSendFailSignal(
                descriptor=f"[{self.host.id}] Failed to send PING #{self.ping_count} (No Route)",
                timestamp=self.host.context.scheduler.now(),
                packet_type="PING",
                seq_num=self.ping_count,
                reason="No Route",
            )
            self._notify_monitors(signal)
            # We treat this as an immediate "timeout" to trigger the retry logic
            self._on_ping_timeout()

    def _on_ping_timeout(self):
        """
        This callback is triggered if a PONG is not received within
        PING_TIMEOUT_DURATION, OR if net.send() failed immediately.
        """
        
        # Check if this timeout is for a PING that was actually sent
        # (i.e., not a net.send() failure)
        if self.ping_timeout_event:
            signal = AppTimeoutSignal(
                descriptor=f"[{self.host.id}] PING #{self.ping_count} timed out.",
                timestamp=self.host.context.scheduler.now(),
                seq_num=self.ping_count,
            )
            self._notify_monitors(signal)
            self.ping_timeout_event = None  # Clear the event tracker
        
        # Schedule the next PING attempt
        retry_time = self.host.context.scheduler.now() + self.PING_RETRY_INTERVAL
        next_ping_event = Event(
            time=retry_time, blame=self, callback=self.generate_traffic
        )
        self.host.context.scheduler.schedule(next_ping_event)

    def receive(self, packet: NetPacket, sender_addr: bytes):
        """
        Handles an incoming packet from the network layer
        """
        payload_str = packet.APDU
        if isinstance(payload_str, bytes):
            payload_str = payload_str.decode("utf-8", errors="ignore")

        # --- Helper to parse payload ---
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
            return # Don't log unknown packets

        # --- Notify monitor about reception ---
        signal = AppReceiveSignal(
            descriptor=f"[{self.host.id}] Received {pkt_type} #{seq_num} from {sender_addr.hex()}",
            timestamp=self.host.context.scheduler.now(),
            packet_type=pkt_type,
            seq_num=seq_num,
            source=sender_addr,
        )
        self._notify_monitors(signal)


        # --- Logic for Ponger (Node-L) ---
        if pkt_type == "PING" and not self.is_pinger:
            reply_payload_str = f"PONG #{seq_num} from {self.host.id}"
            reply_packet = NetPacket(APDU=reply_payload_str.encode("utf-8"))
            
            send_pong_success = False
            try:
                send_pong_success = self.host.net.send(reply_packet, destination=sender_addr)
            except Exception:
                send_pong_success = False

            if send_pong_success:
                signal = AppSendSignal(
                    descriptor=f"[{self.host.id}] Sent PONG #{seq_num} to {sender_addr.hex()}",
                    timestamp=self.host.context.scheduler.now(),
                    packet_type="PONG",
                    seq_num=seq_num,
                    destination=sender_addr,
                )
                self._notify_monitors(signal)
            else:
                signal = AppSendFailSignal(
                    descriptor=f"[{self.host.id}] Failed to send PONG #{seq_num} (No Route)",
                    timestamp=self.host.context.scheduler.now(),
                    packet_type="PONG",
                    seq_num=seq_num,
                    reason="No Route",
                )
                self._notify_monitors(signal)


        # --- Logic for Pinger (Node-D) ---
        if pkt_type == "PONG" and self.is_pinger:
            if self.ping_timeout_event and not self.ping_timeout_event._cancelled:
                # PONG received *before* timeout
                self.host.context.scheduler.unschedule(self.ping_timeout_event)
                self.ping_timeout_event = None
            else:
                # PONG was received *after* the timeout already fired.
                # We still log it, but don't need to cancel anything.
                pass

            next_ping_time = self.host.context.scheduler.now() + self.ping_interval
            next_ping_event = Event(
                time=next_ping_time, blame=self, callback=self.generate_traffic
            )
            self.host.context.scheduler.schedule(next_ping_event)
