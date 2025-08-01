from simulator.entities.protocols.common.Layer import Layer
from entities.physical.devices.Node import Node
from protocols.common.packets import Frame802_15_4
from protocols.mac.common.mac_events import MacCCAEvent

'''
This class implements the non-beacon enabled 802.15.4 MAC CSMA protocol AS IT IS IMPLEMENTED in ContikiOS.
This means that it may not be strictly compliant to the IEEE 802.15.4 standard MAC.
Reference to the C implementation of the CSMA in ContikiOS (offical repository):
https://github.com/contiki-os/contiki/blob/master/core/net/mac/csma.c
'''

class ContikiOS_MAC_802154_Unslotted(Layer):

    macMinBe = 3
    macMaxBe = 5 # min and max backoff exponents
    macMaxCSMABackoffs = 4 # max backoff attempts before failing tranmission
    aUnitBackoffPeriod = 320 * 1e-6 # backoff unit (20 symbols @ 2.4 GhZ around 320 us)
    macMaxFrameRetries = 3 # max retries for missing ACK failures
    macAckWaitDuration = 864 * 1e-6 # time interval for waiting the ACK before retrying the transmission #TODO: check this
    cca_Threshold_dBm = -85 #dBm. Threshold for CCA (for power lower than this threshold we consider the channel as free)

    def __init__(self, host: Node):
        super().__init__(self)
        self.host = host
        rng_id = f"NODE:{self.host.id}/MAC"
        self.host.context.random_manager.create_stream(rng_id)
        self.rng = self.host.context.random_manager.get_stream(rng_id)

        self.BE = ContikiOS_MAC_802154_Unslotted.macMinBe # initial backoff exponent
        self.NB = 0 # number of backoff attempts
        self.retry_count = 0 # number of retries
        self.tx_success = False # is the transmission successful?

        self.frame = None # packet in queue #TODO: probably we will need to build a packet queue because i dont know how we are going to manage multiple packets

    def send(self, payload: Frame802_15_4 = None):
        '''
        triggered by send event from upper layers.
        This function implements the backoff procedure and schedules the related events'''
        if payload is not None: 
            self.frame = payload

        if self.retry_count < ContikiOS_MAC_802154_Unslotted.macMaxFrameRetries:
            backoff_time = self.rng.uniform(low = 0, high = (2**self.BE) -1) # exponential backoff
            cca_time = self.host.context.scheduler.now() + backoff_time
            cca_event = MacCCAEvent(time = cca_time, blame = self, callback = self._sense_channel) # schedule CCA after backoff time
            self.host.context.scheduler.schedule(cca_event)

        else:
            self.tx_success = False

    def _sense_channel(self):
        busy = self.host.phy.cca_802154_Mode1(cca_threshold = self.cca_Threshold_dBm)

        if not busy: # if channel is free, transmit
            self.host.phy.send(payload = self.frame)
        else:
            self.NB += 1 #increment backoff attempts
            self.BE = min(self.BE + 1, ContikiOS_MAC_802154_Unslotted.macMaxBe) # increment backoff exponential
            self.send() # retry 
        

        

    def receive(payload: Frame802_15_4):
        pass