from simulator.entities.protocols.common.Layer import Layer
from simulator.entities.common import Entity
from simulator.entities.protocols.common.packets import (
    Frame_802_15_4,
    Ack_802_15_4,
    NetPacket,
    MACFrame,
)
from simulator.entities.protocols.mac.common.mac_events import (
    MacSendReqEvent,
    MacACKTimeoutEvent,
    MacACKSendEvent,
    MacTrySendNextEvent,
)
from collections import deque
from enum import Enum, auto
from typing import Optional

from simulator.entities.common import NetworkNode


class MACState(Enum):
    """define MAC's states"""

    IDLE = auto()
    IN_BACKOFF = auto()
    AWAITING_ACK = auto()
    SENDING_ACK = auto()


"""
This class implements the non-beacon enabled 802.15.4 MAC CSMA protocol AS IT IS IMPLEMENTED in ContikiOS.
This means that it may not be strictly compliant to the IEEE 802.15.4 standard MAC.
Reference to the C implementation of the CSMA in ContikiOS (offical repository):
https://github.com/contiki-os/contiki/blob/master/core/net/mac/csma.c
"""


class ContikiOS_MAC_802154_Unslotted(Layer, Entity):
    macMinBE = 3
    macMaxBE = 5
    macMaxCSMABackoffs = 4
    aUnitBackoffPeriod = 320 * 1e-6
    macMaxFrameRetries = 3
    # Standard IEEE 802.15.4 (2.4 GHz O-QPSK): 54 symbols * 16 us/symbol = 864 us.
    # Derived from: aUnitBackoffPeriod(20) + aTurnaroundTime(12) + SHR_duration(10) + PHR_and_payload_symbols
    macAckWaitDuration = 864 * 1e-6
    aTurnaroundTime = 192 * 1e-6
    next_send_delay = 5e-6  # wait 5 microseconds before sending next packet (NOTE: this time was chosen just to be small enough, it may not be the best time to choose)
    
    # This delay is used if the radio is busy (e.g. receiving)
    # This value MUST be longer than a typical packet reception time.
    radio_busy_retry_delay = 2 * 1e-3 # 2 milliseconds

    def __init__(self, host: NetworkNode):
        Layer.__init__(self, host=host)
        Entity.__init__(self)
        rng_id = f"NODE:{self.host.id}/MAC"
        self.host.context.random_manager.create_stream(rng_id)
        self.rng = self.host.context.random_manager.get_stream(rng_id)

        self.tx_queue = deque()  # packet queue
        self.current_output_frame: Frame_802_15_4 = None
        self.retry_count = 0
        self.pending_ack_timeout_event = None
        self.pending_send_req_event = None
        self.seqn = 0

        # --- LIVELOCK FIX: Flag to prevent scheduling multiple send attempts
        self._try_send_next_scheduled = False

        # init state machine
        self.state = MACState.IDLE
        self._reset_contention_counters()

    def _reset_contention_counters(self):
        self.BE = self.macMinBE
        self.NB = 0

    def _reset_mac_state(self):
        """resest MAC state to IDLE and reset counters"""
        self.state = MACState.IDLE
        self.current_output_frame = None
        self.retry_count = 0
        self._reset_contention_counters()

    def _schedule_try_send_next(self, delay: float):
        """
        Helper function to schedule a _try_send_next event
        only if one is not already pending.
        """
        if self._try_send_next_scheduled:
            return  # An event is already in the queue

        self._try_send_next_scheduled = True
        send_event = MacTrySendNextEvent(
            time=self.host.context.scheduler.now() + delay,
            blame=self,
            callback=self._try_send_next,
        )
        self.host.context.scheduler.schedule(send_event)

    def send(self, payload: NetPacket, destination: Optional[bytes] = None) -> bool:
        """
        Enqueues a packet from the network layer.
        If the MAC is IDLE, it schedules a send attempt.
        """
        nexthop = destination
        requires_ack = nexthop != Frame_802_15_4.broadcast_linkaddr
        mac_frame = Frame_802_15_4(
            seqn=None,
            tx_addr=self.host.linkaddr,
            rx_addr=nexthop,
            requires_ack=requires_ack,
            NPDU=payload,
        )

        self.tx_queue.append(mac_frame)
        
        # Only trigger a new send attempt if the MAC is IDLE.
        # If it's not IDLE (e.g., IN_BACKOFF), the function that
        # transitions back to IDLE is responsible for
        # scheduling the next send attempt.
        if self.state == MACState.IDLE:
            # Use a near-zero delay to run after the current event finishes
            self._schedule_try_send_next(delay=1e-9) 

        return True  # Always accept the packet

    def _try_send_next(self):
        """
        Central control function for sending.
        Checks MAC state, RDC state, and tx_queue.
        """
        
        self._try_send_next_scheduled = False # we are now running, so clear the flag
        
        # Check if MAC is available
        if self.state != MACState.IDLE:
            # Not IDLE. The current operation (e.g., AWAITING_ACK)
            # will schedule a new attempt when it is done, i.e., when it goes back to IDLE.
            return

        ## Check if Radio is busy (e.g., currently receiving a packet)
        #if self.host.rdc.is_radio_busy():
        #    # Radio is busy. We cannot start a send operation.
        #    # Reschedule this check for a later time.
        #    # (the fix for the polling livelock)
        #    self._schedule_try_send_next(delay=self.radio_busy_retry_delay)
        #    return

        # If we are here, MAC is IDLE and Radio is FREE, so we can check the queue and transmit
        if not self.tx_queue:
            return  # Queue is empty, nothing to do

        # Dequeue packet and prepare for transmission
        self.current_output_frame = self.tx_queue.popleft()
        self.seqn = (self.seqn + 1) % 65536 #NOTE: this means that the seqnum should be 8 bytes which doe snot make sense for 802.15.4. Is a temporary fix 
                                            #to make the PDR counters work and not overstimate PDR matching 2 packets with same seqnum but 2 different modulo rounds. 
        self.current_output_frame.seqn = self.seqn

        if self.current_output_frame.rx_addr == Frame_802_15_4.broadcast_linkaddr:
            self.current_output_frame._requires_ack = False

        self.retry_count = 0
        self._reset_contention_counters()
        
        # Set state to IN_BACKOFF *before* starting the backoff process
        self.state = MACState.IN_BACKOFF
        self._backoff_and_send()

    def _backoff_and_send(self, is_retry: bool = False):
        if self.current_output_frame is None:
            return

        # self.state = MACState.IN_BACKOFF # State is set in _try_send_next

        if is_retry:
            if self.retry_count > self.macMaxFrameRetries:
                self._handle_tx_failure()
                return
            self.retry_count += 1
            self._reset_contention_counters()

        if self.NB >= self.macMaxCSMABackoffs:
            self._handle_tx_failure() #if too many backoffs are failed, fail the transmission
            return

        max_slots = (2**self.BE) - 1
        backoff_slots = self.rng.integers(low=0, high=max_slots)
        backoff_time = backoff_slots * self.aUnitBackoffPeriod

        send_req_time = self.host.context.scheduler.now() + backoff_time
        send_req_event = MacSendReqEvent(
            time=send_req_time,
            blame=self,
            callback=self.host.rdc.send,
            payload=self.current_output_frame,
        )

        if self.pending_send_req_event:
            self.host.context.scheduler.unschedule(self.pending_send_req_event)
        self.pending_send_req_event = send_req_event
        self.host.context.scheduler.schedule(self.pending_send_req_event)

    def on_RDCSent(self, packet: MACFrame):
        self.pending_send_req_event = None

        if isinstance(packet, Ack_802_15_4):
            # An ACK was sent. Go back to IDLE and check queue.
            self.state = MACState.IDLE
            self._schedule_try_send_next(delay=self.next_send_delay)
            return

        if self.current_output_frame is None:
            return

        if self.current_output_frame._requires_ack:
            self.state = MACState.AWAITING_ACK
            ack_timeout_time = (
                self.host.context.scheduler.now() + self.macAckWaitDuration
            )
            ack_timeout_event = MacACKTimeoutEvent(
                time=ack_timeout_time,
                blame=self,
                callback=self._backoff_and_send,
                is_retry=True,
            )
            self.pending_ack_timeout_event = ack_timeout_event
            self.host.context.scheduler.schedule(ack_timeout_event)
        else:
            # Broadcast success
            self._handle_tx_success()

    def on_RDCNotSent(self):
        """RDC/PHY reported channel was busy (CCA failed)."""
        self.NB += 1
        self.BE = min(self.BE + 1, self.macMaxBE)
        self._backoff_and_send() # Reschedule backoff and send

    def receive(
        self, payload: Frame_802_15_4 | Ack_802_15_4, sender_addr: bytes, rssi: float
    ):
        if isinstance(payload, Frame_802_15_4):
            if payload._requires_ack:
                # Schedule an ACK
                self.state = MACState.SENDING_ACK
                auto_ack = Ack_802_15_4(seqn=payload.seqn)
                ack_time = self.host.context.scheduler.now() + self.aTurnaroundTime
                send_ack_event = MacACKSendEvent(
                    time=ack_time,
                    blame=self,
                    callback=self.host.rdc.send,
                    payload=auto_ack,
                )
                self.host.context.scheduler.schedule(send_ack_event)

            # Pass payload up to network layer
            self.host.net.receive(
                payload=payload.NPDU, sender_addr=sender_addr, rssi=rssi
            )

            # NOTE: We do not schedule _try_send_next here.
            # If net.receive() calls self.send(), the logic
            # in self.send() will handle it with the delay.
            # If we sent an ACK, on_RDCSent(ACK) will handle it.
            # If we did not send an ACK, we remain IDLE, and
            # self.send() will work normally if called

        elif isinstance(payload, Ack_802_15_4):
            # Received an ACK
            if (
                self.state == MACState.AWAITING_ACK
                and self.current_output_frame
                and payload.seqn == self.current_output_frame.seqn
            ):
                if self.pending_ack_timeout_event:
                    self.host.context.scheduler.unschedule(
                        self.pending_ack_timeout_event
                    )
                    self.pending_ack_timeout_event = None
                self._handle_tx_success(ack_rssi=rssi)

    def _handle_tx_success(self, ack_rssi: float = None):
        if self.pending_send_req_event:
            self.host.context.scheduler.unschedule(self.pending_send_req_event)
            self.pending_send_req_event = None

        if self.current_output_frame.rx_addr != Frame_802_15_4.broadcast_linkaddr:
            self.host.rdc.uc_tx_outcome(
                rx_addr=self.current_output_frame.rx_addr,
                status_ok=True,
                num_tx=self.retry_count,
                ack_rssi=ack_rssi,
            )

        self._reset_mac_state() # Sets state = IDLE
        
        # Check the queue for more packets
        self._schedule_try_send_next(delay=self.next_send_delay)

    def _handle_tx_failure(self):
        if self.pending_send_req_event:
            self.host.context.scheduler.unschedule(self.pending_send_req_event)
            self.pending_send_req_event = None

        if self.current_output_frame.rx_addr != Frame_802_15_4.broadcast_linkaddr:
            self.host.rdc.uc_tx_outcome(
                rx_addr=self.current_output_frame.rx_addr,
                status_ok=False,
                num_tx=self.retry_count,
                ack_rssi=None,
            )
        self._reset_mac_state() # Sets state = IDLE

        # Check the queue for more packets
        self._schedule_try_send_next(delay=self.next_send_delay)
  

