from simulator.entities.protocols.common.Layer import Layer
from entities.common.Entity import Entity
from protocols.phy.common.ReceptionSession import ReceptionSession
from protocols.phy.common.phy_events import PhyTxEndEvent, PhyTxStartEvent, PhyPacketTypeDetectionEvent, PhyDaddrDetectionEvent
from protocols.phy.common.Transmission import Transmission
from protocols.common.packets import MACFrame, Frame_802154, Ack_802154
from simulator.entities.physical.devices.nodes import StaticNode
from entities.physical.media.WirelessChannel import WirelessChannel
from numpy import log10


class SimplePhyLayer(Layer, Entity):
    def __init__(self, host: StaticNode, transmission_media: WirelessChannel, transmission_power: float = 0):
        Layer.__init__(self, host = host)
        Entity.__init__(self)
        self.capture_threshold_dB = 5 #dB threshold for SINR to check if the transmission can be decoded
        self.cca_Threshold_dBm = -85 #dBm. Threshold for CCA (for power lower than this threshold we consider the channel as free)
        self.correlator_threshold = -95 #dBm. It is the threshold required by the correlator to synchronize to the signal. AKA sensitivity
        self.transmission_power = transmission_power
        self.transmission_media = transmission_media

        self.last_session: ReceptionSession = None
        self.active_session = False
        self.transmitting = False
    

        self._last_seqn = 0 #sequence number of the last sended frame. Used to filter ACKs


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
        for segment in self.last_session.reception_segments: #iterate on each segment
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


    def on_PhyRxStartEvent(self, transmission: Transmission):
        
        '''
        If it is an ack, i need to wait the time for parsing the packet type and then, if the packet has the same seqnum of the last tx, accept it and notify the mac.
        If the ack has a different seqnum, just drop.
        If, instead, it is a data packet, i need to wait to parse the address and if it is for me, send it up to the mac. if is not for me, just drop.
        '''
        received_power = self.transmission_media.get_linear_link_budget(node1 = self.host, node2 = transmission.transmitter, tx_power_dBm = transmission.transmission_power_dBm)
        if received_power < self.correlator_threshold: # if the received power is under the sensitivity, ignore everything
            return
        
        self._open_session(transmission)

        if isinstance(transmission.packet, Ack_802154):
            pending_ack = True if transmission.packet.seqn == self._last_seqn else False
            type_detection_time = self.host.context.scheduler.now() + transmission.packet.ack_detection_time
            type_detection_event =  PhyPacketTypeDetectionEvent(time = type_detection_time, blame = self, callback = self._close_session if not pending_ack else None, transmission = transmission) # if is not a pending ack, close the session. If it is a pending ack continue decoding till PhyRxEndEvent
            self.host.context.scheduler.schedule(type_detection_event)

        elif isinstance(transmission.packet, Frame_802154):
            this_destination = True if (transmission.packet.rx_addr == self.host.linkaddr or transmission.packet.rx_addr == Frame_802154.broadcast_linkaddr) else False
            daddr_detection_time = self.host.context.scheduler.now() + transmission.packet.daddr_detection_time
            daddr_detection_event  = PhyDaddrDetectionEvent(time = daddr_detection_time, blame = self, callback = self._close_session if not this_destination else None, transmission = transmission) # if this node is not the destination, close the session. If it is the destination, continue decoding till PhyRxEndEvent
            self.host.context.scheduler.schedule(daddr_detection_event)

        
    def on_PhyRxEndEvent(self, transmission: Transmission):
        if self.active_session:
            self._close_session()
            if self._is_decoded(self.last_session):
                self.receive(payload = self.last_session.capturing_tx.packet)
                
            else:
                pass #TODO: else what? just update a monitor counter probably
        else: # if the session was already closed (because was an ack with different seqnum or because the packet had another destination address), do nothing
            pass



    def on_PhyTxStartEvent(self, transmission: Transmission):
        self.transmitting = True # radio busy
        self.transmission_media.on_PhyTxStartEvent(transmission=transmission) # notify channel

    def on_PhyTxEndEvent(self, transmission: Transmission):
        self.transmitting = False
        self.transmission_media.on_PhyTxEndEvent(transmission=transmission) # notify channel
        self.host.rdc.on_PhyTxEndEvent() # notify rdc




    def _open_session(self, transmission: Transmission):
        if not self.active_session:
            self.last_session = ReceptionSession(receiving_node=self.host, capturing = transmission, start_time = self.host.context.scheduler.now())
            self.transmission_media.subscribe_listener(self.last_session) # attach reception session
            self.active_session = True
        
    def _close_session(self):
        if self.active_session:
           self.last_session.end_time = self.host.context.scheduler.now()
           self.transmission_media.unsubscribe_listener(self.last_session)
           self.active_session = False



    def send(self, payload: MACFrame):
        '''
        create transmission and schedule the phy_tx events
        '''
        if isinstance(payload, Frame_802154):
            self._last_seqn = payload.seqn

        transmission = Transmission(transmitter = self.host, packet = payload, transmission_power_dBm = self.transmission_power)
        
        start_tx_time = self.host.context.scheduler.now() + 1e-12 # TODO: (maybe?) change this and insert some kind of delay
        end_tx_time = start_tx_time + payload.on_air_duration
        tx_start_event = PhyTxStartEvent(time=start_tx_time, blame = self, callback = self.on_PhyTxStartEvent, transmission = transmission)
        tx_end_event = PhyTxEndEvent(time=end_tx_time, blame=self, callback=self.on_PhyTxEndEvent, transmission = transmission)

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



    def receive(self, payload: MACFrame):
        '''call the RDC'''
        self.host.rdc.receive(payload = payload)