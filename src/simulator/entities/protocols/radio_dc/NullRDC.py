from simulator.entities.protocols.common.Layer import Layer
from protocols.common.packets import Frame802_15_4
from entities.physical.devices.Node import Node


class NullRDC(Layer):
    def __init__(self, host: Node):
        super().__init__(self, host = host)

    def send(self, payload: Frame802_15_4):
        '''NullRDC does nothing in particular. just request the CCA to PHY'''
        self._sense_channel(frame = payload)


    def _sense_channel(self, frame: Frame802_15_4):
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


    def receive(self, payload: Frame802_15_4):
        '''just a pass-though: NullRDC does nothing'''
        self.host.mac.receive(payload = payload)