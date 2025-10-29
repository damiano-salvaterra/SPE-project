from typing import Optional

from simulator.applications.Application import Application
from evaluation.signals.app_signals import AppPingReceivedSignal
from simulator.entities.protocols.common.packets import NetPacket
from simulator.engine.common.Event import Event

from simulator.entities.common import NetworkNode


class PingPongApp(Application):
    """
    A ping pong application that exchanges ping and pong messages between two nodes.
    """

    PING_TIMEOUT_DURATION = 35.0  # Time to wait for a PONG before retrying
    PING_RETRY_INTERVAL = 15.0    # Interval to wait after a failure/PONG before sending next PING
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
        self.ping_interval = ping_interval # Used as interval *after* a PONG is received
        self.ping_timeout_event: Optional[Event] = None
        # DEBUG: Add a flag to track if start was called
        self._started = False

    def start(self):
        """Called by the main script to start the application's logic"""
        # DEBUG: Confirm start is called
        print(f"[DEBUG][{self.host.context.scheduler.now():.6f}s][{self.host.id}] PingPongApp.start() called.")
        self._started = True
        print(f"{self.__class__.__name__}: Application started.")
        if self.is_pinger:
            initial_send_time = 120.0
            print(
                f"{self.__class__.__name__}: Scheduling first PING at t={initial_send_time:.2f}s."
            )
            start_ping_event = Event(
                time=initial_send_time, blame=self, callback=self.generate_traffic
            )
            # DEBUG: Confirm event scheduling
            print(f"[DEBUG][{self.host.context.scheduler.now():.6f}s][{self.host.id}] Scheduling start_ping_event for t={start_ping_event.time:.6f}s")
            self.host.context.scheduler.schedule(start_ping_event)
        # DEBUG: Log if not pinger
        else:
            print(f"[DEBUG][{self.host.context.scheduler.now():.6f}s][{self.host.id}] This node is not the pinger.")

    def generate_traffic(self):
        """
        Generates and sends a single PING packet.
        If sending fails because no route is available, it reschedules itself to retry.
        """
        # DEBUG: Confirm this callback is executed
        print(f"[DEBUG][{self.host.context.scheduler.now():.6f}s][{self.host.id}] PingPongApp.generate_traffic() CALLED.")

        if not self.peer_addr:
             # DEBUG: Log reason for returning early
            print(f"[DEBUG][{self.host.context.scheduler.now():.6f}s][{self.host.id}] generate_traffic: No peer_addr set. Returning.")
            return

        # DEBUG: Check if started flag is set (sanity check)
        if not self._started:
            print(f"[DEBUG][{self.host.context.scheduler.now():.6f}s][{self.host.id}] generate_traffic: Called before start()?. Returning.")
            return


        if self.ping_timeout_event and not self.ping_timeout_event._cancelled:
            # DEBUG: Log timeout cancellation
            print(f"[DEBUG][{self.host.context.scheduler.now():.6f}s][{self.host.id}] generate_traffic: Cancelling pending timeout event ID {self.ping_timeout_event._unique_id}.")
            self.host.context.scheduler.unschedule(self.ping_timeout_event)
            self.ping_timeout_event = None

        self.ping_count += 1
        payload_str = f"PING #{self.ping_count} from {self.host.id}"
        packet = NetPacket(APDU=payload_str)

        print(
            f"[{self.host.context.scheduler.now():.6f}s] [{self.host.id}] "
            f"{self.__class__.__name__}: >>> Attempting to send '{payload_str}' to {self.peer_addr.hex()}."
        )

        # DEBUG: Add try-except around the send call
        send_success = False
        try:
            print(f"[DEBUG][{self.host.context.scheduler.now():.6f}s][{self.host.id}] generate_traffic: Calling self.host.net.send().")
            send_success = self.host.net.send(packet, destination=self.peer_addr)
            # DEBUG: Log the result of the send call
            print(f"[DEBUG][{self.host.context.scheduler.now():.6f}s][{self.host.id}] generate_traffic: self.host.net.send() returned: {send_success}")
        except Exception as e:
            # DEBUG: Catch potential exceptions during send
             print(f"[DEBUG][{self.host.context.scheduler.now():.6f}s][{self.host.id}] generate_traffic: EXCEPTION during self.host.net.send(): {e}")
             # Optionally re-raise or handle appropriately
             # raise e # Re-raise if you want the simulation to stop

        # DEBUG: Log whether send was deemed successful or not by the layer below
        if not send_success:
             print(f"[DEBUG][{self.host.context.scheduler.now():.6f}s][{self.host.id}] generate_traffic: net.send reported failure (returned False or threw exception).")
        # Even if net.send returns False, we still rely on the timeout mechanism below


        timeout_time = self.host.context.scheduler.now() + self.PING_TIMEOUT_DURATION
        print(
            f"[{self.host.context.scheduler.now():.6f}s] [{self.host.id}] "
            f"{self.__class__.__name__}: PING sent (or attempted). Waiting for PONG. Timeout set for t={timeout_time:.2f}s."
        )
        self.ping_timeout_event = Event(
            time=timeout_time,
            blame=self,
            callback=self._on_ping_timeout
        )
        # DEBUG: Log scheduling of timeout
        print(f"[DEBUG][{self.host.context.scheduler.now():.6f}s][{self.host.id}] Scheduling ping_timeout_event ID {self.ping_timeout_event._unique_id} for t={self.ping_timeout_event.time:.6f}s")
        self.host.context.scheduler.schedule(self.ping_timeout_event)

    def _on_ping_timeout(self):
        """
        # This callback is triggered if a PONG is not received within
        # PING_TIMEOUT_DURATION.
        """
        # DEBUG: Confirm timeout callback execution
        print(f"[DEBUG][{self.host.context.scheduler.now():.6f}s][{self.host.id}] PingPongApp._on_ping_timeout() CALLED for PING #{self.ping_count}.")
        print(
            f"[{self.host.context.scheduler.now():.6f}s] [{self.host.id}] "
            f"{self.__class__.__name__}: --- PING #{self.ping_count} TIMED OUT ---"
        )
        self.ping_timeout_event = None # Clear the event tracker

        retry_time = self.host.context.scheduler.now() + self.PING_RETRY_INTERVAL
        print(
            f"[{self.host.context.scheduler.now():.6f}s] [{self.host.id}] "
            f"{self.__class__.__name__}: Scheduling next PING attempt at t={retry_time:.2f}s."
        )

        next_ping_event = Event(
            time=retry_time, blame=self, callback=self.generate_traffic
        )
        # DEBUG: Log scheduling of retry ping
        print(f"[DEBUG][{self.host.context.scheduler.now():.6f}s][{self.host.id}] Scheduling next_ping_event (retry) ID {next_ping_event._unique_id} for t={next_ping_event.time:.6f}s")
        self.host.context.scheduler.schedule(next_ping_event)


    def receive(self, packet: NetPacket, sender_addr: bytes):
        """
        Handles an incoming packet from the network layer
        """
        # DEBUG: Confirm receive is called
        print(f"[DEBUG][{self.host.context.scheduler.now():.6f}s][{self.host.id}] PingPongApp.receive() CALLED from {sender_addr.hex()}.")

        payload_str = packet.APDU
        if isinstance(payload_str, bytes):
            # DEBUG: Log payload decoding
            print(f"[DEBUG][{self.host.context.scheduler.now():.6f}s][{self.host.id}] Decoding payload from bytes.")
            payload_str = payload_str.decode("utf-8")

        print(
            f"{self.__class__.__name__}: <<< Received '{payload_str}' from {sender_addr.hex()}."
        )

        # DEBUG: Confirm monitor notification
        if payload_str.startswith("PING") or payload_str.startswith("PONG"):
            print(f"[DEBUG][{self.host.context.scheduler.now():.6f}s][{self.host.id}] Notifying monitors about received packet.")
            signal = AppPingReceivedSignal(
                descriptor="PING/PONG received at application layer",
                timestamp=self.host.context.scheduler.now(),
                packet=packet,
                source_addr=sender_addr,
            )
            self._notify_monitors(signal)

        # --- Logic for Ponger (Node-L) ---
        if "PING" in payload_str and not self.is_pinger:
            # DEBUG: Ponger received PING
            print(f"[DEBUG][{self.host.context.scheduler.now():.6f}s][{self.host.id}] Ponger received PING. Preparing PONG.")
            try:
                seqn = int(payload_str.split("#")[1].split(" ")[0])
                reply_payload_str = (
                    f"PONG #{seqn} in response to 'PING #{seqn} from {self.host.id}'" # Adjusted reply format slightly
                )
            except (IndexError, ValueError):
                 # DEBUG: Error parsing PING sequence number
                print(f"[DEBUG][{self.host.context.scheduler.now():.6f}s][{self.host.id}] Error parsing PING seqn. Using generic PONG.")
                reply_payload_str = f"PONG in response to '{payload_str}'"

            reply_packet = NetPacket(APDU=reply_payload_str.encode("utf-8"))
            print(
                f"{self.__class__.__name__}: >>> Replying with '{reply_payload_str}' to {sender_addr.hex()}."
            )
             # DEBUG: Add try-except for Ponger's send
            try:
                print(f"[DEBUG][{self.host.context.scheduler.now():.6f}s][{self.host.id}] Ponger calling self.host.net.send() for PONG.")
                send_pong_success = self.host.net.send(reply_packet, destination=sender_addr)
                print(f"[DEBUG][{self.host.context.scheduler.now():.6f}s][{self.host.id}] Ponger self.host.net.send() returned: {send_pong_success}")
            except Exception as e:
                print(f"[DEBUG][{self.host.context.scheduler.now():.6f}s][{self.host.id}] Ponger EXCEPTION during self.host.net.send(): {e}")

        # --- Logic for Pinger (Node-D) ---
        if "PONG" in payload_str and self.is_pinger:
             # DEBUG: Pinger received PONG
            print(f"[DEBUG][{self.host.context.scheduler.now():.6f}s][{self.host.id}] Pinger received PONG.")

            if self.ping_timeout_event and not self.ping_timeout_event._cancelled:
                 # DEBUG: Log timeout cancellation due to PONG
                print(f"[DEBUG][{self.host.context.scheduler.now():.6f}s][{self.host.id}] PONG received. Cancelling pending timeout event ID {self.ping_timeout_event._unique_id}.")
                print(
                    f"[{self.host.context.scheduler.now():.6f}s] [{self.host.id}] "
                    f"{self.__class__.__name__}: PONG received. Cancelling timeout."
                )
                self.host.context.scheduler.unschedule(self.ping_timeout_event)
                self.ping_timeout_event = None
            else:
                 # DEBUG: Log late PONG or no pending timeout
                print(f"[DEBUG][{self.host.context.scheduler.now():.6f}s][{self.host.id}] PONG received, but no active timeout event found (ID: {self.ping_timeout_event._unique_id if self.ping_timeout_event else 'None'}). Was it late?")
                print(
                    f"[{self.host.context.scheduler.now():.6f}s] [{self.host.id}] "
                    f"{self.__class__.__name__}: PONG received (but was late or no timeout was pending)."
                )

            next_ping_time = self.host.context.scheduler.now() + self.ping_interval
            print(
                f"[{self.host.context.scheduler.now():.6f}s] [{self.host.id}] "
                f"{self.__class__.__name__}: Scheduling next PING at t={next_ping_time:.2f}s."
            )

            next_ping_event = Event(
                time=next_ping_time, blame=self, callback=self.generate_traffic
            )
             # DEBUG: Log scheduling of next ping after PONG
            print(f"[DEBUG][{self.host.context.scheduler.now():.6f}s][{self.host.id}] Scheduling next_ping_event (after PONG) ID {next_ping_event._unique_id} for t={next_ping_event.time:.6f}s")
            self.host.context.scheduler.schedule(next_ping_event)