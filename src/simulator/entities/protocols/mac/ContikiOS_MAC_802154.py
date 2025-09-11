from simulator.entities.protocols.common.Layer import Layer
from simulator.entities.common.Entity import Entity
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

    def __init__(self, host: NetworkNode):
        Layer.__init__(self, host=host)
        Entity.__init__(self)
        rng_id = f"NODE:{self.host.id}/MAC"
        self.host.context.random_manager.create_stream(rng_id)
        self.rng = self.host.context.random_manager.get_stream(rng_id)

        self.tx_queue = deque()  # packet queue
        self.current_output_frame: Frame_802_15_4 = None
        self.retry_count = 0
        self.pending_ack_timeout_event = None  # reference to the MacACKTimeoutEvent. Needs to be stored to abort the timeout in case of ack received
        self.pending_send_req_event = None  # reference to the next MacSendReqEvent. Needs to be stored to abort the send in case of ack received (or max retru reached)
        self.seqn = 0

        # init state machine
        self.state = MACState.IDLE
        # self._last_received_rssi: float = -150.0
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

    def send(self, payload: NetPacket, destination: Optional[bytes] = None):
        nexthop = destination  # for compatibility with the Layer interface
        requires_ack = nexthop != Frame_802_15_4.broadcast_linkaddr
        mac_frame = Frame_802_15_4(
            seqn=None,
            tx_addr=self.host.linkaddr,
            rx_addr=nexthop,
            requires_ack=requires_ack,
            NPDU=payload,
        )

        self.tx_queue.append(mac_frame)
        # if mac is idle, than send next packet in queue
        if self.state == MACState.IDLE and not self.host.rdc.is_radio_busy():
            send_delay = 1e-6
            send_event = MacTrySendNextEvent(
                time=self.host.context.scheduler.now() + send_delay,
                blame=self,
                callback=self._try_send_next,
            )
            self.host.context.scheduler.schedule(send_event)

    def _try_send_next(self):
        # if there is nothing to send or the mac is not idle, do nothing
        if not self.tx_queue or self.state != MACState.IDLE:
            return

        self.current_output_frame = self.tx_queue.popleft()
        self.seqn = (self.seqn + 1) % 256
        self.current_output_frame.seqn = (
            self.seqn
        )  # assign MAC seq number to the frame (for ACK recognition)

        if self.current_output_frame.rx_addr == Frame_802_15_4.broadcast_linkaddr:
            self.current_output_frame._requires_ack = False

        self.retry_count = 0
        self._reset_contention_counters()
        self._backoff_and_send()

    def _backoff_and_send(self, is_retry: bool = False):
        if self.current_output_frame is None:
            return

        self.state = MACState.IN_BACKOFF  # enter backoff state

        if is_retry:
            if self.retry_count > self.macMaxFrameRetries:
                self._handle_tx_failure()
                return
            self.retry_count += 1
            self._reset_contention_counters()

        if self.NB >= self.macMaxCSMABackoffs:
            self._handle_tx_failure()
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
            # if it an ACK was sent, the transaction is finished (from this side of the link): get back to idle
            self.state = MACState.IDLE
            # you can try to send the next enqueued packet
            send_next_time = self.host.context.scheduler.now() + self.next_send_delay
            send_next_event = MacTrySendNextEvent(
                time=send_next_time, blame=self, callback=self._try_send_next
            )
            self.host.context.scheduler.schedule(send_next_event)
            return

        if self.current_output_frame is None:
            return

        if self.current_output_frame._requires_ack:
            self.state = (
                MACState.AWAITING_ACK
            )  # if you sent a packet that requires ack, wait for it setting the relative state
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
            # otherwise it was a broadcast: success by default
            self._handle_tx_success()

    def on_RDCNotSent(self):
        """increment  backoff counters and retry"""
        self.NB += 1
        self.BE = min(self.BE + 1, self.macMaxBE)
        self._backoff_and_send()  # was already in backoff state

    def receive(
        self, payload: Frame_802_15_4 | Ack_802_15_4, sender_addr: bytes, rssi: float
    ):
        # print(f">>> DEBUG-MAC [{self.host.id}]: receive() called with RSSI = {rssi:.2f} dBm")
        if isinstance(payload, Frame_802_15_4):
            if payload._requires_ack:
                # if you received a frame you need to send the ack, so set the state and schedule the event
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

            # self._last_received_rssi = self.host.phy.get_last_rssi()
            self.host.net.receive(
                payload=payload.NPDU, sender_addr=sender_addr, rssi=rssi
            )

        elif isinstance(payload, Ack_802_15_4):
            # if the sequence number corresponds to the current output frame and I was waiting for it, then this ack is mine
            if (
                self.state == MACState.AWAITING_ACK
                and self.current_output_frame
                and payload.seqn == self.current_output_frame.seqn
            ):
                if self.pending_ack_timeout_event:
                    self.host.context.scheduler.unschedule(
                        self.pending_ack_timeout_event
                    )  # unschedule the ack timeout
                    self.pending_ack_timeout_event = None
                self._handle_tx_success(ack_rssi=rssi)

    def _handle_tx_success(self, ack_rssi: float = None):
        if self.pending_send_req_event:
            self.host.context.scheduler.unschedule(
                self.pending_send_req_event
            )  # unschedule the retry send event
            self.pending_send_req_event = None

        if self.current_output_frame.rx_addr != Frame_802_15_4.broadcast_linkaddr:
            self.host.rdc.uc_tx_outcome(
                rx_addr=self.current_output_frame.rx_addr,
                status_ok=True,
                num_tx=self.retry_count,
                ack_rssi=ack_rssi,
            )

        self._reset_mac_state()
        send_next_time = self.host.context.scheduler.now() + self.next_send_delay
        send_next_event = MacTrySendNextEvent(
            time=send_next_time, blame=self, callback=self._try_send_next
        )
        self.host.context.scheduler.schedule(send_next_event)

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
        self._reset_mac_state()
        send_next_time = self.host.context.scheduler.now() + self.next_send_delay
        send_next_event = MacTrySendNextEvent(
            time=send_next_time, blame=self, callback=self._try_send_next
        )
        self.host.context.scheduler.schedule(send_next_event)

    # def get_last_packet_rssi(self) -> float:
    #    return self._last_received_rssi
