from typing import Optional

from simulator.applications.Application import Application
from simulator.entities.protocols.common.packets import NetPacket
from simulator.engine.common.Event import Event

from simulator.entities.common import NetworkNode


class PingPongApp(Application):
    """
    A ping pong application that exchanges ping and pong messages between two nodes.
    """

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
        self.ping_interval = ping_interval

    def start(self):
        """Called by the main script to start the application's logic"""
        print(f"{self.__class__.__name__}: Application started.")
        if self.is_pinger:
            initial_send_time = 30.0  # wait a bit for the network to converge
            print(
                f"{self.__class__.__name__}: Scheduling first PING at t={initial_send_time:.2f}s."
            )
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

        self.ping_count += 1
        payload_str = f"PING #{self.ping_count} from {self.host.id}"
        packet = NetPacket(APDU=payload_str)

        print(
            f"{self.__class__.__name__}: >>> Attempting to send '{payload_str}' to {self.peer_addr.hex()}."
        )

        sent_successfully = self.host.net.send(packet, destination=self.peer_addr)

        if not sent_successfully and self.is_pinger:
            retry_interval = 35.0
            retry_time = self.host.context.scheduler.now() + retry_interval
            print(
                f"{self.__class__.__name__}: Send failed. Retrying PING at t={retry_time:.2f}s."
            )

            retry_event = Event(
                time=retry_time, blame=self, callback=self.generate_traffic
            )
            self.host.context.scheduler.schedule(retry_event)

    def receive(self, packet: NetPacket, sender_addr: bytes):
        """
        Handles an incoming packet from the network layer
        """
        # Decode the payload from bytes to a string
        payload_str = packet.APDU
        if isinstance(payload_str, bytes):
            payload_str = payload_str.decode("utf-8")

        print(
            f"{self.__class__.__name__}: <<< Received '{payload_str}' from {sender_addr.hex()}."
        )

        if "PING" in payload_str and not self.is_pinger:
            # Extract the sequence number from the PING to include it in the PONG response
            try:
                seqn = int(payload_str.split("#")[1].split(" ")[0])
                reply_payload_str = (
                    f"PONG #{seqn} in response to 'PING #{seqn} from {self.host.id}'"
                )
            except (IndexError, ValueError):
                reply_payload_str = f"PONG in response to '{payload_str}'"

            reply_packet = NetPacket(APDU=reply_payload_str.encode("utf-8"))
            print(
                f"{self.__class__.__name__}: >>> Replying with '{reply_payload_str}' to {sender_addr.hex()}."
            )
            self.host.net.send(reply_packet, destination=sender_addr)

        if "PONG" in payload_str and self.is_pinger:
            next_ping_time = self.host.context.scheduler.now() + self.ping_interval
            print(
                f"{self.__class__.__name__}: PONG received. Scheduling next PING at t={next_ping_time:.2f}s."
            )

            next_ping_event = Event(
                time=next_ping_time, blame=self, callback=self.generate_traffic
            )
            self.host.context.scheduler.schedule(next_ping_event)
