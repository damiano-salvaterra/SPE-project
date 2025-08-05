from simulator.entities.protocols.common.Layer import Layer
from entities.physical.devices.Node import Node
from protocols.common.packets import Frame_802154, Ack_802154
from protocols.mac.common.mac_events import MacSendReqEvent, MacACKTimeoutEvent, MacACKSendEvent

'''
This class implements the non-beacon enabled 802.15.4 MAC CSMA protocol AS IT IS IMPLEMENTED in ContikiOS.
This means that it may not be strictly compliant to the IEEE 802.15.4 standard MAC.
Reference to the C implementation of the CSMA in ContikiOS (offical repository):
https://github.com/contiki-os/contiki/blob/master/core/net/mac/csma.c
'''

class ContikiOS_MAC_802154_Unslotted(Layer):

    macMinBE = 3
    macMaxBE = 5 # min and max backoff exponents
    macMaxCSMABackoffs = 4 # max backoff attempts before failing tranmission
    aUnitBackoffPeriod = 320 * 1e-6 # backoff unit (20 symbols @ 2.4 GhZ around 320 us)
    macMaxFrameRetries = 3 # max retries for missing ACK failures
    macAckWaitDuration = 864 * 1e-6 # time interval for waiting the ACK before retrying the transmission #TODO: check this
    aTurnaroundTime = 192 * 10**-6 # time between the end of the reception and the sending of the ACK (192 us)

    

    def __init__(self, host: Node):
        super().__init__(self)
        self.host = host
        rng_id = f"NODE:{self.host.id}/MAC"
        self.host.context.random_manager.create_stream(rng_id)
        self.rng = self.host.context.random_manager.get_stream(rng_id)

        self._reset_counters()
        self.tx_success = False # is the transmission successful?
        self.frame = None # packet in queue #TODO: probably we will need to build a packet queue because i dont know how we are going to manage multiple packets
        self.busy = False # busy flag for service status
        self.pending_timeout = None
        self.seqn = 0 #sequence number of the frame


    def _reset_counters(self):
        self.BE = ContikiOS_MAC_802154_Unslotted.macMinBE # initial backoff exponent
        self.NB = 0 # number of backoff attempts
        self.retry_count = 0

    def _reset_status(self):
        self.tx_success = True
        self.busy = False
        self.frame = None


    def send(self, payload: Frame_802154 = None, retry: bool = False):
        '''
        triggered by send event from upper layers.
        This function implements the backoff procedure and schedules the related events'''

        if self.retry_count > ContikiOS_MAC_802154_Unslotted.macMaxFrameRetries: # if maximum retransmissions reached (maximum NOACK), give up
            self.tx_success = False
            #reset counters
            self.busy = False
            self._reset_counters()
            
        else:
            if not self.busy:
                self.busy = True
            if payload is not None: 
                self.seqn += 1
                payload.seqn = self.seqn
                self.frame = payload
                if payload.daddr == Frame_802154.broadcast_linkaddr: # if the packet is broadcast, deactivate ack
                    self.frame._requires_ack = False

            #true if the function is called by ACK timeout event
            if retry: # if it is a retry (missing ACK), then resed the channel contention and restart
                self.retry_count += 1
                self.NB = 0
                self.BE = ContikiOS_MAC_802154_Unslotted.macMinBE

            if self.NB < ContikiOS_MAC_802154_Unslotted.macMaxCSMABackoffs:
                max_slots = 2**self.BE
                backoff_slots = self.rng.integers(low = 0, high = max_slots) # exponential backoff (number of slots)
                backoff_time = backoff_slots * ContikiOS_MAC_802154_Unslotted.aUnitBackoffPeriod # number of slots * time duration of each slot
                send_req_time = self.host.context.scheduler.now() + backoff_time
                send_req_event = MacSendReqEvent(time = send_req_time, blame = self, callback = self.host.rdc.send, payload = payload) # schedule CCA after backoff time
                self.host.context.scheduler.schedule(send_req_event)


    def on_RDCSent(self):
        if self.frame._requires_ack: # if frame requires the ack, then schedule the ack timeout
            ack_timeout_time = self.host.context.scheduler.now() + ContikiOS_MAC_802154_Unslotted.macAckWaitDuration
            ack_timeout_event = MacACKTimeoutEvent(time = ack_timeout_time, blame = self, callback = self.send, retry = True)
            self.pending_timeout = ack_timeout_event # register the pending timout, to cancle it if you receive the ack
            self.host.context.scheduler.schedule(ack_timeout_event)
            self.tx_success = False #pessimism as a default
        else: # else, you can remove the frame from the buffer and set the transmission successful
            self._reset_status()
            self._reset_counters()


    def on_RDCNotSent(self):
        #something happened (channel busy or whatever): increment backoff counters and try again 
        self.NB += 1
        self.BE = min(self.BE + 1, ContikiOS_MAC_802154_Unslotted.macMaxBE)
        self.send()


    def receive(self, payload: Frame_802154 | Ack_802154):
        '''forward the pakcet in upper layers and send ACK'''
        if isinstance(payload, Frame_802154):
            self.host.net.receive(payload) # Contiki notifies the upper layer right away
            #schedule time for sending ACK
            ack_packet = Ack_802154(seqn = payload.seqn)
            ack_time = self.host.context.scheduler.now() + ContikiOS_MAC_802154_Unslotted.aTurnaroundTime
            send_ack_event = MacACKSendEvent(time = ack_time, blame = self, callback = self.host.rdc.send(), payload = ack_packet)
            self.host.context.scheduler.schedule(send_ack_event)

        elif isinstance(payload, Ack_802154): # if ack, trasmission successful
            self._reset_status()
            self._reset_counters()
            self.host.context.scheduler.unschedule(self.pending_timeout)
            

        else:
            raise ValueError(f"MAC@Node {self.host.id}: Unknown packet type.")



        #TODO: i need to manage the reception of the ack: if received, stop retransmitting and unschedule the timeout