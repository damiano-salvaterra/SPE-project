from simulator.entities.protocols.common.Layer import Layer
from entities.common.Entity import Entity
from simulator.entities.physical.devices.nodes import StaticNode
from protocols.common.packets import Frame_802154, Ack_802154, NetPacket
from protocols.mac.common.mac_events import MacSendReqEvent, MacACKTimeoutEvent, MacACKSendEvent
from collections import deque
'''
This class implements the non-beacon enabled 802.15.4 MAC CSMA protocol AS IT IS IMPLEMENTED in ContikiOS.
This means that it may not be strictly compliant to the IEEE 802.15.4 standard MAC.
Reference to the C implementation of the CSMA in ContikiOS (offical repository):
https://github.com/contiki-os/contiki/blob/master/core/net/mac/csma.c
'''

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

    def __init__(self, host: StaticNode):
        Layer.__init__(self, host = host)
        Entity.__init__(self)
        rng_id = f"NODE:{self.host.id}/MAC"
        self.host.context.random_manager.create_stream(rng_id)
        self.rng = self.host.context.random_manager.get_stream(rng_id)

        self.tx_queue = deque()  # Transmission queue
        self.current_output_frame: Frame_802154 = None
        self.last_received_rssi = 0.0
        self.is_busy = False # MAC status
        self.pending_ack_timeout_event = None
        self.seqn = 0

        self._last_received_rssi: float = -150.0 #init to low value 


        self._reset_contention_counters()



    def _reset_contention_counters(self):
        self.BE = self.macMinBE
        self.NB = 0



    def _reset_mac_state(self):
        self.is_busy = False
        self.current_output_frame = None
        self.last_received_rssi = None
        self.retry_count = 0
        self._reset_contention_counters()



    def send(self, payload: NetPacket, nexthop: bytes):
        '''
        Called from upper layer. put the packet in the queue and try to send.
        '''
        requires_ack = True if (nexthop != Frame_802154.broadcast_linkaddr)else False # if the nexthop is not the broadcast address, then the frame requires ack
        mac_frame = Frame_802154(seqn = None, tx_addr = self.host.linkaddr, rx_addr = nexthop, requires_ack = requires_ack, NPDU = payload) # seqnum is set later, just before trying to send this frame
        
        self.tx_queue.append(mac_frame)
        if not self.is_busy:
            self._try_send_next()


    def _try_send_next(self):
        '''
        If radio is not busy, send the next packet
        '''
        if not self.tx_queue or self.is_busy:
            return

        self.is_busy = True
        self.current_output_frame = self.tx_queue.popleft()
        
        self.seqn = (self.seqn + 1) % 256
        self.current_output_frame.seqn = self.seqn # assign seqnum
        
        if self.current_output_frame.rx_addr == Frame_802154.broadcast_linkaddr:
            self.current_output_frame._requires_ack = False  # if broadcast, does not require ack

        self.retry_count = 0
        self._reset_contention_counters()
        self._schedule_cca()



    def _schedule_cca(self, is_retry: bool = False):
        '''
        Backoff and CCA logic
        '''
        if is_retry:
            if self.retry_count > self.macMaxFrameRetries:
                # set transmission as failed
                self._handle_tx_failure()
                return
            self.retry_count += 1
            self._reset_contention_counters() # reset contention counters and retry tranmission
        
        if self.NB >= self.macMaxCSMABackoffs:
            self._handle_tx_failure() # fail because the channel is always busy
            return

        # compute backoffs
        max_slots = (2**self.BE) - 1
        backoff_slots = self.rng.integers(low=0, high=max_slots)
        backoff_time = backoff_slots * self.aUnitBackoffPeriod
        
        send_req_time = self.host.context.scheduler.now() + backoff_time
        send_req_event = MacSendReqEvent(time=send_req_time, blame=self, callback=self.host.rdc.send, payload=self.current_output_frame)
        self.host.context.scheduler.schedule(send_req_event)



    def on_RDCSent(self):
        '''Called by RDC when the phy transmission is terminated'''
        if self.current_output_frame._requires_ack: # if the last packet sent requires ack, schedule the timeout
            ack_timeout_time = self.host.context.scheduler.now() + self.macAckWaitDuration
            ack_timeout_event = MacACKTimeoutEvent(time=ack_timeout_time, blame=self, callback=self._schedule_cca, is_retry=True)
            self.pending_ack_timeout_event = ack_timeout_event
            self.host.context.scheduler.schedule(ack_timeout_event)
        else:
            # otherwise it is a broadcast: success by default
            self._handle_tx_success()



    def on_RDCNotSent(self):
        '''called by RDC if CCA fails'''
        self.NB += 1
        self.BE = min(self.BE + 1, self.macMaxBE)
        self._schedule_cca() # update coutners and retry backoff



    def receive(self, payload: Frame_802154 | Ack_802154):
        '''Mananges the packets received from RDC'''
        self._last_received_rssi = self.host.phy.get_last_rssi()

        if isinstance(payload, Frame_802154):
            self.last_received_rssi
            self.host.net.receive(payload.NPDU, sender = payload.tx_addr)
            if payload._requires_ack:
                auto_ack = Ack_802154(seqn=payload.seqn)
                ack_time = self.host.context.scheduler.now() + self.aTurnaroundTime
                send_ack_event = MacACKSendEvent(time=ack_time, blame=self, callback=self.host.rdc.send, payload=auto_ack)
                self.host.context.scheduler.schedule(send_ack_event)
        
        elif isinstance(payload, Ack_802154):
            if self.is_busy and self.current_output_frame and payload.seqn == self.current_output_frame.seqn:
                # If mac is busy, the current frame is not null and the seqnum f the received ack corresponds, then this ack is for me
                self.host.context.scheduler.unschedule(self.pending_ack_timeout_event)
                self.pending_ack_timeout_event = None
                self._handle_tx_success() # YAY



    def _handle_tx_success(self):
        # TODO: notifuy upper layer
        self._reset_mac_state()
        self._try_send_next() # send other packets in the queue


    def _handle_tx_failure(self):
        # TODO: Notify upper layer
        self._reset_mac_state()
        self._try_send_next() # send other packets in the queue

    def get_last_packet_rssi(self) -> float:
        return self._last_received_rssi