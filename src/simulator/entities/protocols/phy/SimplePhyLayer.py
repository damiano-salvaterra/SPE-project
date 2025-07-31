from Layer import Layer
from protocols.phy.common.ReceptionSession import ReceptionSession
from protocols.phy.common.phy_events import PhyTxEndEvent, PhyTxStartEvent
from protocols.phy.common.Transmission import Transmission
from protocols.common.packets import Frame802_15_4
from entities.physical.devices.Node import Node
from entities.physical.media.WirelessChannel import WirelessChannel
from numpy import log10


class SimplePhyLayer(Layer):
    def __init__(self, host: Node, transmission_media: WirelessChannel, capture_threshold_dB: float = 5, transmission_power: float = 0):
        super().__init__(self, host = host)
        self.capture_threshold_dB = capture_threshold_dB # threshold for SINR to check if the transmission can be decoded
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
        capturing_tx_power_linear = self.transmission_media.get_linear_link_budget(node1 = self.host, node2 = wanted_tx.transmitter, tx_power_dBm = wanted_tx.transmission_power)
        #and get the noise floor
        noise_floor_linear = self.transmission_media.get_linear_noise_floor() # noise floor of the receiver
        # get SINR for each segment
        segments_SINR = []
        for segment in self.current_session.reception_segments: #iterate on each segment
            interferers_power = 0.0
            for transmitter, transmission in segment.interferers.items():
                tx_power = transmission.transmission_power
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




    def on_rx_start_event(self, transmission: Transmission, subject: WirelessChannel):
        
        #This is a simplification, to be fair we should schedule a delayed filter for the address.
        #this will understimate the collisions a bit
        destination = transmission.mac_frame.linkaddr
        if destination == self.host.linkaddr or destination == Frame802_15_4.broadcast_linkaddr:
            #create reception session
            self.current_session = ReceptionSession(receiving_node=self.host, capturing = transmission, start_time = self.host.context.scheduler.now())
            subject.subscribe_listener(self.current_session) # attach reception session
            self.active_session = True
        
        
    def on_rx_end_event(self, subject: WirelessChannel):
        if self.active_session:
            self.current_session.end_time = self.host.context.scheduler.now()
            subject.unsubscribe_listener(self.current_session)
            self.active_session = False
            #TODO: compute statistics of SINR and decide if the packet is received or if tere is a collision
            #if yes, forward to mac layer
            if self._is_decoded(self.current_session):
                self.host.rdc.receive(self.current_session.capturing_tx.mac_frame)
            else:
                pass #TODO: else what?
            self.current_session = None
            self.active_session = False


    def send(self, payload: Frame802_15_4):
        '''
        create transmission and schedule the phy_tx events
        '''
        
        transmission = Transmission(transmitter = self.host, packet = payload, transmission_power = self.transmission_power)
        
        start_tx_time = self.host.context.scheduler.now() # TODO: (maybe?) change this and insert some kind of delay
        end_tx_time = start_tx_time + Frame802_15_4.packet_max_gross_duration
        tx_start_event = PhyTxStartEvent(time=start_tx_time, blame = self, callback = self.transmission_media.on_phy_tx_start_event, transmission = transmission)
        tx_end_event = PhyTxEndEvent(time=end_tx_time, blame=self, callback=self.transmission_media.on_tx_end_event, transmission = transmission)

        self.host.context.scheduler.schedule(tx_start_event)
        self.host.context.scheduler.schedule(tx_end_event)


    def receive(self, payload):
        '''just for fill the interface requirement, not really needed here'''
        pass