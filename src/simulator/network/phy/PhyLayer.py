from Layer import Layer
from network.phy.common.ReceptionSession import ReceptionSession
from network.phy.common.phy_events import PhyTxEndEvent, PhyTxStartEvent
from network.phy.common.Transmission import Transmission
from network.common.packets import Packet802_15_4
from entities.physical.devices.Node import Node
from entities.physical.media.WirelessChannel import WirelessChannel


class PhyLayer(Layer):
    def __init__(self, host: Node, transmission_media: WirelessChannel, transmission_power: float = 0):
        super().__init__(self)
        self.host = host
        self.transmission_power = transmission_power
        self.current_session: ReceptionSession = None
        self.active_session = False
        self.transmission_media = transmission_media


    def on_rx_start_event(self, transmission: Transmission):
        #create reception session
        self.current_session = ReceptionSession(receiving_node=self.host, capturing = transmission, start_time = self.host.context.scheduler.now())
        self.active_session = True
        
        
    def on_rx_end_event(self):
        self.current_session.end_time = self.host.context.scheduler.now()
        self.active_session = False
        #TODO: compute statistics of SINR and decide if the packet is received or if tere is a collision
        #if yes, forward to mac layer


    def send(self, packet: Packet802_15_4):
        '''
        create transmission and schedule the phy_tx events
        '''
        
        transmission = Transmission(transmitter = self.host, packet = packet, power = self.transmission_power)
        
        start_tx_time = self.host.context.scheduler.now() # TODO: change this and insert some kind of delay
        end_tx_time = start_tx_time + Packet802_15_4.packet_max_gross_duration
        tx_start_event = PhyTxStartEvent(time=start_tx_time, blame = self, callback = self.transmission_media.on_phy_tx_start_event, transmission = transmission)
        tx_end_event = PhyTxEndEvent(time=end_tx_time, blame=self, callback=self.transmission_media.on_tx_end_event, transmission = transmission)

        self.host.context.scheduler.schedule(tx_start_event)
        self.host.context.scheduler.schedule(tx_end_event)
