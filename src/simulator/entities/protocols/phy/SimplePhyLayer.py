from simulator.entities.protocols.common.Layer import Layer
from protocols.phy.common.ReceptionSession import ReceptionSession
from protocols.phy.common.phy_events import PhyTxEndEvent, PhyTxStartEvent
from protocols.phy.common.Transmission import Transmission
from protocols.common.packets import Packet, Frame_802154
from entities.physical.devices.Node import Node
from entities.physical.media.WirelessChannel import WirelessChannel
from numpy import log10


class SimplePhyLayer(Layer):
    def __init__(self, host: Node, transmission_media: WirelessChannel, capture_threshold_dB: float = 5, transmission_power: float = 0):
        super().__init__(self, host = host)
        self.capture_threshold_dB = capture_threshold_dB # threshold for SINR to check if the transmission can be decoded
        self.cca_Threshold_dBm = -85 #dBm. Threshold for CCA (for power lower than this threshold we consider the channel as free)
        self.transmission_power = transmission_power
        self.current_session: ReceptionSession = None
        self.active_session = False
        self.transmission_media = transmission_media


    def _is_decoded(self, session: ReceptionSession):
        '''
        compute SINR for each segment, pick the minimum SINR, compare it
        with some threshold (search radio parameters) and decide if the packet can be decoded
        '''
        # to compute the SINR i need the received power of each transmission (except of the one i want),
        # sum it to the noise floor, and do the ration with the received power of the wanted tx
        # to compute the received power from a transmission i need the tranmission power and to query the channel model for the propagation loss


        # all of this needs to be done in linear scale, so convert everything to watts

        #first, compute the received power of the interested transmission
        wanted_tx = session.capturing_tx
        capturing_tx_power_linear = self.transmission_media.get_linear_link_budget(node1 = self.host, node2 = wanted_tx.transmitter, tx_power_dBm = wanted_tx.transmission_power_dBm)
        #and get the noise floor
        noise_floor_linear = self.transmission_media.get_linear_noise_floor() # noise floor of the receiver
        # get SINR for each segment
        segments_SINR = []
        for segment in self.current_session.reception_segments: #iterate on each segment
            interferers_power = 0.0
            for transmitter, transmission in segment.interferers.items():
                tx_power = transmission.transmission_power_dBm
                received_power = self.transmission_media.get_linear_link_budget(node1 = self.host, node2 = transmitter, tx_power_dBm = tx_power)
                interferers_power += received_power
            segment_SINR = capturing_tx_power_linear / (noise_floor_linear + interferers_power)
            segments_SINR.append(segment_SINR)

        # Now get the lowest SINR measured during this reception session
        min_SINR = min(segments_SINR)
        min_SINR_dB = 10 * log10(min_SINR)
        # here we can use also a statistical model to be more precise
        decodable = True if min_SINR_dB >= self.capture_threshold_dB else False

        return decodable




    def on_PhyRxStartEvent(self, transmission: Transmission, subject: WirelessChannel):
        
        #This is a simplification, to be fair we should schedule a delayed filter for the address.
        #The time that the radio takes to synchronize, find SFD and read the header with the address is around 896 us
        #TODO: given what we are modeling we should model also this, because the ack timings are based on this
        
        destination = transmission.mac_frame._daddr
        if destination == self.host.linkaddr or destination == Frame_802154.broadcast_linkaddr:
            #create reception session
            self.current_session = ReceptionSession(receiving_node=self.host, capturing = transmission, start_time = self.host.context.scheduler.now())
            subject.subscribe_listener(self.current_session) # attach reception session
            self.active_session = True
        
        
    def on_PhyRxEndEvent(self, subject: WirelessChannel):
        if self.active_session:
            self.current_session.end_time = self.host.context.scheduler.now()
            subject.unsubscribe_listener(self.current_session)
            self.active_session = False
            #TODO: compute statistics of SINR and decide if the packet is received or if tere is a collision
            #if yes, forward to mac layer
            if self._is_decoded(self.current_session):
                self.receive(payload = self.current_session.capturing_tx.mac_frame)
                
            else:
                pass #TODO: else what?
            self.current_session = None
            self.active_session = False


    def on_PhyTxEndEvent(self, transmission: Transmission):
        self.transmission_media.on_PhyTxEndEvent(transmission=transmission) # notify channel
        self.host.rdc.on_PhyTxEndEvent() # notify rdc



    def send(self, payload: Packet):
        '''
        create transmission and schedule the phy_tx events
        '''
        
        transmission = Transmission(transmitter = self.host, packet = payload, transmission_power_dBm = self.transmission_power)
        
        start_tx_time = self.host.context.scheduler.now() + 1e-12 # TODO: (maybe?) change this and insert some kind of delay
        end_tx_time = start_tx_time + payload.on_air_duration
        tx_start_event = PhyTxStartEvent(time=start_tx_time, blame = self, callback = self.transmission_media.on_PhyTxStartEvent, transmission = transmission)
        tx_end_event = PhyTxEndEvent(time=end_tx_time, blame=self, callback=self.on_PhyTxEndEvent, callback2 = self.host.rdc.on_PhyTxEndEvent, transmission = transmission)

        self.host.context.scheduler.schedule(tx_start_event)
        self.host.context.scheduler.schedule(tx_end_event)


    def cca_802154_Mode1(self) -> bool:
        '''
        this function calls the utilities of WirelessChannel to perform a Mode 1 CCA as specified
         in IEEE 802.15.4. Mode 1 CCA only measures the energy on the channel (does not perform any carrier sense).
         Thus, we also take into account the noise floor. It is not totally precise since (I think) gthat by default
         he type of CCA is Mode 2 (with carrier sense), but in this case it doesnt really matters because we are not modeling
         external interference (coming from other technologies around like WIFi or Bluetooth), so the only energy
         on the channel is the one coming from packet transmissions of this network, so at the end it should be similar enough to Mode 2.

         Returns True if channel is busy, False if the channel is free.
         '''
        noise_floor = self.transmission_media.get_linear_noise_floor()
        channel_power = 0.0
        for transmission in self.transmission_media.active_transmissions.values():
            power_contribute = self.transmission_media.get_linear_link_budget(self.host, transmission.transmitter, transmission.transmission_power_dBm)
            channel_power += power_contribute

        total_received_power = channel_power + noise_floor

        total_dBm = 10 * log10(total_received_power) + 30 #go back in dBm (threshold is in dBm)
        return total_dBm > self.cca_Threshold_dBm



    def receive(self, payload: Packet):
        '''call the RDC'''
        self.host.rdc.receive(payload = payload)