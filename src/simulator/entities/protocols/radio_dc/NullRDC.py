from simulator.entities.protocols.common.Layer import Layer
from entities.common.Entity import Entity
from protocols.common.packets import Frame_802154, Ack_802154, MACFrame
from simulator.entities.physical.devices.nodes import StaticNode


class NullRDC(Layer, Entity):
    def __init__(self, host: StaticNode):
        Layer.__init__(self, host = host)
        Entity.__init__(self)

    def send(self, payload: Frame_802154 | Ack_802154):
        '''NullRDC does nothing in particular. just request the CCA to PHY.
        If it is an ack, the cca is not performed'''
        if isinstance(payload, Frame_802154): # If data frame, do CCA
            self._sense_channel(frame = payload)
        else: # If ACK, just send
            self.host.phy.send(payload = payload)


    def _sense_channel(self, frame: Frame_802154):
        '''
        do CCA. If channel is free, send the packet, otherwise send an event back to MAC'''
        busy = self.host.phy.cca_802154_Mode1() # TODO: check if broadcast packets perform CCA or not, in case skip it fro broadcasts
        if not busy: # if channel is free, transmit
            self.host.phy.send(payload = frame) #TODO: i think there is a small period between the backoff and the actual send, check if we should model it
        else:
            self.host.mac.on_RDCNotSent() # if transmission attempt is not succesful, inform the mac
        
        
    def on_PhyTxEndEvent(self):
        '''
        When the transmission is finished, inform the mac
        '''
        self.host.mac.on_RDCSent()


    def receive(self, payload: MACFrame):
        '''just a pass-through: NullRDC does nothing'''
        self.host.mac.receive(payload = payload)