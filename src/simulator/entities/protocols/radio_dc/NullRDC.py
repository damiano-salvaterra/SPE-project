from protocols.Layer import Layer
from protocols.common.packets import Frame802_15_4
from entities.physical.devices.Node import Node


class NullRDC(Layer):
    def __init__(self, host: Node):
        super().__init__(self, host = host)

    def send(self, payload: Frame802_15_4):
        '''just a pass-though: NullRDC does nothing'''
        self.host.phy.send(payload = payload)


    
    def receive(self, payload: Frame802_15_4):
        self.host.mac.receive(payload = payload)